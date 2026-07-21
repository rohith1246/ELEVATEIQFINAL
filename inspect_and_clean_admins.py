import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def inspect_and_clean_users():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Fetch all users with admin role or admin in name/email
        c.execute("SELECT id, name, email, role FROM users WHERE role = 'admin' OR email LIKE '%admin%' OR name LIKE '%admin%'")
        admins = c.fetchall()
        print("Current Admin-related users in DB:")
        for a in admins:
            print(f"  ID: {a[0]}, Name: {a[1]}, Email: {a[2]}, Role: {a[3]}")

        # Keep primary official admin (admin@elevateiq.com or lowest ID official admin)
        # Delete extra dummy admins like 'demo.admin@elevateiq.com', 'edutech admin', etc.
        c.execute("""
            SELECT id FROM users 
            WHERE role = 'admin' OR email LIKE '%admin%' OR name LIKE '%admin%'
            ORDER BY id ASC
        """)
        all_admin_ids = [r[0] for r in c.fetchall()]

        if len(all_admin_ids) > 1:
            primary_admin_id = all_admin_ids[0]
            extra_admin_ids = all_admin_ids[1:]
            print(f"\nPrimary Admin ID kept: {primary_admin_id}")
            print(f"Extra Admin IDs to delete/purge: {extra_admin_ids}")

            for extra_id in extra_admin_ids:
                c.execute("UPDATE conversations SET created_by = %s WHERE created_by = %s", (primary_admin_id, extra_id))
                c.execute("UPDATE messages SET sender_id = %s WHERE sender_id = %s", (primary_admin_id, extra_id))
                c.execute("UPDATE assessments SET created_by = %s WHERE created_by = %s" if False else "SELECT 1")

            placeholders = ",".join(["%s"] * len(extra_admin_ids))
            
            # Delete from conversation_members
            c.execute(f"DELETE FROM conversation_members WHERE user_id IN ({placeholders})", extra_admin_ids)
            # Delete from employees if any
            c.execute(f"DELETE FROM employees WHERE user_id IN ({placeholders})", extra_admin_ids)
            # Delete from users
            c.execute(f"DELETE FROM users WHERE id IN ({placeholders})", extra_admin_ids)
            print(f"Purged {c.rowcount} extra admin user accounts.")

        # 2. Ensure 'Zoning Team' group contains strictly valid active employees + official primary admin
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
        zoning_row = c.fetchone()
        if zoning_row:
            zoning_id = zoning_row[0]
            print(f"\nZoning Team group ID: {zoning_id}")
            
            # Remove any non-existent user members from Zoning Team
            c.execute("DELETE FROM conversation_members WHERE conversation_id = %s AND user_id NOT IN (SELECT id FROM users)", (zoning_id,))
            print(f"Cleaned {c.rowcount} stale entries from Zoning Team.")
            
            # Print current members of Zoning Team
            c.execute("""
                SELECT u.id, u.name, u.email, u.role 
                FROM conversation_members cm
                JOIN users u ON cm.user_id = u.id
                WHERE cm.conversation_id = %s
                ORDER BY u.name ASC
            """, (zoning_id,))
            members = c.fetchall()
            print(f"Zoning Team now has {len(members)} official members:")
            for m in members:
                print(f"  - {m[1]} ({m[2]}, {m[3]})")

        conn.commit()
        print("\nDatabase admin & Zoning Team cleanup finished successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error cleaning users: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    inspect_and_clean_users()
