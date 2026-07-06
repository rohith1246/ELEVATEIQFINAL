"""
Customer Relationship Management (CRM) and Client portal blueprint routes.

Handles operations relating to lead/client lifecycle management, client account 
provisioning, client interactions tracking, scheduling meetings (internal or client-facing), 
and storing customer support messages from contact forms and newsletter signups.
"""

import bcrypt
from datetime import datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, require_role, check_is_crm_manager, rate_limit, validate_email, validate_password_strength

crm_bp = Blueprint("crm", __name__)

@crm_bp.route("/crm/clients", methods=["GET"])
def get_crm_clients():
    """
    Retrieves all records in the clients table.
    Restricted to users with CRM Manager privileges.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: List of clients.
            - 401: Unauthorized.
            - 403: Forbidden access.
            - 500: Database select query error.
    """
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
    """
    Creates a new client/lead entry.
    Restricted to users with CRM Manager privileges.

    JSON Parameters:
        company_name (str): Name of the client company.
        contact_name (str, optional): Name of primary contact person.
        email (str, optional): Email address.
        phone_number (str, optional): Phone number.
        deal_size (float, optional): Estimated deal size. Defaults to 0.00.
        status (str, optional): CRM pipeline status. Defaults to 'Lead'.
        notes (str, optional): Internal notes.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success message and new client database ID.
            - 400: Missing company_name.
            - 401: Unauthorized.
            - 403: Forbidden access.
            - 500: Database insert errors.
    """
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
    """
    Updates client details dynamically based on input parameters.
    Restricted to users with CRM Manager privileges.

    Args:
        client_id (int): Primary key ID of the client to update.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success update message.
            - 401: Unauthorized.
            - 403: Forbidden access.
            - 404: Client record not found.
            - 500: SQL query assembly or update error.
    """
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

        # Dynamically build UPDATE query parameters to avoid resetting untouched attributes
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
    """
    Creates login credentials for a CRM client to access their sub-portal dashboard.

    Inserts a user record with role 'client', maps user_id to the client row,
    assigns a public client ID (e.g. 'CLI-1005'), and marks their status as 'Active Client'.
    Restricted to CRM Managers.

    Args:
        client_id (int): Primary key ID of the client.

    JSON Parameters:
        email (str): Client login email.
        password (str): Client login password.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success message and client code.
            - 400: Email already exists or client already provisioned.
            - 401/403: Security errors.
            - 404: Client record not found.
            - 500: Database transaction exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not check_is_crm_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        
        data = request.json
        email = data.get("email", "").strip() if data.get("email") else ""
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        if not validate_email(email):
            return jsonify({"error": "Invalid email address format"}), 400

        is_strong, pw_msg = validate_password_strength(password)
        if not is_strong:
            return jsonify({"error": pw_msg}), 400

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
        # Insert client login details into users table
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'client') RETURNING id",
            (client["contact_name"] or client["company_name"], email, hashed_pw)
        )
        new_user_id = cursor.fetchone()["id"]

        # Formulate formatted client string code (CLI-xxxx)
        cli_str = f"CLI-{1000 + client_id}"

        # Update client profile linking user ID and designation code
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
    """
    Fetches logged historical interactions (calls, meetings, emails) for a client.
    Restricted to CRM Managers.

    Args:
        client_id (int): Database key of the client.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of interaction logs.
            - 401/403: Security errors.
            - 500: Database query exceptions.
    """
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
    """
    Logs a new communication event under client profile history.
    Restricted to CRM Managers.

    JSON Parameters:
        client_id (int): Primary key of target client.
        interaction_type (str): Type label (e.g. 'Email', 'Call', 'Meeting').
        notes (str, optional): Summary comments.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success creation message.
            - 400: Missing client_id or interaction_type.
            - 404: Client record not found.
            - 500: DB transaction failure.
    """
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
    """
    Schedules a meeting and logs it.
    Restricted to CRM Managers.

    JSON Parameters:
        title (str): Subject title of meeting.
        platform (str): Streaming app (e.g. Zoom, Google Meet, Teams).
        meeting_link (str): Join URL address.
        scheduled_at (str): ISO date time string.
        meeting_type (str, optional): 'internal' or 'client'. Defaults to 'internal'.
        client_id (int, optional): Mapped client DB key.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success creation message.
            - 400: Missing title, platform, link, or schedule date.
            - 404: Mapped client record not found.
            - 500: Database insert errors.
    """
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
    """
    Lists upcoming meetings occurring from 2 hours in the past onwards.

    - Clients: Retrieves client meetings mapped to their account ID.
    - CRM Managers: Retrieves all internal and client-facing meetings.
    - Employees/Guests: Retrieves only internal company meetings.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Sorted listing of meeting schedules.
            - 401: Unauthorized access.
            - 500: Database aggregate query issues.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Client role filters meetings specifically mapped to their client ID
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
            # CRM Managers audit all corporate scheduled slots
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
            # Standard employees view internal-only meetings
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
    """
    Saves message inquiries posted on the EduTech sub-portal landing site.
    Rate limited to 5 submissions per minute.

    JSON Parameters:
        name (str): User name.
        email (str): User email.
        phone (str): User phone number.
        track (str): Selected technology syllabus track.
        message (str): Question/message string.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success message and form record ID.
            - 400: Missing payload values.
            - 500: Database insertion exceptions.
    """
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

    if len(name) < 2 or len(name) > 100:
        return jsonify({"success": False, "error": "Name must be between 2 and 100 characters long"}), 400

    if not validate_email(email):
        return jsonify({"success": False, "error": "Invalid email address format"}), 400

    clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    if len(clean_phone) < 7 or len(clean_phone) > 15 or not clean_phone.isdigit():
        return jsonify({"success": False, "error": "Invalid phone number format"}), 400
        
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
    """
    Registers client/candidate email subscriptions to newsletter.
    Rate limited to 5 registrations per minute.

    JSON Parameters:
        email (str): Subscriber email.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: If email was already subscribed.
            - 201: Success subscription status code.
            - 400: Missing email.
            - 500: Database query issues.
    """
    data = request.json
    if not data or "email" not in data:
        return jsonify({"success": False, "error": "Email is required"}), 400
        
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    if not validate_email(email):
        return jsonify({"success": False, "error": "Invalid email address format"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if already subscribed to avoid duplicate rows
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
    """
    Stores contact messages submitted through the primary ElevateIQ portal contact page.
    Rate limited to 5 submissions per minute.

    JSON Parameters:
        name (str): Contact name.
        email (str): Contact email.
        message (str): Contact message content.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success receipt message with entry ID.
            - 400: Missing values.
            - 500: Database operation errors.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()
    
    if not name or not email or not message:
        return jsonify({"success": False, "error": "All fields are required"}), 400

    if len(name) < 2 or len(name) > 100:
        return jsonify({"success": False, "error": "Name must be between 2 and 100 characters long"}), 400

    if not validate_email(email):
        return jsonify({"success": False, "error": "Invalid email address format"}), 400
        
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
    """
    Lists all stored inquiry messages sent from the EduTech contact form.
    Restricted to admin users.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of contact objects.
            - 500: SQL query issues.
    """
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
    """
    Lists all messages stored from the primary ElevateIQ contact form.
    Restricted to admin users.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of contact objects.
            - 500: SQL query issues.
    """
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

