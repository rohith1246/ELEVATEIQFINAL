import json
import queue
from flask import Blueprint, request, jsonify, Response
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, serializer, check_is_team_leader

chat_bp = Blueprint("chat", __name__)

# Global dictionary to store SSE subscriber queues
user_queues = {}

def register_queue(user_id, q):
    user_queues.setdefault(user_id, set()).add(q)

def unregister_queue(user_id, q):
    queues = user_queues.get(user_id)
    if queues:
        queues.discard(q)
        if not queues:
            user_queues.pop(user_id, None)


@chat_bp.route("/chat/stream")
def chat_stream():
    token = request.cookies.get("token") or request.args.get("token")
    if not token:
        return "Unauthorized", 401
    try:
        user = serializer.loads(token)
    except Exception:
        return "Unauthorized", 401
        
    user_id = user["id"]
    q = queue.Queue(maxsize=100)
    register_queue(user_id, q)
    
    def event_stream():
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    msg_data = q.get(timeout=20)
                    yield f"data: {msg_data}\n\n"
                except queue.Empty:
                    yield "data: {\"type\": \"ping\"}\n\n"
        finally:
            unregister_queue(user_id, q)
            
    return Response(event_stream(), mimetype="text/event-stream")


@chat_bp.route("/chat/user-details", methods=["GET"])
def chat_user_details():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_tl = check_is_team_leader(user, cursor)
        
        can_approve = False
        is_hr = False
        if user["role"] == "admin":
            can_approve = True
            is_hr = True
        else:
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = (res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")
                designation = designation.lower()
                if "team leader" in designation or "lead" in designation or "hr" in designation or "human resource" in designation:
                    can_approve = True
                if "hr" in designation or "human resource" in designation:
                    is_hr = True

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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/users", methods=["GET"])
def chat_list_users():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            "SELECT id, name, email, role FROM users WHERE role IN ('employee', 'admin') AND id != %s ORDER BY name ASC",
            (user["id"],)
        )
        users = cursor.fetchall()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations", methods=["POST"])
def chat_create_conversation():
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
                
        members = [m_id for m_id in members if m_id != user["id"]]
        all_member_ids = list(set([user["id"]] + members))
        
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
        
        for m_id in all_member_ids:
            cursor.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s)",
                (conv_id, m_id)
            )
            
        conn.commit()

        # Push conversation update via SSE to all conversation members
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations", methods=["GET"])
def chat_list_conversations():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
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
            if c["last_message_time"]:
                c["last_message_time"] = c["last_message_time"].isoformat()
            c["created_at"] = c["created_at"].isoformat()
            
        return jsonify(conversations), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/messages", methods=["GET"])
def chat_get_messages(conv_id):
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
        
        allowed = is_member or is_admin or (is_tl and conv["type"] == "group")
        if not allowed:
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/messages", methods=["POST"])
def chat_send_message(conv_id):
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
        cursor.execute("SELECT id FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (conv_id, user["id"]))
        if not cursor.fetchone():
            return jsonify({"error": "You are not a member of this conversation"}), 403
            
        cursor.execute(
            "INSERT INTO messages (conversation_id, sender_id, content) VALUES (%s, %s, %s) RETURNING id, sent_at",
            (conv_id, user["id"], content)
        )
        res = cursor.fetchone()
        msg_id = res["id"]
        sent_at = res["sent_at"].isoformat()
        
        cursor.execute(
            "INSERT INTO message_reads (message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (msg_id, user["id"])
        )
        
        conn.commit()

        # Push message update to all conversation members via SSE
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/conversations/<int:conv_id>/read", methods=["POST"])
def chat_mark_read(conv_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/admin/all", methods=["GET"])
def chat_admin_all():
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/team-leader/groups", methods=["GET"])
def chat_tl_groups():
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@chat_bp.route("/chat/groups/<int:conv_id>/members", methods=["POST"])
def chat_group_add_member(conv_id):
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
