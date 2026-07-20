import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def purge_junk_employees():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Exact whitelist of emails to keep
        whitelist_emails = {
            'naveenadudekula01@gmail.com',
            'venkateshnaik9956@gmail.com',
            'riteshlingamallu8@gmail.com',
            'saidabeeshaik22@gmail.com',
            'lingamallutharunmanikanta@gmail.com',
            'hashv153@gmail.com',
            # Admin accounts
            'testadmin@elevateiq.com',
            'admin@elevateiq.com',
            'edutechadmin@elevateiq.com'
        }
        
        # Get admin user ID for fallback conversation creator
        c.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin_row = c.fetchone()
        admin_id = admin_row[0] if admin_row else 1

        # Get IDs of all users NOT in whitelist
        c.execute("SELECT id, name, email FROM users")
        all_users = c.fetchall()
        
        to_delete_ids = []
        for u in all_users:
            u_id, u_name, u_email = u[0], u[1], u[2]
            if u_email.lower() not in whitelist_emails:
                to_delete_ids.append((u_id, u_name, u_email))
                
        print(f"Found {len(to_delete_ids)} unnecessary accounts to delete out of {len(all_users)} total accounts.")
        
        for u_id, u_name, u_email in to_delete_ids:
            print(f"Deleting user '{u_name}' ({u_email}, ID: {u_id})...")
            # Cascade delete/update across all related tables
            c.execute("UPDATE conversations SET created_by = %s WHERE created_by = %s", (admin_id, u_id))
            c.execute("DELETE FROM messages WHERE sender_id = %s", (u_id,))
            c.execute("DELETE FROM conversation_members WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM attendance WHERE employee_id IN (SELECT id FROM employees WHERE user_id = %s)", (u_id,))
            c.execute("DELETE FROM leaves WHERE employee_id IN (SELECT id FROM employees WHERE user_id = %s)", (u_id,))
            c.execute("DELETE FROM payroll WHERE employee_id IN (SELECT id FROM employees WHERE user_id = %s)", (u_id,))
            c.execute("DELETE FROM employees WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM clients WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM course_enrollments WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM quiz_attempts WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM assignment_submissions WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM placement_tracks WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM student_leaves WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM login_attempts WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM csrf_tokens WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (u_id,))
            c.execute("DELETE FROM users WHERE id = %s", (u_id,))

        conn.commit()
        print("Successfully purged all unnecessary accounts! Only the 6 official employees and admin remain.")
    except Exception as e:
        conn.rollback()
        print(f"Error purging accounts: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    purge_junk_employees()
