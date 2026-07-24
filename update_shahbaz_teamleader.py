import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def inspect_and_update_shahbaz():
    conn = get_connection()
    c = conn.cursor()
    try:
        # Search for Shahbaz in users and employees
        c.execute("""
            SELECT u.id, u.name, u.email, u.role, e.id as emp_id, e.employee_id, e.designation, e.department
            FROM users u
            LEFT JOIN employees e ON u.id = e.user_id
            WHERE LOWER(u.name) LIKE '%shahbaz%' OR LOWER(u.email) LIKE '%shahbaz%' OR LOWER(u.email) LIKE '%sbzalam%'
        """)
        rows = c.fetchall()
        print("Matching users before update:", rows)

        if not rows:
            print("No user found for Shahbaz!")
            return

        for r in rows:
            user_id = r[0]
            # Update role in users table to 'team_leader' (or keep 'employee' with designation 'Team Leader')
            # Updating both user role and employee designation ensures full access across all endpoints.
            c.execute("UPDATE users SET role = 'team_leader' WHERE id = %s", (user_id,))
            c.execute("UPDATE employees SET designation = 'Team Leader' WHERE user_id = %s", (user_id,))
            print(f"Updated user ID {user_id} ({r[1]} - {r[2]}): role set to 'team_leader' and designation set to 'Team Leader'.")

        conn.commit()

        # Re-fetch to confirm
        c.execute("""
            SELECT u.id, u.name, u.email, u.role, e.employee_id, e.designation, e.department
            FROM users u
            LEFT JOIN employees e ON u.id = e.user_id
            WHERE LOWER(u.name) LIKE '%shahbaz%' OR LOWER(u.email) LIKE '%shahbaz%' OR LOWER(u.email) LIKE '%sbzalam%'
        """)
        print("Updated records:", c.fetchall())

    except Exception as e:
        conn.rollback()
        print("Error updating Shahbaz:", e)
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    inspect_and_update_shahbaz()
