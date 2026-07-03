from datetime import date, datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user

leaves_bp = Blueprint("leaves", __name__)

@leaves_bp.route("/leaves", methods=["GET"])
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


@leaves_bp.route("/leaves", methods=["POST"])
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


@leaves_bp.route("/leaves/<int:leave_id>", methods=["PUT"])
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
                return jsonify({"error": "Employee does not have enough leave balance to approve."}), 400

            cursor.execute(
                f"UPDATE employees SET {balance_col} = {balance_col} - %s WHERE id = %s",
                (leave_days, emp_id)
            )

            # Insert attendance record as 'Leave' for the duration
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

        cursor.execute("UPDATE leaves SET status = %s WHERE id = %s", (action, leave_id))
        conn.commit()
        return jsonify({"message": f"Leave request status updated to '{action}'"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@leaves_bp.route("/attendance", methods=["GET"])
def get_attendance():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

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


@leaves_bp.route("/attendance/checkin", methods=["POST"])
def check_in():
    user = get_current_user()
    if not user or user["role"] != "employee":
        return jsonify({"error": "Forbidden: Only employees can mark attendance"}), 403

    conn = get_connection()
    cursor = conn.cursor()
    today_date = date.today()
    current_time = datetime.now().time().strftime("%H:%M:%S")
    
    try:
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


@leaves_bp.route("/attendance/checkout", methods=["POST"])
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
        
        dt_in = datetime.combine(date.min, check_in_time)
        dt_out = datetime.combine(date.min, current_time)
        delta = dt_out - dt_in
        working_hours = max(0.0, delta.total_seconds() / 3600.0)

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
