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
# gevent uses cooperative greenlets — unlike gthread, long-lived SSE /chat/stream
# connections do NOT block other requests. Each worker can serve 1000 connections.
workers = int(os.environ.get('WORKERS', 4))
worker_class = 'gevent'
worker_connections = 1000

# ── Memory & Process Hygiene ─────────────────────────────────
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5
graceful_timeout = 30
preload_app = False
worker_tmp_dir = '/dev/shm'
