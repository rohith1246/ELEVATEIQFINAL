"""
ElevateIQ — Gunicorn Production Configuration (High Performance)
Added database keepalive warmer to prevent Neon PostgreSQL cold start delays.
"""
import multiprocessing
import os
import threading
import time

# ── Binding ──────────────────────────────────────────────────
bind = os.environ.get('BIND', '127.0.0.1:5000')

# ── Workers & Threads ─────────────────────────────────────────
# Rule of thumb: (2 × CPU cores) + 1 workers, with multi-threading
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gthread'
threads = 4
worker_connections = 1000

# ── Memory & Process Hygiene ─────────────────────────
max_requests = 2000
max_requests_jitter = 100
timeout = 60
keepalive = 5
preload_app = True


import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def _neon_keepalive_loop():
    """
    Sends a lightweight SELECT 1 ping to Neon PostgreSQL every 45 seconds
    to keep the serverless database warm and prevent the 5-20 second cold
    start delay on first login after idle periods.
    """
    time.sleep(10)  # Wait for app to fully boot first
    while True:
        try:
            from elevateiq_app.database import get_connection
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT 1")
            c.fetchone()
            c.close()
            conn.close()
        except Exception:
            pass
        time.sleep(45)


def post_fork(server, worker):
    """Start the Neon keepalive background thread in each worker process."""
    t = threading.Thread(target=_neon_keepalive_loop, daemon=True)
    t.start()
