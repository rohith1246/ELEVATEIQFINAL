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

# ── Workers & Connections (Async High Performance) ─────────────
# Use gevent worker class for asynchronous I/O and high concurrency (1000+ SSE/HTTP connections)
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gevent'
worker_connections = 2000

# ── Memory & Process Hygiene ─────────────────────────
max_requests = 5000
max_requests_jitter = 250
timeout = 120
keepalive = 65
preload_app = False


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
    """
    Apply gevent monkey patching to psycopg2 for non-blocking DB greenlets,
    and start the Neon keepalive background thread in each worker process.
    """
    try:
        from psycogreen.gevent import patch_psycopg
        patch_psycopg()
    except Exception:
        pass

    t = threading.Thread(target=_neon_keepalive_loop, daemon=True)
    t.start()
