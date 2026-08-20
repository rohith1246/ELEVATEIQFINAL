"""
Assessment Blueprint - Job Assessment System.

Routes:
  GET  /api/assessment/take/<token>        - validate token, return questions (no answers)
  POST /api/assessment/start/<token>       - mark In Progress, record screen_share_granted
  POST /api/assessment/submit/<token>      - score answers, mark Completed, send email
  POST /api/assessment/tab-switch/<token>  - increment tab_switches, auto-submit if > 3
  GET  /api/assessment/all                 - admin: list all assessments
  GET  /api/assessment/questions           - admin: list questions (filter by job_id)
  POST /api/assessment/questions           - admin: create question
  PUT  /api/assessment/questions/<id>      - admin: edit question
  DELETE /api/assessment/questions/<id>    - admin: delete question
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor
from ..database import get_connection
from ..auth import get_current_user, rate_limit
from ..config import safe_error
from ..utils.mailer import send_completion_email
import secrets
import csv
import io
from flask import Response
from ..utils.code_sandbox import execute_testcase, execute_testcase_suite

logger = logging.getLogger(__name__)
assessment_bp = Blueprint("assessment", __name__, url_prefix="/api/assessment")


def _now():
    return datetime.now(timezone.utc)


def _get_assessment_by_token(cursor, token):
    cursor.execute("""
        SELECT a.*, ap.candidate_name, ap.email, ap.job_id,
               j.title as job_title
        FROM assessments a
        JOIN applications ap ON a.application_id = ap.id
        JOIN jobs j ON ap.job_id = j.id
        WHERE a.token = %s
    """, (token,))
    return cursor.fetchone()


# ─── PUBLIC ROUTES (no auth - token-based) ─────────────────────────────────

@assessment_bp.route("/take/<token>", methods=["GET"])
@rate_limit(limit=30, period=60)
def take_assessment(token):
    """Return assessment metadata + questions (options only, no correct answers)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _get_assessment_by_token(cur, token)
        if not row:
            return jsonify({"error": "Assessment not found. Check your link."}), 404

        if row["status"] == "Completed":
            return jsonify({"error": "This assessment has already been submitted."}), 410
        if row["status"] == "Expired":
            return jsonify({"error": "This assessment link has expired."}), 410

        # Check expiry
        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            from datetime import timezone as tz
            expires_at = expires_at.replace(tzinfo=tz.utc)
        if _now() > expires_at:
            cur.execute("UPDATE assessments SET status='Expired' WHERE token=%s", (token,))
            conn.commit()
            return jsonify({"error": "This assessment link has expired (72-hour window passed)."}), 410

        # Fetch questions for this job (job-specific first, then global fallback)
        job_id = row["job_id"]
        cur.execute("""
            SELECT id, question_text, option_a, option_b, option_c, option_d, difficulty
            FROM assessment_questions
            WHERE job_id = %s
            ORDER BY id
        """, (job_id,))
        questions = cur.fetchall()

        # Fallback to global questions if job has none
        if not questions:
            cur.execute("""
                SELECT id, question_text, option_a, option_b, option_c, option_d, difficulty
                FROM assessment_questions
                WHERE job_id IS NULL
                ORDER BY id
            """)
            questions = cur.fetchall()

        return jsonify({
            "assessment_id": row["id"],
            "status": row["status"],
            "candidate_name": row["candidate_name"],
            "job_title": row["job_title"],
            "tab_switches": row["tab_switches"],
            "expires_at": row["expires_at"].isoformat(),
            "questions": [dict(q) for q in questions]
        }), 200
    except Exception as e:
        logger.error(f"take_assessment error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/start/<token>", methods=["POST"])
@rate_limit(limit=10, period=60)
def start_assessment(token):
    """Mark assessment as In Progress, record screen_share_granted."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _get_assessment_by_token(cur, token)
        if not row:
            return jsonify({"error": "Assessment not found."}), 404
        if row["status"] in ("Completed", "Expired"):
            return jsonify({"error": f"Assessment is already {row['status']}."}), 410

        data = request.get_json(silent=True) or {}
        screen_granted = bool(data.get("screen_share_granted", False))

        cur.execute("""
            UPDATE assessments
            SET status = 'In Progress', started_at = NOW(), screen_share_granted = %s
            WHERE token = %s AND status = 'Pending'
        """, (screen_granted, token))
        conn.commit()
        return jsonify({"message": "Assessment started."}), 200
    except Exception as e:
        logger.error(f"start_assessment error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/tab-switch/<token>", methods=["POST"])
@rate_limit(limit=10, period=60)
def tab_switch(token):
    """Increment tab switch counter. Auto-submit if > 3."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE assessments
            SET tab_switches = tab_switches + 1
            WHERE token = %s AND status = 'In Progress'
            RETURNING tab_switches, id
        """, (token,))
        result = cur.fetchone()
        conn.commit()
        if not result:
            return jsonify({"error": "Assessment not active."}), 404

        switches = result["tab_switches"]
        if switches >= 3:
            cur.execute("""
                UPDATE assessments
                SET is_suspicious = TRUE, status = 'Flagged'
                WHERE token = %s
            """, (token,))
            conn.commit()
            return jsonify({"auto_submit": True, "tab_switches": switches,
                            "message": "Too many tab switches — assessment auto-submitted."}), 200

        return jsonify({"auto_submit": False, "tab_switches": switches}), 200
    except Exception as e:
        logger.error(f"tab_switch error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/submit/<token>", methods=["POST"])
@rate_limit(limit=10, period=60)
def submit_assessment(token):
    """Accept answers, calculate score, mark Completed, send completion email."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _get_assessment_by_token(cur, token)
        if not row:
            return jsonify({"error": "Assessment not found."}), 404
        if row["status"] == "Completed":
            return jsonify({"error": "Already submitted."}), 410

        data = request.get_json(silent=True) or {}
        # answers: { "question_id": "A" | "B" | "C" | "D", ... }
        answers = data.get("answers", {})

        # Fetch correct options
        if answers:
            q_ids = list(answers.keys())
            placeholders = ",".join(["%s"] * len(q_ids))
            cur.execute(f"""
                SELECT id, correct_option FROM assessment_questions
                WHERE id IN ({placeholders})
            """, q_ids)
        else:
            cur.fetchall  # no-op
            cur.execute("SELECT id, correct_option FROM assessment_questions WHERE FALSE")

        correct_map = {str(r["id"]): r["correct_option"] for r in cur.fetchall()}

        score = 0
        total = len(correct_map) if correct_map else len(answers)

        # Store answers
        assessment_id = row["id"]
        for q_id_str, selected in answers.items():
            correct = correct_map.get(q_id_str, "")
            is_correct = (selected.upper() == correct.upper()) if selected and correct else False
            if is_correct:
                score += 1
            cur.execute("""
                INSERT INTO assessment_answers (assessment_id, question_id, selected_option, is_correct)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (assessment_id, int(q_id_str), selected.upper() if selected else None, is_correct))

        percentage = round((score / total * 100), 2) if total > 0 else 0.0

        # Mark completed
        final_status = "Flagged" if row["is_suspicious"] or row["tab_switches"] >= 3 else "Completed"
        cur.execute("""
            UPDATE assessments
            SET status = %s, score = %s, total_questions = %s,
                percentage = %s, completed_at = NOW()
            WHERE token = %s
        """, (final_status, score, total, percentage, token))
        conn.commit()

        # Send completion email (non-blocking — log on failure)
        send_completion_email(
            candidate_name=row["candidate_name"],
            to_email=row["email"],
            score=score,
            total=total,
            percentage=percentage,
            job_title=row["job_title"]
        )

        return jsonify({
            "message": "Assessment submitted successfully!",
            "score": score,
            "total": total,
            "percentage": percentage,
            "status": final_status
        }), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"submit_assessment error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


# ─── ADMIN ROUTES ──────────────────────────────────────────────────────────

@assessment_bp.route("/all", methods=["GET"])
def get_all_assessments():
    """Admin: list all assessments with candidate and job info."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        status_filter = request.args.get("status", "")
        base_query = """
            SELECT a.id, a.token, a.status, a.score, a.total_questions, a.percentage,
                   a.tab_switches, a.is_suspicious, a.screen_share_granted,
                   a.started_at, a.completed_at, a.expires_at, a.created_at,
                   ap.candidate_name, ap.email, ap.phone,
                   j.title as job_title, j.department as job_department
            FROM assessments a
            JOIN applications ap ON a.application_id = ap.id
            JOIN jobs j ON ap.job_id = j.id
        """
        if status_filter:
            cur.execute(base_query + " WHERE a.status = %s ORDER BY a.created_at DESC", (status_filter,))
        else:
            cur.execute(base_query + " ORDER BY a.created_at DESC")

        rows = cur.fetchall()
        for r in rows:
            for key in ("started_at", "completed_at", "expires_at", "created_at"):
                if r.get(key):
                    r[key] = r[key].isoformat()
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"get_all_assessments error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/answers/<int:assessment_id>", methods=["GET"])
def get_assessment_answers(assessment_id):
    """Admin: get detailed Q&A breakdown for a specific assessment."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT aa.id, aa.selected_option, aa.is_correct,
                   aq.question_text, aq.option_a, aq.option_b, aq.option_c, aq.option_d,
                   aq.correct_option, aq.difficulty
            FROM assessment_answers aa
            JOIN assessment_questions aq ON aa.question_id = aq.id
            WHERE aa.assessment_id = %s
            ORDER BY aq.id
        """, (assessment_id,))
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"get_assessment_answers error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/resend/<int:assessment_id>", methods=["POST"])
def resend_assessment_email(assessment_id):
    """Admin: resend assessment invitation email."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT a.token, a.status, ap.candidate_name, ap.email, j.title as job_title
            FROM assessments a
            JOIN applications ap ON a.application_id = ap.id
            JOIN jobs j ON ap.job_id = j.id
            WHERE a.id = %s
        """, (assessment_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Assessment not found."}), 404
        if row["status"] == "Completed":
            return jsonify({"error": "Assessment already completed."}), 400

        from ..utils.mailer import send_assessment_email
        send_assessment_email(row["candidate_name"], row["email"], row["token"], row["job_title"])
        return jsonify({"message": f"Assessment email resent to {row['email']}"}), 200
    except Exception as e:
        logger.error(f"resend_assessment_email error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


# ─── QUESTION BANK ROUTES ──────────────────────────────────────────────────

@assessment_bp.route("/questions", methods=["GET"])
def get_questions():
    """Admin: list questions, optionally filtered by job_id."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        job_id = request.args.get("job_id")
        if job_id:
            cur.execute("""
                SELECT q.*, j.title as job_title
                FROM assessment_questions q
                LEFT JOIN jobs j ON q.job_id = j.id
                WHERE q.job_id = %s ORDER BY q.id
            """, (int(job_id),))
        else:
            cur.execute("""
                SELECT q.*, j.title as job_title
                FROM assessment_questions q
                LEFT JOIN jobs j ON q.job_id = j.id
                ORDER BY q.job_id NULLS LAST, q.id
            """)
        rows = cur.fetchall()
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"get_questions error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/questions", methods=["POST"])
def create_question():
    """Admin: create a new assessment question."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        data = request.get_json(silent=True) or {}
        job_id      = data.get("job_id")  # None = global
        question    = data.get("question_text", "").strip()
        opt_a       = data.get("option_a", "").strip()
        opt_b       = data.get("option_b", "").strip()
        opt_c       = data.get("option_c", "").strip()
        opt_d       = data.get("option_d", "").strip()
        correct     = (data.get("correct_option") or "").strip().upper()
        difficulty  = data.get("difficulty", "Medium")

        if not all([question, opt_a, opt_b, opt_c, opt_d, correct]):
            return jsonify({"error": "All fields required (question, options A-D, correct_option)."}), 400
        if correct not in ("A", "B", "C", "D"):
            return jsonify({"error": "correct_option must be A, B, C, or D."}), 400

        cur.execute("""
            INSERT INTO assessment_questions
              (job_id, question_text, option_a, option_b, option_c, option_d, correct_option, difficulty)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (job_id if job_id else None, question, opt_a, opt_b, opt_c, opt_d, correct, difficulty))
        conn.commit()
        return jsonify({"message": "Question created successfully."}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"create_question error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/questions/<int:q_id>", methods=["PUT"])
def update_question(q_id):
    """Admin: update an existing assessment question."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        data = request.get_json(silent=True) or {}
        cur.execute("""
            UPDATE assessment_questions
            SET question_text=%s, option_a=%s, option_b=%s, option_c=%s, option_d=%s,
                correct_option=%s, difficulty=%s
            WHERE id=%s
        """, (
            data.get("question_text"), data.get("option_a"), data.get("option_b"),
            data.get("option_c"), data.get("option_d"),
            (data.get("correct_option") or "").upper(), data.get("difficulty", "Medium"),
            q_id
        ))
        conn.commit()
        return jsonify({"message": "Question updated."}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"update_question error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/questions/<int:q_id>", methods=["DELETE"])
def delete_question(q_id):
    """Admin: delete an assessment question."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") not in ["admin", "hr", "hr_manager", "team_leader", "employee"]:
        return jsonify({"error": "Forbidden"}), 403

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM assessment_questions WHERE id=%s", (q_id,))
        conn.commit()
        return jsonify({"message": "Question deleted."}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"delete_question error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()



# ==============================================================================
# ─── CAMPUS DRIVE & LIVE CODING SANDBOX ROUTES ───────────────────────────────
# ==============================================================================

@assessment_bp.route("/drive/<drive_code>", methods=["GET"])
@rate_limit(limit=60, period=60)
def get_campus_drive(drive_code):
    """Public: Fetch campus drive metadata by drive_code."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, drive_code, college_name, title, total_duration_minutes,
                   mcq_duration_minutes, coding_duration_minutes, target_batch,
                   allowed_branches, cutoff_percentage, is_active,
                   (passcode IS NOT NULL AND passcode != '') as has_passcode
            FROM campus_drives
            WHERE drive_code = %s
        """, (drive_code,))
        drive = cur.fetchone()
        if not drive:
            return jsonify({"error": "Campus Drive not found. Please verify your drive code."}), 404
        if not drive["is_active"]:
            return jsonify({"error": "This Campus Drive is currently inactive or closed."}), 403

        return jsonify(dict(drive)), 200
    except Exception as e:
        logger.error(f"get_campus_drive error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/drive/register", methods=["POST"])
@rate_limit(limit=20, period=60)
def register_campus_candidate():
    """Public: Register student for campus drive."""
    data = request.get_json(silent=True) or {}
    drive_code = (data.get("drive_code") or "").strip()
    student_name = (data.get("student_name") or "").strip()
    roll_number = (data.get("roll_number") or "").strip().upper()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    branch = (data.get("branch") or "").strip()
    cgpa = data.get("cgpa")
    passcode = (data.get("passcode") or "").strip()

    if not drive_code or not student_name or not roll_number or not email or not branch:
        return jsonify({"error": "Drive code, Student Name, Roll Number, Email, and Branch are required."}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, passcode, is_active, total_duration_minutes FROM campus_drives WHERE drive_code = %s", (drive_code,))
        drive = cur.fetchone()
        if not drive:
            return jsonify({"error": "Invalid Campus Drive code."}), 404
        if not drive["is_active"]:
            return jsonify({"error": "This Campus Drive has closed."}), 403
        if drive["passcode"] and drive["passcode"] != passcode:
            return jsonify({"error": "Invalid Campus Drive passcode."}), 401

        drive_id = drive["id"]

        # Check if candidate already registered
        cur.execute("""
            SELECT id, token, status FROM campus_candidates
            WHERE drive_id = %s AND (roll_number = %s OR email = %s)
        """, (drive_id, roll_number, email))
        existing = cur.fetchone()

        if existing:
            if existing["status"] == "Completed":
                return jsonify({"error": "You have already completed and submitted this campus drive assessment."}), 400
            token = existing["token"]
        else:
            token = secrets.token_urlsafe(32)
            cur.execute("""
                INSERT INTO campus_candidates (drive_id, token, student_name, roll_number, email, phone, branch, cgpa, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Registered')
                RETURNING id, token
            """, (drive_id, token, student_name, roll_number, email, phone, branch, float(cgpa) if cgpa else None))
            conn.commit()

        return jsonify({
            "message": "Campus registration successful.",
            "token": token,
            "drive_code": drive_code
        }), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"register_campus_candidate error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/drive/session/<token>", methods=["GET"])
@rate_limit(limit=60, period=60)
def get_campus_session(token):
    """Public: Load candidate assessment session (MCQs + Coding Problems)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT c.*, d.title as drive_title, d.college_name, d.drive_code,
                   d.total_duration_minutes, d.mcq_duration_minutes, d.coding_duration_minutes
            FROM campus_candidates c
            JOIN campus_drives d ON c.drive_id = d.id
            WHERE c.token = %s
        """, (token,))
        candidate = cur.fetchone()
        if not candidate:
            return jsonify({"error": "Assessment session not found. Please register."}), 404

        if candidate["status"] == "Completed":
            return jsonify({"error": "This assessment has already been completed.", "status": "Completed"}), 410
        if candidate["status"] == "Disqualified":
            return jsonify({"error": "Assessment disqualified due to security / proctoring violations.", "status": "Disqualified"}), 403

        drive_id = candidate["drive_id"]

        # Fetch Section 1: MCQs (Aptitude + CS Fundamentals)
        cur.execute("""
            SELECT id, question as question_text, option_a, option_b, option_c, option_d
            FROM assessment_questions
            ORDER BY id
            LIMIT 15
        """)
        mcqs = [dict(q) for q in cur.fetchall()]

        # Fetch Section 2: Coding Problems
        cur.execute("""
            SELECT id, title, difficulty, points, problem_statement,
                   input_format, output_format, constraints, time_limit_seconds,
                   memory_limit_mb, starter_code_json
            FROM coding_problems
            WHERE drive_id = %s OR drive_id IS NULL
            ORDER BY id
        """, (drive_id,))
        problems = cur.fetchall()

        problems_list = []
        for p in problems:
            prob_dict = dict(p)
            # Fetch public sample testcases for candidate testing
            cur.execute("""
                SELECT id, input_data, expected_output, weight
                FROM coding_testcases
                WHERE problem_id = %s AND is_hidden = FALSE
                ORDER BY id
            """, (p["id"],))
            prob_dict["sample_testcases"] = [dict(tc) for tc in cur.fetchall()]

            # Check if candidate has existing code submission
            cur.execute("""
                SELECT language, source_code, passed_testcases, total_testcases, score, status
                FROM coding_submissions
                WHERE candidate_id = %s AND problem_id = %s
            """, (candidate["id"], p["id"]))
            sub = cur.fetchone()
            prob_dict["saved_submission"] = dict(sub) if sub else None

            problems_list.append(prob_dict)

        return jsonify({
            "candidate": {
                "id": candidate["id"],
                "student_name": candidate["student_name"],
                "roll_number": candidate["roll_number"],
                "email": candidate["email"],
                "college_name": candidate["college_name"],
                "branch": candidate["branch"],
                "cgpa": float(candidate["cgpa"]) if candidate["cgpa"] else None,
                "status": candidate["status"],
                "tab_switches": candidate["tab_switches"],
                "fullscreen_exits": candidate["fullscreen_exits"],
                "started_at": candidate["started_at"].isoformat() if candidate["started_at"] else None
            },
            "drive": {
                "id": drive_id,
                "title": candidate["drive_title"],
                "drive_code": candidate["drive_code"],
                "college_name": candidate["college_name"],
                "total_duration_minutes": candidate["total_duration_minutes"],
                "mcq_duration_minutes": candidate["mcq_duration_minutes"],
                "coding_duration_minutes": candidate["coding_duration_minutes"]
            },
            "mcqs": mcqs,
            "coding_problems": problems_list
        }), 200
    except Exception as e:
        logger.error(f"get_campus_session error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/drive/start/<token>", methods=["POST"])
@rate_limit(limit=20, period=60)
def start_campus_drive(token):
    """Public: Start candidate timer and mark In Progress."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE campus_candidates
            SET status = 'In Progress', started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
            WHERE token = %s AND status = 'Registered'
            RETURNING id, started_at, status
        """, (token,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            # Check current status
            cur.execute("SELECT status, started_at FROM campus_candidates WHERE token = %s", (token,))
            c = cur.fetchone()
            if not c:
                return jsonify({"error": "Candidate not found."}), 404
            return jsonify({"message": "Assessment already in progress.", "status": c["status"], "started_at": c["started_at"].isoformat() if c["started_at"] else None}), 200

        return jsonify({"message": "Assessment started.", "started_at": row["started_at"].isoformat(), "status": row["status"]}), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"start_campus_drive error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/code/run", methods=["POST"])
@rate_limit(limit=60, period=60)
def run_sandbox_code():
    """Public: Execute code against sample testcases or custom input."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    problem_id = data.get("problem_id")
    language = (data.get("language") or "python").strip()
    source_code = data.get("source_code") or ""
    custom_input = data.get("custom_input")

    if not token or not source_code:
        return jsonify({"error": "Token and source code are required."}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id FROM campus_candidates WHERE token = %s AND status IN ('Registered', 'In Progress')", (token,))
        if not cur.fetchone():
            return jsonify({"error": "Active candidate session required."}), 403

        if custom_input is not None:
            # Custom input run
            res = execute_testcase(source_code, language, custom_input, expected_output=None)
            return jsonify({
                "mode": "custom",
                "status": res["status"],
                "passed": res["passed"],
                "actual_output": res["actual_output"],
                "stderr": res["stderr"],
                "execution_time_ms": res["execution_time_ms"],
                "error": res["error"]
            }), 200

        # Run against public sample test cases of the problem
        cur.execute("""
            SELECT id, input_data, expected_output, weight, is_hidden
            FROM coding_testcases
            WHERE problem_id = %s AND is_hidden = FALSE
            ORDER BY id
        """, (problem_id,))
        sample_cases = [dict(tc) for tc in cur.fetchall()]

        if not sample_cases:
            # Fallback if no sample cases defined
            res = execute_testcase(source_code, language, "", expected_output=None)
            return jsonify({"mode": "empty", "status": res["status"], "actual_output": res["actual_output"], "stderr": res["stderr"], "execution_time_ms": res["execution_time_ms"]}), 200

        suite_res = execute_testcase_suite(source_code, language, sample_cases)
        return jsonify({
            "mode": "sample_suite",
            "all_passed": suite_res["all_passed"],
            "passed_count": suite_res["passed_count"],
            "total_count": suite_res["total_count"],
            "overall_status": suite_res["overall_status"],
            "results": suite_res["results"]
        }), 200

    except Exception as e:
        logger.error(f"run_sandbox_code error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/code/submit", methods=["POST"])
@rate_limit(limit=30, period=60)
def submit_sandbox_code():
    """Public: Evaluate code against ALL testcases (hidden + public) and save score."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    problem_id = data.get("problem_id")
    language = (data.get("language") or "python").strip()
    source_code = data.get("source_code") or ""

    if not token or not problem_id or not source_code:
        return jsonify({"error": "Token, Problem ID, and Source Code are required."}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, drive_id FROM campus_candidates WHERE token = %s AND status IN ('Registered', 'In Progress')", (token,))
        cand = cur.fetchone()
        if not cand:
            return jsonify({"error": "Active assessment session required."}), 403

        candidate_id = cand["id"]

        # Fetch all testcases (public + hidden)
        cur.execute("""
            SELECT id, input_data, expected_output, weight, is_hidden
            FROM coding_testcases
            WHERE problem_id = %s
            ORDER BY is_hidden ASC, id ASC
        """, (problem_id,))
        testcases = [dict(tc) for tc in cur.fetchall()]

        if not testcases:
            return jsonify({"error": "No testcases configured for this problem."}), 400

        suite_res = execute_testcase_suite(source_code, language, testcases)

        # Upsert submission
        cur.execute("""
            INSERT INTO coding_submissions (candidate_id, problem_id, language, source_code, passed_testcases, total_testcases, score, execution_time_ms, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (candidate_id, problem_id) DO UPDATE
            SET language = EXCLUDED.language,
                source_code = EXCLUDED.source_code,
                passed_testcases = EXCLUDED.passed_testcases,
                total_testcases = EXCLUDED.total_testcases,
                score = EXCLUDED.score,
                execution_time_ms = EXCLUDED.execution_time_ms,
                status = EXCLUDED.status,
                submitted_at = CURRENT_TIMESTAMP
        """, (
            candidate_id, problem_id, language, source_code,
            suite_res["passed_count"], suite_res["total_count"],
            suite_res["total_score"],
            max((r["execution_time_ms"] for r in suite_res["results"]), default=0),
            suite_res["overall_status"]
        ))

        # Re-calculate total candidate coding score
        cur.execute("""
            UPDATE campus_candidates
            SET coding_score = (
                SELECT COALESCE(SUM(score), 0) FROM coding_submissions WHERE candidate_id = %s
            )
            WHERE id = %s
        """, (candidate_id, candidate_id))

        conn.commit()

        return jsonify({
            "message": "Code submitted successfully.",
            "all_passed": suite_res["all_passed"],
            "passed_count": suite_res["passed_count"],
            "total_count": suite_res["total_count"],
            "score": suite_res["total_score"],
            "max_score": suite_res["max_score"],
            "overall_status": suite_res["overall_status"],
            "results": suite_res["results"]
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"submit_sandbox_code error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/drive/tab-switch/<token>", methods=["POST"])
@rate_limit(limit=60, period=60)
def record_campus_violation(token):
    """Public: Track anti-cheat violations (tab switch, fullscreen exit)."""
    data = request.get_json(silent=True) or {}
    vtype = data.get("violation_type", "tab_switch")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if vtype == "fullscreen_exit":
            cur.execute("""
                UPDATE campus_candidates
                SET fullscreen_exits = fullscreen_exits + 1
                WHERE token = %s
                RETURNING tab_switches, fullscreen_exits, status
            """, (token,))
        else:
            cur.execute("""
                UPDATE campus_candidates
                SET tab_switches = tab_switches + 1
                WHERE token = %s
                RETURNING tab_switches, fullscreen_exits, status
            """, (token,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Candidate not found."}), 404

        total_violations = row["tab_switches"] + row["fullscreen_exits"]
        is_disqualified = False
        if total_violations >= 5 and row["status"] != "Completed":
            cur.execute("UPDATE campus_candidates SET status = 'Disqualified' WHERE token = %s", (token,))
            conn.commit()
            is_disqualified = True

        return jsonify({
            "tab_switches": row["tab_switches"],
            "fullscreen_exits": row["fullscreen_exits"],
            "total_violations": total_violations,
            "is_disqualified": is_disqualified,
            "max_violations": 5
        }), 200
    except Exception as e:
        conn.rollback()
        logger.error(f"record_campus_violation error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/drive/submit/<token>", methods=["POST"])
@rate_limit(limit=10, period=60)
def submit_campus_drive(token):
    """Public: Finalize both MCQs + Coding sections and calculate total score."""
    data = request.get_json(silent=True) or {}
    mcq_answers = data.get("mcq_answers", {}) # { "question_id": "A" }

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT c.*, d.cutoff_percentage, d.title as drive_title, d.college_name
            FROM campus_candidates c
            JOIN campus_drives d ON c.drive_id = d.id
            WHERE c.token = %s
        """, (token,))
        cand = cur.fetchone()
        if not cand:
            return jsonify({"error": "Candidate not found."}), 404
        if cand["status"] == "Completed":
            return jsonify({"error": "Assessment already submitted.", "status": "Completed"}), 200

        candidate_id = cand["id"]

        # 1. Score MCQ Section
        mcq_correct = 0
        total_mcqs = len(mcq_answers)
        if mcq_answers:
            q_ids = [int(k) for k in mcq_answers.keys() if str(k).isdigit()]
            if q_ids:
                cur.execute("""
                    SELECT id, correct_answer FROM assessment_questions
                    WHERE id = ANY(%s)
                """, (q_ids,))
                key_map = {row["id"]: row["correct_answer"].upper() for row in cur.fetchall()}
                for q_id_str, selected in mcq_answers.items():
                    if int(q_id_str) in key_map and str(selected).upper() == key_map[int(q_id_str)]:
                        mcq_correct += 1

        mcq_score = mcq_correct * 10 # 10 points per MCQ

        # 2. Get Coding Score from submissions
        cur.execute("SELECT COALESCE(SUM(score), 0) as coding_sum FROM coding_submissions WHERE candidate_id = %s", (candidate_id,))
        coding_score = cur.fetchone()["coding_sum"]

        # Total Calculation
        # Max MCQ points (assuming 15 MCQs = 150 pts) + Max Coding points (2 problems = 200 pts)
        max_score = 350
        total_score = mcq_score + coding_score
        percentage = round((total_score / max_score) * 100, 2)

        cur.execute("""
            UPDATE campus_candidates
            SET mcq_score = %s, coding_score = %s, total_score = %s, max_score = %s,
                percentage = %s, status = 'Completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
        """, (mcq_score, coding_score, total_score, max_score, percentage, candidate_id))
        updated_cand = cur.fetchone()
        conn.commit()

        is_shortlisted = (percentage >= float(cand["cutoff_percentage"] or 60.0))

        return jsonify({
            "message": "Campus Drive Assessment submitted successfully.",
            "student_name": updated_cand["student_name"],
            "roll_number": updated_cand["roll_number"],
            "college_name": cand["college_name"],
            "mcq_score": mcq_score,
            "coding_score": coding_score,
            "total_score": total_score,
            "max_score": max_score,
            "percentage": float(percentage),
            "cutoff_percentage": float(cand["cutoff_percentage"]),
            "is_shortlisted": is_shortlisted,
            "status": "Completed"
        }), 200

    except Exception as e:
        conn.rollback()
        logger.error(f"submit_campus_drive error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


# ==============================================================================
# ─── ADMIN CAMPUS DRIVE MANAGEMENT ROUTES ─────────────────────────────────────
# ==============================================================================

@assessment_bp.route("/admin/drives", methods=["GET"])
def list_admin_campus_drives():
    """Admin: List all campus drives with candidate counts and performance."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT d.*,
                   COUNT(c.id) as total_candidates,
                   COUNT(CASE WHEN c.status = 'Completed' THEN 1 END) as completed_count,
                   COUNT(CASE WHEN c.status = 'In Progress' THEN 1 END) as active_count,
                   COALESCE(ROUND(AVG(CASE WHEN c.status = 'Completed' THEN c.percentage END), 2), 0) as avg_percentage
            FROM campus_drives d
            LEFT JOIN campus_candidates c ON d.id = c.drive_id
            GROUP BY d.id
            ORDER BY d.created_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"list_admin_campus_drives error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/admin/drives", methods=["POST"])
def create_admin_campus_drive():
    """Admin: Create new campus drive."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    drive_code = (data.get("drive_code") or "").strip().upper()
    college_name = (data.get("college_name") or "").strip()
    title = (data.get("title") or "").strip()

    if not drive_code or not college_name or not title:
        return jsonify({"error": "Drive Code, College Name, and Drive Title are required."}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO campus_drives (
                drive_code, college_name, title, total_duration_minutes,
                mcq_duration_minutes, coding_duration_minutes, passcode,
                target_batch, allowed_branches, cutoff_percentage, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            drive_code, college_name, title,
            int(data.get("total_duration_minutes", 90)),
            int(data.get("mcq_duration_minutes", 30)),
            int(data.get("coding_duration_minutes", 60)),
            data.get("passcode") or None,
            data.get("target_batch", "2025/2026"),
            data.get("allowed_branches", "CSE, IT, ECE, AI/ML"),
            float(data.get("cutoff_percentage", 60.0)),
            bool(data.get("is_active", True))
        ))
        row = cur.fetchone()
        conn.commit()
        return jsonify({"message": "Campus Drive created.", "drive": dict(row)}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"create_admin_campus_drive error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/admin/drive/<int:drive_id>/leaderboard", methods=["GET"])
def get_drive_leaderboard(drive_id):
    """Admin: Return ranked candidate leaderboard for a campus drive."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT c.id, c.student_name, c.roll_number, c.email, c.phone,
                   c.branch, c.cgpa, c.status, c.mcq_score, c.coding_score,
                   c.total_score, c.max_score, c.percentage, c.tab_switches,
                   c.fullscreen_exits, c.started_at, c.completed_at,
                   d.cutoff_percentage
            FROM campus_candidates c
            JOIN campus_drives d ON c.drive_id = d.id
            WHERE c.drive_id = %s
            ORDER BY c.total_score DESC, c.cgpa DESC NULLS LAST, c.completed_at ASC NULLS LAST
        """, (drive_id,))
        candidates = [dict(c) for c in cur.fetchall()]
        return jsonify(candidates), 200
    except Exception as e:
        logger.error(f"get_drive_leaderboard error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/admin/drive/<int:drive_id>/export", methods=["GET"])
def export_drive_csv(drive_id):
    """Admin: 1-Click CSV export of campus drive results for placement officers."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT college_name, drive_code FROM campus_drives WHERE id = %s", (drive_id,))
        drive = cur.fetchone()
        if not drive:
            return jsonify({"error": "Drive not found"}), 404

        cur.execute("""
            SELECT c.roll_number, c.student_name, c.branch, c.cgpa, c.email, c.phone,
                   c.mcq_score, c.coding_score, c.total_score, c.percentage,
                   c.status,
                   CASE WHEN c.percentage >= d.cutoff_percentage AND c.status = 'Completed' THEN 'SHORTLISTED' ELSE 'REJECTED' END as placement_status,
                   c.tab_switches as anti_cheat_flags,
                   c.completed_at
            FROM campus_candidates c
            JOIN campus_drives d ON c.drive_id = d.id
            WHERE c.drive_id = %s
            ORDER BY c.total_score DESC, c.cgpa DESC NULLS LAST
        """, (drive_id,))
        rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Roll Number", "Student Name", "Branch", "CGPA", "Email", "Phone",
            "MCQ Score", "Coding Score", "Total Score", "Percentage", "Test Status",
            "Placement Shortlist", "Anti-Cheat Violations", "Submitted At"
        ])
        for r in rows:
            writer.writerow([
                r["roll_number"], r["student_name"], r["branch"], r["cgpa"],
                r["email"], r["phone"], r["mcq_score"], r["coding_score"],
                r["total_score"], f"{r['percentage']}%", r["status"],
                r["placement_status"], r["anti_cheat_flags"], r["completed_at"]
            ])

        output.seek(0)
        filename = f"{drive['drive_code']}_{drive['college_name'].replace(' ', '_')}_Results.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        logger.error(f"export_drive_csv error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()


@assessment_bp.route("/admin/coding-problems", methods=["GET"])
def list_admin_coding_problems():
    """Admin: List coding problems with testcases."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        drive_id = request.args.get("drive_id")
        if drive_id:
            cur.execute("""
                SELECT p.*, COUNT(t.id) as testcase_count
                FROM coding_problems p
                LEFT JOIN coding_testcases t ON p.id = t.problem_id
                WHERE p.drive_id = %s OR p.drive_id IS NULL
                GROUP BY p.id
                ORDER BY p.id
            """, (drive_id,))
        else:
            cur.execute("""
                SELECT p.*, COUNT(t.id) as testcase_count
                FROM coding_problems p
                LEFT JOIN coding_testcases t ON p.id = t.problem_id
                GROUP BY p.id
                ORDER BY p.id
            """)
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows), 200
    except Exception as e:
        logger.error(f"list_admin_coding_problems error: {e}")
        return jsonify(safe_error()), 500
    finally:
        cur.close(); conn.close()
