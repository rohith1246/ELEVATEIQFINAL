import sys
import os

# Add backend folder to python search path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Import create_app from the modular elevateiq_app package
# pyrefly: ignore [missing-import]
from elevateiq_app import create_app
app = create_app()
