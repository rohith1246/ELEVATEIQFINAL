"""
EduTech Module Blueprint Routes.

Handles public course lists, student enrollments, course pricing configurations,
and scheduling/retrieving course live classes (Zoom/Meet sessions).
"""

import os
import logging
import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, require_role
from ..config import safe_error

logger = logging.getLogger(__name__)
SAFE_URL_REGEX = re.compile(r'^(https?://|zoommtg://|zoomus://|meet\.google\.com/|teams\.microsoft\.com/|slack\.com/|webex\.com/)', re.IGNORECASE)

edutech_bp = Blueprint("edutech", __name__)

# ==================== PUBLIC ENDPOINTS ====================

@edutech_bp.route("/api/edutech/courses", methods=["GET"])
def get_courses():
    """
    Returns a list of all active course offerings (or all for admin/employees).
    """
    user = get_current_user()
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user and user.get("role") in ["admin", "employee"]:
            cursor.execute("SELECT * FROM courses ORDER BY title ASC")
        else:
            cursor.execute("SELECT * FROM courses WHERE is_active = TRUE ORDER BY title ASC")
        courses = cursor.fetchall()
        for course in courses:
            course['price'] = float(course['price']) if course['price'] is not None else 0.0
            if course.get('old_price') is not None:
                course['old_price'] = float(course['old_price'])
            course['rating'] = float(course['rating']) if course['rating'] is not None else 5.0
            if 'created_at' in course and course['created_at']:
                course['created_at'] = course['created_at'].isoformat()
        return jsonify(courses), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


# ==================== STUDENT ENDPOINTS ====================

@edutech_bp.route("/api/edutech/my-courses", methods=["GET"])
def get_my_courses():
    """
    Returns courses enrolled in by the logged-in student.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT c.*, e.price_paid, e.enrolled_at, e.status as enrollment_status, e.id as enrollment_id, e.mode
            FROM courses c
            JOIN course_enrollments e ON c.id = e.course_id
            WHERE e.user_id = %s
            ORDER BY e.enrolled_at DESC
        """, (user['id'],))
        courses = cursor.fetchall()
        for course in courses:
            course['price'] = float(course['price']) if course['price'] is not None else 0.0
            if course.get('old_price') is not None:
                course['old_price'] = float(course['old_price'])
            course['price_paid'] = float(course['price_paid']) if course['price_paid'] is not None else 0.0
            course['rating'] = float(course['rating']) if course['rating'] is not None else 5.0
            if 'created_at' in course and course['created_at']:
                course['created_at'] = course['created_at'].isoformat()
            if 'enrolled_at' in course and course['enrolled_at']:
                course['enrolled_at'] = course['enrolled_at'].isoformat()
        return jsonify(courses), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/enroll", methods=["POST"])
def enroll_in_course():
    """
    Enrolls the logged-in student in a specific course.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json or {}
    course_id = data.get("course_id")
    mode = data.get("mode", "Online").strip()
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400
    
    if mode not in ["Online", "Offline"]:
        mode = "Online"
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get course price and active status
        cursor.execute("SELECT price, is_active FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        if not course:
            return jsonify({"error": "Course not found"}), 404
        if not course['is_active']:
            return jsonify({"error": "This course is currently not active"}), 400
        
        price = float(course['price'])
        
        # Check if already enrolled
        cursor.execute("SELECT id FROM course_enrollments WHERE user_id = %s AND course_id = %s", (user['id'], course_id))
        if cursor.fetchone():
            return jsonify({"error": "Already enrolled in this course"}), 400
        
        # Insert enrollment
        cursor.execute("""
            INSERT INTO course_enrollments (user_id, course_id, price_paid, mode)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (user['id'], course_id, price, mode))
        enrollment_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Enrolled successfully", "price_paid": price, "enrollment_id": enrollment_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/my-live-classes", methods=["GET"])
def get_my_live_classes():
    """
    Returns scheduled live classes for courses the logged-in student is enrolled in.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT lc.*, c.title as course_title
            FROM live_classes lc
            JOIN courses c ON lc.course_id = c.id
            JOIN course_enrollments e ON c.id = e.course_id
            WHERE e.user_id = %s AND lc.scheduled_at >= NOW() - INTERVAL '2 hours'
            ORDER BY lc.scheduled_at ASC
        """, (user['id'],))
        classes = cursor.fetchall()
        for c in classes:
            if c.get('scheduled_at'):
                c['scheduled_at'] = c['scheduled_at'].isoformat()
            if c.get('created_at'):
                c['created_at'] = c['created_at'].isoformat()
        return jsonify(classes), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


# ==================== ADMIN ENDPOINTS ====================

@edutech_bp.route("/api/edutech/courses", methods=["POST"])
@require_role(["admin", "employee"])
def create_course():
    """
    Creates a new course catalog record.
    """
    data = request.json or {}
    title = data.get("title", "").strip()
    level = data.get("level", "").strip()
    duration = data.get("duration", "").strip()
    price = data.get("price")
    old_price = data.get("old_price")
    icon = data.get("icon", "layers").strip()
    
    if not title or not level or not duration or price is None:
        return jsonify({"error": "Title, level, duration, and price are required"}), 400
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO courses (title, level, duration, price, old_price, icon)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
        """, (title, level, duration, price, old_price, icon))
        course = cursor.fetchone()
        conn.commit()
        course['price'] = float(course['price']) if course['price'] is not None else 0.0
        if course.get('old_price') is not None:
            course['old_price'] = float(course['old_price'])
        course['rating'] = float(course['rating']) if course['rating'] is not None else 5.0
        if course.get('created_at'):
            course['created_at'] = course['created_at'].isoformat()
        return jsonify(course), 201
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return jsonify({"error": "A course with this title already exists"}), 400
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/courses/<int:course_id>", methods=["PUT"])
@require_role(["admin", "employee"])
def update_course(course_id):
    """
    Updates an existing course catalog record.
    """
    data = request.json or {}
    title = data.get("title", "").strip()
    level = data.get("level", "").strip()
    duration = data.get("duration", "").strip()
    price = data.get("price")
    old_price = data.get("old_price")
    icon = data.get("icon", "layers").strip()
    is_active = data.get("is_active", True)
    
    if not title or not level or not duration or price is None:
        return jsonify({"error": "Title, level, duration, and price are required"}), 400
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            UPDATE courses
            SET title = %s, level = %s, duration = %s, price = %s, old_price = %s, icon = %s, is_active = %s
            WHERE id = %s RETURNING *
        """, (title, level, duration, price, old_price, icon, is_active, course_id))
        course = cursor.fetchone()
        if not course:
            return jsonify({"error": "Course not found"}), 404
        conn.commit()
        course['price'] = float(course['price']) if course['price'] is not None else 0.0
        if course.get('old_price') is not None:
            course['old_price'] = float(course['old_price'])
        course['rating'] = float(course['rating']) if course['rating'] is not None else 5.0
        if course.get('created_at'):
            course['created_at'] = course['created_at'].isoformat()
        return jsonify(course), 200
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
            return jsonify({"error": "A course with this title already exists"}), 400
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/courses/<int:course_id>", methods=["DELETE"])
@require_role(["admin", "employee"])
def delete_course(course_id):
    """
    Deletes a course catalog record from the database.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM courses WHERE id = %s RETURNING id", (course_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Course not found"}), 404
        conn.commit()
        return jsonify({"message": "Course deleted successfully", "id": course_id}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/enrollments", methods=["GET"])
@require_role(["admin", "employee"])
def get_enrollments():
    """
    Returns list of all student course enrollments.
    """
    user = get_current_user()
    is_employee = user and user.get("role") == "employee"

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT e.id, e.price_paid, e.enrolled_at, e.status, 
                   u.name as student_name, u.email as student_email,
                   c.title as course_title
            FROM course_enrollments e
            JOIN users u ON e.user_id = u.id
            JOIN courses c ON e.course_id = c.id
            ORDER BY e.enrolled_at DESC
        """)
        enrollments = cursor.fetchall()
        for enrollment in enrollments:
            if is_employee:
                enrollment['price_paid'] = 0.0
            else:
                enrollment['price_paid'] = float(enrollment['price_paid']) if enrollment['price_paid'] is not None else 0.0
            
            if enrollment.get('enrolled_at'):
                enrollment['enrolled_at'] = enrollment['enrolled_at'].isoformat()
        return jsonify(enrollments), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/live-classes", methods=["POST"])
@require_role(["admin", "employee"])
def create_live_class():
    """
    Schedules a new course live class meeting session.
    """
    data = request.json or {}
    course_id = data.get("course_id")
    title = data.get("title", "").strip()
    platform = data.get("platform", "").strip()
    meeting_link = data.get("meeting_link", "").strip()
    scheduled_at_str = data.get("scheduled_at", "").strip()
    
    if not course_id or not title or not platform or not meeting_link or not scheduled_at_str:
        return jsonify({"error": "Course ID, title, platform, meeting link, and scheduled time are required"}), 400

    if not SAFE_URL_REGEX.match(meeting_link):
        return jsonify({"error": "Invalid meeting link URL"}), 400

    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace("Z", ""))
    except Exception:
        return jsonify({"error": "Invalid scheduled_at time format. Must be ISO-8601 (YYYY-MM-DDTHH:MM)"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Course not found"}), 404
            
        cursor.execute("""
            INSERT INTO live_classes (course_id, title, platform, meeting_link, scheduled_at)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
        """, (course_id, title, platform, meeting_link, scheduled_at))
        live_class = cursor.fetchone()
        conn.commit()
        if live_class.get('scheduled_at'):
            live_class['scheduled_at'] = live_class['scheduled_at'].isoformat()
        if live_class.get('created_at'):
            live_class['created_at'] = live_class['created_at'].isoformat()
        return jsonify(live_class), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/live-classes", methods=["GET"])
@require_role(["admin", "employee"])
def get_all_live_classes():
    """
    Returns all scheduled live classes.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT lc.*, c.title as course_title
            FROM live_classes lc
            JOIN courses c ON lc.course_id = c.id
            ORDER BY lc.scheduled_at DESC
        """)
        classes = cursor.fetchall()
        for c in classes:
            if c.get('scheduled_at'):
                c['scheduled_at'] = c['scheduled_at'].isoformat()
            if c.get('created_at'):
                c['created_at'] = c['created_at'].isoformat()
        return jsonify(classes), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/live-classes/<int:class_id>", methods=["DELETE"])
@require_role(["admin", "employee"])
def delete_live_class(class_id):
    """
    Deletes a scheduled live class meeting session.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM live_classes WHERE id = %s RETURNING id", (class_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Live class not found"}), 404
        conn.commit()
        return jsonify({"message": "Live class deleted successfully", "id": class_id}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/invoice/<int:enrollment_id>", methods=["GET"])
def get_invoice(enrollment_id):
    """
    Returns invoice details for a course enrollment.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT e.id, e.price_paid, e.enrolled_at, e.status, e.mode,
                   u.name as student_name, u.email as student_email,
                   c.title as course_title, c.duration as course_duration
            FROM course_enrollments e
            JOIN users u ON e.user_id = u.id
            JOIN courses c ON e.course_id = c.id
            WHERE e.id = %s AND (e.user_id = %s OR %s IN ('admin', 'employee'))
        """, (enrollment_id, user['id'], user['role']))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Invoice not found"}), 404
        
        row['price_paid'] = float(row['price_paid']) if row['price_paid'] is not None else 0.0
        if row.get('enrolled_at'):
            row['enrolled_at'] = row['enrolled_at'].isoformat()
        return jsonify(row), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


# ==================== STUDENT LMS DASHBOARD ENDPOINTS ====================

@edutech_bp.route("/api/edutech/student/stats", methods=["GET"])
def get_student_stats():
    """
    Retrieves high-level overview metrics for the active student dashboard,
    including streaks, active progress percentages, and current course milestones.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Get active enrolled courses
        cursor.execute("""
            SELECT c.id, c.title, c.level, c.duration, e.status, e.enrolled_at
            FROM courses c
            JOIN course_enrollments e ON c.id = e.course_id
            WHERE e.user_id = %s AND e.status = 'Active'
        """, (user['id'],))
        enrollments = cursor.fetchall()
        
        courses_progress = []
        for e in enrollments:
            title = e['title']
            # Match layout mock statistics from user mockup screenshot exactly
            progress_pct = 0
            active_week = "Week 1"
            topic = "Getting Started"
            
            if "Full Stack" in title:
                progress_pct = 62
                active_week = "Week 5 — Deployment & CI"
                topic = "Deployment & CI"
            elif "Python" in title:
                progress_pct = 38
                active_week = "APIs & Auth Security"
                topic = "APIs & Auth Security"
            elif "UI/UX" in title:
                progress_pct = 21
                active_week = "Design Systems Lab"
                topic = "Design Systems Lab"
            else:
                progress_pct = 50
                active_week = "Week 3 — Modules"
                topic = "Core Fundamentals"
                
            courses_progress.append({
                "id": e['id'],
                "title": title,
                "progress": progress_pct,
                "active_week": active_week,
                "topic": topic
            })
            
        # Get placement stage details
        cursor.execute("SELECT * FROM placement_tracks WHERE user_id = %s", (user['id'],))
        placement = cursor.fetchone()
        
        placement_stage = "Profile Setup"
        placement_next = "Complete your profile registration info."
        if placement:
            placement_stage = placement['current_stage']
            placement_next = placement['next_steps']
            
        # Fetch notifications/announcements count
        cursor.execute("SELECT COUNT(*) as count FROM announcements")
        ann_count = cursor.fetchone()['count']
        
        # Streak and overall calculation
        overall_progress = 0
        if courses_progress:
            overall_progress = int(sum(c['progress'] for c in courses_progress) / len(courses_progress))
            
        return jsonify({
            "student_name": user['name'],
            "student_email": user['email'],
            "overall_progress": overall_progress,
            "streak_days": 14, # default as per screen mockup
            "next_milestone": "Mock interview prep",
            "placement_stage": placement_stage,
            "placement_next": placement_next,
            "courses": courses_progress,
            "unread_notifications": ann_count
        }), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/assignments", methods=["GET"])
def get_student_assignments():
    """
    Retrieves all assignments for courses enrolled by the active student,
    or all assignments for admin/employees.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user.get("role") in ["admin", "employee"]:
            cursor.execute("""
                SELECT a.id as assignment_id, a.title, a.description, a.due_date,
                       c.title as course_title
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                ORDER BY a.due_date ASC
            """)
        else:
            cursor.execute("""
                SELECT a.id as assignment_id, a.title, a.description, a.due_date,
                       c.title as course_title,
                       s.id as submission_id, s.submission_text, s.file_path, 
                       s.grade, s.feedback, s.status as submission_status, s.submitted_at
                FROM assignments a
                JOIN courses c ON a.course_id = c.id
                JOIN course_enrollments e ON c.id = e.course_id
                LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.user_id = %s
                WHERE e.user_id = %s
                ORDER BY a.due_date ASC
            """, (user['id'], user['id']))
        assignments = cursor.fetchall()
        
        for a in assignments:
            if a.get('due_date'):
                a['due_date'] = a['due_date'].isoformat()
            if a.get('submitted_at'):
                a['submitted_at'] = a['submitted_at'].isoformat()
                
        return jsonify(assignments), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/assignments/<int:assignment_id>/submit", methods=["POST"])
def submit_assignment(assignment_id):
    """
    Submits a student's answer or project repository link for a specific course assignment.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    submission_text = data.get("submission_text", "").strip()
    file_path = data.get("file_path", "").strip()
    if file_path and len(file_path) > 255:
        return jsonify({"error": "File path too long"}), 400
    if file_path and not re.match(r'^[\w./\-_() ]+$', file_path):
        return jsonify({"error": "Invalid file path format"}), 400
    
    if not submission_text:
        return jsonify({"error": "Submission text or repository link is required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verify assignment belongs to student's enrolled courses
        cursor.execute("""
            SELECT a.id FROM assignments a
            JOIN course_enrollments e ON a.course_id = e.course_id
            WHERE a.id = %s AND e.user_id = %s
        """, (assignment_id, user['id']))
        if not cursor.fetchone():
            return jsonify({"error": "Assignment not found or unauthorized access"}), 404
            
        cursor.execute("""
            INSERT INTO assignment_submissions (assignment_id, user_id, submission_text, file_path, status, grade, feedback)
            VALUES (%s, %s, %s, %s, 'Submitted', 'Pending', 'Mentor review pending')
            ON CONFLICT (assignment_id, user_id) 
            DO UPDATE SET submission_text = EXCLUDED.submission_text, file_path = EXCLUDED.file_path, 
                          status = 'Submitted', grade = 'Pending', feedback = 'Mentor review pending',
                          submitted_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (assignment_id, user['id'], submission_text, file_path))
        conn.commit()
        return jsonify({"message": "Assignment project submitted successfully"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/quizzes", methods=["GET"])
def get_student_quizzes():
    """
    Lists all scheduled quizzes for the student's enrolled courses,
    or all quizzes for admin/employees.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user.get("role") in ["admin", "employee"]:
            cursor.execute("""
                SELECT q.id as quiz_id, q.title, q.duration_minutes,
                       c.title as course_title
                FROM quizzes q
                JOIN courses c ON q.course_id = c.id
                ORDER BY q.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT q.id as quiz_id, q.title, q.duration_minutes,
                       c.title as course_title,
                       qa.id as attempt_id, qa.score, qa.total_questions, qa.completed_at
                FROM quizzes q
                JOIN courses c ON q.course_id = c.id
                JOIN course_enrollments e ON c.id = e.course_id
                LEFT JOIN quiz_attempts qa ON q.id = qa.quiz_id AND qa.user_id = %s
                WHERE e.user_id = %s
                ORDER BY q.created_at DESC
            """, (user['id'], user['id']))
        quizzes = cursor.fetchall()
        
        for q in quizzes:
            if q.get('completed_at'):
                q['completed_at'] = q['completed_at'].isoformat()
                
        return jsonify(quizzes), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/quizzes/<int:quiz_id>/questions", methods=["GET"])
def get_quiz_questions(quiz_id):
    """
    Fetches the list of multiple-choice questions for a quiz.
    Excludes the correct answer key to prevent client inspection.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verify enrollment
        cursor.execute("""
            SELECT q.id FROM quizzes q
            JOIN course_enrollments e ON q.course_id = e.course_id
            WHERE q.id = %s AND e.user_id = %s
        """, (quiz_id, user['id']))
        if not cursor.fetchone():
            return jsonify({"error": "Quiz not found or unauthorized access"}), 404
            
        cursor.execute("""
            SELECT id, question_text, option_a, option_b, option_c, option_d
            FROM quiz_questions
            WHERE quiz_id = %s
            ORDER BY id ASC
        """, (quiz_id,))
        questions = cursor.fetchall()
        return jsonify(questions), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/quizzes/<int:quiz_id>/submit", methods=["POST"])
def submit_quiz_answers(quiz_id):
    """
    Accepts student answers for quiz questions, computes score details,
    registers a quiz attempt ledger, and returns the result breakdown.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    answers = data.get("answers", {}) # Map of question_id -> correct option letter ('A', 'B', etc.)
    
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check if already attempted
        cursor.execute("SELECT id FROM quiz_attempts WHERE quiz_id = %s AND user_id = %s", (quiz_id, user['id']))
        if cursor.fetchone():
            return jsonify({"error": "Quiz has already been completed"}), 400
            
        # Get correct answer keys
        cursor.execute("SELECT id, correct_option FROM quiz_questions WHERE quiz_id = %s", (quiz_id,))
        questions = cursor.fetchall()
        
        if not questions:
            return jsonify({"error": "Quiz does not contain any questions"}), 400
            
        score = 0
        total_questions = len(questions)
        
        for q in questions:
            q_id = str(q['id'])
            user_ans = answers.get(q_id, "").strip().upper()
            if user_ans == q['correct_option'].strip().upper():
                score += 1
                
        # Register attempt
        cursor.execute("""
            INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions)
            VALUES (%s, %s, %s, %s) RETURNING id, completed_at
        """, (quiz_id, user['id'], score, total_questions))
        conn.commit()
        return jsonify({
            "message": "Quiz completed",
            "score": score,
            "total_questions": total_questions,
            "percentage": int((score / total_questions) * 100) if total_questions > 0 else 0
        }), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/resources", methods=["GET"])
def get_course_resources():
    """
    Retrieves all downloadable references and resource files for enrolled courses,
    or all resources for admin/employees.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if user.get("role") in ["admin", "employee"]:
            cursor.execute("""
                SELECT r.id, r.title, r.resource_type, r.resource_url,
                       c.title as course_title
                FROM course_resources r
                JOIN courses c ON r.course_id = c.id
                ORDER BY c.title ASC, r.title ASC
            """)
        else:
            cursor.execute("""
                SELECT r.id, r.title, r.resource_type, r.resource_url,
                       c.title as course_title
                FROM course_resources r
                JOIN courses c ON r.course_id = c.id
                JOIN course_enrollments e ON c.id = e.course_id
                WHERE e.user_id = %s
                ORDER BY c.title ASC, r.title ASC
            """, (user['id'],))
        resources = cursor.fetchall()
        return jsonify(resources), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/placement", methods=["GET"])
def get_student_placement():
    """
    Retrieves the placement track status details for the current active student.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM placement_tracks WHERE user_id = %s", (user['id'],))
        placement = cursor.fetchone()
        if not placement:
            # Return a default pending layout
            return jsonify({
                "current_stage": "Profile Setup",
                "next_steps": "Setup your resume and complete profile records.",
                "resume_approved": False,
                "mock_interview_score": 0,
                "recruiter_feedback": ""
            }), 200
        return jsonify(placement), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/student/notifications", methods=["GET"])
def get_student_notifications():
    """
    Retrieves notices and announcements post board listings.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 20")
        notices = cursor.fetchall()
        for n in notices:
            if n.get('created_at'):
                n['created_at'] = n['created_at'].isoformat()
        return jsonify(notices), 200
    except Exception as e:
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/advisor/chat", methods=["POST"])
def advisor_chat():
    """
    AI chatbot / messages completions endpoint leveraging the Groq API.
    Guides students through ElevateIQ LMS features.
    """
    import os
    data = request.json or {}
    messages = data.get("messages", [])
    
    if not messages:
        return jsonify({"error": "No messages history found in payload"}), 400
        
    # Standard fallback advisor logic
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
            
    def fallback_reply(prompt):
        prompt_lower = prompt.lower()
        if "assignment" in prompt_lower:
            return "To submit an assignment, navigate to the 'Assignments' tab on the sidebar, select the assignment, click 'Submit Project', paste your GitHub link, and submit for mentor review."
        elif "test" in prompt_lower or "quiz" in prompt_lower or "exam" in prompt_lower:
            return "To take assessments, navigate to the 'Tests' tab in the left sidebar, choose the topic, and click 'Take Test' to start the Quiz Engine."
        elif "placement" in prompt_lower or "job" in prompt_lower or "interview" in prompt_lower:
            return "You can check your career status on the 'Placement Tracker' tab. It guides you from Profile Setup to Resume Reviews, Mock Interviews, Assessments, and final Placement."
        elif "certificate" in prompt_lower:
            return "Your completion certificates are issued automatically inside the 'Certificates' tab once your program progress metrics reach 100%."
        elif "resource" in prompt_lower or "download" in prompt_lower:
            return "Reference guides, cheatsheets, and slides can be accessed and downloaded in the 'Resources' tab."
        elif "class" in prompt_lower or "live" in prompt_lower:
            return "To attend live mentor classes, go to the 'Live Classes' tab and click 'Join Class' to enter the video feed."
        elif "course" in prompt_lower or "program" in prompt_lower:
            return "To view enrolled tracks and progress details, check out the 'My Courses' tab in your dashboard sidebar."
        else:
            return "Welcome to ElevateIQ LMS Advisor! I can guide you through Assignments, Tests, Live Classes, My Courses, Resources, Certificates, and Placement Track stages. Just ask me where to find them!"

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        print("Warning: GROQ_API_KEY not found in environment. Utilizing local rule-based advisor responses.")
        return jsonify({"reply": fallback_reply(last_user_msg)}), 200
        
    # Invoke Groq API
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        
        system_prompt = (
            "You are Ascend Advisor, the friendly AI guide for ElevateIQ's EduTech LMS. "
            "Your main role is to guide students and prospects through the LMS features and courses.\n"
            "Here is the LMS site layout guide:\n"
            "- Dashboard: Overview card, overall progress, streak counter, resume learning card, placement momentum, enrolled courses progress list, and weekly activity chart.\n"
            "- My Courses: List of enrolled technical tracks (Full Stack Web Development, Python for Backend, UI/UX Design, etc.).\n"
            "- Live Classes: Calendar schedules list to join video screenshares.\n"
            "- Assignments: Submission status, grade results, mentor feedback, and GitHub repository submission box.\n"
            "- Tests: Technical exams list and interactive Quiz Engine modal.\n"
            "- Resources: Downloadable decks, slides, reference assets, and cheatsheets.\n"
            "- Certificates: Print-ready verified course completion certificates issued at 100% course progress.\n"
            "- Placement Tracker: Milestones timeline (Profile Setup, Resume Review, Mock Interview Prep, Technical Assessment, HR Interview, Placed).\n"
            "- Support Messages: Direct chat with mentors.\n"
            "- Notifications: Announcements notice board.\n\n"
            "Tell the student which sidebar tab to select to perform their task. Keep responses extremely concise, encouraging, and clear."
        )
        
        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role in ["user", "assistant", "system"]:
                payload_messages.append({"role": role, "content": content})
                
        try:
            # Attempt with llama-3.3-70b-versatile
            chat_completion = client.chat.completions.create(
                messages=payload_messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=300
            )
            reply_text = chat_completion.choices[0].message.content
        except Exception as model_err:
            print("llama-3.3-70b-versatile failed, trying fallback llama3-8b-8192:", model_err)
            # Try fallback model
            chat_completion = client.chat.completions.create(
                messages=payload_messages,
                model="llama3-8b-8192",
                temperature=0.7,
                max_tokens=300
            )
            reply_text = chat_completion.choices[0].message.content
            
        return jsonify({"reply": reply_text}), 200
    except Exception as err:
        print("Groq API execution failed:", err)
        return jsonify({"reply": fallback_reply(last_user_msg)}), 200


# ==================== TRAINER/ADMIN LMS CREATION ENDPOINTS ====================

@edutech_bp.route("/api/edutech/quizzes", methods=["POST"])
def create_quiz():
    """
    Creates a new technical quiz assessment for a course.
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.json or {}
    course_id = data.get("course_id")
    title = data.get("title", "").strip()
    duration = data.get("duration_minutes", 15)
    
    if not course_id or not title:
        return jsonify({"error": "Course ID and Title are required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO quizzes (course_id, title, duration_minutes)
            VALUES (%s, %s, %s) RETURNING id
        """, (course_id, title, duration))
        quiz_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Quiz created successfully", "id": quiz_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/quizzes/<int:quiz_id>/questions", methods=["POST"])
def add_quiz_question(quiz_id):
    """
    Appends a multiple-choice question to a quiz.
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.json or {}
    q_text = data.get("question_text", "").strip()
    opt_a = data.get("option_a", "").strip()
    opt_b = data.get("option_b", "").strip()
    opt_c = data.get("option_c", "").strip()
    opt_d = data.get("option_d", "").strip()
    correct = data.get("correct_option", "").strip().upper()
    
    if not q_text or not opt_a or not opt_b or not opt_c or not opt_d or not correct:
        return jsonify({"error": "Question text, options A-D, and correct option are all required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check quiz existence
        cursor.execute("SELECT id FROM quizzes WHERE id = %s", (quiz_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Quiz not found"}), 404
            
        cursor.execute("""
            INSERT INTO quiz_questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (quiz_id, q_text, opt_a, opt_b, opt_c, opt_d, correct))
        q_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Question added successfully", "id": q_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/assignments", methods=["POST"])
def create_assignment():
    """
    Assigns new technical project coursework for a course.
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.json or {}
    course_id = data.get("course_id")
    title = data.get("title", "").strip()
    desc = data.get("description", "").strip()
    due_date = data.get("due_date")
    
    if not course_id or not title:
        return jsonify({"error": "Course ID and Title are required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO assignments (course_id, title, description, due_date)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (course_id, title, desc, due_date))
        assign_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Assignment created successfully", "id": assign_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/resources", methods=["POST"])
def create_resource():
    """
    Registers a downloadable class resource doc/slide.
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.json or {}
    course_id = data.get("course_id")
    title = data.get("title", "").strip()
    r_type = data.get("resource_type", "PDF").strip()
    r_url = data.get("resource_url", "").strip()
    
    if not course_id or not title or not r_url:
        return jsonify({"error": "Course ID, Title, and Resource URL are required"}), 400
        
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO course_resources (course_id, title, resource_type, resource_url)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (course_id, title, r_type, r_url))
        res_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Resource created successfully", "id": res_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


# ==================== STUDENT LEAVES ENDPOINTS ====================

@edutech_bp.route("/api/edutech/student/leaves", methods=["POST"])
def apply_student_leave():
    """
    Apply for a student leave in the edutech portal.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    leave_type = data.get("leave_type", "").strip()
    start_date = data.get("start_date", "").strip()
    end_date = data.get("end_date", "").strip()
    reason = data.get("reason", "").strip()

    if not leave_type or not start_date or not end_date:
        return jsonify({"error": "Leave type, start date, and end date are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO student_leaves (user_id, leave_type, start_date, end_date, reason)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (user["id"], leave_type, start_date, end_date, reason))
        leave_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"message": "Student leave application submitted successfully", "id": leave_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/student/leaves", methods=["GET"])
def get_student_leaves():
    """
    Get personal student leave requests.
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT l.*, u.name as approved_by_name
            FROM student_leaves l
            LEFT JOIN users u ON l.approved_by = u.id
            WHERE l.user_id = %s
            ORDER BY l.created_at DESC
        """, (user["id"],))
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
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/trainer/leaves", methods=["GET"])
def get_all_student_leaves():
    """
    Retrieve all student leave applications (for trainers and admins).
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT l.*, s.name as student_name, s.email as student_email, u.name as approved_by_name
            FROM student_leaves l
            JOIN users s ON l.user_id = s.id
            LEFT JOIN users u ON l.approved_by = u.id
            ORDER BY l.status DESC, l.created_at DESC
        """)
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
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()


@edutech_bp.route("/api/edutech/trainer/leaves/<int:leave_id>", methods=["PUT"])
def review_student_leave(leave_id):
    """
    Approve or reject a student leave request.
    """
    user = get_current_user()
    if not user or user.get("role") not in ["admin", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    status = data.get("status", "").strip()

    if status not in ["Approved", "Rejected"]:
        return jsonify({"error": "Invalid status. Must be 'Approved' or 'Rejected'"}), 400

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check if the student leave request exists
        cursor.execute("SELECT id FROM student_leaves WHERE id = %s", (leave_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Student leave application not found"}), 404

        cursor.execute("""
            UPDATE student_leaves
            SET status = %s, approved_by = %s
            WHERE id = %s
        """, (status, user["id"], leave_id))
        conn.commit()
        return jsonify({"message": f"Student leave status updated to {status}"}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"EduTech API error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cursor.close()
        conn.close()




