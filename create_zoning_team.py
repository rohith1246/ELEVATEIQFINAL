import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def ensure_zoning_team():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Check if 'Zoning Team' already exists
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
        row = c.fetchone()
        
        if row:
            conv_id = row[0]
            print(f"Zoning Team group already exists (ID: {conv_id}).")
        else:
            # Get admin user ID
            c.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin_row = c.fetchone()
            admin_id = admin_row[0] if admin_row else 1
            
            c.execute(
                "INSERT INTO conversations (type, name, created_by) VALUES ('group', 'Zoning Team', %s) RETURNING id",
                (admin_id,)
            )
            conv_id = c.fetchone()[0]
            print(f"Created new 'Zoning Team' group chat (ID: {conv_id}).")

        # Add all users as members of Zoning Team
        c.execute("SELECT id FROM users")
        users = c.fetchall()
        for u in users:
            u_id = u[0]
            c.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (conv_id, u_id)
            )

        conn.commit()
        print(f"Successfully added {len(users)} members to 'Zoning Team'!")
    except Exception as e:
        conn.rollback()
        print(f"Error setting up Zoning Team: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    ensure_zoning_team()
