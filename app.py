import sys
import os

# Add backend folder to the front of python module search path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Import create_app and create the Flask application instance
from app import create_app
app = create_app()
