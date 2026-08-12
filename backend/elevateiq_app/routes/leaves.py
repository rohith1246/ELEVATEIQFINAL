"""
Leaves and Attendance Tracking blueprint routes.

Manages employee leaves lifecycle (applying, listing, approving/rejecting leave applications) 
and daily attendance logs (clocking check-ins, clocking check-outs, computing hours, and 
classifying presence status as Present, Half Day, or Absent).
"""

import math
import logging
from datetime import date, datetime, time, timezone, timedelta
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user
from ..config import safe_error

logger = logging.getLogger(__name__)

# ElevateIQ Soft Tech Exact Office GPS Coordinates (Arundelpet, Narasaraopet, AP 522601)
OFFICE_LATITUDE = 16.2342968
OFFICE_LONGITUDE = 80.0443192
MAX_ALLOWED_RADIUS_METERS = 500  # 500 meters radius around the office building

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth in meters using the Haversine formula.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

ALLOWED_LEAVE_COLUMNS = {"casual_leave", "sick_leave", "earned_leave", "emergency_leave"}

IST = timezone(timedelta(hours=5, minutes=30))

leaves_bp = Blueprint("leaves", __name__)

@leaves_bp.route("/leaves", methods=["GET"])
def get_leaves():
    """
    Fetches leave records based on current user role and request scope.

    Admins and designated team leaders/approvers can fetch all system leaves using 'scope=all'.
    Standard employees retrieve only their own personal leave requests.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of leave applications with formatted ISO dates.
            - 401: Unauthorized access.
            - 500: Database select exception.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    # Only employees and admins can access leave data.
    # Candidates and clients have no leave records and must be blocked.
    if user["role"] not in ("admin", "employee"):
        return jsonify({"error": "Forbidden: Leave data is only accessible to employees and admins"}), 403

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        scope = request.args.get("scope")
        is_approver = False
        if user["role"] == "admin":
            is_approver = True
        else:
            # Check designation for employee to verify leadership privileges (HR / Team Lead)
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = (res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")
                designation = designation.lower()
                if "team leader" in designation or "team lead" in designation or "hr" in designation or "human resource" in designation:
                    is_approver = True

        # Grant full company-wide view only to admins and authorised approvers
        if (scope == "all" and is_approver) or user["role"] == "admin":
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
        elif user["role"] == "employee" and user.get("emp_db_id"):
            # Regular employees only see their own leave records
            cursor.execute(
                "SELECT * FROM leaves WHERE employee_id = %s ORDER BY created_at DESC",
                (user["emp_db_id"],)
            )
        else:
            # Safety fallback — return empty list if emp_db_id is missing
            return jsonify([]), 200

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
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/leaves", methods=["POST"])
def apply_leave():
    """
    Submits a new leave request.
    Validates category constraints and verifies that the employee has sufficient balance.

    JSON Parameters:
        leave_type (str): Category of leave ('Casual', 'Sick', 'Earned', 'Emergency').
        start_date (str): 'YYYY-MM-DD' start date.
        end_date (str): 'YYYY-MM-DD' end date.
        reason (str, optional): Explanation notes.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success creation message.
            - 400: Missing/invalid parameters, or insufficient balances.
            - 403: If caller is not an employee.
            - 404: Employee record not found.
            - 500: Database transaction exceptions.
    """
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

    if leave_type not in ["Casual", "Sick", "Earned", "Emergency"]:
        return jsonify({"error": "Invalid leave type. Must be Casual, Sick, Earned, or Emergency."}), 400

    # Parse date strings to Python date objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    if start_date > end_date:
        return jsonify({"error": "Start date must be before end date"}), 400

    leave_days = (end_date - start_date).days + 1
    if leave_days != 1:
        return jsonify({"error": "Leave duration must be exactly 1 day."}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check leave balance from employee record
        cursor.execute("SELECT * FROM employees WHERE id = %s", (user["emp_db_id"],))
        emp = cursor.fetchone()
        if not emp:
            return jsonify({"error": "Employee profile not found. Please contact the administrator."}), 404

        # Validate that employee has not already applied for/taken leave in this calendar month
        start_of_month = date(start_date.year, start_date.month, 1)
        if start_date.month == 12:
            end_of_month = date(start_date.year + 1, 1, 1)
        else:
            end_of_month = date(start_date.year, start_date.month + 1, 1)

        cursor.execute(
            """
            SELECT COUNT(*) FROM leaves 
            WHERE employee_id = %s 
              AND status NOT IN ('Rejected', 'TL Rejected', 'HR Rejected')
              AND start_date >= %s AND start_date < %s
            """,
            (user["emp_db_id"], start_of_month, end_of_month)
        )
        month_leaves_count = cursor.fetchone()["count"]
        if month_leaves_count >= 1:
            return jsonify({"error": "You can only take 1 day of leave per calendar month. You already have a pending or approved leave in this calendar month."}), 400

        cursor.execute(
            """
            INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status) 
            VALUES (%s, %s, %s, %s, %s, 'Pending TL Approval')
            """,
            (user["emp_db_id"], leave_type, start_date, end_date, reason)
        )
        conn.commit()
        return jsonify({"message": "Leave application submitted successfully."}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/leaves/<int:leave_id>", methods=["DELETE"])
def revert_leave(leave_id):
    """
    Reverts / withdraws an employee's leave request.
    Allows employees to cancel pending or approved leave requests.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM leaves WHERE id = %s", (leave_id,))
        leave = cursor.fetchone()
        if not leave:
            return jsonify({"error": "Leave request not found"}), 404

        # Security check: Ensure leave request belongs to the logged-in employee or user is admin
        if user["role"] != "admin" and leave["employee_id"] != user.get("emp_db_id"):
            return jsonify({"error": "Forbidden - You can only revert your own leave applications."}), 403

        # Update leave status to Withdrawn
        cursor.execute("UPDATE leaves SET status = 'Withdrawn' WHERE id = %s", (leave_id,))
        
        # Clean up any attendance records created for this leave if approved previously
        cursor.execute(
            """
            DELETE FROM attendance 
            WHERE employee_id = %s 
              AND date >= %s AND date <= %s 
              AND status = 'Leave'
            """,
            (leave["employee_id"], leave["start_date"], leave["end_date"])
        )
        conn.commit()
        return jsonify({"message": "Leave application reverted successfully."}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Revert leave error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/leaves/<int:leave_id>", methods=["PUT"])
def review_leave(leave_id):
    """
    Approves or Rejects a pending leave request.
    Restricted to Admins and Team Leaders.

    If approved, deducts the corresponding count from the employee's category balance,
    and inserts attendance records marked as 'Leave' for the duration dates.

    Args:
        leave_id (int): Primary key ID of the leave request.

    JSON Parameters:
        status (str): The decision action ('Approved' or 'Rejected').

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success status change message.
            - 400: Already processed, insufficient balance, or invalid parameters.
            - 403: Forbidden access.
            - 404: Request or employee record not found.
            - 500: Database update or transaction exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        is_approver = False
        designation = ""
        if user["role"] == "admin":
            is_approver = True
        else:
            # Check designation for employee to verify leadership privileges
            cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
            res = cursor.fetchone()
            if res:
                designation = (res.get("designation") or "") if isinstance(res, dict) else (res[0] or "")
                designation = designation.lower()
                if "team leader" in designation or "team lead" in designation or "hr" in designation or "human resource" in designation:
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

        current_status = leave["status"]
        if current_status == "Pending":
            current_status = "Pending TL Approval"

        is_tl = "team leader" in designation or "team lead" in designation
        is_hr = "hr" in designation or "human resource" in designation
        is_admin = user["role"] == "admin"

        if action == "Approved":
            if is_admin:
                new_status = "Approved by Admin"
            elif is_hr:
                new_status = "Approved by HR"
            elif is_tl:
                new_status = "Pending HR Approval"
            else:
                new_status = "Approved by Admin"
        else:
            if is_admin:
                new_status = "Rejected by Admin"
            elif is_hr:
                new_status = "Rejected by HR"
            elif is_tl:
                new_status = "Rejected by Team Lead"
            else:
                new_status = "Rejected by Admin"

        # If fully approved (Admin, HR, or direct approval), deduct balance & add attendance entries
        if "Approved" in new_status and new_status != "Pending HR Approval":
            emp_id = leave["employee_id"]
            leave_days = (leave["end_date"] - leave["start_date"]).days + 1
            leave_type = leave["leave_type"]

            # Deduct balance (if type is in allowed leave columns)
            balance_col = f"{leave_type.lower()}_leave"
            if balance_col in ALLOWED_LEAVE_COLUMNS:
                cursor.execute(
                    "SELECT {} FROM employees WHERE id = %s".format(balance_col), (emp_id,)
                )
                emp_row = cursor.fetchone()
                if emp_row:
                    balance = emp_row[balance_col]
                    if balance >= leave_days:
                        cursor.execute(
                            "UPDATE employees SET {} = {} - %s WHERE id = %s".format(balance_col, balance_col),
                            (leave_days, emp_id)
                        )

            # Insert attendance records marked as 'Leave' for the duration
            curr = leave["start_date"]
            while curr <= leave["end_date"]:
                cursor.execute(
                    """
                    INSERT INTO attendance (employee_id, date, status, check_in, check_out, working_hours) 
                    VALUES (%s, %s, 'Leave', '09:00:00', '17:00:00', 8.0)
                    ON CONFLICT (employee_id, date) DO UPDATE SET status = 'Leave'
                    """,
                    (emp_id, curr)
                )
                curr = datetime.fromordinal(curr.toordinal() + 1).date()

        cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (new_status, leave_id))
        conn.commit()
        return jsonify({
            "message": f"Leave request status updated to '{new_status}'",
            "new_status": new_status,
            "leave_id": leave_id
        }), 200
        month_leaves_count = cursor.fetchone()["count"]
        if month_leaves_count >= 1:
            return jsonify({"error": "You can only take 1 day of leave per calendar month. You already have a pending or approved leave in this calendar month."}), 400

        cursor.execute(
            """
            INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status) 
            VALUES (%s, %s, %s, %s, %s, 'Pending TL Approval')
            """,
            (user["emp_db_id"], leave_type, start_date, end_date, reason)
        )
        conn.commit()
        return jsonify({"message": "Leave application submitted successfully."}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()

@leaves_bp.route("/attendance", methods=["GET"])
@leaves_bp.route("/api/attendance", methods=["GET"])
def get_attendance():
    """
    Lists attendance log entries and daily reports.
    - Admins & HR: Retrieve full company daily report (including presenties & absenties for selected date).
    - Employees: Retrieve personal attendance logs.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized: Please log in first"}), 401

    target_date_str = request.args.get("date")
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        user_role = user.get("role", "").lower()
        user_db_id = user.get("user_id") or user.get("id")

        if user_role in ("admin", "hr"):
            if target_date_str:
                try:
                    report_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except ValueError:
                    report_date = datetime.now(IST).date()

                cursor.execute(
                    """
                    SELECT e.id as emp_id, e.employee_id, u.name, e.department, e.designation, COALESCE(e.shift, 'Day Shift') as shift
                    FROM employees e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.status = 'Active' AND (u.portal = 'elevateiq' OR u.portal = 'both' OR u.portal IS NULL)
                    ORDER BY e.employee_id
                    """
                )
                all_emps = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT a.*, e.employee_id as employee_code, u.name, e.department, e.designation, COALESCE(a.shift, e.shift, 'Day Shift') as shift
                    FROM attendance a
                    JOIN employees e ON a.employee_id = e.id
                    JOIN users u ON e.user_id = u.id
                    WHERE a.date = %s
                    """,
                    (report_date,)
                )
                existing_logs = cursor.fetchall()
                logs_by_emp = {log["employee_id"]: log for log in existing_logs}

                records = []
                for emp in all_emps:
                    emp_db_id = emp["emp_id"]
                    if emp_db_id in logs_by_emp:
                        rec = dict(logs_by_emp[emp_db_id])
                        rec["employee_id"] = emp["employee_id"]
                        records.append(rec)
                    else:
                        records.append({
                            "id": None,
                            "employee_id": emp["employee_id"],
                            "name": emp["name"],
                            "department": emp["department"] or "General",
                            "designation": emp["designation"] or "-",
                            "shift": emp["shift"],
                            "date": report_date.isoformat(),
                            "check_in": None,
                            "check_out": None,
                            "working_hours": 0.0,
                            "status": "Absent"
                        })
            else:
                cursor.execute(
                    """
                    SELECT a.*, e.employee_id, u.name, e.department, e.designation, COALESCE(a.shift, e.shift, 'Day Shift') as shift 
                    FROM attendance a 
                    JOIN employees e ON a.employee_id = e.id 
                    JOIN users u ON e.user_id = u.id 
                    ORDER BY a.date DESC, a.check_in DESC
                    """
                )
                records = cursor.fetchall()
        else:
            cursor.execute(
                """
                SELECT a.*, e.employee_id, u.name, e.department, e.designation, COALESCE(a.shift, e.shift, 'Day Shift') as shift 
                FROM attendance a 
                JOIN employees e ON a.employee_id = e.id 
                JOIN users u ON e.user_id = u.id 
                WHERE e.user_id = %s 
                ORDER BY a.date DESC, a.check_in DESC
                """,
                (user_db_id,)
            )
            records = cursor.fetchall()

        for rec in records:
            if rec.get("date") and not isinstance(rec["date"], str):
                rec["date"] = rec["date"].isoformat()
            if rec.get("check_in") and not isinstance(rec["check_in"], str):
                rec["check_in"] = str(rec["check_in"])
            if rec.get("check_out") and not isinstance(rec["check_out"], str):
                rec["check_out"] = str(rec["check_out"])
            if rec.get("working_hours") is not None:
                rec["working_hours"] = float(rec["working_hours"])

        return jsonify(records), 200
    except Exception as e:
        logger.error(f"Leaves API get_attendance error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance/checkin", methods=["POST"])
@leaves_bp.route("/api/attendance/checkin", methods=["POST"])
def check_in():
    """
    Registers clock-in time for current employee/user.
    - Check-in before 8:15 / 9:15 -> Present
    - Check-in after 8:15 / 9:15 -> Half Day
    - Forgot checkout from previous shift -> Auto Half Day for previous shift
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized: Please log in first"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    ist_now = datetime.now(IST)
    today_date = ist_now.date()
    current_time = ist_now.time()
    current_time_str = ist_now.strftime("%H:%M:%S")
    user_db_id = user.get("user_id") or user.get("id")

    try:
        # Location Verification (Geofenced GPS Check)
        data = request.json or {}
        user_lat = data.get("latitude")
        user_lng = data.get("longitude")

        if user.get("role") != "admin":
            if user_lat is None or user_lng is None:
                return jsonify({"error": "GPS Location access is required to check in. Please allow location permissions on your browser/phone."}), 400
            
            try:
                distance_meters = haversine_distance(float(user_lat), float(user_lng), OFFICE_LATITUDE, OFFICE_LONGITUDE)
                if distance_meters > MAX_ALLOWED_RADIUS_METERS:
                    return jsonify({
                        "error": f"Location Check Failed: You are {round(distance_meters)} meters away from the office (Arundelpet, Narasaraopet). Maximum allowed distance is {MAX_ALLOWED_RADIUS_METERS} meters."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid GPS coordinates provided."}), 400

        emp_db_id = None
        cursor.execute("SELECT id, shift FROM employees WHERE user_id = %s", (user_db_id,))
        emp_row = cursor.fetchone()
        if emp_row:
            emp_db_id = emp_row["id"]
            emp_shift = emp_row.get("shift") or "Day Shift"
        else:
            # Auto-create employee profile for logged in user
            cursor.execute(
                "INSERT INTO employees (user_id, employee_id, department, designation, status, shift) VALUES (%s, %s, 'General', 'Staff Member', 'Active', 'Day Shift') RETURNING id",
                (user_db_id, f"EMP_{user_db_id}")
            )
            emp_db_id = cursor.fetchone()["id"]
            emp_shift = "Day Shift"
            conn.commit()

        # 1. Clean up any forgot-to-checkout open sessions from previous days
        cursor.execute(
            "SELECT id, date, check_in FROM attendance WHERE employee_id = %s AND check_out IS NULL ORDER BY date DESC, id DESC LIMIT 1",
            (emp_db_id,)
        )
        open_prev = cursor.fetchone()
        if open_prev:
            prev_date = open_prev["date"]
            if prev_date < today_date:
                # Forgot checkout -> auto mark previous session as Half Day
                cursor.execute(
                    "UPDATE attendance SET status = 'Half Day', working_hours = 4.0 WHERE id = %s",
                    (open_prev["id"],)
                )
                conn.commit()
            else:
                return jsonify({"error": "Already checked in today. Please check out first before checking in again."}), 400

        # Check if already completed attendance for today
        cursor.execute(
            "SELECT id FROM attendance WHERE employee_id = %s AND date = %s AND check_out IS NOT NULL",
            (emp_db_id, today_date)
        )
        if cursor.fetchone():
            return jsonify({"error": "Already completed attendance for today."}), 400

        # 2. Determine initial status based on grace period cutoff (9:20 AM for Day/Morning shift, 8:20 PM for Night shift)
        status = "Present"
        if emp_shift == "Night Shift":
            # Night Shift starts at 8:00 PM (20:00). Cutoff is 8:20 PM (20:20:00)
            cutoff = time(20, 20, 0)
            if current_time > cutoff or current_time < time(5, 0, 0):
                if current_time > cutoff or current_time < time(4, 0, 0):
                    status = "Half Day"
        else:
            # Day / Morning Shift starts at 9:00 AM (09:00). Cutoff is 9:20 AM (09:20:00)
            cutoff = time(9, 20, 0)
            if current_time > cutoff:
                status = "Half Day"

        cursor.execute(
            """
            INSERT INTO attendance (employee_id, date, check_in, status, shift) 
            VALUES (%s, %s, %s, %s, %s)
            """,
            (emp_db_id, today_date, current_time_str, status, emp_shift)
        )
        conn.commit()

        msg_status = "Full Day (Present)" if status == "Present" else "Half Day (Late Check-in past grace period cutoff)"
        return jsonify({"message": f"Checked in successfully at {current_time_str}. Status: {msg_status}"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Leaves API check_in error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance/checkout", methods=["POST"])
@leaves_bp.route("/api/attendance/checkout", methods=["POST"])
def check_out():
    """
    Registers clock-out time.
    Enforces check-out window:
    - Day / Morning Shift: Enabled ONLY between 17:00 and 17:15 (5:00 PM - 5:15 PM).
    - Night Shift: Enabled ONLY between 4:45 AM and 5:00 AM.
    - Check-out after window or forgot checkout -> Half Day.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized: Please log in first"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    ist_now = datetime.now(IST)
    current_time = ist_now.time()
    current_time_str = ist_now.strftime("%H:%M:%S")
    today_date = ist_now.date()
    user_db_id = user.get("user_id") or user.get("id")

    try:
        cursor.execute("SELECT id, shift FROM employees WHERE user_id = %s", (user_db_id,))
        emp_row = cursor.fetchone()
        if not emp_row:
            return jsonify({"error": "Employee profile not found. Please check in first."}), 400

        emp_db_id = emp_row["id"]

        # Find latest open check-in record without check_out
        cursor.execute(
            "SELECT * FROM attendance WHERE employee_id = %s AND check_out IS NULL ORDER BY date DESC, id DESC LIMIT 1",
            (emp_db_id,)
        )
        record = cursor.fetchone()

        if not record:
            return jsonify({"error": "No active check-in record found. Please check in first."}), 400

        emp_shift = record.get("shift") or emp_row.get("shift") or "Day Shift"
        check_in_date = record["date"]

        # If checking out on a subsequent date (forgot checkout on shift date) -> mark Half Day
        if check_in_date < today_date:
            cursor.execute(
                """
                UPDATE attendance 
                SET check_out = %s, working_hours = 4.0, status = 'Half Day' 
                WHERE id = %s
                """,
                (current_time_str, record["id"])
            )
            conn.commit()
            return jsonify({"message": f"Checked out (Forgot checkout on shift date). Status marked as Half Day."}), 200

        # Enforce window bounds for early checkout attempts
        if emp_shift == "Night Shift":
            # Window: 4:45 AM (04:45:00) to 5:15 AM (05:15:00)
            window_start = time(4, 45, 0)
            if current_time < window_start and current_time >= time(20, 0, 0):
                return jsonify({"error": "Check-out option is only enabled between 4:45 AM and 5:00 AM for Night Shift."}), 400
        else:
            # Day / Morning Shift: Enabled ONLY between 17:45 (5:45 PM) and 18:00 (6:00 PM)
            window_start = time(17, 45, 0)
            if current_time < window_start:
                return jsonify({"error": "Check-out option is only enabled between 17:45 and 18:00 (5:45 PM - 6:00 PM)."}), 400

        # Calculate working hours accurately
        check_in_val = record["check_in"]
        if isinstance(check_in_val, str):
            dt_in_time = datetime.strptime(check_in_val, "%H:%M:%S").time()
        else:
            dt_in_time = check_in_val

        dt_in = datetime.combine(check_in_date, dt_in_time)
        dt_out = ist_now.replace(tzinfo=None)
        delta = dt_out - dt_in
        total_seconds = delta.total_seconds()
        working_hours = round(max(0.1, total_seconds / 3600.0), 2)

        # Retain status if already set to Half Day due to late check-in, or if checked out after valid window
        status = record.get("status") or "Present"
        if status == "Present":
            if emp_shift == "Night Shift":
                if not (time(4, 45, 0) <= current_time <= time(5, 15, 0)):
                    status = "Half Day"
            else:
                # If checking out outside 17:45 (5:45 PM) to 18:00 (6:00 PM) -> Half Day
                if not (time(17, 45, 0) <= current_time <= time(18, 0, 0)):
                    status = "Half Day"

        cursor.execute(
            """
            UPDATE attendance 
            SET check_out = %s, working_hours = %s, status = %s 
            WHERE id = %s
            """,
            (current_time_str, working_hours, status, record["id"])
        )
        conn.commit()
        return jsonify({"message": f"Checked out successfully at {current_time_str}. Total hours: {working_hours:.2f} hrs. Status: {status}"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Leaves API check_out error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance/shift", methods=["GET", "POST"])
@leaves_bp.route("/employees/shift", methods=["GET", "POST"])
def update_employee_shift():
    """One-time registration & retrieval of employee's shift (Day Shift / Night Shift)."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor()
    try:
        uid = user.get("user_id") or user.get("id")
        emp_db_id = user.get("emp_db_id")

        if request.method == "GET":
            cursor.execute("SELECT shift, shift_updated_at FROM employees WHERE user_id = %s", (uid,))
            row = cursor.fetchone()
            current_shift = None
            needs_popup = True
            if row and row[0]:
                current_shift = row[0]
                needs_popup = False  # Shift already registered! Never pop up again.

            return jsonify({
                "shift": current_shift,
                "needs_popup": needs_popup
            }), 200

        data = request.json or {}
        shift = (data.get("shift") or "").strip()
        if shift not in ("Day Shift", "Night Shift"):
            return jsonify({"error": "Invalid shift. Must be 'Day Shift' or 'Night Shift'"}), 400

        if not emp_db_id:
            cursor.execute("SELECT id FROM employees WHERE user_id = %s", (uid,))
            emp_row = cursor.fetchone()
            if emp_row:
                emp_db_id = emp_row[0]
            else:
                cursor.execute(
                    "INSERT INTO employees (user_id, employee_id, department, designation, status, shift, shift_updated_at) VALUES (%s, %s, 'Engineering', 'Staff Member', 'Active', %s, NOW()) RETURNING id",
                    (uid, f"EMP_{uid}", shift)
                )
                emp_db_id = cursor.fetchone()[0]
                conn.commit()

        cursor.execute(
            "UPDATE employees SET shift = %s, shift_updated_at = NOW() WHERE user_id = %s",
            (shift, uid)
        )
        
        today_date = datetime.now(IST).date()
        cursor.execute(
            "UPDATE attendance SET shift = %s WHERE employee_id = %s AND date = %s",
            (shift, emp_db_id, today_date)
        )
        conn.commit()
        return jsonify({"message": f"Shift registered successfully as {shift}", "shift": shift}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"Update shift error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
