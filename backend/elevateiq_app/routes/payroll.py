"""
Demo-only Payroll System blueprint routes.

Provides static mock data for dashboard summaries, ledger records, and payruns.
Avoids all live database operations to ensure zero performance overhead and system stability.
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from ..auth import get_current_user, require_role

payroll_bp = Blueprint("payroll", __name__)

def get_days_in_month(month_str):
    return 30

@payroll_bp.route("/api/payroll/summary", methods=["GET"])
@require_role(["admin"])
def get_payroll_summary():
    """
    Returns static mock summary for payroll demo metrics.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    portal = request.args.get("portal", "elevateiq")
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    
    # Calculate mock elapsed seconds in current month
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    elapsed_seconds = (now - start_of_month).total_seconds()
    
    # Custom mock data depending on portal
    if portal == "edutech":
        total_monthly_payroll = 12300.00
        employee_count = 3
        burn_rate_sec = total_monthly_payroll / (30 * 24 * 3600)
        paid_amount = 8700.00
        status_counts = {"Paid": 2, "Processing": 1, "Pending": 0}
    else:
        total_monthly_payroll = 18500.00
        employee_count = 4
        burn_rate_sec = total_monthly_payroll / (30 * 24 * 3600)
        paid_amount = 14500.00
        status_counts = {"Paid": 3, "Processing": 0, "Pending": 1}

    return jsonify({
        "month": month,
        "total_monthly_payroll": total_monthly_payroll,
        "employee_count": employee_count,
        "burn_rate_sec": burn_rate_sec,
        "elapsed_seconds": elapsed_seconds,
        "paid_amount": paid_amount,
        "status_counts": status_counts
    }), 200

@payroll_bp.route("/api/payroll/ledger", methods=["GET"])
@require_role(["admin"])
def get_payroll_ledger():
    """
    Returns static mock ledger records for staff.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    portal = request.args.get("portal", "elevateiq")
    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    
    if portal == "edutech":
        ledger = [
            {
                "payroll_id": 101,
                "employee_db_id": 1001,
                "employee_id": "EDU-TR-001",
                "name": "Test Trainer",
                "email": "trainer@elevateiq.com",
                "department": "Technical Training",
                "designation": "Senior Instructor",
                "base_salary": 5500.00,
                "allowances": 2075.00,
                "deductions": 770.00,
                "net_pay": 6805.00,
                "status": "Paid",
                "payment_date": f"{month}-05T10:00:00",
                "is_generated": True,
                "absent_days_count": 0,
                "calc_details": {
                    "hra": 550.0,
                    "da": 275.0,
                    "flat": 1250.0,
                    "pf": 660.0,
                    "pt": 110.0,
                    "lop": 0.0
                }
            },
            {
                "payroll_id": 102,
                "employee_db_id": 1002,
                "employee_id": "EDU-MN-002",
                "name": "Mohammed Abdul Jaleel",
                "email": "mohd730@gmail.com",
                "department": "Student Support",
                "designation": "Mentor",
                "base_salary": 3200.00,
                "allowances": 1730.00,
                "deductions": 661.33,
                "net_pay": 4268.67,
                "status": "Paid",
                "payment_date": f"{month}-05T11:15:00",
                "is_generated": True,
                "absent_days_count": 2,
                "calc_details": {
                    "hra": 320.0,
                    "da": 160.0,
                    "flat": 1250.0,
                    "pf": 384.0,
                    "pt": 64.0,
                    "lop": 213.33
                }
            },
            {
                "payroll_id": None,
                "employee_db_id": 1003,
                "employee_id": "EDU-CD-003",
                "name": "Pendala Shiva",
                "email": "shiva@gmail.com",
                "department": "Curriculum",
                "designation": "Content Developer",
                "base_salary": 3600.00,
                "allowances": 1790.00,
                "deductions": 504.00,
                "net_pay": 4886.00,
                "status": "Processing",
                "payment_date": None,
                "is_generated": False,
                "absent_days_count": 0,
                "calc_details": {
                    "hra": 360.0,
                    "da": 180.0,
                    "flat": 1250.0,
                    "pf": 432.0,
                    "pt": 72.0,
                    "lop": 0.0
                }
            }
        ]
    else:
        ledger = [
            {
                "payroll_id": 201,
                "employee_db_id": 2001,
                "employee_id": "EMP-001",
                "name": "BATHIKA DILEEP",
                "email": "bathikadileep@gmail.com",
                "department": "Engineering",
                "designation": "Software Engineer",
                "base_salary": 4500.00,
                "allowances": 1925.00,
                "deductions": 630.00,
                "net_pay": 5795.00,
                "status": "Paid",
                "payment_date": f"{month}-05T09:30:00",
                "is_generated": True,
                "absent_days_count": 0,
                "calc_details": {
                    "hra": 450.0,
                    "da": 225.0,
                    "flat": 1250.0,
                    "pf": 540.0,
                    "pt": 90.0,
                    "lop": 0.0
                }
            },
            {
                "payroll_id": 202,
                "employee_db_id": 2002,
                "employee_id": "EMP-002",
                "name": "SHIVA",
                "email": "shiva1@gmail.com",
                "department": "Engineering",
                "designation": "Team Lead",
                "base_salary": 6200.00,
                "allowances": 2180.00,
                "deductions": 868.00,
                "net_pay": 7512.00,
                "status": "Paid",
                "payment_date": f"{month}-05T09:45:00",
                "is_generated": True,
                "absent_days_count": 0,
                "calc_details": {
                    "hra": 620.0,
                    "da": 310.0,
                    "flat": 1250.0,
                    "pf": 744.0,
                    "pt": 124.0,
                    "lop": 0.0
                }
            },
            {
                "payroll_id": 203,
                "employee_db_id": 2003,
                "employee_id": "EMP-003",
                "name": "Rajesh Kumar",
                "email": "rajesh@gmail.com",
                "department": "Human Resources",
                "designation": "HR Specialist",
                "base_salary": 3800.00,
                "allowances": 1820.00,
                "deductions": 785.33,
                "net_pay": 4834.67,
                "status": "Paid",
                "payment_date": f"{month}-05T14:00:00",
                "is_generated": True,
                "absent_days_count": 2,
                "calc_details": {
                    "hra": 380.0,
                    "da": 190.0,
                    "flat": 1250.0,
                    "pf": 456.0,
                    "pt": 76.0,
                    "lop": 253.33
                }
            },
            {
                "payroll_id": None,
                "employee_db_id": 2004,
                "employee_id": "EMP-004",
                "name": "Sravani",
                "email": "sravani@gmail.com",
                "department": "Quality Assurance",
                "designation": "QA Engineer",
                "base_salary": 4000.00,
                "allowances": 1850.00,
                "deductions": 560.00,
                "net_pay": 5290.00,
                "status": "Pending",
                "payment_date": None,
                "is_generated": False,
                "absent_days_count": 0,
                "calc_details": {
                    "hra": 400.0,
                    "da": 200.0,
                    "flat": 1250.0,
                    "pf": 480.0,
                    "pt": 80.0,
                    "lop": 0.0
                }
            }
        ]
        
    return jsonify(ledger), 200

@payroll_bp.route("/api/payroll/process", methods=["POST"])
@require_role(["admin"])
def process_employee_payroll():
    """
    Simulates single employee payroll process run.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    emp_db_id = data.get("employee_db_id")
    month = data.get("month")
    
    if not emp_db_id or not month:
        return jsonify({"error": "Missing required payroll parameters"}), 400
        
    return jsonify({
        "message": "Payroll processed successfully (Demo Mode)", 
        "payroll_id": 9999
    }), 200

@payroll_bp.route("/api/payroll/bulk-process", methods=["POST"])
@require_role(["admin"])
def bulk_process_payroll():
    """
    Simulates bulk payroll processing run.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    month = data.get("month")
    
    if not month:
        return jsonify({"error": "Month parameter (YYYY-MM) is required"}), 400
        
    return jsonify({
        "message": "Successfully processed bulk payroll run for all active staff (Demo Mode)."
    }), 200
