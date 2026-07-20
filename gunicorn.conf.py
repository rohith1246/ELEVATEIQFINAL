# ElevateIQ — Gunicorn Production Configuration (High Performance)
import multiprocessing
import os

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
