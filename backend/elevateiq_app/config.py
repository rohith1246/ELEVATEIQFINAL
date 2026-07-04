"""
Configuration Module for ElevateIQ.

Loads environment variables from a .env file (if present) and defines the config parameters
for the Flask application (secret key, database URI, execution environment, port, and file uploads).
"""

import os
from dotenv import load_dotenv

# Load key-value pairs from .env file into the shell environment variables
load_dotenv()

class Config:
    """
    Application configuration settings.

    Reads configuration values from environment variables with fallback defaults.
    """
    # Key used for cryptographic signing of cookies and security tokens
    SECRET_KEY = os.getenv("SECRET_KEY", "elevate_iq_secret_key")
    
    # Path or connection string to the database (typically SQLite for this project)
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Execution mode (development, production, or testing)
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    
    # Upload folder located at the root level 'uploads/resumes'
    # Computed dynamically relative to this file's position
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'resumes')
    
    # Networking port the application server binds to
    PORT = int(os.getenv("PORT", 5000))

