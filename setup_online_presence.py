import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def setup_presence():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Add last_seen column to users table if not exists
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        conn.commit()
        print("Column 'last_seen' added/verified in users table.")
    except Exception as e:
        conn.rollback()
        print(f"Error setting up presence tracking: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    setup_presence()
