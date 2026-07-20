"""
Database Connectivity and Pool Management Module.

This module initializes and manages a thread-safe PostgreSQL connection pool using 
psycopg2's `ThreadedConnectionPool`. It ensures connection safety across concurrent execution 
threads and gevent greenlets by tracking checkouts with unique UUID-based keys. It also 
provides self-healing checkouts by verifying connection health with a lightweight query 
('SELECT 1') before handing them off to callers.
"""

import os
import uuid
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from .config import Config

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
            # Initialize thread-safe connection pool with minimum 5 and maximum 120 connections
            db_pool = ThreadedConnectionPool(5, 120, dsn=dsn)
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
            count = cursor.fetchone()[0]
            if count == 0:
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
        """
        Initializes the PooledConnection wrapper.

        Args:
            pool (ThreadedConnectionPool): The database connection pool instance.
            conn (psycopg2.extensions.connection): The actual database connection object.
            key (str): Unique UUID string assigned to this connection checkout instance.
        """
        self._pool = pool
        self._conn = conn
        self._key = key

    def __getattr__(self, name):
        """
        Delegates attribute access to the underlying connection object.
        """
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        """
        Creates a cursor object using the underlying connection.
        """
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        """
        Commits any pending transactions.
        """
        self._conn.commit()

    def rollback(self):
        """
        Rolls back any pending transactions.
        """
        self._conn.rollback()

    def close(self):
        """
        Returns the connection back to the connection pool rather than closing it.
        """
        if self._conn and self._pool:
            # Safely return the connection to the pool using the unique checkout key
            self._pool.putconn(self._conn, key=self._key)
            self._conn = None
            self._pool = None

def get_connection():
    """
    Checks out a database connection from the global pool.

    Generates a unique UUID key for tracking the checkout, handles self-healing by 
    validating the connection with 'SELECT 1', and discards/recreates connections that 
    have dropped due to socket timeout or backend closure.

    Returns:
        PooledConnection: A wrapped connection safe for thread/greenlet usage.

    Raises:
        Exception: If no healthy connections can be retrieved after max retries.
    """
    global db_pool
    if db_pool is None:
        init_db()
        
    retries = 5
    import time
    for attempt in range(retries):
        # Generate a unique key for tracking checkout and returning to the pool
        key = str(uuid.uuid4())
        try:
            conn = db_pool.getconn(key=key)
            if conn.closed == 0:
                now = time.time()
                last_check = getattr(conn, "_last_checked_ts", 0)
                if now - last_check > 30:
                    try:
                        c = conn.cursor()
                        c.execute("SELECT 1")
                        c.fetchone()
                        c.close()
                        conn._last_checked_ts = now
                    except Exception:
                        # Connection is dead; discard and put it back to close it
                        try:
                            db_pool.putconn(conn, key=key, close=True)
                        except Exception:
                            pass
                        continue

                # Reset connection state if it was left in an error/aborted transaction
                if conn.info.transaction_status != 0:  # 0 = IDLE
                    conn.rollback()
                return PooledConnection(db_pool, conn, key)
            else:
                try:
                    db_pool.putconn(conn, key=key, close=True)
                except Exception:
                    pass
        except Exception as e:
            # Catch pool exhaustion or dead socket errors, back off, and retry
            if "exhausted" in str(e).lower() or "closed" in str(e).lower() or "unexpectedly" in str(e).lower():
                time.sleep(0.05 * (attempt + 1))
                continue
            raise e
                
    # Fallback: If all retries failed, attempt one final checkout
    key = str(uuid.uuid4())
    conn = db_pool.getconn(key=key)
    return PooledConnection(db_pool, conn, key)

