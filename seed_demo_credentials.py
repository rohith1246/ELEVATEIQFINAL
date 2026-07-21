import os
import sys
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def seed_demo_accounts():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    
    password = "Password123!"
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    demo_accounts = [
        {
            "name": "Demo Admin",
            "email": "demo.admin@elevateiq.com",
            "role": "admin",
            "portal": "elevateiq"
        },
        {
            "name": "Demo Team Leader",
            "email": "demo.tl@elevateiq.com",
            "role": "employee",
            "portal": "elevateiq",
            "employee_id": "ELVIQ_TL01",
            "department": "Engineering",
            "designation": "Team Lead"
        },
        {
            "name": "Demo Employee",
            "email": "demo.employee@elevateiq.com",
            "role": "employee",
            "portal": "elevateiq",
            "employee_id": "ELVIQ_EMP01",
            "department": "Engineering",
            "designation": "Software Engineer"
        },
        {
            "name": "Demo Client",
            "email": "demo.client@elevateiq.com",
            "role": "client",
            "portal": "elevateiq",
            "client_id": "CLT_DEMO01",
            "company_name": "Demo Enterprise Inc"
        },
        {
            "name": "Demo Student",
            "email": "demo.student@elevateiq.com",
            "role": "candidate",
            "portal": "edutech"
        }
    ]

    try:
        for acc in demo_accounts:
            email = acc["email"]
            name = acc["name"]
            role = acc["role"]
            portal = acc["portal"]

            # Upsert into users table
            c.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = c.fetchone()
            if row:
                user_id = row[0]
                c.execute(
                    "UPDATE users SET name = %s, password = %s, role = %s, portal = %s WHERE id = %s",
                    (name, hashed_pw, role, portal, user_id)
                )
                print(f"Updated existing demo account: {name} ({email})")
            else:
                c.execute(
                    "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (name, email, hashed_pw, role, portal)
                )
                user_id = c.fetchone()[0]
                print(f"Created new demo account: {name} ({email})")

            # Create employee profile if role is employee
            if role == "employee":
                emp_id = acc["employee_id"]
                dept = acc["department"]
                desg = acc["designation"]
                c.execute("SELECT id FROM employees WHERE user_id = %s", (user_id,))
                if not c.fetchone():
                    c.execute(
                        "INSERT INTO employees (user_id, employee_id, department, designation, status) VALUES (%s, %s, %s, %s, 'Active')",
                        (user_id, emp_id, dept, desg)
                    )

            # Create client profile if role is client
            if role == "client":
                clt_id = acc["client_id"]
                comp_name = acc["company_name"]
                c.execute("SELECT id FROM clients WHERE user_id = %s", (user_id,))
                if not c.fetchone():
                    c.execute(
                        "INSERT INTO clients (user_id, client_id, company_name) VALUES (%s, %s, %s)",
                        (user_id, clt_id, comp_name)
                    )

            # Create placement track if candidate
            if role == "candidate":
                c.execute("SELECT id FROM placement_tracks WHERE user_id = %s", (user_id,))
                if not c.fetchone():
                    c.execute(
                        """
                        INSERT INTO placement_tracks (user_id, current_stage, next_steps, resume_approved, mock_interview_score, recruiter_feedback)
                        VALUES (%s, 'Technical Evaluation', 'Complete Python Backend Assessment', TRUE, 90, 'Excellent technical background.')
                        """,
                        (user_id,)
                    )

        conn.commit()
        print("\nAll role demo credentials created successfully in database!")
    except Exception as e:
        conn.rollback()
        print(f"Error seeding demo accounts: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    seed_demo_accounts()
