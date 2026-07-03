import os
import bcrypt
from datetime import datetime, date
from flask import Blueprint, request, jsonify, redirect, send_from_directory
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import (
    get_current_user, require_role, serializer, 
    check_is_recruitment_manager, check_is_crm_manager
)
from ..config import Config

auth_bp = Blueprint("auth", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EDUTECH_DIR = os.path.join(BASE_DIR, "edutech")

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = "candidate"  # Enforce candidate role for public registration

    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email already registered"}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, email, hashed_password, role)
        )
        conn.commit()
        return jsonify({"message": "Registration successful"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    login_id = data.get("email")  # can be email, Employee ID, or Client ID
    password = data.get("password")

    if not login_id or not password:
        return jsonify({"error": "Email/Employee ID/Client ID and password are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        user_record = None
        # Try finding employee first
        cursor.execute(
            """
            SELECT u.*, e.id as emp_db_id, e.employee_id 
            FROM users u 
            JOIN employees e ON u.id = e.user_id 
            WHERE e.employee_id = %s OR u.email = %s
            """,
            (login_id, login_id)
        )
        user_record = cursor.fetchone()

        if not user_record:
            # Try finding client by client_id or email
            cursor.execute(
                """
                SELECT u.*, c.id as client_db_id, c.client_id, c.company_name
                FROM users u
                JOIN clients c ON u.id = c.user_id
                WHERE c.client_id = %s OR u.email = %s
                """,
                (login_id, login_id)
            )
            user_record = cursor.fetchone()

        if not user_record:
            # Check users table directly (for candidates or admins who don't have employee/client records)
            cursor.execute("SELECT * FROM users WHERE email = %s", (login_id,))
            user_record = cursor.fetchone()

        if not user_record:
            return jsonify({"error": "Invalid credentials"}), 401

        if bcrypt.checkpw(password.encode("utf-8"), user_record["password"].encode("utf-8")):
            # Build payload
            payload = {
                "id": user_record["id"],
                "name": user_record["name"],
                "email": user_record["email"],
                "role": user_record["role"],
                "employee_id": user_record.get("employee_id"),
                "emp_db_id": user_record.get("emp_db_id"),
                "client_db_id": user_record.get("client_db_id"),
                "client_id": user_record.get("client_id"),
                "company_name": user_record.get("company_name")
            }
            token = serializer.dumps(payload)
            response = jsonify({
                "message": "Login successful",
                "token": token,
                "user": payload
            })
            response.set_cookie(
                "token",
                token,
                httponly=True,
                secure=os.getenv("FLASK_ENV") == "production",
                samesite="Lax",
                max_age=86400
            )
            return response, 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = jsonify({"message": "Logout successful"})
    response.delete_cookie("token")
    return response, 200


@auth_bp.route("/profile", methods=["GET", "PUT"])
def profile():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if request.method == "GET":
            if user["role"] == "employee":
                cursor.execute(
                    """
                    SELECT u.name, u.email, e.* 
                    FROM users u 
                    JOIN employees e ON e.user_id = u.id 
                    WHERE u.id = %s
                    """,
                    (user["id"],)
                )
                profile_data = cursor.fetchone()
                if profile_data and profile_data.get("date_of_joining"):
                    profile_data["date_of_joining"] = profile_data["date_of_joining"].isoformat()
            elif user["role"] == "client":
                cursor.execute(
                    """
                    SELECT u.name, u.email, c.* 
                    FROM users u 
                    JOIN clients c ON c.user_id = u.id 
                    WHERE u.id = %s
                    """,
                    (user["id"],)
                )
                profile_data = cursor.fetchone()
            else:
                cursor.execute("SELECT id, name, email, role FROM users WHERE id = %s", (user["id"],))
                profile_data = cursor.fetchone()
            
            return jsonify(profile_data), 200

        elif request.method == "PUT":
            data = request.json
            name = data.get("name")
            email = data.get("email")
            phone = data.get("phone_number")
            password = data.get("password")

            # Update User table
            if name or email:
                cursor.execute(
                    "UPDATE users SET name = COALESCE(%s, name), email = COALESCE(%s, email) WHERE id = %s",
                    (name, email, user["id"])
                )

            if password:
                hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, user["id"]))

            # Update Employee table
            if user["role"] == "employee" and phone:
                cursor.execute(
                    "UPDATE employees SET phone_number = %s WHERE user_id = %s",
                    (phone, user["id"])
                )

            # Update Client table
            if user["role"] == "client" and phone:
                cursor.execute(
                    "UPDATE clients SET phone_number = %s WHERE user_id = %s",
                    (phone, user["id"])
                )

            conn.commit()
            return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees", methods=["GET"])
@require_role(["admin"])
def list_employees():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT u.name, u.email, e.* 
            FROM employees e 
            JOIN users u ON e.user_id = u.id 
            ORDER BY e.employee_id
            """
        )
        employees = cursor.fetchall()
        for emp in employees:
            if emp.get("date_of_joining"):
                emp["date_of_joining"] = emp["date_of_joining"].isoformat()
        return jsonify(employees), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees", methods=["POST"])
@require_role(["admin"])
def add_employee():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")  # defaults to email username if empty
    employee_id = data.get("employee_id")
    phone = data.get("phone_number")
    department = data.get("department")
    designation = data.get("designation")
    date_of_joining = data.get("date_of_joining") or date.today().isoformat()
    status = data.get("status", "Active")

    if not name or not email or not employee_id or not department or not designation:
        return jsonify({"error": "Required fields are missing"}), 400

    if not password:
        password = email.split("@")[0] + "123"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email already exists in users"}), 400

        cursor.execute("SELECT id FROM employees WHERE employee_id = %s", (employee_id,))
        if cursor.fetchone():
            return jsonify({"error": "Employee ID already exists"}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'employee') RETURNING id",
            (name, email, hashed_password)
        )
        user_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO employees (user_id, employee_id, phone_number, department, designation, date_of_joining, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, employee_id, phone, department, designation, date_of_joining, status)
        )
        conn.commit()
        return jsonify({"message": f"Employee added successfully. Temporary password is '{password}'"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees/<int:emp_id>", methods=["PUT"])
@require_role(["admin"])
def update_employee(emp_id):
    data = request.json
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone_number")
    department = data.get("department")
    designation = data.get("designation")
    date_of_joining = data.get("date_of_joining")
    status = data.get("status")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        if name or email:
            cursor.execute(
                "UPDATE users SET name = COALESCE(%s, name), email = COALESCE(%s, email) WHERE id = %s",
                (name, email, user_id)
            )

        cursor.execute(
            """
            UPDATE employees 
            SET phone_number = %s, department = %s, designation = %s, date_of_joining = %s, status = %s 
            WHERE id = %s
            """,
            (phone, department, designation, date_of_joining, status, emp_id)
        )
        conn.commit()
        return jsonify({"message": "Employee updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees/<int:emp_id>", methods=["DELETE"])
@require_role(["admin"])
def delete_employee(emp_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        cursor.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({"message": "Employee record deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/announcements", methods=["GET"])
def get_announcements():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
        announcements = cursor.fetchall()
        for a in announcements:
            if a.get("created_at"):
                a["created_at"] = a["created_at"].isoformat()
        return jsonify(announcements), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/announcements", methods=["POST"])
@require_role(["admin"])
def create_announcement():
    data = request.json
    title = data.get("title")
    content = data.get("content")

    if not title or not content:
        return jsonify({"error": "Title and Content are required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO announcements (title, content) VALUES (%s, %s)",
            (title, content)
        )
        conn.commit()
        return jsonify({"message": "Announcement created successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today_date = date.today()
    try:
        if user["role"] == "admin":
            cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
            active_employees = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = %s AND status IN ('Present', 'Half Day')", (today_date,))
            present_today = cursor.fetchone()["count"]

            absent_today = max(0, active_employees - present_today)

            cursor.execute("SELECT COUNT(*) FROM leaves WHERE status = 'Pending'")
            pending_leaves = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'Open'")
            active_jobs = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM applications")
            total_applications = cursor.fetchone()["count"]

            stats = {
                "active_employees": active_employees,
                "present_today": present_today,
                "absent_today": absent_today,
                "pending_leaves": pending_leaves,
                "active_jobs": active_jobs,
                "total_applications": total_applications
            }
            return jsonify(stats), 200
        elif user["role"] == "employee":
            cursor.execute("SELECT * FROM employees WHERE id = %s", (user["emp_db_id"],))
            emp = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id = %s AND status = 'Present'", (user["emp_db_id"],))
            p_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id = %s AND status = 'Half Day'", (user["emp_db_id"],))
            h_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM leaves WHERE employee_id = %s AND status = 'Pending'", (user["emp_db_id"],))
            pending_leaves = cursor.fetchone()["count"]

            stats = {
                "casual_leave_balance": emp.get("casual_leave", 0) if emp else 0,
                "sick_leave_balance": emp.get("sick_leave", 0) if emp else 0,
                "earned_leave_balance": emp.get("earned_leave", 0) if emp else 0,
                "emergency_leave_balance": emp.get("emergency_leave", 0) if emp else 0,
                "attendance_present": p_count,
                "attendance_half_day": h_count,
                "pending_leaves": pending_leaves
            }
            return jsonify(stats), 200
        else:
            cursor.execute("SELECT COUNT(*) FROM applications WHERE email = %s", (user["email"],))
            total_apps = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM applications WHERE email = %s AND status = 'Shortlisted'", (user["email"],))
            shortlisted_apps = cursor.fetchone()["count"]

            stats = {
                "total_applications": total_apps,
                "shortlisted_applications": shortlisted_apps
            }
            return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/reports/<report_type>", methods=["GET"])
@require_role(["admin"])
def get_report(report_type):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if report_type == "attendance":
            cursor.execute(
                """
                SELECT a.date, a.status, COUNT(a.id) as count
                FROM attendance a
                GROUP BY a.date, a.status
                ORDER BY a.date DESC
                LIMIT 30
                """
            )
            data = cursor.fetchall()
            for r in data:
                if r.get("date"):
                    r["date"] = r["date"].isoformat()
            
        elif report_type == "employee":
            cursor.execute(
                """
                SELECT department, COUNT(id) as employee_count
                FROM employees
                WHERE status = 'Active'
                GROUP BY department
                ORDER BY employee_count DESC
                """
            )
            data = cursor.fetchall()
            
        elif report_type == "recruitment":
            cursor.execute(
                """
                SELECT status, COUNT(id) as application_count
                FROM applications
                GROUP BY status
                ORDER BY application_count DESC
                """
            )
            data = cursor.fetchall()
        else:
            return jsonify({"error": "Invalid report type"}), 400

        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/edutech")
def serve_edutech_redirect():
    return redirect("/edutech/")


@auth_bp.route("/edutech/")
@auth_bp.route("/edutech/<path:path>")
def serve_edutech(path="index.html"):
    if not path or path == "":
        path = "index.html"
    return send_from_directory(EDUTECH_DIR, path)


@auth_bp.route("/designations", methods=["GET"])
@require_role(["admin", "employee"])
def get_designations():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, name FROM designations ORDER BY name ASC")
        rows = cursor.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/designations", methods=["POST"])
@require_role(["admin"])
def create_designation():
    data = request.json
    name = data.get("name")
    if not name or name.strip() == "":
        return jsonify({"error": "Designation name is required"}), 400
    
    name = name.strip()
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("INSERT INTO designations (name) VALUES (%s) RETURNING id, name", (name,))
        new_row = cursor.fetchone()
        conn.commit()
        return jsonify(new_row), 201
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return jsonify({"error": "Designation already exists"}), 400
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

