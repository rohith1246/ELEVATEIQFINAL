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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
    if not user or user.get("role") != "admin":
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
