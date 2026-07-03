from flask import Flask, send_from_directory
from flask_cors import CORS
from .config import Config
from .database import init_db

import os

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.abspath(os.path.join(base_dir, "../../frontend"))
    app = Flask(__name__, static_url_path="", static_folder=frontend_dir)
    app.config.from_object(Config)
    
    CORS(app)
    init_db(app)

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # Register blueprints
    from .routes.auth_routes import auth_bp
    from .routes.crm_routes import crm_bp
    from .routes.recruitment import recruitment_bp
    from .routes.chat import chat_bp
    from .routes.leaves import leaves_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(recruitment_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(leaves_bp)

    return app
