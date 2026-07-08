"""
Support Tickets Module.

Handles creating, retrieving, and resolving support tickets.
Admins can view and resolve all tickets, while standard users can only view their own
and close them if resolved.
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user
from ..config import safe_error

logger = logging.getLogger(__name__)

tickets_bp = Blueprint("tickets", __name__)

@tickets_bp.route("/api/tickets", methods=["POST"])
def create_ticket():
    """
    Submits a new support ticket.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category = data.get("category", "General").strip()
    priority = data.get("priority", "Medium").strip()

    if not title or not description:
        return jsonify({"error": "Title and description are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO tickets (user_id, title, description, category, priority, status)
            VALUES (%s, %s, %s, %s, %s, 'Open')
            RETURNING id
            """,
            (user["id"], title, description, category, priority)
        )
        ticket_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Ticket created successfully", "ticket_id": ticket_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Tickets API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()

@tickets_bp.route("/api/tickets", methods=["GET"])
def get_tickets():
    """
    Fetches support tickets.
    Admins can request 'scope=all' to see all tickets.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    scope = request.args.get("scope")
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if scope == "all" and user["role"] == "admin":
            cursor.execute(
                """
                SELECT t.*, u.name as user_name, u.email as user_email, u.role as user_role, u.portal as user_portal,
                       r.name as resolved_by_name
                FROM tickets t
                JOIN users u ON t.user_id = u.id
                LEFT JOIN users r ON t.resolved_by = r.id
                ORDER BY t.created_at DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT t.*, r.name as resolved_by_name
                FROM tickets t
                LEFT JOIN users r ON t.resolved_by = r.id
                WHERE t.user_id = %s
                ORDER BY t.created_at DESC
                """,
                (user["id"],)
            )

        tickets = cursor.fetchall()
        for t in tickets:
            if t.get("created_at"):
                t["created_at"] = t["created_at"].isoformat()
            if t.get("updated_at"):
                t["updated_at"] = t["updated_at"].isoformat()
            if t.get("resolved_at"):
                t["resolved_at"] = t["resolved_at"].isoformat()

        return jsonify(tickets), 200
    except Exception as e:
        logger.error(f"Tickets API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()

@tickets_bp.route("/api/tickets/<int:ticket_id>", methods=["PUT"])
def update_ticket(ticket_id):
    """
    Updates or resolves a ticket.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cursor.fetchone()
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        if user["role"] == "admin":
            status = data.get("status")
            admin_notes = data.get("admin_notes")

            updates = []
            params = []

            if status:
                updates.append("status = %s")
                params.append(status)
                if status == "Resolved":
                    updates.append("resolved_by = %s")
                    params.append(user["id"])
                    updates.append("resolved_at = %s")
                    params.append(datetime.now())

            if admin_notes is not None:
                updates.append("admin_notes = %s")
                params.append(admin_notes)

            if not updates:
                return jsonify({"error": "No update fields provided"}), 400

            updates.append("updated_at = %s")
            params.append(datetime.now())

            params.append(ticket_id)

            cursor.execute(
                f"UPDATE tickets SET {', '.join(updates)} WHERE id = %s",
                tuple(params)
            )
            conn.commit()
            return jsonify({"message": "Ticket updated successfully by admin"}), 200
        else:
            if ticket["user_id"] != user["id"]:
                return jsonify({"error": "Forbidden"}), 403

            status = data.get("status")
            if status != "Closed":
                return jsonify({"error": "Users can only change ticket status to Closed"}), 400

            cursor.execute(
                "UPDATE tickets SET status = 'Closed', updated_at = %s WHERE id = %s",
                (datetime.now(), ticket_id)
            )
            conn.commit()
            return jsonify({"message": "Ticket closed successfully"}), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Tickets API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()
