"""
EduTech Module Blueprint Routes.

Handles public course lists, student enrollments, course pricing configurations,
and scheduling/retrieving course live classes (Zoom/Meet sessions).
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, require_role

edutech_bp = Blueprint("edutech", __name__)

# ==================== PUBLIC ENDPOINTS ====================

@edutech_bp.route("/api/edutech/courses", methods=["GET"])
def get_courses():
    """
    Returns a list of all active course offerings.
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
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
        return jsonify({"error": str(e)}), 500
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
            SELECT c.*, e.price_paid, e.enrolled_at, e.status as enrollment_status, e.id as enrollment_id
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
        return jsonify({"error": str(e)}), 500
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
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400
    
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
            INSERT INTO course_enrollments (user_id, course_id, price_paid)
            VALUES (%s, %s, %s) RETURNING id
        """, (user['id'], course_id, price))
        enrollment_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Enrolled successfully", "price_paid": price, "enrollment_id": enrollment_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
            SELECT e.id, e.price_paid, e.enrolled_at, e.status,
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
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
