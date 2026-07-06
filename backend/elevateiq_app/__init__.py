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

    # Register each modular blueprint with the central Flask application
    app.register_blueprint(auth_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(recruitment_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(leaves_bp)

    return app

