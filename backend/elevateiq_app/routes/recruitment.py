"""
Recruitment and Careers blueprint routes.

Manages job openings and career applications. Handles uploading and downloading candidate 
resumes, verifying file extension limits, parsing multipart form-data, cleaning storage 
on database connection failures, and managing workflow states (Pending, Shortlisted, 
Accepted, Rejected).
"""

import os
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename
from ..database import get_connection
from ..auth import get_current_user, check_is_recruitment_manager, rate_limit
from ..config import safe_error

logger = logging.getLogger(__name__)

recruitment_bp = Blueprint("recruitment", __name__)

# Permitted file formats for candidate resume uploads
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}

MIME_MAGIC = {
    b'%PDF': 'pdf',
    b'\x50\x4B\x03\x04': 'docx',
    b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1': 'doc',
}

def allowed_file(filename, file_stream=None):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if file_stream:
        magic = file_stream.read(8)
        file_stream.seek(0)
        for sig, expected_ext in MIME_MAGIC.items():
            if magic.startswith(sig):
                return ext == expected_ext
    return True

@recruitment_bp.route("/jobs", methods=["GET"])
def get_jobs():
    """
    Fetches job listings from the database.

    Administrators and recruitment managers retrieve all jobs (including Closed positions).
    Standard guests or candidates retrieve only 'Open' job openings.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of job objects with serialized timestamps.
            - 500: Database select exception.
    """
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
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/jobs", methods=["POST"])
def create_job():
    """
    Creates a new job opening position.
    Restricted to recruitment managers and admins.

    JSON Parameters:
        title (str): Title name of the opening.
        department (str): Corporate department.
        experience_required (str, optional): Target experience years description.
        skills_required (str, optional): Key skills description.
        location (str, optional): Work location (e.g. Remote, City).
        salary_range (str, optional): Compensation description.
        description (str, optional): Job responsibility details.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success message.
            - 400: Missing title or department parameters.
            - 401/403: Security errors.
            - 500: Database insertion exceptions.
    """
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
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    """
    Updates the availability status of a job posting.
    Restricted to recruitment managers and admins.

    Args:
        job_id (int): Primary key ID of the job posting to update.

    JSON Parameters:
        status (str): The target job status ('Open' or 'Closed').

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success status update.
            - 400: Invalid status value.
            - 401/403: Security errors.
            - 500: Database update exceptions.
    """
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
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/applications", methods=["GET"])
def get_applications():
    """
    Lists job applications.

    - Recruitment managers: Fetch all applications.
    - Candidates: Fetch applications associated with their email address.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Array of job applications with serialized dates.
            - 401: Unauthorized.
            - 500: Database lookup query exceptions.
    """
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
            # Candidates query their application logs matching their verified email
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
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/applications", methods=["POST"])
@rate_limit(limit=3, period=60)
def submit_application():
    """
    Submits a career application. Handles resume uploads.
    Rate limited to 3 applications per minute.

    Multipart Form-Data Parameters:
        job_id (str/int): The ID of the target job posting.
        name (str): Candidate's full name.
        email (str): Candidate's contact email.
        phone (str, optional): Candidate's contact phone number.
        resume (File): PDF/DOC/DOCX resume file stream.

    Returns:
        tuple: (JSON response, HTTP status code)
            - 201: Success creation message.
            - 400: Missing/invalid parameters or unsupported file format.
            - 404: Job posting not found.
            - 500: Database insertion exceptions.
    """
    job_id = request.form.get("job_id")
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    file = request.files.get("resume")

    if not job_id or not name or not email or not file:
        return jsonify({"error": "Missing required application parameters"}), 400

    try:
        job_id = int(job_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid job_id"}), 400

    if not allowed_file(file.filename, file.stream):
        return jsonify({"error": "Unsupported file format. Only PDF, DOC, and DOCX files are allowed."}), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Verify job exists
        cursor.execute("SELECT id FROM jobs WHERE id = %s", (job_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Job posting not found"}), 404

        # Generate unique secure filename using UUID to prevent enumeration
        import uuid
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else ""
        filename = secure_filename(f"{uuid.uuid4().hex}.{ext}") if ext else secure_filename(f"{uuid.uuid4().hex}")
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

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
        # Delete uploaded file to prevent orphan files if DB transaction fails
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass  # already removed — race avoided
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/applications/<int:app_id>", methods=["PUT"])
def update_application_status(app_id):
    """
    Updates status details of a job application.
    Restricted to recruitment managers and admins.

    Args:
        app_id (int): Primary key ID of the application to review.

    JSON Parameters:
        status (str): Workflow status ('Pending', 'Shortlisted', 'Accepted', 'Rejected').

    Returns:
        tuple: (JSON response, HTTP status code)
            - 200: Success status change message.
            - 400: Invalid application status value.
            - 401/403: Security errors.
            - 500: Database update exceptions.
    """
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
        logger.error(f"Recruitment API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@recruitment_bp.route("/uploads/resumes/<filename>")
def download_resume(filename):
    """
    Serves resume files from the uploads directory.
    Restricted to recruitment managers and admins.

    Args:
        filename (str): The secure name of the target resume file.

    Returns:
        Response: Resume file stream.
    """
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

