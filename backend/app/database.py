import os
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from .config import Config

db_pool = None

def init_db(app=None):
    global db_pool
    if db_pool is None:
        dsn = app.config.get("DATABASE_URL") if app else Config.DATABASE_URL
        # Initialize thread-safe connection pool
        db_pool = ThreadedConnectionPool(1, 20, dsn=dsn)
        
        # Ensure designations table is created and seeded on startup
        conn = db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS designations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            db_pool.putconn(conn)

class PooledConnection:
    """
    A connection wrapper that intercept connection close
    to return it to the ThreadedConnectionPool instead of closing it.
    """
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._conn and self._pool:
            self._pool.putconn(self._conn)
            self._conn = None
            self._pool = None

def get_connection():
    global db_pool
    if db_pool is None:
        init_db()
    conn = db_pool.getconn()
    return PooledConnection(db_pool, conn)
