import sys
import os

# Insert backend directory to the search path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Unregister root-level 'app' module from the cache to prevent circular import resolution
if 'app' in sys.modules:
    del sys.modules['app']

# Load the real app package from backend/app and create the Flask application instance
from app import create_app
app = create_app()
