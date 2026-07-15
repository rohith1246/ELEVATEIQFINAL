"""
ElevateIQ Application Factory Module.

This module initializes the Flask application configuration, enables Cross-Origin Resource
Sharing (CORS), sets up the database connection pool, registers application blueprints, 
and serves the frontend static assets.
"""

import logging
import os
import secrets
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from .config import Config, safe_error
from .database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """
    Factory function to create and configure the Flask application.

    This function configures the app to serve frontend files, initializes the SQLite 
    database, configures CORS, and registers all feature blueprints (Auth, CRM, 
    Recruitment, Chat, Leaves).

    Returns:
        Flask: The configured Flask application instance.
    """
    # Determine the directory path of the frontend static files relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(base_dir, "../../frontend"))
    
    # Initialize the Flask instance with static routing pointing to the frontend directory
    app = Flask(__name__, static_url_path="", static_folder=frontend_dir)
    app.config.from_object(Config)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # Configure Cross-Origin Resource Sharing (CORS) for external api access
    cors_origins = app.config.get("CORS_ORIGINS", "")
    if cors_origins:
        CORS(app, origins=cors_origins.split(), supports_credentials=True)
    else:
        CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=False)
    
    # Initialize database tables and connection pool
    init_db(app)

    # Seed default RBAC permissions
    from .auth import seed_default_permissions
    try:
        seed_default_permissions()
    except Exception as e:
        logger.warning(f"Could not seed permissions (non-critical): {e}")

    # Generate a nonce per request for CSP
    @app.before_request
    def set_csp_nonce():
        if not hasattr(request, "csp_nonce"):
            request.csp_nonce = secrets.token_urlsafe(16)

    # Per-endpoint request body size limits
    @app.before_request
    def limit_request_size():
        size_limits = {
            "/login": 1024,
            "/register": 1024,
            "/api/contact": 2048,
            "/api/newsletter": 512,
            "/api/auth/refresh": 256,
            "/profile": 4096,
        }
        for path, limit in size_limits.items():
            if request.path == path and request.content_length and request.content_length > limit:
                return jsonify({"error": f"Request body too large for {path}"}), 413

    @app.route("/")
    def index():
        """
        Serves the landing page of the application.

        Returns:
            Response: The frontend/index.html file.
        """
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/favicon.ico")
    def favicon():
        """
        Serves the application favicon from static folder.
        """
        return send_from_directory(app.static_folder, "images/logo.png")

    # Lazy import and register Blueprints to prevent circular dependency issues
    from .routes.auth_routes import auth_bp
    from .routes.crm_routes import crm_bp
    from .routes.recruitment import recruitment_bp
    from .routes.chat import chat_bp
    from .routes.leaves import leaves_bp
    from .routes.edutech_routes import edutech_bp
    from .routes.payroll import payroll_bp
    from .routes.tickets import tickets_bp

    # Register each modular blueprint with the central Flask application
    app.register_blueprint(auth_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(recruitment_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(leaves_bp)
    app.register_blueprint(edutech_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(tickets_bp)

    @app.errorhandler(500)
    def handle_500(error):
        logger.error(f"Internal server error: {error}")
        return jsonify(safe_error()), 500

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_405(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        nonce = getattr(request, "csp_nonce", secrets.token_urlsafe(16))
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            f"img-src 'self' data:; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"connect-src 'self' https://unpkg.com; "
            f"frame-src 'self' https://www.google.com https://maps.google.com; "
            f"object-src 'none'"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Nonce"] = nonce
        if app.config.get("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Cache static assets (images, CSS, JS, fonts) for 1 year
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            if any(ext in content_type for ext in ("image", "font", "text/css", "javascript")):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    import gzip
    import io

    @app.after_request
    def compress_response(response):
        """
        Compresses response payloads using gzip to reduce latency.
        """
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response
            
        if response.status_code < 200 or response.status_code >= 300:
            return response
            
        if "Content-Encoding" in response.headers:
            return response
            
        content_type = response.headers.get("Content-Type", "").lower()
        is_compressible = (
            "text" in content_type or
            "javascript" in content_type or
            "css" in content_type or
            "json" in content_type
        )
        if not is_compressible:
            return response

        response.direct_passthrough = False
        data = response.get_data()
        
        # Only compress payloads larger than 500 bytes
        if len(data) < 500:
            return response
            
        gzip_buffer = io.BytesIO()
        with gzip.GzipFile(mode="wb", fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(data)
            
        response.set_data(gzip_buffer.getvalue())
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = len(response.get_data())
        return response

    @app.after_request
    def add_cache_headers(response):
        """
        Configures aggressive browser caching for static assets to reduce network roundtrips.
        """
        ext = os.path.splitext(request.path)[1].lower()
        if ext in ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.mp4', '.webp', '.svg']:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    return app

