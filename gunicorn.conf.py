"""
ElevateIQ — Gunicorn Production Configuration
"""
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# ── Binding ──────────────────────────────────────────────────
bind = os.environ.get('BIND', '127.0.0.1:5000')

# ── Workers & Concurrency ────────────────────────────────────
# 4 worker processes x 16 threads = 64 simultaneous concurrent slots
workers = int(os.environ.get('WORKERS', 4))
threads = int(os.environ.get('THREADS', 16))
worker_class = 'gthread'
worker_connections = 2000

# ── Memory & Process Hygiene ─────────────────────────────────
max_requests = 2000
max_requests_jitter = 100
timeout = 180
keepalive = 5
graceful_timeout = 60
preload_app = False
worker_tmp_dir = '/dev/shm'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'warning'
