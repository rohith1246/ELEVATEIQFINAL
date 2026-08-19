"""
Real-Time Chat blueprint route handlers.

Implements instant messaging features using Server-Sent Events (SSE) stream connections.
Includes support for Direct Messages (DMs) and group chat rooms created by Admins/Team Leaders.
Messages, attachments, and conversation notifications are broadcasted instantly to online members'
active SSE event queues.
"""

import os
import uuid
import json
import queue
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, Response, send_from_directory, current_app
from werkzeug.utils import secure_filename
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, serializer, check_is_team_leader, TOKEN_MAX_AGE
from ..config import safe_error

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

# Upload configuration
# Detect project root directory properly
_pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if not os.path.exists(os.path.join(_pkg_root, "frontend")):
    _pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UPLOAD_FOLDER = os.environ.get("CHAT_UPLOAD_FOLDER") or os.path.join(_pkg_root, "uploads", "chat")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

# Global dictionary storing list of active SSE subscriber queues keyed by user ID
# Format: { user_id (int): set(queue.Queue) }
user_queues = {}


def register_queue(user_id, q):
    """
    Registers a client's message queue to receive real-time push events.
    """
    user_queues.setdefault(user_id, set()).add(q)


def unregister_queue(user_id, q):
    """
    Unregisters a client's message queue, cleaning up memory when a client disconnects.
    """
    queues = user_queues.get(user_id)
    if queues:
        queues.discard(q)
        if not queues:
            user_queues.pop(user_id, None)


@chat_bp.route("/uploads/chat/<path:filename>")
def serve_chat_upload(filename):
    """
    Serves uploaded chat attachments with appropriate content disposition.
    """
    return send_from_directory(UPLOAD_FOLDER, filename)


@chat_bp.route("/chat/stream")
@chat_bp.route("/api/chat/stream")
def chat_stream():
    """
    Serves a persistent HTTP Server-Sent Events (SSE) data stream.
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
        
    user_id = user.get("user_id") or user.get("id")
    q = queue.Queue(maxsize=100)
    register_queue(user_id, q)
    
    def event_stream():
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            ping_counter = 0
            while True:
                try:
                    msg_data = q.get(timeout=1)
                    yield f"data: {msg_data}\n\n"
                except queue.Empty:
                    yield ":keepalive\n\n"
                    ping_counter += 1
                    if ping_counter >= 20:
                        yield "data: {\"type\": \"ping\"}\n\n"
                        ping_counter = 0
        finally:
            unregister_queue(user_id, q)
            
    return Response(event_stream(), mimetype="text/event-stream")


@chat_bp.route("/chat/user-details", methods=["GET"])
def chat_user_details():
    """
    Retrieves authorized privileges and profile metadata for the chat layout.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        uid = user.get("user_id") or user.get("id")
        designation = ""
        if user.get("role") != "admin":
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (uid,))
            res = cursor.fetchone()
            if res:
                designation = ((res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")).lower()

        is_tl = user.get("role") in ["admin", "team_leader"] or "team leader" in designation or "team lead" in designation
        can_approve = user.get("role") == "admin" or "team leader" in designation or "team lead" in designation or "hr" in designation or "human resource" in designation
        is_hr = user.get("role") == "admin" or "hr" in designation or "human resource" in designation

        return jsonify({
            "id": uid,
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
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


@chat_bp.route("/chat/heartbeat", methods=["POST"])
@chat_bp.route("/api/chat/heartbeat", methods=["POST"])
def chat_heartbeat():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor()
    try:
        uid = user.get("user_id") or user.get("id")
        cursor.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (uid,))
        conn.commit()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/users", methods=["GET"])
@chat_bp.route("/api/chat/users", methods=["GET"])
def chat_list_users():
    """
    Lists all system users eligible for chat (Employees, Team Leaders, and Admins), excluding self.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        uid = user.get("user_id") or user.get("id")
        cursor.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (uid,))
        conn.commit()

        if user.get("role") == "client":
            cursor.execute(
                """
                SELECT id, name, email, role,
                       (last_seen IS NOT NULL AND ABS(EXTRACT(EPOCH FROM (NOW() - last_seen))) < 300) as is_online 
                FROM users WHERE role = 'admin' AND id != %s ORDER BY name ASC
                """,
                (user["id"],)
            )
        else:
            cursor.execute(
                """
                SELECT id, name, email, role,
                       (last_seen IS NOT NULL AND ABS(EXTRACT(EPOCH FROM (NOW() - last_seen))) < 300) as is_online 
                FROM users WHERE role IN ('employee', 'admin', 'team_leader') AND id != %s ORDER BY name ASC
                """,
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
@chat_bp.route("/chat/groups", methods=["POST"])
@chat_bp.route("/api/chat/groups", methods=["POST"])
def chat_create_conversation():
    """
    Initializes a Direct Message session or a Group Chat room.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    conv_type = data.get("type", "dm")
    if "is_group" in data or "name" in data or "group_name" in data:
        conv_type = "group" if (data.get("is_group") or data.get("name")) else "dm"
        
    name = data.get("name") or data.get("group_name")
    member_ids = data.get("member_ids") or data.get("members") or []
    
    if isinstance(member_ids, int):
        member_ids = [member_ids]
    if isinstance(member_ids, str):
        try:
            member_ids = [int(x.strip()) for x in member_ids.split(",") if x.strip()]
        except ValueError:
            member_ids = []
            
    if conv_type not in ["dm", "group"]:
        return jsonify({"error": "Invalid conversation type"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        if conv_type == "group":
            if user.get("role") == "client":
                return jsonify({"error": "Clients cannot create group chats."}), 403
            if not name:
                name = "New Group Chat"
                
            if not (is_admin or is_tl):
                return jsonify({"error": "Only Admins and Team Leaders can create groups."}), 403
        else:
            if not member_ids:
                return jsonify({"error": "Member ID is required for direct messages"}), 400
            target_user_id = member_ids[0]
            
            cursor.execute("SELECT role FROM users WHERE id = %s", (target_user_id,))
            target_user = cursor.fetchone()
            if not target_user:
                return jsonify({"error": "User not found"}), 404
                
            if user.get("role") == "client" and target_user["role"] != "admin":
                return jsonify({"error": "Clients can only initiate chats with Admins."}), 403
            if target_user["role"] == "client" and user.get("role") != "admin":
                return jsonify({"error": "Employees cannot message clients directly."}), 403
            
            cursor.execute(
                """
                SELECT c.id, c.type, c.name, c.created_at
                FROM conversations c
                JOIN conversation_members cm1 ON c.id = cm1.conversation_id AND cm1.user_id = %s
                JOIN conversation_members cm2 ON c.id = cm2.conversation_id AND cm2.user_id = %s
                WHERE c.type = 'dm'
                LIMIT 1
                """,
                (user["id"], target_user_id)
            )
            existing = cursor.fetchone()
            if existing:
                return jsonify(existing), 200

        cursor.execute(
            """
            INSERT INTO conversations (type, name, created_by)
            VALUES (%s, %s, %s)
            RETURNING id, type, name, created_at
            """,
            (conv_type, name if conv_type == "group" else None, user["id"])
        )
        conv = cursor.fetchone()
        conv_id = conv["id"]
        
        all_members = set(member_ids)
        all_members.add(user["id"])
        
        for m_id in all_members:
            cursor.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (conv_id, m_id)
            )
            
        conn.commit()

        try:
            event_payload = json.dumps({
                "type": "conversation_update",
                "conversation": {
                    "id": conv_id,
                    "type": conv_type,
                    "name": name,
                    "group_name": name,
                    "is_group": (conv_type == "group"),
                    "created_by": user["id"]
                }
            })
            for m_id in all_members:
                queues = user_queues.get(m_id)
                if queues:
                    for q in list(queues):
                        try:
                            q.put_nowait(event_payload)
                        except queue.Full:
                            pass
        except Exception as push_err:
            logger.error(f"SSE conversation push error: {push_err}")
            
        conv["group_name"] = conv["name"]
        conv["is_group"] = (conv["type"] == "group")
        return jsonify(conv), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations", methods=["GET"])
@chat_bp.route("/chat/groups", methods=["GET"])
@chat_bp.route("/api/chat/groups", methods=["GET"])
def chat_list_conversations():
    """
    Lists conversations for the authenticated user (including all group conversations).
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        uid = user.get("user_id") or user.get("id")
        cursor.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (uid,))
        conn.commit()

        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"

        if is_admin or is_tl or user.get("role") == "employee":
            cursor.execute(
                """
                SELECT c.id, c.type, c.name as group_name, c.created_by, c.created_at,
                       (SELECT m.content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message,
                       (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message_time,
                       (SELECT COUNT(*) FROM messages m 
                        WHERE m.conversation_id = c.id 
                          AND m.id NOT IN (SELECT mr.message_id FROM message_reads mr WHERE mr.user_id = %s)
                          AND m.sender_id != %s
                       ) as unread_count
                FROM conversations c
                WHERE c.id IN (
                    SELECT conversation_id FROM conversation_members WHERE user_id = %s
                ) OR c.type = 'group'
                ORDER BY last_message_time DESC NULLS LAST, c.created_at DESC
                """,
                (user["id"], user["id"], user["id"])
            )
            conversations = cursor.fetchall()
        else:
            cursor.execute(
                """
                SELECT c.id, c.type, c.name as group_name, c.created_by, c.created_at,
                       (SELECT m.content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message,
                       (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message_time,
                       (SELECT COUNT(*) FROM messages m 
                        WHERE m.conversation_id = c.id 
                          AND m.id NOT IN (SELECT mr.message_id FROM message_reads mr WHERE mr.user_id = %s)
                          AND m.sender_id != %s
                       ) as unread_count
                FROM conversations c
                JOIN conversation_members cm ON c.id = cm.conversation_id
                WHERE cm.user_id = %s
                ORDER BY last_message_time DESC NULLS LAST, c.created_at DESC
                """,
                (user["id"], user["id"], user["id"])
            )
            conversations = cursor.fetchall()
            
        for c in conversations:
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            c["is_group"] = (c["type"] == "group")
            c["name"] = c.get("group_name") or c.get("name") or "Group Chat"
            
            if c["type"] == "dm":
                cursor.execute(
                    """
                    SELECT u.id, u.name, u.email, u.role,
                           (u.last_seen IS NOT NULL AND ABS(EXTRACT(EPOCH FROM (NOW() - u.last_seen))) < 300) as is_online
                    FROM conversation_members cm
                    JOIN users u ON cm.user_id = u.id
                    WHERE cm.conversation_id = %s AND u.id != %s
                    LIMIT 1
                    """,
                    (c["id"], user["id"])
                )
                c["dm_user"] = cursor.fetchone()
                if c["dm_user"] and not c.get("group_name"):
                    c["name"] = c["dm_user"]["name"]

        if user.get("role") == "client":
            valid_convs = []
            for c in conversations:
                if c["type"] == "dm" and c.get("dm_user") and c["dm_user"]["role"] == "admin":
                    valid_convs.append(c)
            conversations = valid_convs
            
        return jsonify(conversations), 200
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/messages", methods=["GET"])
def chat_get_messages(conv_id):
    """
    Fetches message history and participant profiles (including file attachments).
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, type, name as group_name, created_by FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404
            
        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        is_member = cursor.fetchone() is not None
        
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        if not is_member and conv["type"] == "group" and user.get("role") in ["admin", "employee", "team_leader"]:
            cursor.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (conv_id, user["id"]))
            conn.commit()
            is_member = True

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
            SELECT m.id, m.conversation_id, m.sender_id, u.name as sender_name, u.email as sender_email, 
                   m.content, m.sent_at, m.file_url, m.file_name, m.file_type, m.file_size
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
        if conv["type"] == "group":
            cursor.execute(
                """
                SELECT u.id, u.name, u.email, u.role, e.designation,
                       (u.last_seen IS NOT NULL AND ABS(EXTRACT(EPOCH FROM (NOW() - u.last_seen))) < 300) as is_online
                FROM conversation_members cm
                JOIN users u ON cm.user_id = u.id
                LEFT JOIN employees e ON u.id = e.user_id
                WHERE cm.conversation_id = %s
                ORDER BY u.name ASC
                """,
                (conv_id,)
            )
            members_list = cursor.fetchall()
            
            if not members_list:
                cursor.execute(
                    """
                    SELECT u.id, u.name, u.email, u.role, e.designation,
                           (u.last_seen IS NOT NULL AND ABS(EXTRACT(EPOCH FROM (NOW() - u.last_seen))) < 300) as is_online
                    FROM users u
                    LEFT JOIN employees e ON u.id = e.user_id
                    WHERE u.role IN ('employee', 'admin', 'team_leader') AND u.status = 'active'
                    ORDER BY u.name ASC
                    """
                )
                members_list = cursor.fetchall()
                
        conv_payload = {
            "id": conv["id"],
            "type": conv["type"],
            "name": conv.get("group_name") or ("Group Chat" if conv["type"] == "group" else "Direct Message"),
            "group_name": conv.get("group_name") or ("Group Chat" if conv["type"] == "group" else "Direct Message"),
            "created_by": conv.get("created_by")
        }

        return jsonify({
            "conversation": conv_payload,
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
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "Message content is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT type FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404

        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        is_member = cursor.fetchone() is not None
        
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        if not is_member:
            if conv["type"] == "group" and user.get("role") in ["admin", "employee", "team_leader"]:
                cursor.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (conv_id, user["id"]))
                conn.commit()
                is_member = True
            else:
                return jsonify({"error": "You are not a member of this conversation"}), 403
            
        if user.get("role") == "client":
            if conv["type"] != "dm":
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
            
        cursor.execute(
            "INSERT INTO messages (conversation_id, sender_id, content) VALUES (%s, %s, %s) RETURNING id, sent_at",
            (conv_id, user["id"], content)
        )
        res = cursor.fetchone()
        msg_id = res["id"]
        sent_at_val = res.get("sent_at")
        if hasattr(sent_at_val, "isoformat"):
            sent_at = sent_at_val.isoformat()
        elif sent_at_val:
            sent_at = str(sent_at_val)
        else:
            sent_at = datetime.now(timezone.utc).isoformat()
        
        cursor.execute(
            "INSERT INTO message_reads (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (msg_id, user["id"])
        )
        conn.commit()

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
                            q.put_nowait(event_payload)
                        except queue.Full:
                            pass
        except Exception as push_err:
            logger.error(f"SSE message push error: {push_err}")

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


@chat_bp.route("/chat/conversations/<int:conv_id>/upload", methods=["POST"])
@chat_bp.route("/api/chat/conversations/<int:conv_id>/upload", methods=["POST"])
def chat_upload_file(conv_id):
    """
    Uploads a file or image attachment to a conversation (group or DM) and broadcasts to members.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
        
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    caption = request.form.get("content", "").strip()
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT type FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404
            
        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        is_member = cursor.fetchone() is not None
        
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        if not is_member:
            if conv["type"] == "group" and user.get("role") in ["admin", "employee", "team_leader"]:
                cursor.execute("INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (conv_id, user["id"]))
                conn.commit()
                is_member = True
            else:
                return jsonify({"error": "You are not a member of this conversation"}), 403
                
        if user.get("role") == "client":
            if conv["type"] != "dm":
                return jsonify({"error": "Forbidden"}), 403
                
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": "File size exceeds the maximum limit of 25MB."}), 400
            
        original_filename = secure_filename(file.filename) or "attachment"
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        
        unique_name = f"{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}_{original_filename}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(save_path)
        
        file_url = f"/uploads/chat/{unique_name}"
        file_type = file.content_type or (f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'] else 'application/octet-stream')
        
        content = caption if caption else f"Shared a file: {original_filename}"
        
        cursor.execute(
            """
            INSERT INTO messages (conversation_id, sender_id, content, file_url, file_name, file_type, file_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, sent_at
            """,
            (conv_id, user["id"], content, file_url, original_filename, file_type, file_size)
        )
        res = cursor.fetchone()
        msg_id = res["id"]
        sent_at_val = res.get("sent_at")
        sent_at = sent_at_val.isoformat() if hasattr(sent_at_val, "isoformat") else (str(sent_at_val) if sent_at_val else datetime.now(timezone.utc).isoformat())
        
        cursor.execute(
            "INSERT INTO message_reads (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (msg_id, user["id"])
        )
        conn.commit()
        
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
                    "file_url": file_url,
                    "file_name": original_filename,
                    "file_type": file_type,
                    "file_size": file_size,
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
                            q.put_nowait(event_payload)
                        except queue.Full:
                            pass
        except Exception as push_err:
            logger.error(f"SSE file push error: {push_err}")
            
        return jsonify({
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": user["id"],
            "sender_name": user["name"],
            "content": content,
            "file_url": file_url,
            "file_name": original_filename,
            "file_type": file_type,
            "file_size": file_size,
            "sent_at": sent_at
        }), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat file upload error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/read", methods=["POST"])
def chat_mark_read(conv_id):
    """
    Marks all messages within the specified conversation as read for the user.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO message_reads (message_id, user_id)
            SELECT m.id, %s
            FROM messages m
            WHERE m.conversation_id = %s
            ON CONFLICT DO NOTHING
            """,
            (user["id"], conv_id)
        )
        conn.commit()
        return jsonify({"message": "Marked as read"}), 200
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
    Lists all system conversation records for administrative review.
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
                   (SELECT m.content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message,
                   (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message_time,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as total_messages
            FROM conversations c
            ORDER BY last_message_time DESC NULLS LAST, c.created_at DESC
            """
        )
        conversations = cursor.fetchall()
        for c in conversations:
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            if c["created_at"]:
                c["created_at"] = c["created_at"].isoformat()
            c["is_group"] = (c["type"] == "group")
            c["name"] = c.get("group_name") or c.get("name") or ("Group Chat" if c["type"] == "group" else "Direct Message")
            
            if c["type"] == "dm":
                cursor.execute(
                    """
                    SELECT u.name FROM conversation_members cm
                    JOIN users u ON cm.user_id = u.id
                    WHERE cm.conversation_id = %s
                    LIMIT 2
                    """,
                    (c["id"],)
                )
                users = cursor.fetchall()
                names = [u["name"] for u in users]
                c["participants"] = " & ".join(names)
                if names:
                    c["name"] = f"DM: {' & '.join(names)}"
            else:
                c["participants"] = "Group Channel"

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
    Lists group conversations accessible for supervision by Team Leaders and Admins.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        if not (is_tl or is_admin):
            return jsonify({"error": "Forbidden - Team Leader role required"}), 403
            
        cursor.execute(
            """
            SELECT c.id, c.type, c.name as group_name, c.created_at,
                   (SELECT m.content FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message,
                   (SELECT m.sent_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.sent_at DESC LIMIT 1) as last_message_time,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as total_messages
            FROM conversations c
            WHERE c.type = 'group'
            ORDER BY last_message_time DESC NULLS LAST, c.created_at DESC
            """
        )
        conversations = cursor.fetchall()
        for c in conversations:
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            if c["created_at"]:
                c["created_at"] = c["created_at"].isoformat()
            c["is_group"] = True
            c["name"] = c.get("group_name") or "Group Chat"
            c["participants"] = "Group Channel"

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
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    member_id = data.get("user_id") or data.get("member_id")
    if not member_id:
        return jsonify({"error": "User ID to add is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        cursor.execute("SELECT id, type, created_by FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv or conv["type"] != "group":
            return jsonify({"error": "Group conversation not found"}), 404
            
        is_creator = conv.get("created_by") == user.get("id")
        if not (is_admin or is_tl or is_creator):
            return jsonify({"error": "Only Admins, Team Leaders, or the group creator can add members."}), 403
            
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


@chat_bp.route("/chat/groups/<int:conv_id>/members/<int:member_id>", methods=["DELETE"])
@chat_bp.route("/api/chat/groups/<int:conv_id>/members/<int:member_id>", methods=["DELETE"])
def chat_group_remove_member(conv_id, member_id):
    """
    Removes a member from an existing group conversation.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        is_admin = user.get("role") == "admin"
        
        cursor.execute("SELECT id, type, created_by FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv or conv["type"] != "group":
            return jsonify({"error": "Group conversation not found"}), 404
            
        is_creator = conv.get("created_by") == user.get("id")
        is_self = user.get("id") == member_id
        
        if not (is_admin or is_tl or is_creator or is_self):
            return jsonify({"error": "Access denied"}), 403
            
        cursor.execute(
            "DELETE FROM conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, member_id)
        )
        conn.commit()
        return jsonify({"message": "Member removed successfully"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Chat remove member error: {e}")
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
