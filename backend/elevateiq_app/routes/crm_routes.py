import bcrypt
from datetime import datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, require_role, check_is_crm_manager, rate_limit

crm_bp = Blueprint("crm", __name__)

@crm_bp.route("/crm/clients", methods=["GET"])
def get_crm_clients():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
        clients = cursor.fetchall()
        for c in clients:
            if c.get("created_at"):
                c["created_at"] = c["created_at"].isoformat()
        return jsonify(clients), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/crm/clients", methods=["POST"])
def create_crm_client():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        data = request.json
        company_name = data.get("company_name")
        contact_name = data.get("contact_name")
        email = data.get("email")
        phone_number = data.get("phone_number")
        deal_size = data.get("deal_size", 0.00)
        status = data.get("status", "Lead")
        notes = data.get("notes")

        if not company_name:
            return jsonify({"error": "Company Name is required"}), 400

        cursor.execute(
            """
            INSERT INTO clients (company_name, contact_name, email, phone_number, deal_size, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (company_name, contact_name, email, phone_number, deal_size, status, notes)
        )
        client_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Lead/Client created successfully", "id": client_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/crm/clients/<int:client_id>", methods=["PUT"])
def update_crm_client(client_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        data = request.json
        company_name = data.get("company_name")
        contact_name = data.get("contact_name")
        email = data.get("email")
        phone_number = data.get("phone_number")
        deal_size = data.get("deal_size")
        status = data.get("status")
        notes = data.get("notes")

        cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Lead/Client not found"}), 404

        update_fields = []
        params = []
        
        if company_name is not None:
            update_fields.append("company_name = %s")
            params.append(company_name)
        if contact_name is not None:
            update_fields.append("contact_name = %s")
            params.append(contact_name)
        if email is not None:
            update_fields.append("email = %s")
            params.append(email)
        if phone_number is not None:
            update_fields.append("phone_number = %s")
            params.append(phone_number)
        if deal_size is not None:
            update_fields.append("deal_size = %s")
            params.append(deal_size)
        if status is not None:
            update_fields.append("status = %s")
            params.append(status)
        if notes is not None:
            update_fields.append("notes = %s")
            params.append(notes)

        if update_fields:
            params.append(client_id)
            query = f"UPDATE clients SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, tuple(params))
            conn.commit()

        return jsonify({"message": "Lead/Client updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/crm/clients/<int:client_id>/provision", methods=["POST"])
def provision_crm_client(client_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        data = request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found"}), 404

        if client["user_id"]:
            return jsonify({"error": "Client has already been provisioned"}), 400

        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email is already taken"}), 400

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'client') RETURNING id",
            (client["contact_name"] or client["company_name"], email, hashed_pw)
        )
        new_user_id = cursor.fetchone()["id"]

        cli_str = f"CLI-{1000 + client_id}"

        cursor.execute(
            "UPDATE clients SET user_id = %s, client_id = %s, status = 'Active Client' WHERE id = %s",
            (new_user_id, cli_str, client_id)
        )
        conn.commit()
        return jsonify({"message": "Client access provisioned successfully", "client_id": cli_str}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/crm/clients/<int:client_id>/interactions", methods=["GET"])
def get_crm_interactions(client_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        cursor.execute("SELECT * FROM client_interactions WHERE client_id = %s ORDER BY created_at DESC", (client_id,))
        interactions = cursor.fetchall()
        for i in interactions:
            if i.get("created_at"):
                i["created_at"] = i["created_at"].isoformat()
        return jsonify(interactions), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/crm/interactions", methods=["POST"])
def create_crm_interaction():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        data = request.json
        client_id = data.get("client_id")
        interaction_type = data.get("interaction_type")
        notes = data.get("notes")

        if not client_id or not interaction_type:
            return jsonify({"error": "Client ID and Interaction Type are required"}), 400

        # Verify client exists
        cursor.execute("SELECT id FROM clients WHERE id = %s", (client_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Client not found"}), 404

        cursor.execute(
            """
            INSERT INTO client_interactions (client_id, interaction_type, notes)
            VALUES (%s, %s, %s) RETURNING id
            """,
            (client_id, interaction_type, notes)
        )
        interaction_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Interaction logged successfully", "id": interaction_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/dashboard/meetings", methods=["POST"])
def create_meeting():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
            
        title = data.get("title", "").strip()
        platform = data.get("platform", "").strip()
        meeting_link = data.get("meeting_link", "").strip()
        scheduled_at = data.get("scheduled_at", "").strip()
        meeting_type = data.get("meeting_type", "internal").strip()
        client_id = data.get("client_id")

        if not title or not platform or not meeting_link or not scheduled_at:
            return jsonify({"error": "All fields are required"}), 400
            
        if not client_id or client_id == "":
            client_id = None
        else:
            client_id = int(client_id)
            # Verify client exists
            cursor.execute("SELECT id FROM clients WHERE id = %s", (client_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Client not found"}), 404

        cursor.execute(
            """
            INSERT INTO meetings (title, platform, meeting_link, scheduled_at, meeting_type, client_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (title, platform, meeting_link, scheduled_at, meeting_type, client_id)
        )
        meeting_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Meeting created and shared successfully!", "id": meeting_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/dashboard/meetings", methods=["GET"])
def list_meetings():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user["role"] == "client":
            cursor.execute(
                """
                SELECT m.id, m.title, m.platform, m.meeting_link, m.scheduled_at, m.created_at, m.meeting_type, m.client_id, c.company_name
                FROM meetings m
                JOIN clients c ON m.client_id = c.id
                WHERE m.meeting_type = 'client' AND c.user_id = %s AND m.scheduled_at >= NOW() - INTERVAL '2 hours'
                ORDER BY m.scheduled_at ASC;
                """,
                (user["id"],)
            )
        elif check_is_crm_manager(user, cursor):
            cursor.execute(
                """
                SELECT m.id, m.title, m.platform, m.meeting_link, m.scheduled_at, m.created_at, m.meeting_type, m.client_id, c.company_name
                FROM meetings m
                LEFT JOIN clients c ON m.client_id = c.id
                WHERE m.scheduled_at >= NOW() - INTERVAL '2 hours'
                ORDER BY m.scheduled_at ASC;
                """
            )
        else:
            cursor.execute(
                """
                SELECT m.id, m.title, m.platform, m.meeting_link, m.scheduled_at, m.created_at, m.meeting_type, m.client_id
                FROM meetings m
                WHERE m.meeting_type = 'internal' AND m.scheduled_at >= NOW() - INTERVAL '2 hours'
                ORDER BY m.scheduled_at ASC;
                """
            )

        meetings = cursor.fetchall()
        for m in meetings:
            if m.get("scheduled_at"):
                m["scheduled_at"] = m["scheduled_at"].isoformat()
            if m.get("created_at"):
                m["created_at"] = m["created_at"].isoformat()
        return jsonify(meetings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/api/contact", methods=["POST"])
@rate_limit(limit=5, period=60)
def save_contact():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    track = data.get("track", "").strip()
    message = data.get("message", "").strip()
    
    if not name or not email or not phone or not track or not message:
        return jsonify({"success": False, "error": "All fields are required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO edutech_contacts (name, email, phone, track, message)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (name, email, phone, track, message)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Thank you! Your inquiry has been successfully registered.",
            "id": new_id
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/api/newsletter", methods=["POST"])
@rate_limit(limit=5, period=60)
def save_newsletter():
    data = request.json
    if not data or "email" not in data:
        return jsonify({"success": False, "error": "Email is required"}), 400
        
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM newsletter_subscribers WHERE email = %s;", (email,))
        existing = cursor.fetchone()
        if existing:
            return jsonify({
                "success": True,
                "message": "You are already subscribed to our newsletter!"
            }), 200
            
        cursor.execute(
            "INSERT INTO newsletter_subscribers (email) VALUES (%s) RETURNING id;",
            (email,)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Subscribed successfully!",
            "id": new_id
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/api/elevate-contact", methods=["POST"])
@rate_limit(limit=5, period=60)
def save_elevate_contact():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()
    
    if not name or not email or not message:
        return jsonify({"success": False, "error": "All fields are required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO elevate_iq_contacts (name, email, message)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (name, email, message)
        )
        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Thank you! Your message has been successfully sent.",
            "id": new_id
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/admin/contacts/edutech", methods=["GET"])
@require_role(["admin"])
def get_edutech_contacts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, name, email, phone, track, message, created_at FROM edutech_contacts ORDER BY created_at DESC")
        contacts = cursor.fetchall()
        for c in contacts:
            if c.get("created_at"):
                c["created_at"] = c["created_at"].isoformat()
        return jsonify(contacts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@crm_bp.route("/admin/contacts/elevate", methods=["GET"])
@require_role(["admin"])
def get_elevate_contacts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, name, email, message, created_at FROM elevate_iq_contacts ORDER BY created_at DESC")
        contacts = cursor.fetchall()
        for c in contacts:
            if c.get("created_at"):
                c["created_at"] = c["created_at"].isoformat()
        return jsonify(contacts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
