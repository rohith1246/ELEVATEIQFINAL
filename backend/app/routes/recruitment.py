import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename
from ..database import get_connection
from ..auth import get_current_user, check_is_recruitment_manager

recruitment_bp = Blueprint("recruitment", __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@recruitment_bp.route("/jobs", methods=["GET"])
def get_jobs():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
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


@recruitment_bp.route("/jobs", methods=["POST"])
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


@recruitment_bp.route("/jobs/<int:job_id>", methods=["PUT"])
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


@recruitment_bp.route("/applications", methods=["GET"])
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


@recruitment_bp.route("/applications", methods=["POST"])
def submit_application():
    job_id = request.form.get("job_id")
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    file = request.files.get("resume")

    if not job_id or not name or not email or not file:
        return jsonify({"error": "Missing required application parameters"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file format. Only PDF, DOC, and DOCX files are allowed."}), 400

    # Clean file and save
    filename = secure_filename(f"{int(datetime.now().timestamp())}_{file.filename}")
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
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


@recruitment_bp.route("/applications/<int:app_id>", methods=["PUT"])
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


@recruitment_bp.route("/uploads/resumes/<filename>")
def download_resume(filename):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if not check_is_recruitment_manager(user, cursor):
            return jsonify({"error": "Forbidden"}), 403
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
    finally:
        cursor.close()
        conn.close()
