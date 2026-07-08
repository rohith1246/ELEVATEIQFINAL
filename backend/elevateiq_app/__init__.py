"""
ElevateIQ Application Factory Module.

This module initializes the Flask application configuration, enables Cross-Origin Resource
Sharing (CORS), sets up the database connection pool, registers application blueprints, 
and serves the frontend static assets.
"""

from flask import Flask, send_from_directory
from flask_cors import CORS
from .config import Config
from .database import init_db

import os

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
    
    # Configure Cross-Origin Resource Sharing (CORS) for external api access
    CORS(app)
    
    # Initialize database tables and connection pool
    init_db(app)

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

    import gzip
    import io
    from flask import request

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

    return app

