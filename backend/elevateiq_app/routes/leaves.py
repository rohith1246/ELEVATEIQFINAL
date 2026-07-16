"""
Leaves and Attendance Tracking blueprint routes.

Manages employee leaves lifecycle (applying, listing, approving/rejecting leave applications) 
and daily attendance logs (clocking check-ins, clocking check-outs, computing hours, and 
classifying presence status as Present, Half Day, or Absent).
"""

import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user
from ..config import safe_error

logger = logging.getLogger(__name__)

ALLOWED_LEAVE_COLUMNS = {"casual_leave", "sick_leave", "earned_leave", "emergency_leave"}

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
                if "team leader" in designation or "hr" in designation or "human resource" in designation:
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
              AND status NOT IN ('Rejected', 'Team Lead Rejected', 'HR Rejected')
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
            VALUES (%s, %s, %s, %s, %s, 'Pending Team Lead Approval')
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
                if "team leader" in designation or "hr" in designation or "human resource" in designation:
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
            current_status = "Pending Team Lead Approval"

        is_tl = "team leader" in designation
        is_hr_or_admin = "hr" in designation or "human resource" in designation or user["role"] == "admin"

        if current_status == "Pending Team Lead Approval":
            if not is_tl and not is_hr_or_admin:  # Fallback: let HR/Admin approve if no TL is available
                return jsonify({"error": "Forbidden: Only a Team Leader can review this request at this stage."}), 403
            
            if action == "Approved":
                new_status = "Pending HR Approval"
            else:
                new_status = "Team Lead Rejected"

            cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (new_status, leave_id))
            conn.commit()
            return jsonify({"message": f"Leave request status updated to '{new_status}'"}), 200

        elif current_status == "Pending HR Approval":
            if not is_hr_or_admin:
                return jsonify({"error": "Forbidden: Only HR or Admin can review this request at this stage."}), 403

            if action == "Approved":
                new_status = "Approved"
                
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
                    if not emp_row:
                        return jsonify({"error": "Employee record not found."}), 404
                    balance = emp_row[balance_col]

                    if balance < leave_days:
                        return jsonify({"error": "Employee does not have enough leave balance to approve."}), 400

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
            else:
                new_status = "HR Rejected"

            cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (new_status, leave_id))
            conn.commit()
            return jsonify({"message": f"Leave request status updated to '{new_status}'"}), 200

        else:
            return jsonify({"error": "Leave request has already been processed"}), 400
    except Exception as e:
        conn.rollback()
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance", methods=["GET"])
def get_attendance():
    """
    Lists attendance log entries.

    - Admins: Retrieve all logs across the company.
    - Employees: Retrieve only their own logged attendance dates.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of attendance objects.
            - 401: Unauthorized access.
            - 500: Database select query exceptions.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    # Attendance data is strictly for employees and admins only.
    if user["role"] not in ("admin", "employee"):
        return jsonify({"error": "Forbidden: Attendance data is only accessible to employees and admins"}), 403

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user["role"] == "admin":
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

        # Format dates, check-in, check-out times, and working hours for clean JSON responses
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
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()



@leaves_bp.route("/attendance/checkin", methods=["POST"])
def check_in():
    """
    Registers the start clock-in time for the current date.
    Restricted to employees.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Checked in successfully.
            - 400: If already checked in today.
            - 403: Forbidden access.
            - 500: Database insertion exceptions.
    """
    user = get_current_user()
    if not user or user["role"] != "employee":
        return jsonify({"error": "Forbidden: Only employees can mark attendance"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    today_date = date.today()
    current_time = datetime.now().time().strftime("%H:%M:%S")
    
    try:
        # Enforce unique check-ins per day per employee
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
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance/checkout", methods=["POST"])
def check_out():
    """
    Registers the clock-out time for the current date.
    Restricted to employees.

    Computes working hours using duration delta and updates status classification:
    - >= 8.0 hours: 'Present'
    - >= 4.0 hours: 'Half Day'
    - < 4.0 hours: 'Absent'

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Checked out successfully along with hours and status.
            - 400: If check-in is missing or checkout was already recorded today.
            - 403: Forbidden access.
            - 500: Database update exceptions.
    """
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
        
        # Calculate delta difference between check-in and check-out
        dt_in = datetime.combine(date.min, check_in_time)
        dt_out = datetime.combine(date.min, current_time)
        delta = dt_out - dt_in
        working_hours = max(0.0, delta.total_seconds() / 3600.0)

        # Status rules based on hours worked
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
        logger.error(f"Leaves API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()

