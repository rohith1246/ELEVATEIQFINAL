"""
Real-Time Chat blueprint route handlers.

Implements instant messaging features using Server-Sent Events (SSE) stream connections.
Includes support for Direct Messages (DMs) and group chat rooms created by Admins/Team Leaders.
Messages and conversation notifications are broadcasted instantly to online members'
active SSE event queues.
"""

import json
import queue
import logging
from flask import Blueprint, request, jsonify, Response
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, serializer, check_is_team_leader, TOKEN_MAX_AGE
from ..config import safe_error

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

# Global dictionary storing list of active SSE subscriber queues keyed by user ID
# Format: { user_id (int): set(queue.Queue) }
user_queues = {}

def register_queue(user_id, q):
    """
    Registers a client's message queue to receive real-time push events.

    Args:
        user_id (int): The primary key ID of the user.
        q (queue.Queue): The queue instance to bind.
    """
    user_queues.setdefault(user_id, set()).add(q)

def unregister_queue(user_id, q):
    """
    Unregisters a client's message queue, cleaning up memory when a client disconnects.

    Args:
        user_id (int): The primary key ID of the user.
        q (queue.Queue): The queue instance to remove.
    """
    queues = user_queues.get(user_id)
    if queues:
        queues.discard(q)
        # Clean up empty parent set to prevent dictionary bloat
        if not queues:
            user_queues.pop(user_id, None)


@chat_bp.route("/chat/stream")
def chat_stream():
    """
    Serves a persistent HTTP Server-Sent Events (SSE) data stream.

    Validates authentication token from cookies or query arguments. Keeps the socket 
    connection open, sending a 'ping' frame every 20 seconds to keep connection alive, 
    and yielding chat messages or notifications immediately when they are pushed.

    Returns:
        Response: A Flask Response object streaming content with 'text/event-stream' mimetype.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.args.get("token")
    if not token:
        token = request.cookies.get("token")
    if not token:
        return "Unauthorized", 401
    try:
        user = serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except Exception:
        return "Unauthorized", 401
        
    user_id = user["id"]
    # Initialize a queue to buffer messages with a safe maximum limit of 100 entries
    q = queue.Queue(maxsize=100)
    register_queue(user_id, q)
    
    def event_stream():
        """
        Generator function yielding SSE structured event strings.
        """
        try:
            # Yield initial connection success packet
            yield "data: {\"type\": \"connected\"}\n\n"
            ping_counter = 0
            while True:
                try:
                    # Block waiting for a message for 1 second to release thread quickly on disconnect
                    msg_data = q.get(timeout=1)
                    yield f"data: {msg_data}\n\n"
                except queue.Empty:
                    # Yield a lightweight comment keep-alive to test if connection is still open
                    yield ":keepalive\n\n"
                    ping_counter += 1
                    if ping_counter >= 20:
                        yield "data: {\"type\": \"ping\"}\n\n"
                        ping_counter = 0
        finally:
            # Ensure socket closure cleans up queue pointers
            unregister_queue(user_id, q)
            
    return Response(event_stream(), mimetype="text/event-stream")


@chat_bp.route("/chat/user-details", methods=["GET"])
def chat_user_details():
    """
    Retrieves authorized privileges and profile metadata for the chat layout.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Object containing user credentials and capability flags.
            - 401: Unauthorized access.
            - 500: Database exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        designation = ""
        if user["role"] != "admin":
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = ((res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")).lower()

        is_tl = user.get("role") in ["admin", "team_leader"] or "team leader" in designation or "team lead" in designation
        can_approve = user.get("role") == "admin" or "team leader" in designation or "team lead" in designation or "hr" in designation or "human resource" in designation
        is_hr = user.get("role") == "admin" or "hr" in designation or "human resource" in designation

        return jsonify({
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "employee_id": user.get("employee_id"),
            "is_team_leader": is_tl,
            "can_approve_leaves": can_approve,
            "is_hr": is_hr
        }), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/users", methods=["GET"])
def chat_list_users():
    """
    Lists all system users eligible for chat (Employees and Admins), excluding self.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of user profiles.
            - 401: Unauthorized.
            - 500: SQL query issues.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Select active employees/admins to prevent displaying guest candidates in corporate chat
        if user.get("role") == "client":
            cursor.execute(
                "SELECT id, name, email, role FROM users WHERE role = 'admin' AND id != %s ORDER BY name ASC",
                (user["id"],)
            )
        else:
            cursor.execute(
                "SELECT id, name, email, role FROM users WHERE role IN ('employee', 'admin', 'team_leader') AND id != %s ORDER BY name ASC",
                (user["id"],)
            )
        users = cursor.fetchall()
        return jsonify(users), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations", methods=["POST"])
def chat_create_conversation():
    """
    Initializes a Direct Message session or a Group Chat room.

    Checks permissions for group creation. Returns existing direct message metadata 
    if a session between the two users already exists. Disseminates updates to all members.

    JSON Parameters:
        type (str, optional): 'dm' or 'group'. Defaults to 'dm'.
        name (str, optional): The label of the group chat. Required for group.
        members (list of int): List of participant user IDs.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200/201: Conversation configuration metadata.
            - 400: Validation exceptions.
            - 403: Security restriction (e.g. groups restricted to Leaders/Admins).
            - 500: Database insertion or broadcast failures.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    conv_type = data.get("type", "dm")
    name = data.get("name")
    members = data.get("members", [])
    
    if conv_type not in ["dm", "group"]:
        return jsonify({"error": "Invalid conversation type"}), 400
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if conv_type == "group":
            is_tl = check_is_team_leader(user, cursor)
            if not is_tl:
                return jsonify({"error": "Only Admins and Team Leaders can create group chats."}), 403
            if not name:
                return jsonify({"error": "Group name is required."}), 400
        else:
            if len(members) != 1:
                return jsonify({"error": "DM requires exactly 1 counterparty user ID."}), 400
                
        if user.get("role") == "client":
            if conv_type != "dm":
                return jsonify({"error": "Clients are only allowed to start direct messages."}), 403
            counterparty_id = members[0]
            cursor.execute("SELECT role FROM users WHERE id = %s", (counterparty_id,))
            counterparty = cursor.fetchone()
            if not counterparty or counterparty["role"] != "admin":
                return jsonify({"error": "Clients can only initiate chats with administrators."}), 403
                
        # Exclude sender from members array before compiling final participants list
        members = [m_id for m_id in members if m_id != user["id"]]
        all_member_ids = list(set([user["id"]] + members))
        
        # Prevent duplicate Direct Message channels
        if conv_type == "dm":
            cursor.execute(
                """
                SELECT c.id 
                FROM conversations c
                JOIN conversation_members cm1 ON c.id = cm1.conversation_id AND cm1.user_id = %s
                JOIN conversation_members cm2 ON c.id = cm2.conversation_id AND cm2.user_id = %s
                WHERE c.type = 'dm'
                """,
                (all_member_ids[0], all_member_ids[1])
            )
            existing = cursor.fetchone()
            if existing:
                return jsonify({"id": existing["id"], "message": "DM already exists"}), 200
                
        cursor.execute(
            "INSERT INTO conversations (type, name, created_by) VALUES (%s, %s, %s) RETURNING id",
            (conv_type, name if conv_type == "group" else None, user["id"])
        )
        conv_id = cursor.fetchone()["id"]
        
        # Link member IDs in intermediate mapping table
        for m_id in all_member_ids:
            cursor.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s)",
                (conv_id, m_id)
            )
            
        conn.commit()

        # Push conversation configuration notification via SSE to all conversation members
        try:
            event_payload = json.dumps({
                "type": "conversation_update",
                "conversation_id": conv_id,
                "conversation_type": conv_type
            })
            for m_id in all_member_ids:
                queues = user_queues.get(m_id)
                if queues:
                    for q in list(queues):
                        try:
                            q.put_nowait(event_payload)
                        except queue.Full:
                            pass
        except Exception as push_err:
            print("SSE conversation update push error:", push_err)

        return jsonify({"id": conv_id, "type": conv_type, "name": name, "message": "Conversation created successfully"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations", methods=["GET"])
@chat_bp.route("/chat/groups", methods=["GET"])
def chat_list_conversations():
    """
    Lists all active conversation channels the current user is a member of.

    Includes details of the last sent message, last message timestamp, and count 
    of unread messages. Dynamically appends counterparty metadata ('dm_user') for DMs.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Sorted listing of conversation channels.
            - 401: Unauthorized.
            - 500: Database runtime issues.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Select conversation details sorted by activity or creation date
        if user.get("role") == "client":
            cursor.execute(
                """
                SELECT c.id, c.type, c.name as group_name, c.created_by, c.created_at,
                       (
                           SELECT m.content 
                           FROM messages m 
                           WHERE m.conversation_id = c.id 
                           ORDER BY m.sent_at DESC LIMIT 1
                       ) as last_message,
                       (
                           SELECT m.sent_at 
                           FROM messages m 
                           WHERE m.conversation_id = c.id 
                           ORDER BY m.sent_at DESC LIMIT 1
                       ) as last_message_time,
                       (
                           SELECT COUNT(m.id) 
                           FROM messages m
                           LEFT JOIN message_reads mr ON m.id = mr.message_id AND mr.user_id = %s
                           WHERE m.conversation_id = c.id AND mr.id IS NULL AND m.sender_id != %s
                       ) as unread_count
                FROM conversations c
                JOIN conversation_members cm ON c.id = cm.conversation_id AND cm.user_id = %s
                WHERE c.type = 'dm'
                  AND EXISTS (
                      SELECT 1 FROM conversation_members cm2
                      JOIN users u2 ON cm2.user_id = u2.id
                      WHERE cm2.conversation_id = c.id AND u2.id != %s AND u2.role = 'admin'
                  )
                ORDER BY COALESCE(
                    (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1),
                    c.created_at
                ) DESC
                """,
                (user["id"], user["id"], user["id"], user["id"])
            )
        else:
            cursor.execute(
                """
                SELECT c.id, c.type, c.name as group_name, c.created_by, c.created_at,
                       (
                           SELECT m.content 
                           FROM messages m 
                           WHERE m.conversation_id = c.id 
                           ORDER BY m.sent_at DESC LIMIT 1
                       ) as last_message,
                       (
                           SELECT m.sent_at 
                           FROM messages m 
                           WHERE m.conversation_id = c.id 
                           ORDER BY m.sent_at DESC LIMIT 1
                       ) as last_message_time,
                       (
                           SELECT COUNT(m.id) 
                           FROM messages m
                           LEFT JOIN message_reads mr ON m.id = mr.message_id AND mr.user_id = %s
                           WHERE m.conversation_id = c.id AND mr.id IS NULL AND m.sender_id != %s
                       ) as unread_count
                FROM conversations c
                JOIN conversation_members cm ON c.id = cm.conversation_id AND cm.user_id = %s
                ORDER BY COALESCE(
                    (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1),
                    c.created_at
                ) DESC
                """,
                (user["id"], user["id"], user["id"])
            )
        conversations = cursor.fetchall()
        
        valid_conversations = []
        # Append DM counterparty user info (filter out DMs with deleted users)
        for c in conversations:
            if c["type"] == "dm":
                cursor.execute(
                    """
                    SELECT u.id, u.name, u.email 
                    FROM conversation_members cm
                    JOIN users u ON cm.user_id = u.id
                    WHERE cm.conversation_id = %s AND u.id != %s
                    """,
                    (c["id"], user["id"])
                )
                other = cursor.fetchone()
                if other:
                    c["dm_user"] = other
                    valid_conversations.append(c)
            else:
                valid_conversations.append(c)

            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            c["created_at"] = c["created_at"].isoformat()
            
        return jsonify(valid_conversations), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/messages", methods=["GET"])
def chat_get_messages(conv_id):
    """
    Fetches the conversation message history and member profile list.

    Enforces security by confirming the user is a member of the room, or is an admin,
    or is a team leader accessing a group room.

    Args:
        conv_id (int): Primary key ID of the conversation.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Object containing conversation config, message list, and members info.
            - 403: Forbidden access.
            - 404: Conversation not found.
            - 500: Database aggregation query exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT type, name FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404
            
        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        is_member = cursor.fetchone() is not None
        
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        # Restrict history access to members, admins, or group team leaders
        allowed = is_member or is_admin or (is_tl and conv["type"] == "group")
        if not allowed:
            return jsonify({"error": "Access denied"}), 403
            
        if user.get("role") == "client":
            if conv["type"] != "dm":
                return jsonify({"error": "Access denied"}), 403
            cursor.execute(
                """
                SELECT u.role FROM conversation_members cm
                JOIN users u ON cm.user_id = u.id
                WHERE cm.conversation_id = %s AND u.id != %s
                """,
                (conv_id, user["id"])
            )
            counterparty = cursor.fetchone()
            if not counterparty or counterparty["role"] != "admin":
                return jsonify({"error": "Access denied"}), 403
            
        cursor.execute(
            """
            SELECT m.id, m.conversation_id, m.sender_id, u.name as sender_name, u.email as sender_email, m.content, m.sent_at
            FROM messages m
            LEFT JOIN users u ON m.sender_id = u.id
            WHERE m.conversation_id = %s
            ORDER BY m.sent_at ASC
            """,
            (conv_id,)
        )
        messages = cursor.fetchall()
        for m in messages:
            if m["sent_at"]:
                m["sent_at"] = m["sent_at"].isoformat()
                
        members_list = []
        # Return participant profile listings for group chats
        if conv["type"] == "group":
            cursor.execute(
                """
                SELECT u.id, u.name, u.email, u.role, e.designation
                FROM conversation_members cm
                JOIN users u ON cm.user_id = u.id
                LEFT JOIN employees e ON u.id = e.user_id
                WHERE cm.conversation_id = %s
                ORDER BY u.name ASC
                """,
                (conv_id,)
            )
            members_list = cursor.fetchall()
            
            # Fallback to all active system users if group members list is unpopulated
            if not members_list:
                cursor.execute(
                    """
                    SELECT u.id, u.name, u.email, u.role, e.designation
                    FROM users u
                    LEFT JOIN employees e ON u.id = e.user_id
                    WHERE u.role IN ('employee', 'admin', 'team_leader')
                    ORDER BY u.name ASC
                    """
                )
                members_list = cursor.fetchall()
            
        return jsonify({
            "conversation": {
                "id": conv_id,
                "type": conv["type"],
                "group_name": conv["name"]
            },
            "messages": messages,
            "members": members_list
        }), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/messages", methods=["POST"])
def chat_send_message(conv_id):
    """
    Submits a message text string and broadcasts it to all conversation members.

    Inserts the message into database records, appends a read receipt mark for the sender,
    and publishes the message metadata directly to matching subscriber queues in user_queues.

    Args:
        conv_id (int): Primary key ID of the target conversation.

    JSON Parameters:
        content (str): Text message string.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Newly inserted message schema.
            - 400: Empty content.
            - 403: User is not a member of the conversation.
            - 500: Database insertion exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    content = data.get("content")
    if not content:
        return jsonify({"error": "Message content is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verify room membership
        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        if not cursor.fetchone():
            return jsonify({"error": "You are not a member of this conversation"}), 403
            
        if user.get("role") == "client":
            cursor.execute("SELECT type FROM conversations WHERE id = %s", (conv_id,))
            conv = cursor.fetchone()
            if not conv or conv["type"] != "dm":
                return jsonify({"error": "Forbidden"}), 403
            cursor.execute(
                """
                SELECT u.role FROM conversation_members cm
                JOIN users u ON cm.user_id = u.id
                WHERE cm.conversation_id = %s AND u.id != %s
                """,
                (conv_id, user["id"])
            )
            counterparty = cursor.fetchone()
            if not counterparty or counterparty["role"] != "admin":
                return jsonify({"error": "Forbidden"}), 403
            
        # Store message record
        cursor.execute(
            "INSERT INTO messages (conversation_id, sender_id, content) VALUES (%s, %s, %s) RETURNING id, sent_at",
            (conv_id, user["id"], content)
        )
        res = cursor.fetchone()
        msg_id = res["id"]
        sent_at = res["sent_at"].isoformat()
        
        # Self-mark as read
        cursor.execute(
            "INSERT INTO message_reads (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (msg_id, user["id"])
        )
        
        conn.commit()

        # Push message update to all conversation members via SSE queues
        try:
            event_payload = json.dumps({
                "type": "message",
                "conversation_id": conv_id,
                "message": {
                    "id": msg_id,
                    "conversation_id": conv_id,
                    "sender_id": user["id"],
                    "sender_name": user["name"],
                    "content": content,
                    "sent_at": sent_at
                }
            })
            cursor.execute("SELECT user_id FROM conversation_members WHERE conversation_id = %s", (conv_id,))
            members = cursor.fetchall()
            for m in members:
                member_id = m.get("user_id") if isinstance(m, dict) else m[0]
                queues = user_queues.get(member_id)
                if queues:
                    for q in list(queues):
                        try:
                            # Non-blocking write to avoid throttling if subscriber queue is full
                            q.put_nowait(event_payload)
                        except queue.Full:
                            pass
        except Exception as push_err:
            print("SSE message push error:", push_err)

        return jsonify({
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": user["id"],
            "sender_name": user["name"],
            "content": content,
            "sent_at": sent_at
        }), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/read", methods=["POST"])
def chat_mark_read(conv_id):
    """
    Marks all received messages in a conversation as read.

    Creates records in the 'message_reads' table for messages where user is not the sender.

    Args:
        conv_id (int): Primary key ID of the conversation.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success notification.
            - 401: Unauthorized.
            - 500: Database insertion errors.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Retrieve all unread counterparty messages in the conversation
        cursor.execute(
            "SELECT id FROM messages WHERE conversation_id = %s AND sender_id != %s",
            (conv_id, user["id"])
        )
        messages = cursor.fetchall()
        for msg in messages:
            msg_id = msg[0]
            cursor.execute(
                "INSERT INTO message_reads (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (msg_id, user["id"])
            )
        conn.commit()
        return jsonify({"message": "Conversation marked as read"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/admin/all", methods=["GET"])
def chat_admin_all():
    """
    Lists all system conversation rooms for security auditing and management.
    Restricted to admin users.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: List of all chats with message states and active member logs.
            - 403: Forbidden access.
            - 500: Database aggregation query exceptions.
    """
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.type, c.name as group_name, c.created_at,
                   (
                       SELECT m.content 
                       FROM messages m 
                       WHERE m.conversation_id = c.id 
                       ORDER BY m.sent_at DESC LIMIT 1
                   ) as last_message,
                   (
                       SELECT m.sent_at 
                       FROM messages m 
                       WHERE m.conversation_id = c.id 
                       ORDER BY m.sent_at DESC LIMIT 1
                   ) as last_message_time
            FROM conversations c
            ORDER BY c.created_at DESC
            """
        )
        conversations = cursor.fetchall()
        for c in conversations:
            if c["type"] == "dm":
                # List names and roles for all DM participants
                cursor.execute(
                    """
                    SELECT u.id, u.name, u.email 
                    FROM conversation_members cm
                    JOIN users u ON cm.user_id = u.id
                    WHERE cm.conversation_id = %s
                    """,
                    (c["id"],)
                )
                c["dm_members"] = cursor.fetchall()
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            c["created_at"] = c["created_at"].isoformat()
            
        return jsonify(conversations), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/team-leader/groups", methods=["GET"])
def chat_tl_groups():
    """
    Lists group conversations accessible for supervision.
    Restricted to Team Leaders and Admins.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: List of group conversations.
            - 403: Forbidden access.
            - 500: SQL execution errors.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        if not is_tl:
            return jsonify({"error": "Forbidden"}), 403
            
        cursor.execute(
            """
            SELECT c.id, c.type, c.name as group_name, c.created_at,
                   (
                       SELECT m.content 
                       FROM messages m 
                       WHERE m.conversation_id = c.id 
                       ORDER BY m.sent_at DESC LIMIT 1
                   ) as last_message,
                   (
                       SELECT m.sent_at 
                       FROM messages m 
                       WHERE m.conversation_id = c.id 
                       ORDER BY m.sent_at DESC LIMIT 1
                   ) as last_message_time
            FROM conversations c
            WHERE c.type = 'group'
            ORDER BY c.created_at DESC
            """
        )
        conversations = cursor.fetchall()
        for c in conversations:
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            c["created_at"] = c["created_at"].isoformat()
            
        return jsonify(conversations), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/groups/<int:conv_id>/members", methods=["POST"])
def chat_group_add_member(conv_id):
    """
    Adds a new member to an existing group conversation.
    Restricted to Team Leaders and Admins.

    Args:
        conv_id (int): Primary key ID of the group conversation.

    JSON Parameters:
        user_id (int): The primary key ID of the user to append.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success notification.
            - 400: Missing user_id.
            - 404: Group not found.
            - 403: Forbidden access.
            - 500: Database insertion failure.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    member_id = data.get("user_id")
    if not member_id:
        return jsonify({"error": "User ID is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        if not is_tl:
            return jsonify({"error": "Forbidden"}), 403
            
        cursor.execute("SELECT type FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv or conv["type"] != "group":
            return jsonify({"error": "Group conversation not found"}), 404
            
        cursor.execute(
            "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (conv_id, member_id)
        )
        conn.commit()
        return jsonify({"message": "Member added successfully"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    """
    Deletes a conversation (DM or Group) and all associated messages/members.
    Restricted to Admins, Team Leaders, or the creator of the group.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, type, created_by FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404
            
        is_admin = user.get("role") == "admin"
        is_creator = conv.get("created_by") == user.get("id")
        is_tl = check_is_team_leader(user, cursor)
        
        if not (is_admin or is_creator or is_tl):
            return jsonify({"error": "Only Admins, Team Leaders, or group creators can delete conversations."}), 403
            
        cursor.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
        cursor.execute("DELETE FROM conversation_members WHERE conversation_id = %s", (conv_id,))
        cursor.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))
        conn.commit()
        
        return jsonify({"message": "Conversation deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete conversation error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


