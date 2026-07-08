"""
Authentication and Core Management Blueprint Routes.

Handles user signup/login sessions, user profiles, employee management (CRUD operations 
restricted to admins), dashboard statistics generation, system announcements, report data, 
designations lookup/creation, and serving the EduTech static portal.
"""

import os
import secrets
import string
import logging
import bcrypt
from datetime import datetime, date
from flask import Blueprint, request, jsonify, redirect, send_from_directory
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import (
    get_current_user, require_role, serializer, refresh_serializer,
    check_is_recruitment_manager, check_is_crm_manager, rate_limit,
    validate_email, validate_password_strength, blacklist_token,
    ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_MAX_AGE,
    record_failed_attempt, is_account_locked, reset_login_attempts,
    check_password_history, store_password_history,
    revoke_all_refresh_tokens, issue_refresh_token,
    validate_and_rotate_refresh_token,
    get_csrf_token, csrf_required, require_permission,
    get_permissions_for_role, seed_default_permissions,
    audit_log, get_audit_logs,
    BRUTE_FORCE_THRESHOLD, BRUTE_FORCE_WINDOW_MINUTES,
    PASSWORD_HISTORY_COUNT,
)
from ..config import Config, safe_error

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

# Absolute paths for serving EduTech portal static content
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EDUTECH_DIR = os.path.join(BASE_DIR, "edutech")

@auth_bp.route("/register", methods=["POST"])
@rate_limit(limit=5, period=60)
def register():
    """
    Registers a new candidate user in the system.

    Accepts registration details from JSON body, hashes the password using bcrypt,
    and inserts a record into the 'users' table with a default 'candidate' role.
    Rate limited to 5 registrations per minute per IP.

    JSON Parameters:
        name (str): The full name of the user.
        email (str): The email address (used as unique login credential).
        password (str): The plaintext password.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success message.
            - 400: If fields are missing or email is already registered.
            - 500: Database insertion or bcrypt hashing failure message.
    """
    data = request.json
    name = data.get("name", "").strip() if data.get("name") else ""
    email = data.get("email", "").strip() if data.get("email") else ""
    password = data.get("password", "")
    role = "candidate"  # Enforce candidate role for public registration
    portal = data.get("portal", "elevateiq").strip().lower()
    if portal not in ["elevateiq", "edutech"]:
        portal = "elevateiq"

    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if len(name) < 2 or len(name) > 100:
        return jsonify({"error": "Name must be between 2 and 100 characters long"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email address format"}), 400

    is_strong, pw_msg = validate_password_strength(password)
    if not is_strong:
        return jsonify({"error": pw_msg}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email already registered"}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, email, hashed_password, role, portal)
        )
        user_id = cursor.fetchone()[0]

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_verifications (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(128) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        import hashlib
        verify_token = secrets.token_urlsafe(64)
        verify_hash = hashlib.sha256(verify_token.encode()).hexdigest()
        cursor.execute(
            "INSERT INTO email_verifications (user_id, token, expires_at) VALUES (%s, %s, NOW() + INTERVAL '24 hours')",
            (user_id, verify_hash)
        )
        conn.commit()
        return jsonify({
            "message": "Registration successful",
            "verify_token": verify_token
        }), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/api/auth/verify-email", methods=["POST"])
def verify_email():
    data = request.json
    token = data.get("token") if data else None
    if not token:
        return jsonify({"error": "Verification token required"}), 400
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_verifications (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(128) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "SELECT user_id FROM email_verifications WHERE token = %s AND verified = FALSE AND expires_at > NOW()",
            (token_hash,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Invalid or expired verification token"}), 400
        user_id = row[0] if isinstance(row, dict) else row[0]
        cursor.execute("UPDATE email_verifications SET verified = TRUE WHERE token = %s", (token_hash,))
        cursor.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({"message": "Email verified successfully"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Email verification error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/login", methods=["POST"])
@rate_limit(limit=10, period=60)
def login():
    data = request.json
    login_id = data.get("email")
    password = data.get("password")

    if not login_id or not password:
        return jsonify({"error": "Email/Employee ID/Client ID and password are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        user_record = None
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
            cursor.execute("SELECT * FROM users WHERE email = %s", (login_id,))
            user_record = cursor.fetchone()

        if not user_record:
            return jsonify({"error": "Invalid email or password"}), 401

        user_id = user_record["id"]

        locked, locked_until = is_account_locked(user_id)
        if locked:
            remaining = int((locked_until - datetime.now()).total_seconds()) if locked_until else BRUTE_FORCE_WINDOW_MINUTES * 60
            return jsonify({
                "error": f"Account locked due to too many failed login attempts. Try again in {max(60, remaining)} seconds."
            }), 429

        if bcrypt.checkpw(password.encode("utf-8"), user_record["password"].encode("utf-8")):
            reset_login_attempts(user_id)
            requested_portal = data.get("portal", "elevateiq")
            user_portal = user_record.get("portal") or "elevateiq"
            
            if user_portal != "both" and user_portal != requested_portal:
                return jsonify({"error": "Unauthorized portal access"}), 403

            payload = {
                "id": user_id,
                "name": user_record["name"],
                "email": user_record["email"],
                "role": user_record["role"],
                "employee_id": user_record.get("employee_id"),
                "emp_db_id": user_record.get("emp_db_id"),
                "client_db_id": user_record.get("client_db_id"),
            }
            token = serializer.dumps(payload)
            refresh_token = issue_refresh_token(user_id)
            csrf_token = get_csrf_token(user_id)
            response = jsonify({
                "message": "Login successful",
                "token": token,
                "refresh_token": refresh_token,
                "csrf_token": csrf_token,
                "user": payload
            })
            is_secure = os.getenv("FLASK_ENV") == "production" or request.is_secure
            response.set_cookie(
                "token", token,
                httponly=True, secure=is_secure,
                samesite="Strict", max_age=ACCESS_TOKEN_MAX_AGE
            )
            response.set_cookie(
                "refresh_token", refresh_token,
                httponly=True, secure=is_secure,
                samesite="Strict", path="/api/auth/refresh",
                max_age=REFRESH_TOKEN_MAX_AGE
            )
            seed_default_permissions()
            return response, 200
        else:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
            record_failed_attempt(user_id, ip)
            return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/api/auth/refresh", methods=["POST"])
@rate_limit(limit=5, period=60)
def refresh_token():
    refresh_token_str = None
    auth_header = request.headers.get("X-Refresh-Token")
    if auth_header:
        refresh_token_str = auth_header
    if not refresh_token_str:
        refresh_token_str = request.cookies.get("refresh_token")
    if not refresh_token_str:
        return jsonify({"error": "Refresh token required"}), 401

    user_id, new_refresh = validate_and_rotate_refresh_token(refresh_token_str)
    if not user_id:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_record = cursor.fetchone()
        if not user_record:
            return jsonify({"error": "User not found"}), 404

        payload = {
            "id": user_record["id"],
            "name": user_record["name"],
            "email": user_record["email"],
            "role": user_record["role"],
        }
        new_access = serializer.dumps(payload)
        csrf_token = get_csrf_token(user_id)
        response = jsonify({
            "message": "Token refreshed",
            "token": new_access,
            "refresh_token": new_refresh,
            "csrf_token": csrf_token,
            "user": payload
        })
        is_secure = os.getenv("FLASK_ENV") == "production" or request.is_secure
        response.set_cookie("token", new_access, httponly=True, secure=is_secure, samesite="Strict", max_age=ACCESS_TOKEN_MAX_AGE)
        response.set_cookie("refresh_token", new_refresh, httponly=True, secure=is_secure, samesite="Strict", path="/api/auth/refresh", max_age=REFRESH_TOKEN_MAX_AGE)
        return response, 200
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()

@auth_bp.route("/api/auth/csrf-token", methods=["GET"])
def get_csrf():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_csrf_token(user["id"])
    if not token:
        return jsonify(safe_error()), 500
    return jsonify({"csrf_token": token}), 200

@auth_bp.route("/api/auth/permissions", methods=["GET"])
def get_my_permissions():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    perms = get_permissions_for_role(user.get("role", ""))
    return jsonify({"permissions": list(perms)}), 200

@auth_bp.route("/api/audit-logs", methods=["GET"])
@require_role(["admin"])
def audit_logs():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    logs = get_audit_logs(limit=limit, offset=offset)
    return jsonify(logs), 200

@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("token")
    if token:
        blacklist_token(token)
    user = get_current_user()
    if user:
        revoke_all_refresh_tokens(user["id"])
    response = jsonify({"message": "Logout successful"})
    response.delete_cookie("token")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return response, 200


@auth_bp.route("/profile", methods=["GET", "PUT"])
def profile():
    """
    Retrieves or updates the currently logged-in user's profile details.

    GET: Returns specific details depending on the user's role (employee, client, admin/candidate).
    PUT: Updates editable user fields (name, email, password, phone_number).

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Profile details or profile update success message.
            - 401: Unauthorized if token is missing or invalid.
            - 500: Database operation errors.
    """
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
                # Serialize Python date objects to ISO string representation
                if profile_data:
                    if profile_data.get("date_of_joining"):
                        profile_data["date_of_joining"] = profile_data["date_of_joining"].isoformat()
                    if profile_data.get("salary") is not None:
                        profile_data["salary"] = float(profile_data["salary"])
                    else:
                        profile_data["salary"] = 35000.00
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
            current_password = data.get("current_password")

            if name or email:
                cursor.execute(
                    "UPDATE users SET name = COALESCE(%s, name), email = COALESCE(%s, email) WHERE id = %s",
                    (name, email, user["id"])
                )

            if password:
                if not current_password:
                    return jsonify({"error": "Current password is required to set a new password"}), 400
                cursor.execute("SELECT password FROM users WHERE id = %s", (user["id"],))
                stored = cursor.fetchone()
                if not stored or not bcrypt.checkpw(current_password.encode("utf-8"), stored["password"].encode("utf-8")):
                    return jsonify({"error": "Current password is incorrect"}), 403
                is_strong, pw_msg = validate_password_strength(password)
                if not is_strong:
                    return jsonify({"error": pw_msg}), 400
                hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                if not check_password_history(user["id"], hashed):
                    return jsonify({"error": f"Password has been used recently. Choose a different password."}), 400
                store_password_history(user["id"], hashed)
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, user["id"]))
                revoke_all_refresh_tokens(user["id"])

            if user["role"] == "employee" and phone:
                cursor.execute(
                    "UPDATE employees SET phone_number = %s WHERE user_id = %s",
                    (phone, user["id"])
                )

            if user["role"] == "client" and phone:
                cursor.execute(
                    "UPDATE clients SET phone_number = %s WHERE user_id = %s",
                    (phone, user["id"])
                )

            conn.commit()
            return jsonify({"message": "Profile updated successfully"}), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"Profile update error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees", methods=["GET"])
@require_role(["admin"])
def list_employees():
    """
    Lists all employees registered in the system.
    Restricted to admin users.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: List of employees with details (dates formatted as ISO format).
            - 401/403: Security errors.
            - 500: SQL query issues.
    """
    portal = request.args.get("portal")
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if portal:
            cursor.execute(
                """
                SELECT u.name, u.email, e.* 
                FROM employees e 
                JOIN users u ON e.user_id = u.id 
                WHERE u.portal = %s
                ORDER BY e.employee_id
                """,
                (portal,)
            )
        else:
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
            if emp.get("salary") is not None:
                emp["salary"] = float(emp["salary"])
            else:
                emp["salary"] = 35000.00
        return jsonify(employees), 200
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees", methods=["POST"])
@require_role(["admin"])
def add_employee():
    """
    Registers a new employee. Creates both a 'users' record and an 'employees' profile.
    Restricted to admin users.

    JSON Parameters:
        name (str): Full name of the employee.
        email (str): Unique email address.
        employee_id (str): Unique corporate employee identifier.
        department (str): Corporate department.
        designation (str): Work designation.
        password (str, optional): Account password. Defaults to '<email_username>123'.
        phone_number (str, optional): Phone number.
        date_of_joining (str, optional): ISO date string. Defaults to today's date.
        status (str, optional): Status field. Defaults to 'Active'.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success message and temporary password.
            - 400: Missing required parameters or conflicts on email/employee_id.
            - 500: Database insertion exceptions.
    """
    data = request.json
    name = data.get("name", "").strip() if data.get("name") else ""
    email = data.get("email", "").strip() if data.get("email") else ""
    password = data.get("password")  # defaults to auto-generated if empty
    employee_id = data.get("employee_id")
    if employee_id:
        employee_id = employee_id.strip().upper()
    phone = data.get("phone_number")
    department = data.get("department")
    designation = data.get("designation")
    date_of_joining = data.get("date_of_joining") or date.today().isoformat()
    status = data.get("status", "Active")

    if not name or not email or not employee_id or not department or not designation:
        return jsonify({"error": "Required fields are missing"}), 400

    if len(name) < 2 or len(name) > 100:
        return jsonify({"error": "Name must be between 2 and 100 characters long"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email address format"}), 400

    if not password:
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        password += secrets.choice("!@#$%&*")
    else:
        is_strong, pw_msg = validate_password_strength(password)
        if not is_strong:
            return jsonify({"error": pw_msg}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check email availability
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Email already exists in users"}), 400

        # Check employee ID availability (case-insensitive)
        cursor.execute("SELECT id FROM employees WHERE UPPER(employee_id) = UPPER(%s)", (employee_id,))
        if cursor.fetchone():
            return jsonify({"error": "Employee ID already exists"}), 400

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # Insert user login credentials
        salary = data.get("salary", 35000.00)
        if salary is not None:
            try:
                salary = float(salary)
            except ValueError:
                return jsonify({"error": "Invalid salary amount format"}), 400

        # Insert user login credentials
        portal = data.get("portal", "elevateiq")
        cursor.execute(
            "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, 'employee', %s) RETURNING id",
            (name, email, hashed_password, portal)
        )
        user_id = cursor.fetchone()[0]

        # Check if the salary column exists in the database
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='employees' AND column_name='salary'
            );
            """
        )
        has_salary = cursor.fetchone()[0]

        # Insert detailed employee metadata
        if has_salary:
            cursor.execute(
                """
                INSERT INTO employees (user_id, employee_id, phone_number, department, designation, date_of_joining, status, salary) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, employee_id, phone, department, designation, date_of_joining, status, salary)
            )
        else:
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees/<int:emp_id>", methods=["PUT"])
@require_role(["admin"])
def update_employee(emp_id):
    """
    Updates employee details in both employees and users tables.
    Restricted to admin users.

    Args:
        emp_id (int): DB primary key ID of the employee to update.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success update message.
            - 400: Email already in use by another account.
            - 404: Employee record not found.
            - 500: Database execution errors.
    """
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
        # Retrieve mapped user ID to update users credentials table
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        # Prevent duplicate email assignments across different accounts
        if email:
            cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
            if cursor.fetchone():
                return jsonify({"error": "Email is already taken by another user"}), 400

        # Update core user credentials
        if name or email:
            cursor.execute(
                "UPDATE users SET name = COALESCE(%s, name), email = COALESCE(%s, email) WHERE id = %s",
                (name, email, user_id)
            )

        salary = data.get("salary")
        if salary is not None:
            try:
                salary = float(salary)
            except ValueError:
                return jsonify({"error": "Invalid salary amount format"}), 400

        # Check if the salary column exists in the database
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='employees' AND column_name='salary'
            );
            """
        )
        has_salary = cursor.fetchone()[0]

        # Update employee information
        if has_salary:
            cursor.execute(
                """
                UPDATE employees 
                SET phone_number = %s, department = %s, designation = %s, date_of_joining = %s, status = %s, salary = COALESCE(%s, salary) 
                WHERE id = %s
                """,
                (phone, department, designation, date_of_joining, status, salary, emp_id)
            )
        else:
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/employees/<int:emp_id>", methods=["DELETE"])
@require_role(["admin"])
def delete_employee(emp_id):
    """
    Permanently deletes employee record and corresponding login user account.
    Restricted to admin users.

    Args:
        emp_id (int): DB primary key ID of the employee to delete.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success deletion message.
            - 404: Employee record not found.
            - 500: Database constraints or SQL exceptions.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check existence and map user_id
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        # Delete employee details and credentials
        cursor.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({"message": "Employee record deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/announcements", methods=["GET"])
def get_announcements():
    """
    Fetches all system announcements sorted chronologically by creation timestamp.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: List of announcement items.
            - 500: SQL query issues.
    """
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/announcements", methods=["POST"])
@require_role(["admin"])
def create_announcement():
    """
    Posts a new announcement block.
    Restricted to admin users.

    JSON Parameters:
        title (str): Title of the announcement.
        content (str): Content body of the announcement.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success creation message.
            - 400: Missing title or content.
            - 500: Database insertion exceptions.
    """
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    """
    Generates statistics for the dashboard panels adjusted for the current user's role.

    - Admins: Counts active employees, attendance counts today, pending leaves, and active job/app counts.
    - Employees: Retrieves leave category balances, personal attendance records, and pending leave counts.
    - Candidates: Counts submitted applications and current shortlisted applications.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Dictionary of metrics customized for the requestor's role.
            - 401: Unauthorized access.
            - 500: Aggregation query errors.
    """
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
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id = %s AND status = 'Present'", (user["emp_db_id"],))
            p_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE employee_id = %s AND status = 'Half Day'", (user["emp_db_id"],))
            h_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) FROM leaves WHERE employee_id = %s AND status = 'Pending'", (user["emp_db_id"],))
            pending_leaves = cursor.fetchone()["count"]

            # Calculate total leaves approved (in days)
            cursor.execute("SELECT COALESCE(SUM(end_date - start_date + 1), 0) AS total_leaves FROM leaves WHERE employee_id = %s AND status = 'Approved'", (user["emp_db_id"],))
            total_leaves = cursor.fetchone()["total_leaves"]

            stats = {
                "total_present_days": p_count + h_count,
                "total_leaves": total_leaves,
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/reports/<report_type>", methods=["GET"])
@require_role(["admin"])
def get_report(report_type):
    """
    Returns aggregated metrics for administrative chart visualizers.
    Restricted to admin users.

    - attendance: Grouped count of attendance statuses over the last 30 days.
    - employee: Count of active employees per department.
    - recruitment: Grouped count of applications by current workflow status.

    Args:
        report_type (str): Type of report dataset ('attendance', 'employee', 'recruitment').

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of aggregated report objects.
            - 400: If report_type matches none of the available reports.
            - 500: Database aggregate query issues.
    """
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
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/reports/details/<report_type>", methods=["GET"])
@require_role(["admin"])
def get_report_details(report_type):
    """
    Returns detailed lists of employees or candidates contributing to a report metric.
    Restricted to admin users.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if report_type == "attendance":
            date_val = request.args.get("date")
            status_val = request.args.get("status")
            if not date_val or not status_val:
                return jsonify({"error": "Parameters 'date' and 'status' are required"}), 400
            cursor.execute(
                """
                SELECT e.employee_id, u.name, e.department, e.designation, 
                       a.check_in, a.check_out, a.working_hours
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                JOIN users u ON e.user_id = u.id
                WHERE a.date = %s AND UPPER(a.status) = UPPER(%s)
                ORDER BY u.name
                """,
                (date_val, status_val)
            )
            rows = cursor.fetchall()
            for r in rows:
                if r.get("check_in"):
                    r["check_in"] = r["check_in"].strftime("%H:%M:%S") if hasattr(r["check_in"], "strftime") else str(r["check_in"])
                if r.get("check_out"):
                    r["check_out"] = r["check_out"].strftime("%H:%M:%S") if hasattr(r["check_out"], "strftime") else str(r["check_out"])
                if r.get("working_hours") is not None:
                    r["working_hours"] = float(r["working_hours"])
            return jsonify(rows), 200

        elif report_type == "employee":
            dept_val = request.args.get("department")
            if not dept_val:
                return jsonify({"error": "Parameter 'department' is required"}), 400
            cursor.execute(
                """
                SELECT e.employee_id, u.name, e.designation, e.phone_number, e.status
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE e.department = %s AND e.status = 'Active'
                ORDER BY u.name
                """,
                (dept_val,)
            )
            rows = cursor.fetchall()
            return jsonify(rows), 200

        elif report_type == "recruitment":
            status_val = request.args.get("status")
            if not status_val:
                return jsonify({"error": "Parameter 'status' is required"}), 400
            cursor.execute(
                """
                SELECT a.candidate_name, a.email, a.phone, j.title as job_title, 
                       j.department, a.applied_at
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                WHERE a.status = %s
                ORDER BY a.applied_at DESC
                """,
                (status_val,)
            )
            rows = cursor.fetchall()
            for r in rows:
                if r.get("applied_at"):
                    r["applied_at"] = r["applied_at"].isoformat()
            return jsonify(rows), 200

        else:
            return jsonify({"error": "Invalid report details type"}), 400
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/edutech")
def serve_edutech_redirect():
    """
    Redirects bare edutech routes to have trailing slash to ensure path integrity.

    Returns:
        Response: Redirection mapping client to /edutech/.
    """
    return redirect("/edutech/")


@auth_bp.route("/edutech/")
@auth_bp.route("/edutech/<path:path>")
def serve_edutech(path="index.html"):
    """
    Serves static portal assets for the EduTech sub-portal.

    Args:
        path (str): File path relative to edutech directory. Defaults to 'index.html'.

    Returns:
        Response: The file from directory.
    """
    if not path or path == "":
        path = "index.html"
    return send_from_directory(EDUTECH_DIR, path)


@auth_bp.route("/designations", methods=["GET"])
@require_role(["admin", "employee"])
def get_designations():
    """
    Lists designations registered in the designations lookup table.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Sorted designations listing.
            - 500: Database lookup errors.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id, name FROM designations ORDER BY name ASC")
        rows = cursor.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@auth_bp.route("/designations", methods=["POST"])
@require_role(["admin"])
def create_designation():
    """
    Registers a new unique designation name.
    Restricted to admin users.

    JSON Parameters:
        name (str): The label of the new designation.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Newly created designation entity.
            - 400: If parameters are empty or the designation already exists.
            - 500: DB transaction or insert failure.
    """
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
        # Safely parse database unique violation errors to return clean API messages
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return jsonify({"error": "Designation already exists"}), 400
        logger.error(f"API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


