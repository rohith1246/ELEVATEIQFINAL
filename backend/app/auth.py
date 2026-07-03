from flask import request, jsonify
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from .config import Config

serializer = URLSafeTimedSerializer(Config.SECRET_KEY)

def get_current_user():
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=604800)  # Token valid for max 7 days
        return data  # dict containing id, email, role, name, employee_id
    except (SignatureExpired, BadSignature):
        return None

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

# --- Designation check helpers ---

def check_is_team_leader(user, cursor):
    if not user:
        return False
    if user.get("role") in ["admin", "team_leader"]:
        return True
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "team leader" in designation or "lead" in designation:
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
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "team leader" in designation or "lead" in designation or "hr" in designation or "human resource" in designation:
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
        designation = ""
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "hr" in designation or "human resource" in designation:
            return True
    return False
