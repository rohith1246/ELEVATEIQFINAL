"""
Database Connectivity Module.

Uses direct psycopg2 connections (no client-side pool) since Neon PostgreSQL
provides PgBouncer connection pooling on the server side. This eliminates all
dead-socket hang issues caused by client-side pool stale connections.
"""

import os
import uuid
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from .config import Config

# Keep ThreadedConnectionPool import for PooledConnection compatibility
from psycopg2.pool import ThreadedConnectionPool

# Global database connection pool instance
db_pool = None


def init_db(app=None):
    """
    Initializes the global PostgreSQL connection pool and seeds default schema tables.

    Checks the 'DATABASE_URL' config parameter. Instantiates a ThreadedConnectionPool with a 
    minimum of 1 and maximum of 40 connections. Automatically initializes the 'designations' 
    table and seeds default designation roles if they do not already exist.

    Args:
        app (Flask, optional): The Flask application instance to read configuration from.

    Raises:
        ValueError: If the database connection string is missing.
        RuntimeError: If connection to the database cannot be established.
    """
    global db_pool
    if db_pool is None:
        dsn = app.config.get("DATABASE_URL") if app else Config.DATABASE_URL
        if not dsn:
            raise ValueError("CRITICAL: DATABASE_URL environment variable is missing or empty. Please check your config.")
        
        try:
            # Initialize thread-safe connection pool with TCP keepalives to prevent Neon serverless socket stalls
            pool_kwargs = {
                'connect_timeout': 5,
                'keepalives': 1,
                'keepalives_idle': 5,
                'keepalives_interval': 2,
                'keepalives_count': 3
            }
            # Initialize connection pool capped at 60 connections for high-concurrency 100+ member workloads
            db_pool = ThreadedConnectionPool(5, 60, dsn=dsn, cursor_factory=RealDictCursor, **pool_kwargs)
        except Exception as e:
            raise RuntimeError(f"CRITICAL: Failed to create database connection pool: {e}")
        
        # Ensure designations table is created and seeded on startup
        # We generate a unique UUID key for this checkout to prevent conflicts with concurrent requests
        key = str(uuid.uuid4())
        conn = db_pool.getconn(key=key)
        try:
            cursor = conn.cursor()
            # Create designations table if it doesn't already exist in the database schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS designations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create student_leaves table if it doesn't already exist
            cursor.execute("""
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
                )
            """)
            # Create tickets table if it doesn't already exist
            cursor.execute("""
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(user_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_sent ON messages(conversation_id, sent_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_reads_user_msg ON message_reads(user_id, message_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leaves_emp_status ON leaves(employee_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance(employee_id, date)")

            # Create authentication and brute force lockout helper tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS csrf_tokens (
                    user_id INT NOT NULL, token VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, token)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_lockouts (
                    user_id INT PRIMARY KEY,
                    locked_until TIMESTAMP NOT NULL,
                    attempt_count INT DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_history (
                    id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id SERIAL PRIMARY KEY, user_id INT NOT NULL,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role VARCHAR(50) NOT NULL,
                    permission VARCHAR(100) NOT NULL,
                    PRIMARY KEY (role, permission)
                )
            """)
            conn.commit()
            
            # Seed default designations if table is empty
            cursor.execute("SELECT COUNT(*) FROM designations")
            count = cursor.fetchone()
            count_val = count['count'] if isinstance(count, dict) else count[0]
            if count_val == 0:
                defaults = [
                    "HR Manager",
                    "Team Leader",
                    "Software Engineer",
                    "Backend Lead",
                    "Frontend Developer",
                    "QA Engineer",
                    "Product Manager"
                ]
                for name in defaults:
                    cursor.execute(
                        "INSERT INTO designations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (name,)
                    )
                conn.commit()
            cursor.close()
        except Exception as e:
            print("Failed to initialize designations table:", e)
            conn.rollback()
        finally:
            # Return connection to the pool using the same checkout key
            db_pool.putconn(conn, key=key)

class PooledConnection:
    """
    A wrapper class for database connections retrieved from the pool.

    Intercepts the connection close call to return the connection to the 
    ThreadedConnectionPool using a unique key instead of physically terminating 
    the socket connection. This prevents connection leaks and ensures thread-safe/
    greenlet-safe operation under asynchronous frameworks.
    """
    def __init__(self, pool, conn, key):
        self._pool = pool
        self._conn = conn
        self._key = key

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        if "cursor_factory" not in kwargs:
            kwargs["cursor_factory"] = RealDictCursor
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        if self._conn:
            self._conn.commit()

    def rollback(self):
        if self._conn:
            self._conn.rollback()

    def close(self):
        """
        Returns the connection back to the connection pool rather than closing it.
        """
        if self._conn and self._pool:
            try:
                self._pool.putconn(self._conn, key=self._key)
            except Exception:
                pass
            self._conn = None
            self._pool = None


def get_connection():
    """
    High-Performance Connection Retrieval for 100+ Member Load.
    Reuses pooled connections from ThreadedConnectionPool to eliminate WAN TLS latency.
    Falls back to direct connection if pool is uninitialized.
    """
    global db_pool
    dsn = Config.DATABASE_URL
    if db_pool:
        try:
            key = str(uuid.uuid4())
            raw_conn = db_pool.getconn(key=key)
            if raw_conn:
                return PooledConnection(db_pool, raw_conn, key)
        except Exception:
            pass

    return psycopg2.connect(
        dsn,
        connect_timeout=5,
        cursor_factory=RealDictCursor,
        keepalives=1,
        keepalives_idle=5,
        keepalives_interval=2,
        keepalives_count=3
    )

