import os
import sys
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def create_admin():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    
    password = "Password123!"
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    admin_accounts = [
        {
            "name": "ElevateIQ Admin",
            "email": "admin@elevateiq.com",
            "role": "admin",
            "portal": "elevateiq"
        },
        {
            "name": "Test Administrator",
            "email": "testadmin@elevateiq.com",
            "role": "admin",
            "portal": "elevateiq"
        }
    ]

    try:
        for acc in admin_accounts:
            email = acc["email"]
            name = acc["name"]
            role = acc["role"]
            portal = acc["portal"]

            c.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = c.fetchone()
            if row:
                user_id = row[0]
                c.execute(
                    "UPDATE users SET name = %s, password = %s, role = %s, portal = %s WHERE id = %s",
                    (name, hashed_pw, role, portal, user_id)
                )
                print(f"Updated existing admin account: {name} ({email})")
            else:
                c.execute(
                    "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (name, email, hashed_pw, role, portal)
                )
                user_id = c.fetchone()[0]
                print(f"Created new admin account: {name} ({email})")

            # Add admin user to Zoning Team group chat if it exists
            c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
            z_row = c.fetchone()
            if z_row:
                c.execute(
                    "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (z_row[0], user_id)
                )

        conn.commit()
        print("\nNew Admin user accounts successfully created and configured in database!")
    except Exception as e:
        conn.rollback()
        print(f"Error creating admin accounts: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    create_admin()
