import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def create_elevateiq_company_group():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        group_name = "ElevateIQ"
        
        # Check if 'ElevateIQ' group already exists
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = %s", (group_name,))
        row = c.fetchone()
        
        if row:
            conv_id = row[0]
            print(f"Group chat '{group_name}' already exists (ID: {conv_id}).")
        else:
            # Get admin user ID
            c.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin_row = c.fetchone()
            admin_id = admin_row[0] if admin_row else 1
            
            c.execute(
                "INSERT INTO conversations (type, name, created_by) VALUES ('group', %s, %s) RETURNING id",
                (group_name, admin_id)
            )
            conv_id = c.fetchone()[0]
            print(f"Created new company-wide group chat '{group_name}' (ID: {conv_id}).")

        # Enroll ALL active system users into ElevateIQ group
        c.execute("SELECT id FROM users WHERE role IN ('employee', 'admin', 'team_leader')")
        all_users = c.fetchall()
        
        enrolled_count = 0
        for u in all_users:
            u_id = u[0]
            c.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (conv_id, u_id)
            )
            enrolled_count += c.rowcount

        # Post welcome message if message history is empty
        c.execute("SELECT id FROM messages WHERE conversation_id = %s LIMIT 1", (conv_id,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO messages (conversation_id, sender_id, content) VALUES (%s, (SELECT id FROM users WHERE role = 'admin' LIMIT 1), %s)",
                (conv_id, "Welcome everyone to the official ElevateIQ company-wide group chat! 🎉 Feel free to connect and collaborate here.")
            )

        conn.commit()

        # Fetch member count
        c.execute("SELECT COUNT(*) FROM conversation_members WHERE conversation_id = %s", (conv_id,))
        total_members = c.fetchone()[0]

        print(f"\nSuccessfully created and enrolled {total_members} company members into '{group_name}' group chat!")
    except Exception as e:
        conn.rollback()
        print(f"Error creating company-wide group: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    create_elevateiq_company_group()
