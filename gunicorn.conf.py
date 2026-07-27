"""
ElevateIQ — Gunicorn Production Configuration (Python 3.12 Stable)
"""
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# ── Binding ──────────────────────────────────────────────────
bind = os.environ.get('BIND', '127.0.0.1:5000')

# ── Workers & Threads (Python 3.12 Compatible) ────────────────
workers = int(os.environ.get('WORKERS', 4))
worker_class = 'gthread'
threads = 4
worker_connections = 1000

# ── Memory & Process Hygiene ─────────────────────────
max_requests = 1000
max_requests_jitter = 50
timeout = 60
keepalive = 5
graceful_timeout = 30
preload_app = False
worker_tmp_dir = '/dev/shm'
