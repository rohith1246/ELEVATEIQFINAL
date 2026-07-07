"""
Real-time Payroll System blueprint routes.

Manages employee salaries, monthly pay runs, real-time accrued expense metrics,
dynamic proration based on attendance, tax deductions, benefits allowances, and printable payslip records.
"""

from datetime import date, datetime
import calendar
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, require_role

payroll_bp = Blueprint("payroll", __name__)

def get_days_in_month(month_str):
    """
    Helper to get the number of days in a given YYYY-MM month string.
    """
    try:
        year, month = map(int, month_str.split("-"))
        return calendar.monthrange(year, month)[1]
    except Exception:
        return 30

@payroll_bp.route("/api/payroll/summary", methods=["GET"])
@require_role(["admin"])
def get_payroll_summary():
    """
    Calculates overall payroll expenses, company burn rate per second, and status breakdown.
    
    Query Parameters:
        portal (str, optional): filter by 'elevateiq' or 'edutech' portal
        month (str, optional): month filter in 'YYYY-MM' format (defaults to current month)
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    portal = request.args.get("portal")
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get total salaries for active employees in the specified portal
        if portal:
            cursor.execute(
                """
                SELECT COALESCE(SUM(e.salary), 0) as total_salary, COUNT(e.id) as employee_count
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE e.status = 'Active' AND u.portal = %s
                """,
                (portal,)
            )
        else:
            cursor.execute(
                """
                SELECT COALESCE(SUM(e.salary), 0) as total_salary, COUNT(e.id) as employee_count
                FROM employees e
                WHERE e.status = 'Active'
                """
            )
        salary_data = cursor.fetchone()
        total_monthly_payroll = float(salary_data["total_salary"])
        employee_count = salary_data["employee_count"]
        
        # Calculate real-time stats
        days_in_month = get_days_in_month(month)
        seconds_in_month = days_in_month * 24 * 3600
        burn_rate_sec = total_monthly_payroll / seconds_in_month if total_monthly_payroll > 0 else 0.0
        
        now = datetime.now()
        current_month_str = now.strftime("%Y-%m")
        if month == current_month_str:
            start_of_month = datetime(now.year, now.month, 1)
            elapsed_seconds = (now - start_of_month).total_seconds()
        elif month < current_month_str:
            # Past month: fully elapsed
            elapsed_seconds = seconds_in_month
        else:
            # Future month: not started
            elapsed_seconds = 0
            
        # Get processed stats from database
        if portal:
            cursor.execute(
                """
                SELECT p.status, COUNT(p.id) as status_count, COALESCE(SUM(p.net_pay), 0) as total_net_pay
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                JOIN users u ON e.user_id = u.id
                WHERE p.month = %s AND u.portal = %s
                GROUP BY p.status
                """,
                (month, portal)
            )
        else:
            cursor.execute(
                """
                SELECT p.status, COUNT(p.id) as status_count, COALESCE(SUM(p.net_pay), 0) as total_net_pay
                FROM payroll p
                WHERE p.month = %s
                GROUP BY p.status
                """,
                (month,)
            )
        
        status_rows = cursor.fetchall()
        status_counts = {"Paid": 0, "Processing": 0, "Pending": employee_count}
        paid_amount = 0.0
        
        processed_count = 0
        for r in status_rows:
            status_counts[r["status"]] = r["status_count"]
            processed_count += r["status_count"]
            if r["status"] == "Paid":
                paid_amount = float(r["total_net_pay"])
                
        # Pending means active employees not registered in processed runs
        status_counts["Pending"] = max(0, employee_count - processed_count)
        
        return jsonify({
            "month": month,
            "total_monthly_payroll": total_monthly_payroll,
            "employee_count": employee_count,
            "burn_rate_sec": burn_rate_sec,
            "elapsed_seconds": elapsed_seconds,
            "paid_amount": paid_amount,
            "status_counts": status_counts
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@payroll_bp.route("/api/payroll/ledger", methods=["GET"])
@require_role(["admin"])
def get_payroll_ledger():
    """
    Returns the payroll ledger for a given month, computing dynamic previews for non-processed employees.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    portal = request.args.get("portal")
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Fetch all active employees
        if portal:
            cursor.execute(
                """
                SELECT e.id as employee_db_id, e.employee_id, u.name, u.email, 
                       e.department, e.designation, e.salary, e.date_of_joining
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE e.status = 'Active' AND u.portal = %s
                ORDER BY e.employee_id
                """,
                (portal,)
            )
        else:
            cursor.execute(
                """
                SELECT e.id as employee_db_id, e.employee_id, u.name, u.email, 
                       e.department, e.designation, e.salary, e.date_of_joining
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE e.status = 'Active'
                ORDER BY e.employee_id
                """
            )
        employees = cursor.fetchall()
        
        ledger = []
        for emp in employees:
            base_salary = float(emp["salary"]) if emp["salary"] is not None else 35000.00
            emp_db_id = emp["employee_db_id"]
            
            # Fetch existing payroll run details
            cursor.execute(
                "SELECT * FROM payroll WHERE employee_id = %s AND month = %s",
                (emp_db_id, month)
            )
            payroll_rec = cursor.fetchone()
            
            if payroll_rec:
                record = {
                    "payroll_id": payroll_rec["id"],
                    "employee_db_id": emp_db_id,
                    "employee_id": emp["employee_id"],
                    "name": emp["name"],
                    "email": emp["email"],
                    "department": emp["department"],
                    "designation": emp["designation"],
                    "base_salary": float(payroll_rec["base_salary"]),
                    "allowances": float(payroll_rec["allowances"]),
                    "deductions": float(payroll_rec["deductions"]),
                    "net_pay": float(payroll_rec["net_pay"]),
                    "status": payroll_rec["status"],
                    "payment_date": payroll_rec["payment_date"].isoformat() if payroll_rec["payment_date"] else None,
                    "is_generated": True
                }
            else:
                # Dynamic proration: Check attendance for the month
                days_in_month = get_days_in_month(month)
                
                # We count absent days
                start_date_str = f"{month}-01"
                end_date_str = f"{month}-{days_in_month}"
                cursor.execute(
                    """
                    SELECT COUNT(*) as absent_count FROM attendance
                    WHERE employee_id = %s AND status = 'Absent' 
                      AND date >= %s AND date <= %s
                    """,
                    (emp_db_id, start_date_str, end_date_str)
                )
                absent_data = cursor.fetchone()
                absent_days = absent_data["absent_count"] if absent_data else 0
                
                # Standard tax/allowances definitions (dynamic calculation based on salary)
                hra = base_salary * 0.10  # 10% House Rent Allowance
                da = base_salary * 0.05   # 5% Dearness Allowance
                flat_allowance = 1250.00  # Flat Medical & Travel Allowance
                allowances = hra + da + flat_allowance
                
                pf = base_salary * 0.12   # 12% Provident Fund
                pt = base_salary * 0.02   # 2% Professional Tax
                lop = absent_days * (base_salary / days_in_month) # Loss of Pay for absent days
                deductions = pf + pt + lop
                
                net_pay = base_salary + allowances - deductions
                
                record = {
                    "payroll_id": None,
                    "employee_db_id": emp_db_id,
                    "employee_id": emp["employee_id"],
                    "name": emp["name"],
                    "email": emp["email"],
                    "department": emp["department"],
                    "designation": emp["designation"],
                    "base_salary": base_salary,
                    "allowances": allowances,
                    "deductions": deductions,
                    "net_pay": net_pay,
                    "status": "Pending",
                    "payment_date": None,
                    "is_generated": False,
                    "absent_days_count": absent_days,
                    "calc_details": {
                        "hra": hra,
                        "da": da,
                        "flat": flat_allowance,
                        "pf": pf,
                        "pt": pt,
                        "lop": lop
                    }
                }
            
            ledger.append(record)
            
        return jsonify(ledger), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@payroll_bp.route("/api/payroll/process", methods=["POST"])
@require_role(["admin"])
def process_employee_payroll():
    """
    Saves or updates a payroll record for a single employee.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    emp_db_id = data.get("employee_db_id")
    month = data.get("month")
    base_salary = data.get("base_salary")
    allowances = data.get("allowances", 0.0)
    deductions = data.get("deductions", 0.0)
    net_pay = data.get("net_pay")
    status = data.get("status", "Pending")
    
    if not emp_db_id or not month or base_salary is None or net_pay is None:
        return jsonify({"error": "Missing required payroll parameters"}), 400
        
    payment_date = datetime.now() if status == "Paid" else None
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Upsert payroll record
        cursor.execute(
            """
            INSERT INTO payroll (employee_id, month, base_salary, allowances, deductions, net_pay, status, payment_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (employee_id, month) DO UPDATE
            SET base_salary = EXCLUDED.base_salary,
                allowances = EXCLUDED.allowances,
                deductions = EXCLUDED.deductions,
                net_pay = EXCLUDED.net_pay,
                status = EXCLUDED.status,
                payment_date = EXCLUDED.payment_date
            RETURNING id
            """,
            (emp_db_id, month, base_salary, allowances, deductions, net_pay, status, payment_date)
        )
        payroll_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Payroll processed successfully", "payroll_id": payroll_id}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@payroll_bp.route("/api/payroll/bulk-process", methods=["POST"])
@require_role(["admin"])
def bulk_process_payroll():
    """
    Bulk registers/processes payroll for all active employees.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    month = data.get("month")
    status = data.get("status", "Paid")
    portal = data.get("portal")
    
    if not month:
        return jsonify({"error": "Month parameter (YYYY-MM) is required"}), 400
        
    payment_date = datetime.now() if status == "Paid" else None
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Fetch all active employees
        if portal:
            cursor.execute(
                """
                SELECT e.id, e.salary 
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE e.status = 'Active' AND u.portal = %s
                """,
                (portal,)
            )
        else:
            cursor.execute("SELECT id, salary FROM employees WHERE status = 'Active'")
        employees = cursor.fetchall()
        
        days_in_month = get_days_in_month(month)
        start_date_str = f"{month}-01"
        end_date_str = f"{month}-{days_in_month}"
        
        success_count = 0
        for emp in employees:
            emp_db_id = emp["id"]
            base_salary = float(emp["salary"]) if emp["salary"] is not None else 35000.00
            
            # Check if payroll record already exists and is already paid
            cursor.execute(
                "SELECT id, status FROM payroll WHERE employee_id = %s AND month = %s",
                (emp_db_id, month)
            )
            existing = cursor.fetchone()
            if existing and existing["status"] == "Paid":
                continue # Skip already paid records
                
            # Compute dynamic values
            cursor.execute(
                """
                SELECT COUNT(*) as absent_count FROM attendance
                WHERE employee_id = %s AND status = 'Absent' 
                  AND date >= %s AND date <= %s
                """,
                (emp_db_id, start_date_str, end_date_str)
            )
            absent_data = cursor.fetchone()
            absent_days = absent_data["absent_count"] if absent_data else 0
            
            hra = base_salary * 0.10
            da = base_salary * 0.05
            flat_allowance = 1250.00
            allowances = hra + da + flat_allowance
            
            pf = base_salary * 0.12
            pt = base_salary * 0.02
            lop = absent_days * (base_salary / days_in_month)
            deductions = pf + pt + lop
            
            net_pay = base_salary + allowances - deductions
            
            cursor.execute(
                """
                INSERT INTO payroll (employee_id, month, base_salary, allowances, deductions, net_pay, status, payment_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id, month) DO UPDATE
                SET base_salary = EXCLUDED.base_salary,
                    allowances = EXCLUDED.allowances,
                    deductions = EXCLUDED.deductions,
                    net_pay = EXCLUDED.net_pay,
                    status = EXCLUDED.status,
                    payment_date = EXCLUDED.payment_date
                """,
                (emp_db_id, month, base_salary, allowances, deductions, net_pay, status, payment_date)
            )
            success_count += 1
            
        conn.commit()
        return jsonify({"message": f"Successfully processed payroll for {success_count} employees."}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
