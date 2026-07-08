from flask import request, jsonify
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from .config import Config
from .database import get_connection
import secrets
import hashlib
import time
import re
import logging

logger = logging.getLogger(__name__)

# Track which tables have been checked to avoid repeated CREATE TABLE IF NOT EXISTS
_tables_checked = set()

ACCESS_TOKEN_MAX_AGE = 900
REFRESH_TOKEN_MAX_AGE = 604800

serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt="access")
refresh_serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt="refresh")
TOKEN_MAX_AGE = ACCESS_TOKEN_MAX_AGE

# ─── CSRF Protection ──────────────────────────────────────────

CSRF_TOKEN_LENGTH = 32

def _ensure_csrf_table():
    if 'csrf_tokens' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS csrf_tokens (
            user_id INT NOT NULL, token VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, token))""")
        conn.commit()
        _tables_checked.add('csrf_tokens')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def get_csrf_token(user_id):
    _ensure_csrf_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        token = secrets.token_hex(CSRF_TOKEN_LENGTH)
        c.execute("INSERT INTO csrf_tokens (user_id, token) VALUES (%s, %s)", (user_id, token))
        conn.commit()
        return token
    except Exception as e:
        conn.rollback()
        logger.error(f"CSRF gen error: {e}")
        return None
    finally:
        c.close()
        conn.close()

def validate_csrf_token(user_id, token):
    if not token or not user_id:
        return False
    _ensure_csrf_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM csrf_tokens WHERE user_id = %s AND token = %s RETURNING 1", (user_id, token))
        valid = c.fetchone() is not None
        conn.commit()
        return valid
    except Exception as e:
        conn.rollback()
        logger.error(f"CSRF validate error: {e}")
        return False
    finally:
        c.close()
        conn.close()

def cleanup_expired_csrf():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM csrf_tokens WHERE created_at < NOW() - INTERVAL '1 hour'")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def csrf_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        token = request.headers.get("X-CSRF-Token")
        if not token:
            return jsonify({"error": "CSRF token required"}), 403
        if not validate_csrf_token(user["id"], token):
            return jsonify({"error": "Invalid or expired CSRF token"}), 403
        return f(*args, **kwargs)
    return wrapper

# ─── Brute Force Lockout ───────────────────────────────────────

BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW_MINUTES = 15

def _ensure_lockout_tables():
    if 'login_attempts' in _tables_checked and 'account_lockouts' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(45))""")
        c.execute("""CREATE TABLE IF NOT EXISTS account_lockouts (
            user_id INT PRIMARY KEY,
            locked_until TIMESTAMP NOT NULL,
            attempt_count INT DEFAULT 0)""")
        conn.commit()
        _tables_checked.add('login_attempts')
        _tables_checked.add('account_lockouts')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def record_failed_attempt(user_id, ip_address):
    _ensure_lockout_tables()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO login_attempts (user_id, ip_address) VALUES (%s, %s)", (user_id, ip_address))
        c.execute("""SELECT COUNT(*) FROM login_attempts
            WHERE user_id = %s AND attempted_at > NOW() - INTERVAL '%s minutes'""",
            (user_id, BRUTE_FORCE_WINDOW_MINUTES))
        count = c.fetchone()[0]
        if count >= BRUTE_FORCE_THRESHOLD:
            c.execute("""INSERT INTO account_lockouts (user_id, locked_until, attempt_count)
                VALUES (%s, NOW() + INTERVAL '%s minutes', %s)
                ON CONFLICT (user_id) DO UPDATE
                SET locked_until = NOW() + INTERVAL '%s minutes', attempt_count = %s""",
                (user_id, BRUTE_FORCE_WINDOW_MINUTES, count,
                 BRUTE_FORCE_WINDOW_MINUTES, count))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed attempt record error: {e}")
    finally:
        c.close()
        conn.close()

def record_failed_attempt_conn(conn, user_id, ip_address):
    _ensure_lockout_tables()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO login_attempts (user_id, ip_address) VALUES (%s, %s)", (user_id, ip_address))
        c.execute("""SELECT COUNT(*) FROM login_attempts
            WHERE user_id = %s AND attempted_at > NOW() - INTERVAL '%s minutes'""",
            (user_id, BRUTE_FORCE_WINDOW_MINUTES))
        count = c.fetchone()[0]
        if count >= BRUTE_FORCE_THRESHOLD:
            c.execute("""INSERT INTO account_lockouts (user_id, locked_until, attempt_count)
                VALUES (%s, NOW() + INTERVAL '%s minutes', %s)
                ON CONFLICT (user_id) DO UPDATE
                SET locked_until = NOW() + INTERVAL '%s minutes', attempt_count = %s""",
                (user_id, BRUTE_FORCE_WINDOW_MINUTES, count,
                 BRUTE_FORCE_WINDOW_MINUTES, count))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed attempt record error: {e}")
    finally:
        c.close()

def is_account_locked(user_id):
    _ensure_lockout_tables()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT locked_until FROM account_lockouts WHERE user_id = %s AND locked_until > NOW()", (user_id,))
        row = c.fetchone()
        return (True, row[0]) if row else (False, None)
    except Exception as e:
        logger.error(f"Lock check error: {e}")
        return False, None
    finally:
        c.close()
        conn.close()

def is_account_locked_conn(conn, user_id):
    _ensure_lockout_tables()
    c = conn.cursor()
    try:
        c.execute("SELECT locked_until FROM account_lockouts WHERE user_id = %s AND locked_until > NOW()", (user_id,))
        row = c.fetchone()
        return (True, row[0]) if row else (False, None)
    except Exception as e:
        logger.error(f"Lock check error: {e}")
        return False, None
    finally:
        c.close()

def reset_login_attempts(user_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM login_attempts WHERE user_id = %s", (user_id,))
        c.execute("DELETE FROM account_lockouts WHERE user_id = %s", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

# ─── Password History ──────────────────────────────────────────

PASSWORD_HISTORY_COUNT = 5

def _ensure_password_history_table():
    if 'password_history' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS password_history (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        _tables_checked.add('password_history')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def check_password_history(user_id, password_hash):
    _ensure_password_history_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""SELECT password_hash FROM password_history
            WHERE user_id = %s ORDER BY created_at DESC LIMIT %s""",
            (user_id, PASSWORD_HISTORY_COUNT))
        for row in c.fetchall():
            h = row[0] if isinstance(row, dict) else row[0]
            if h == password_hash:
                return False
        return True
    except Exception as e:
        logger.error(f"Password history check error: {e}")
        return True
    finally:
        c.close()
        conn.close()

def store_password_history(user_id, password_hash):
    _ensure_password_history_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO password_history (user_id, password_hash) VALUES (%s, %s)", (user_id, password_hash))
        c.execute("""DELETE FROM password_history WHERE user_id = %s AND id NOT IN (
            SELECT id FROM password_history WHERE user_id = %s
            ORDER BY created_at DESC LIMIT %s)""",
            (user_id, user_id, PASSWORD_HISTORY_COUNT))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

# ─── Audit Log ─────────────────────────────────────────────────

def _ensure_audit_log_table():
    if 'audit_log' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY, user_id INT,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50), resource_id INT,
            details TEXT, ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        _tables_checked.add('audit_log')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def _write_audit_log(user_id, action, resource_type, resource_id, details):
    conn = get_connection()
    c = conn.cursor()
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
        c.execute("""INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, action, resource_type, resource_id, details, ip))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Audit log error: {e}")
    finally:
        c.close()
        conn.close()

def audit_log(action, resource_type=None, resource_id=None, details=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if user:
                _ensure_audit_log_table()
                _write_audit_log(user["id"], action, resource_type, resource_id, details)
            return f(*args, **kwargs)
        return wrapper
    return decorator

def get_audit_logs(limit=100, offset=0):
    conn = get_connection()
    c = conn.cursor()
    try:
        _ensure_audit_log_table()
        c.execute("""SELECT al.*, u.name as user_name FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            ORDER BY al.created_at DESC LIMIT %s OFFSET %s""", (limit, offset))
        rows = c.fetchall()
        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error(f"Audit log fetch error: {e}")
        return []
    finally:
        c.close()
        conn.close()

# ─── Refresh Token Rotation ────────────────────────────────────

def _ensure_refresh_tokens_table():
    if 'refresh_tokens' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            revoked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        _tables_checked.add('refresh_tokens')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def issue_refresh_token(user_id):
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    _ensure_refresh_tokens_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND revoked = FALSE", (user_id,))
        c.execute("""INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '7 days')""", (user_id, token_hash))
        conn.commit()
        return token
    except Exception as e:
        conn.rollback()
        logger.error(f"Refresh token issue error: {e}")
        return None
    finally:
        c.close()
        conn.close()

def validate_and_rotate_refresh_token(token):
    if not token:
        return None, None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    _ensure_refresh_tokens_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""SELECT user_id FROM refresh_tokens
            WHERE token_hash = %s AND revoked = FALSE AND expires_at > NOW()""", (token_hash,))
        row = c.fetchone()
        if not row:
            return None, None
        uid = row[0] if isinstance(row, dict) else row[0]
        c.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = %s", (token_hash,))
        new_token = secrets.token_urlsafe(64)
        new_hash = hashlib.sha256(new_token.encode()).hexdigest()
        c.execute("""INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '7 days')""", (uid, new_hash))
        conn.commit()
        return uid, new_token
    except Exception as e:
        conn.rollback()
        logger.error(f"Refresh token validate error: {e}")
        return None, None
    finally:
        c.close()
        conn.close()

def revoke_all_refresh_tokens(user_id):
    _ensure_refresh_tokens_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND revoked = FALSE", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

# Connection-aware helpers (for sharing a connection across multiple operations)
def issue_refresh_token_conn(conn, user_id):
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    c = conn.cursor()
    try:
        c.execute("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND revoked = FALSE", (user_id,))
        c.execute("""INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, NOW() + INTERVAL '7 days')""", (user_id, token_hash))
        conn.commit()
        return token
    except Exception as e:
        conn.rollback()
        logger.error(f"Refresh token issue error: {e}")
        return None
    finally:
        c.close()

def get_csrf_token_conn(conn, user_id):
    _ensure_csrf_table()
    c = conn.cursor()
    try:
        token = secrets.token_hex(CSRF_TOKEN_LENGTH)
        c.execute("INSERT INTO csrf_tokens (user_id, token) VALUES (%s, %s)", (user_id, token))
        conn.commit()
        return token
    except Exception as e:
        conn.rollback()
        logger.error(f"CSRF gen error: {e}")
        return None
    finally:
        c.close()

def seed_default_permissions_conn(conn):
    _ensure_permissions_table()
    c = conn.cursor()
    try:
        role_perms = {
            "admin": list(PERMISSIONS.keys()),
            "employee": [
                "leaves:read",
                "chat:read", "chat:write",
                "tickets:read", "tickets:write",
                "recruitment:read",
            ],
            "candidate": [
                "recruitment:read",
            ],
            "client": [
                "crm:read",
                "chat:read", "chat:write",
            ],
        }
        for role, perms in role_perms.items():
            for p in perms:
                c.execute("INSERT INTO role_permissions (role, permission) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (role, p))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Seed permissions error: {e}")
    finally:
        c.close()

def reset_login_attempts_conn(conn, user_id):
    c = conn.cursor()
    try:
        c.execute("DELETE FROM login_attempts WHERE user_id = %s", (user_id,))
        c.execute("DELETE FROM account_lockouts WHERE user_id = %s", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()

# ─── Token Helpers ─────────────────────────────────────────────

def get_current_user():
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("token")
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        if is_token_blacklisted(token):
            return None
        return data
    except (SignatureExpired, BadSignature):
        return None

def _ensure_blacklist_table():
    if 'token_blacklist' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS token_blacklist (
            token_hash VARCHAR(255) PRIMARY KEY,
            blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        _tables_checked.add('token_blacklist')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def blacklist_token(token):
    _ensure_blacklist_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO token_blacklist (token_hash) VALUES (%s) ON CONFLICT DO NOTHING",
            (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def is_token_blacklisted(token):
    _ensure_blacklist_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT 1 FROM token_blacklist WHERE token_hash = %s",
            (hashlib.sha256(token.encode()).hexdigest(),))
        return c.fetchone() is not None
    except Exception:
        return False
    finally:
        c.close()
        conn.close()

def cleanup_blacklist():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM token_blacklist WHERE blacklisted_at < NOW() - INTERVAL '7 days'")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

# ─── RBAC Permission System ────────────────────────────────────

PERMISSIONS = {
    "crm:read": "View CRM clients and contacts",
    "crm:write": "Create/update CRM entries",
    "crm:delete": "Delete CRM entries",
    "recruitment:read": "View job postings and applications",
    "recruitment:write": "Create/update job postings",
    "recruitment:delete": "Delete job postings",
    "payroll:read": "View payroll data",
    "payroll:write": "Process payroll",
    "leaves:read": "View leave requests",
    "leaves:approve": "Approve/reject leave requests",
    "tickets:read": "View support tickets",
    "tickets:write": "Create/update tickets",
    "tickets:delete": "Delete tickets",
    "chat:read": "View chat conversations",
    "chat:write": "Send messages",
    "users:read": "View user list",
    "users:write": "Create/update users",
    "users:delete": "Delete users",
    "settings:read": "View system settings",
    "settings:write": "Modify system settings",
    "reports:read": "View reports",
    "audit:read": "View audit logs",
}

def _ensure_permissions_table():
    if 'role_permissions' in _tables_checked:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS role_permissions (
            role VARCHAR(50) NOT NULL,
            permission VARCHAR(100) NOT NULL,
            PRIMARY KEY (role, permission))""")
        conn.commit()
        _tables_checked.add('role_permissions')
    except Exception:
        conn.rollback()
    finally:
        c.close()
        conn.close()

def get_permissions_for_role(role):
    perms = set()
    if role == "admin":
        return set(PERMISSIONS.keys())
    _ensure_permissions_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT permission FROM role_permissions WHERE role = %s", (role,))
        for row in c.fetchall():
            perms.add(row[0] if isinstance(row, dict) else row[0])
    except Exception:
        pass
    finally:
        c.close()
        conn.close()
    return perms

def require_permission(permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") == "admin":
                return f(*args, **kwargs)
            perms = get_permissions_for_role(user.get("role", ""))
            if permission not in perms:
                return jsonify({"error": "Forbidden: insufficient permissions"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

def seed_default_permissions():
    _ensure_permissions_table()
    conn = get_connection()
    c = conn.cursor()
    try:
        role_perms = {
            "admin": list(PERMISSIONS.keys()),
            "employee": [
                "leaves:read",
                "chat:read", "chat:write",
                "tickets:read", "tickets:write",
                "recruitment:read",
            ],
            "candidate": [
                "recruitment:read",
            ],
            "client": [
                "crm:read",
                "chat:read", "chat:write",
            ],
        }
        for role, perms in role_perms.items():
            for p in perms:
                c.execute("INSERT INTO role_permissions (role, permission) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (role, p))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Seed permissions error: {e}")
    finally:
        c.close()
        conn.close()

# ─── Role & Validation Helpers ─────────────────────────────────

def require_role(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

def check_is_team_leader(user, cursor):
    if not user:
        return False
    if user.get("role") in ["admin", "team_leader"]:
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        d = ""
        if isinstance(res, dict):
            d = res.get("designation") or ""
        elif isinstance(res, (tuple, list)):
            d = res[0] or ""
        if "team leader" in d.lower() or "lead" in d.lower():
            return True
    return False

def check_is_crm_manager(user, cursor):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        d = ""
        if isinstance(res, dict):
            d = res.get("designation") or ""
        elif isinstance(res, (tuple, list)):
            d = res[0] or ""
        d = d.lower()
        if "team leader" in d or "lead" in d or "hr" in d or "human resource" in d:
            return True
    return False

def check_is_recruitment_manager(user, cursor):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        d = ""
        if isinstance(res, dict):
            d = res.get("designation") or ""
        elif isinstance(res, (tuple, list)):
            d = res[0] or ""
        if "hr" in d.lower() or "human resource" in d.lower():
            return True
    return False

# ─── Rate Limiting ─────────────────────────────────────────────

rate_limit_records = {}

def rate_limit(limit=100, period=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
            now = time.time()
            timestamps = rate_limit_records.get(ip, [])
            timestamps = [t for t in timestamps if now - t < period]
            if len(timestamps) >= limit:
                return jsonify({"error": "Too many requests. Please try again in a few moments."}), 429
            timestamps.append(now)
            rate_limit_records[ip] = timestamps
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ─── Validation ────────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")

def validate_email(email):
    if not email or len(email) > 150:
        return False
    return bool(EMAIL_REGEX.match(email))

def validate_password_strength(password):
    if not password:
        return False, "Password cannot be empty"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password must not exceed 128 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    special_chars = "!@#$%^&*()-_=+[]{}|;:',.<>?/`~"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    return True, ""
