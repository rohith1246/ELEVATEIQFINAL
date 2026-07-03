import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "elevate_iq_secret_key")
    DATABASE_URL = os.getenv("DATABASE_URL")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    
    # Upload folder located at the root level 'uploads/resumes'
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'resumes')
    
    PORT = int(os.getenv("PORT", 5000))
