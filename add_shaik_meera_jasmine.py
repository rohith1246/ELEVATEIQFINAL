import os
import sys
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def add_employee():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    
    # Ensure phone and phone_number columns exist
    try:
        c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone VARCHAR(30)")
        c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone_number VARCHAR(30)")
        conn.commit()
    except Exception as e:
        conn.rollback()

    name = "Shaik Meera Jasmine"
    email = "jashusk786@gmail.com"
    phone = "8985429675"
    dept = "IT"
    desg = "Cyber Security Analyst"
    doj = "2026-07-22"
    password = "Password123!"

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        # Get next available employee_id number
        c.execute("SELECT MAX(CAST(SUBSTRING(employee_id FROM 10) AS INT)) FROM employees WHERE employee_id LIKE 'ELVIQ_EMP%'")
        row_max = c.fetchone()
        max_num = row_max[0] if row_max and row_max[0] is not None else 122
        next_num = max_num + 1
        emp_id = f"ELVIQ_EMP{next_num}"

        # 1. Insert or update user record
        c.execute("SELECT id FROM users WHERE LOWER(email) = %s", (email.lower(),))
        row = c.fetchone()
        if row:
            user_id = row[0]
            c.execute(
                "UPDATE users SET name = %s, password = %s, role = 'employee', portal = 'elevateiq' WHERE id = %s",
                (name, hashed_pw, user_id)
            )
            print(f"Updated existing user ID {user_id}: {name} ({email})")
        else:
            c.execute(
                "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, 'employee', 'elevateiq') RETURNING id",
                (name, email, hashed_pw)
            )
            user_id = c.fetchone()[0]
            print(f"Created new user ID {user_id}: {name} ({email})")

        # 2. Insert or update employee record
        c.execute("SELECT id FROM employees WHERE user_id = %s", (user_id,))
        e_row = c.fetchone()
        if e_row:
            c.execute(
                "UPDATE employees SET employee_id = %s, phone = %s, phone_number = %s, department = %s, designation = %s, date_of_joining = %s, status = 'Active' WHERE id = %s",
                (emp_id, phone, phone, dept, desg, doj, e_row[0])
            )
            print(f"Updated employee record: {emp_id}")
        else:
            c.execute(
                "INSERT INTO employees (user_id, employee_id, phone, phone_number, department, designation, date_of_joining, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')",
                (user_id, emp_id, phone, phone, dept, desg, doj)
            )
            print(f"Created employee record: {emp_id}")

        # 3. Enroll in company-wide 'ElevateIQ' group chat
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'ElevateIQ'")
        g_row = c.fetchone()
        if g_row:
            conv_id = g_row[0]
            c.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (conv_id, user_id)
            )
            print(f"Enrolled {name} in company-wide 'ElevateIQ' group chat.")

        # 4. Enroll in 'Zoning Team' group chat if present
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
        z_row = c.fetchone()
        if z_row:
            z_id = z_row[0]
            c.execute(
                "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (z_id, user_id)
            )
            print(f"Enrolled {name} in 'Zoning Team' group chat.")

        conn.commit()

        # Re-fetch to verify
        c.execute("""
            SELECT u.id, u.name, u.email, u.role, e.employee_id, e.phone, e.department, e.designation, e.date_of_joining, e.status
            FROM users u
            JOIN employees e ON u.id = e.user_id
            WHERE u.id = %s
        """, (user_id,))
        record = c.fetchone()

        print("\nEmployee details added successfully:")
        print(f"  - User ID: {record[0]}")
        print(f"  - Name: {record[1]}")
        print(f"  - Email: {record[2]}")
        print(f"  - Role: {record[3]}")
        print(f"  - Employee ID: {record[4]}")
        print(f"  - Phone: {record[5]}")
        print(f"  - Department: {record[6]}")
        print(f"  - Designation: {record[7]}")
        print(f"  - Date of Joining: {record[8]}")
        print(f"  - Status: {record[9]}")
        print(f"  - Password: {password}")

    except Exception as e:
        conn.rollback()
        print("Error adding employee:", e)
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    add_employee()
