"""
Database Connectivity Module with High-Performance Warm Connection Pool for Neon PostgreSQL.

Features:
- Fast LIFO connection pooling (0ms checkout for warm sockets)
- Request-scoped tracking via Flask g for guaranteed zero-leak teardown
- Automatic health check and socket recovery
- Multi-query statement support and keepalives
"""

import os
import time
import queue
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from flask import g, has_request_context
from .config import Config

class WarmConnectionPool:
    """
    Lightweight, thread-safe, self-healing LIFO connection pool.
    Reuses warm TCP sockets to eliminate 1.5s TLS handshakes on every web request.
    """
    def __init__(self, dsn, min_conn=4, max_conn=35):
        self.dsn = dsn
        self.max_conn = max_conn
        self._pool = queue.LifoQueue(maxsize=max_conn)
        self._total_created = 0
        
        # Pre-warm initial sockets
        for _ in range(min_conn):
            try:
                conn = self._create_conn()
                self._pool.put_nowait((conn, time.time()))
                self._total_created += 1
            except Exception as e:
                print("Pool pre-warm notice:", e)
                break

    def _create_conn(self):
        return psycopg2.connect(
            self.dsn,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=10,
            keepalives_interval=3,
            keepalives_count=5
        )

    def get_conn(self):
        # Try retrieving a warm connection from pool
        while not self._pool.empty():
            try:
                conn, last_used = self._pool.get_nowait()
                # If connection is alive and healthy, return it
                if conn.closed == 0:
                    try:
                        # Reset transaction state if anything left open
                        if conn.info.transaction_status != 0:
                            conn.rollback()
                        return conn
                    except Exception:
                        pass
                # Dead socket: close cleanly
                try:
                    conn.close()
                except Exception:
                    pass
            except queue.Empty:
                break

        # Create new connection if pool was empty or had stale sockets
        return self._create_conn()

    def put_conn(self, conn):
        if conn and conn.closed == 0:
            try:
                if conn.info.transaction_status != 0:
                    conn.rollback()
                self._pool.put_nowait((conn, time.time()))
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
        else:
            try:
                conn.close()
            except Exception:
                pass


_global_pool = None

def get_pool():
    global _global_pool
    if _global_pool is None:
        dsn = Config.DATABASE_URL
        if not dsn:
            raise ValueError("CRITICAL: DATABASE_URL is not configured.")
        _global_pool = WarmConnectionPool(dsn, min_conn=4, max_conn=35)
    return _global_pool


def init_db(app=None):
    """
    Initializes required schema tables and seeds default designations.
    """
    dsn = app.config.get("DATABASE_URL") if app else Config.DATABASE_URL
    if not dsn:
        raise ValueError("CRITICAL: DATABASE_URL environment variable is missing.")

    conn = psycopg2.connect(
        dsn,
        connect_timeout=8,
        keepalives=1,
        keepalives_idle=5,
        keepalives_interval=2,
        keepalives_count=3
    )
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS student_leaves (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                leave_type VARCHAR(50) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                reason TEXT,
                status VARCHAR(20) DEFAULT 'Pending',
                approved_by INT REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'General',
                status VARCHAR(20) DEFAULT 'Open',
                priority VARCHAR(20) DEFAULT 'Medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_notes TEXT,
                resolved_by INT REFERENCES users(id) ON DELETE SET NULL,
                resolved_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

            CREATE TABLE IF NOT EXISTS csrf_tokens (
                user_id INT NOT NULL, token VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, token)
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45)
            );
            CREATE TABLE IF NOT EXISTS account_lockouts (
                user_id INT PRIMARY KEY,
                locked_until TIMESTAMP NOT NULL,
                attempt_count INT DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS password_history (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                token_hash VARCHAR(255) NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                revoked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS role_permissions (
                role VARCHAR(50) NOT NULL,
                permission VARCHAR(100) NOT NULL,
                PRIMARY KEY (role, permission)
            );
        """)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM designations;")
        if cursor.fetchone()[0] == 0:
            defaults = [
                "HR Manager", "Team Leader", "Software Engineer",
                "Backend Lead", "Frontend Developer", "QA Engineer", "Product Manager"
            ]
            for name in defaults:
                cursor.execute("INSERT INTO designations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (name,))
            conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        print("Schema init notice:", e)
    finally:
        conn.close()


class PooledConnectionWrapper:
    """
    Wrapper around database connection that returns it to the warm pool on close().
    """
    def __init__(self, raw_conn, pool):
        self._conn = raw_conn
        self._pool = pool
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        if self._conn and not self._closed:
            self._conn.commit()

    def rollback(self):
        if self._conn and not self._closed:
            self._conn.rollback()

    def close(self):
        if not self._closed and self._conn:
            self._closed = True
            if self._pool:
                self._pool.put_conn(self._conn)
            else:
                try:
                    self._conn.close()
                except Exception:
                    pass


def get_connection():
    """
    Fast, instant checkout from warm connection pool.
    Automatically tracked in Flask g for zero-leak teardown.
    """
    pool = get_pool()
    raw_conn = pool.get_conn()
    wrapped = PooledConnectionWrapper(raw_conn, pool)

    if has_request_context():
        if not hasattr(g, '_active_db_connections'):
            g._active_db_connections = []
        g._active_db_connections.append(wrapped)

    return wrapped


def teardown_appcontext_db(exception=None):
    """
    Guarantees every checked-out connection is returned to the pool at the end of the request.
    """
    if has_request_context() and hasattr(g, '_active_db_connections'):
        for conn in g._active_db_connections:
            try:
                conn.close()
            except Exception:
                pass
        g._active_db_connections.clear()

