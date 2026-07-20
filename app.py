import sys
import os

# Enable gevent & psycogreen non-blocking async I/O
try:
    import gevent.monkey
    gevent.monkey.patch_all(thread=False)
    import psycogreen.gevent
    psycogreen.gevent.patch_psycopg()
except Exception:
    pass

# Add backend folder to python search path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Import create_app from the modular elevateiq_app package
from elevateiq_app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
