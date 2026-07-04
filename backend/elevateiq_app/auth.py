"""
Authentication and Authorization Security Module.

This module provides functions and decorators to handle user sessions and roles. 
It uses URLSafeTimedSerializer from the `itsdangerous` package to generate/verify tokens, 
checks user authorization based on role/designation records in the database, 
and provides a custom in-memory rate limiting mechanism to mitigate brute-force attacks.
"""

from flask import request, jsonify
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from .config import Config

# Initialize a URLSafeTimedSerializer with the application's SECRET_KEY.
# This is used to securely sign cookies/tokens to prevent client-side tampering.
serializer = URLSafeTimedSerializer(Config.SECRET_KEY)

def get_current_user():
    """
    Retrieves and validates the current user's session token.

    Checks the 'token' cookie first, and falls back to checking the 'Authorization' header 
    for 'Bearer <token>' format. Decodes and verifies the token integrity using the 
    URLSafeTimedSerializer. The token is valid for a maximum duration of 7 days (604800 seconds).

    Returns:
        dict: A dictionary containing the user's details (id, email, role, name, employee_id) if valid.
        None: If no token is provided, or the token is expired or has an invalid signature.
    """
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None
    try:
        # Load token payload, verifying that it hasn't expired (max_age = 7 days)
        data = serializer.loads(token, max_age=604800)  # Token valid for max 7 days
        return data  # dict containing id, email, role, name, employee_id
    except (SignatureExpired, BadSignature):
        # SignatureExpired: Token timestamp exceeds max_age
        # BadSignature: Token signature doesn't match/is corrupted
        return None

def require_role(roles):
    """
    Decorator to restrict route access to users with specific roles.

    Args:
        roles (list of str): List of permitted roles (e.g. ['admin', 'employee']).

    Returns:
        function: The decorated view function wrapper.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            # Check if the user's role is in the list of authorized roles
            if user.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# --- Designation check helpers ---

def check_is_team_leader(user, cursor):
    """
    Checks if the user has team leadership privileges.

    Privileges are granted if the user's system role is 'admin' or 'team_leader', 
    or if their designation within the database contains "team leader" or "lead".

    Args:
        user (dict): The current user dictionary containing 'id' and 'role'.
        cursor (sqlite3.Cursor): Database cursor for executing queries.

    Returns:
        bool: True if the user is authorized as a team leader, False otherwise.
    """
    if not user:
        return False
    # Admins and designated team_leaders automatically receive team leader rights
    if user.get("role") in ["admin", "team_leader"]:
        return True
    
    # Query database to check designation from employees table
    cursor.execute("SELECT designation FROM employees WHERE user_id = %s", (user["id"],))
    res = cursor.fetchone()
    if res:
        designation = ""
        # Handle cases where SQLite row factory returns dict-like or tuple-like outputs
        if isinstance(res, dict):
            designation = res.get("designation") or ""
        elif isinstance(res, tuple) or isinstance(res, list):
            designation = res[0] or ""
        designation = designation.lower()
        if "team leader" in designation or "lead" in designation:
            return True
    return False

def check_is_crm_manager(user, cursor):
    """
    Checks if the user has CRM Manager privileges.

    Privileges are granted if the user is an 'admin' or if their designation 
    in the database contains "team leader", "lead", "hr", or "human resource".

    Args:
        user (dict): The current user dictionary containing 'id' and 'role'.
        cursor (sqlite3.Cursor): Database cursor for executing queries.

    Returns:
        bool: True if authorized as CRM manager, False otherwise.
    """
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    
    # Check designation from employees table
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
    """
    Checks if the user has Recruitment Manager privileges.

    Privileges are granted if the user is an 'admin' or if their designation 
    in the database contains "hr" or "human resource".

    Args:
        user (dict): The current user dictionary containing 'id' and 'role'.
        cursor (sqlite3.Cursor): Database cursor for executing queries.

    Returns:
        bool: True if authorized as recruitment manager, False otherwise.
    """
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    
    # Check designation from employees table
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

import time

# Dictionary to store request logs: {ip: [timestamps]}
rate_limit_records = {}

def rate_limit(limit=100, period=60):
    """
    Simple in-memory rate limiter decorator.

    Restricts clients based on IP addresses. Stores timestamps of requests in memory 
    and checks if the count exceeds the threshold in the given sliding window.

    Args:
        limit (int): Max number of requests allowed in the period. Default 100.
        period (int): Time window size in seconds. Default 60.

    Returns:
        function: Decorated route function that returns 429 status code if limited.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get client IP address
            # Support X-Forwarded-For header if behind Nginx or Render proxies
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if not ip:
                ip = "unknown"
            
            # Get current timestamp
            now = time.time()
            
            # Clean up old timestamps for this IP to prevent memory growth
            timestamps = rate_limit_records.get(ip, [])
            timestamps = [t for t in timestamps if now - t < period]
            
            # Check if limit has been exceeded
            if len(timestamps) >= limit:
                return jsonify({"error": f"Too many requests. Please try again in a few moments (limit: {limit} requests per {period} seconds)."}), 429
            
            # Record current request timestamp
            timestamps.append(now)
            rate_limit_records[ip] = timestamps
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

