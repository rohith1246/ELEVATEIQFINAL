from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os
import queue
import json
from datetime import datetime, date, time
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__, static_url_path="", static_folder=".")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# Session Serializer
SECRET_KEY = os.getenv("SECRET_KEY", "elevate_iq_secret_key")
serializer = URLSafeSerializer(SECRET_KEY)

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

# Resume Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'resumes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# --- Helper Functions ---
def get_current_user():
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None
    try:
        data = serializer.loads(token)
        return data  # dict containing id, email, role, name, employee_id
    except BadSignature:
        return None

def require_role(roles):
    def decorator(f):
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# --- Auth Routes ---

@app.route("/register", methods=["POST"])
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


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    login_id = data.get("email")  # can be email, Employee ID, or Client ID
    password = data.get("password")

    if not login_id or not password:
        return jsonify({"error": "Email/Employee ID/Client ID and password are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        user = None
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
        user = cursor.fetchone()

        if not user:
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
            user = cursor.fetchone()

        if not user:
            # Check users table directly (for candidates or admins who don't have employee/client records)
            cursor.execute("SELECT * FROM users WHERE email = %s", (login_id,))
            user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            # Build payload
            payload = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "employee_id": user.get("employee_id"),
                "emp_db_id": user.get("emp_db_id"),
                "client_db_id": user.get("client_db_id"),
                "client_id": user.get("client_id"),
                "company_name": user.get("company_name")
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


@app.route("/logout", methods=["POST"])
def logout():
    response = jsonify({"message": "Logout successful"})
    response.delete_cookie("token")
    return response, 200


# --- Announcements Routes ---

@app.route("/announcements", methods=["GET"])
def get_announcements():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
        announcements = cursor.fetchall()
        return jsonify(announcements), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/announcements", methods=["POST"])
def create_announcement():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

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


# --- Employee Management CRUD ---

@app.route("/employees", methods=["GET"])
def list_employees():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

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
        # Convert date objects to ISO strings for json serialization
        for emp in employees:
            if emp.get("date_of_joining"):
                emp["date_of_joining"] = emp["date_of_joining"].isoformat()
        return jsonify(employees), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/employees", methods=["POST"])
def add_employee():
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

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
        # Create User
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

        # Create Employee profile
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


@app.route("/employees/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

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
        # Get user_id from employees record
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        # Update User details
        if name or email:
            cursor.execute(
                "UPDATE users SET name = COALESCE(%s, name), email = COALESCE(%s, email) WHERE id = %s",
                (name, email, user_id)
            )

        # Update Employee details
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


@app.route("/employees/<int:emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (emp_id,))
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "Employee not found"}), 404
        user_id = record[0]

        # Delete from employees (cascades or drops)
        cursor.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        # Delete from users
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return jsonify({"message": "Employee record deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# --- Profile Management (Employee self-update) ---

@app.route("/profile", methods=["GET", "PUT"])
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


# --- Attendance Management ---

@app.route("/attendance", methods=["GET"])
def get_attendance():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user["role"] == "admin":
            # Admin sees all attendance records
            cursor.execute(
                """
                SELECT a.*, e.employee_id, u.name, e.department, e.designation 
                FROM attendance a 
                JOIN employees e ON a.employee_id = e.id 
                JOIN users u ON e.user_id = u.id 
                ORDER BY a.date DESC, a.check_in DESC
                """
            )
            records = cursor.fetchall()
        else:
            # Employee sees their own attendance
            cursor.execute(
                """
                SELECT a.* 
                FROM attendance a 
                JOIN employees e ON a.employee_id = e.id 
                WHERE e.user_id = %s 
                ORDER BY a.date DESC
                """,
                (user["id"],)
            )
            records = cursor.fetchall()

        # Format dates/times
        for rec in records:
            if rec.get("date"):
                rec["date"] = rec["date"].isoformat()
            if rec.get("check_in"):
                rec["check_in"] = rec["check_in"].strftime("%H:%M:%S")
            if rec.get("check_out"):
                rec["check_out"] = rec["check_out"].strftime("%H:%M:%S")
            if rec.get("working_hours"):
                rec["working_hours"] = float(rec["working_hours"])

        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/attendance/checkin", methods=["POST"])
def check_in():
    user = get_current_user()
    if not user or user["role"] != "employee":
        return jsonify({"error": "Forbidden: Only employees can mark attendance"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    today_date = date.today()
    current_time = datetime.now().time().strftime("%H:%M:%S")
    
    try:
        # Check if checked in today already
        cursor.execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND date = %s",
            (user["emp_db_id"], today_date)
        )
        if cursor.fetchone():
            return jsonify({"error": "Already checked in today"}), 400

        cursor.execute(
            "INSERT INTO attendance (employee_id, date, check_in, status) VALUES (%s, %s, %s, 'Present')",
            (user["emp_db_id"], today_date, current_time)
        )
        conn.commit()
        return jsonify({"message": f"Checked in successfully at {current_time}"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/attendance/checkout", methods=["POST"])
def check_out():
    user = get_current_user()
    if not user or user["role"] != "employee":
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today_date = date.today()
    current_time_str = datetime.now().time().strftime("%H:%M:%S")
    current_time = datetime.now().time()

    try:
        cursor.execute(
            "SELECT * FROM attendance WHERE employee_id = %s AND date = %s",
            (user["emp_db_id"], today_date)
        )
        record = cursor.fetchone()
        if not record:
            return jsonify({"error": "You must check in first before checking out"}), 400
        if record.get("check_out"):
            return jsonify({"error": "Already checked out today"}), 400

        check_in_time = record["check_in"]
        
        # Calculate working hours
        dt_in = datetime.combine(date.min, check_in_time)
        dt_out = datetime.combine(date.min, current_time)
        delta = dt_out - dt_in
        working_hours = max(0.0, delta.total_seconds() / 3600.0)

        # Determine attendance status
        status = 'Present'
        if working_hours >= 8.0:
            status = 'Present'
        elif working_hours >= 4.0:
            status = 'Half Day'
        else:
            status = 'Absent'

        cursor.execute(
            """
            UPDATE attendance 
            SET check_out = %s, working_hours = %s, status = %s 
            WHERE id = %s
            """,
            (current_time_str, working_hours, status, record["id"])
        )
        conn.commit()
        return jsonify({"message": f"Checked out successfully at {current_time_str}. Total hours: {working_hours:.2f} ({status})"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# --- Leave Management ---

@app.route("/leaves", methods=["GET"])
def get_leaves():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        scope = request.args.get("scope")
        is_approver = False
        if user["role"] == "admin":
            is_approver = True
        else:
            # Check designation for employee
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = (res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")
                designation = designation.lower()
                if "team leader" in designation or "lead" in designation or "hr" in designation or "human resource" in designation:
                    is_approver = True

        if (scope == "all" and is_approver) or user["role"] == "admin":
            # Admin/Approver sees all leave requests
            cursor.execute(
                """
                SELECT l.*, e.employee_id, u.name, e.department, e.designation,
                       e.casual_leave, e.sick_leave, e.earned_leave, e.emergency_leave
                FROM leaves l
                JOIN employees e ON l.employee_id = e.id
                JOIN users u ON e.user_id = u.id
                ORDER BY l.status DESC, l.created_at DESC
                """
            )
        else:
            # Employee sees their own leave requests
            cursor.execute(
                "SELECT * FROM leaves WHERE employee_id = %s ORDER BY created_at DESC",
                (user["emp_db_id"],)
            )
        records = cursor.fetchall()
        for rec in records:
            if rec.get("start_date"):
                rec["start_date"] = rec["start_date"].isoformat()
            if rec.get("end_date"):
                rec["end_date"] = rec["end_date"].isoformat()
            if rec.get("created_at"):
                rec["created_at"] = rec["created_at"].isoformat()

        return jsonify(records), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/leaves", methods=["POST"])
def apply_leave():
    user = get_current_user()
    if not user or user["role"] != "employee":
        return jsonify({"error": "Forbidden"}), 403

    data = request.json
    leave_type = data.get("leave_type")  # Casual, Sick, Earned, Emergency
    start_date_str = data.get("start_date")
    end_date_str = data.get("end_date")
    reason = data.get("reason")

    if not leave_type or not start_date_str or not end_date_str:
        return jsonify({"error": "Required fields are missing"}), 400

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    if start_date > end_date:
        return jsonify({"error": "Start date must be before end date"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check leave balance
        cursor.execute("SELECT * FROM employees WHERE id = %s", (user["emp_db_id"],))
        emp = cursor.fetchone()

        leave_days = (end_date - start_date).days + 1
        balance_col = f"{leave_type.lower()}_leave"
        balance = emp.get(balance_col, 0)

        if balance < leave_days:
            return jsonify({"error": f"Insufficient leave balance. Requested {leave_days} days of {leave_type} leave, but only {balance} days remaining."}), 400

        cursor.execute(
            """
            INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status) 
            VALUES (%s, %s, %s, %s, %s, 'Pending')
            """,
            (user["emp_db_id"], leave_type, start_date, end_date, reason)
        )
        conn.commit()
        return jsonify({"message": "Leave application submitted successfully."}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/leaves/<int:leave_id>", methods=["PUT"])
def review_leave(leave_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_approver = False
        if user["role"] == "admin":
            is_approver = True
        else:
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = (res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")
                designation = designation.lower()
                if "team leader" in designation or "lead" in designation or "hr" in designation or "human resource" in designation:
                    is_approver = True

        if not is_approver:
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        action = data.get("status")  # Approved or Rejected

        if action not in ["Approved", "Rejected"]:
            return jsonify({"error": "Status must be Approved or Rejected"}), 400

        # Get leave details
        cursor.execute("SELECT * FROM leaves WHERE id = %s", (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify({"error": "Leave request not found"}), 404

        if leave["status"] != "Pending":
            return jsonify({"error": "Leave request has already been processed"}), 400

        emp_id = leave["employee_id"]
        leave_days = (leave["end_date"] - leave["start_date"]).days + 1
        leave_type = leave["leave_type"]

        if action == "Approved":
            # Deduct balance
            balance_col = f"{leave_type.lower()}_leave"
            cursor.execute(f"SELECT {balance_col} FROM employees WHERE id = %s", (emp_id,))
            balance = cursor.fetchone()[balance_col]

            if balance < leave_days:
                # If balance became insufficient somehow, mark as rejected or return error
                return jsonify({"error": "Employee does not have enough leave balance to approve."}), 400

            cursor.execute(
                f"UPDATE employees SET {balance_col} = {balance_col} - %s WHERE id = %s",
                (leave_days, emp_id)
            )

            # Insert attendance record as 'Leave' for the duration
            # Helper to mark days
            curr = leave["start_date"]
            while curr <= leave["end_date"]:
                # Attempt to insert, ignore if check_in exists or overwrite status
                cursor.execute(
                    """
                    INSERT INTO attendance (employee_id, date, status, check_in, check_out, working_hours) 
                    VALUES (%s, %s, 'Leave', '09:00:00', '17:00:00', 8.0)
                    ON CONFLICT (employee_id, date) DO UPDATE SET status = 'Leave'
                    """,
                    (emp_id, curr)
                )
                curr = datetime.fromordinal(curr.toordinal() + 1).date()

        cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (action, leave_id))
        conn.commit()
        return jsonify({"message": f"Leave request status updated to '{action}'"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# --- Recruitment (Jobs) ---

@app.route("/jobs", methods=["GET"])
def get_jobs():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # If admin, fetch all, otherwise only Open
        user = get_current_user()
        if user and user.get("role") == "admin":
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM jobs WHERE status = 'Open' ORDER BY created_at DESC")
        
        jobs = cursor.fetchall()
        for job in jobs:
            if job.get("created_at"):
                job["created_at"] = job["created_at"].isoformat()
        return jsonify(jobs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/jobs", methods=["POST"])
def create_job():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not check_is_recruitment_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        title = data.get("title")
        department = data.get("department")
        experience = data.get("experience_required")
        skills = data.get("skills_required")
        location = data.get("location")
        salary = data.get("salary_range")
        description = data.get("description")

        if not title or not department:
            return jsonify({"error": "Title and Department are required"}), 400

        cursor.execute(
            """
            INSERT INTO jobs (title, department, experience_required, skills_required, location, salary_range, description, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Open')
            """,
            (title, department, experience, skills, location, salary, description)
        )
        conn.commit()
        return jsonify({"message": "Job posting created successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not check_is_recruitment_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        status = data.get("status")  # 'Open' or 'Closed'

        if status not in ["Open", "Closed"]:
            return jsonify({"error": "Status must be Open or Closed"}), 400

        cursor.execute("UPDATE jobs SET status = %s WHERE id = %s", (status, job_id))
        conn.commit()
        return jsonify({"message": "Job status updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# --- Candidate Applications ---

@app.route("/applications", methods=["GET"])
def get_applications():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if check_is_recruitment_manager(user, cursor):
            cursor.execute(
                """
                SELECT a.*, j.title as job_title, j.department as job_department 
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                ORDER BY a.applied_at DESC
                """
            )
            apps = cursor.fetchall()
        else:
            # Candidate views their applications matched by email
            cursor.execute(
                """
                SELECT a.*, j.title as job_title, j.department as job_department 
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                WHERE a.email = %s
                ORDER BY a.applied_at DESC
                """,
                (user["email"],)
            )
            apps = cursor.fetchall()

        for ap in apps:
            if ap.get("applied_at"):
                ap["applied_at"] = ap["applied_at"].isoformat()
        return jsonify(apps), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/applications", methods=["POST"])
def submit_application():
    job_id = request.form.get("job_id")
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    file = request.files.get("resume")

    if not job_id or not name or not email or not file:
        return jsonify({"error": "Missing required application parameters"}), 400

    # Clean file and save
    filename = secure_filename(f"{int(datetime.now().timestamp())}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO applications (job_id, candidate_name, email, phone, resume_filename, status) 
            VALUES (%s, %s, %s, %s, %s, 'Pending')
            """,
            (job_id, name, email, phone, filename)
        )
        conn.commit()
        return jsonify({"message": "Application submitted successfully."}), 201
    except Exception as e:
        conn.rollback()
        # Clean file on DB failure
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/applications/<int:app_id>", methods=["PUT"])
def update_application_status(app_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not check_is_recruitment_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        data = request.json or {}
        status = data.get("status")
        if status not in ['Pending', 'Shortlisted', 'Accepted', 'Rejected']:
            return jsonify({"error": "Invalid application status"}), 400
        cursor.execute("UPDATE applications SET status = %s WHERE id = %s", (status, app_id))
        conn.commit()
        return jsonify({"message": f"Application status updated to '{status}'"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/uploads/resumes/<filename>")
def download_resume(filename):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not check_is_recruitment_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    finally:
        cursor.close()
        conn.close()


# --- Reports & Dashboard Analytics ---

@app.route("/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    today_date = date.today()
    try:
        if user["role"] == "admin":
            # Counts
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
            # Get employee's own stats
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
            # Candidate
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


@app.route("/reports/<report_type>", methods=["GET"])
def get_report(report_type):
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

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


# --- Chat & Groups System ---

@app.route("/chat/stream")
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

def check_is_team_leader(user, cursor):
    if not user:
        return False
    if user.get("role") in ["admin", "team_leader"]:
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "team leader" in designation or "lead" in designation:
            return True
    return False

@app.route("/chat/user-details", methods=["GET"])
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

@app.route("/chat/users", methods=["GET"])
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

@app.route("/chat/conversations", methods=["POST"])
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

@app.route("/chat/conversations", methods=["GET"])
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

@app.route("/chat/conversations/<int:conv_id>/messages", methods=["GET"])
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

@app.route("/chat/conversations/<int:conv_id>/messages", methods=["POST"])
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

@app.route("/chat/conversations/<int:conv_id>/read", methods=["POST"])
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

@app.route("/chat/admin/all", methods=["GET"])
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

@app.route("/chat/team-leader/groups", methods=["GET"])
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

@app.route("/chat/groups/<int:conv_id>/members", methods=["POST"])
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


# --- EduTech Routes & APIs ---
@app.route("/edutech")
def serve_edutech_redirect():
    from flask import redirect
    return redirect("/edutech/")

@app.route("/edutech/")
@app.route("/edutech/<path:path>")
def serve_edutech(path="index.html"):
    return send_from_directory("edutech", path)

@app.route('/api/contact', methods=['POST'])
def save_contact():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    track = data.get('track', '').strip()
    message = data.get('message', '').strip()
    
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

@app.route('/api/newsletter', methods=['POST'])
def save_newsletter():
    data = request.json
    if not data or 'email' not in data:
        return jsonify({"success": False, "error": "Email is required"}), 400
        
    email = data.get('email', '').strip()
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


@app.route('/api/elevate-contact', methods=['POST'])
def save_elevate_contact():
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400
        
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    message = data.get('message', '').strip()
    
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


@app.route('/admin/contacts/edutech', methods=['GET'])
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

@app.route('/admin/contacts/elevate', methods=['GET'])
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


@app.route('/dashboard/meetings', methods=['POST'])
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
            
        title = data.get('title', '').strip()
        platform = data.get('platform', '').strip()
        meeting_link = data.get('meeting_link', '').strip()
        scheduled_at = data.get('scheduled_at', '').strip()
        meeting_type = data.get('meeting_type', 'internal').strip()
        client_id = data.get('client_id')

        if not title or not platform or not meeting_link or not scheduled_at:
            return jsonify({"error": "All fields are required"}), 400
            
        if not client_id or client_id == "":
            client_id = None
        else:
            client_id = int(client_id)

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

@app.route('/dashboard/meetings', methods=['GET'])
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


def check_is_crm_manager(user, cursor):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "team leader" in designation or "lead" in designation or "hr" in designation or "human resource" in designation:
            return True
    return False

def check_is_recruitment_manager(user, cursor):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "hr" in designation or "human resource" in designation:
            return True
    return False

@app.route("/crm/clients", methods=["GET"])
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

@app.route("/crm/clients", methods=["POST"])
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

@app.route("/crm/clients/<int:client_id>", methods=["PUT"])
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

@app.route("/crm/clients/<int:client_id>/provision", methods=["POST"])
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

@app.route("/crm/clients/<int:client_id>/interactions", methods=["GET"])
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

@app.route("/crm/interactions", methods=["POST"])
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_debug = os.getenv("FLASK_ENV") != "production"
    app.run(debug=is_debug, port=port)
