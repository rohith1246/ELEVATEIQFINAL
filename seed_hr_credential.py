import os
import sys
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def seed_hr_account():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    
    password = "Password123!"
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    hr_email = "demo.hr@elevateiq.com"
    hr_name = "Demo HR Specialist"
    hr_role = "employee"
    hr_emp_id = "ELVIQ_HR01"
    hr_dept = "Human Resources"
    hr_desg = "HR Specialist"

    try:
        # Upsert into users table
        c.execute("SELECT id FROM users WHERE email = %s", (hr_email,))
        row = c.fetchone()
        if row:
            user_id = row[0]
            c.execute(
                "UPDATE users SET name = %s, password = %s, role = %s, portal = 'elevateiq' WHERE id = %s",
                (hr_name, hashed_pw, hr_role, user_id)
            )
            print(f"Updated existing HR account: {hr_name} ({hr_email})")
        else:
            c.execute(
                "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, %s, 'elevateiq') RETURNING id",
                (hr_name, hr_email, hashed_pw, hr_role)
            )
            user_id = c.fetchone()[0]
            print(f"Created new HR account: {hr_name} ({hr_email})")

        # Create/update employee profile
        c.execute("SELECT id FROM employees WHERE user_id = %s", (user_id,))
        emp_row = c.fetchone()
        if emp_row:
            c.execute(
                "UPDATE employees SET employee_id = %s, department = %s, designation = %s, status = 'Active' WHERE id = %s",
                (hr_emp_id, hr_dept, hr_desg, emp_row[0])
            )
        else:
            c.execute(
                "INSERT INTO employees (user_id, employee_id, department, designation, status) VALUES (%s, %s, %s, %s, 'Active')",
                (user_id, hr_emp_id, hr_dept, hr_desg)
            )

        conn.commit()
        print("\nHR demo credentials successfully created and configured in database!")
    except Exception as e:
        conn.rollback()
        print(f"Error seeding HR account: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    seed_hr_account()
