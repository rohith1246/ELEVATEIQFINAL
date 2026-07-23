import os
import sys
import bcrypt
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

new_employees_data = [
    {"name": "Pendala Shiva", "email": "shivapendala9@gmail.com", "phone": "8008529416", "dept": "IT", "desg": "SQL DEVELOPER", "doj": "2026-04-08"},
    {"name": "Gandhi Komarala", "email": "komaralagandhi@gmail.com", "phone": "9959461095", "dept": "IT", "desg": "Python Developer", "doj": "2026-06-29"},
    {"name": "Pitta Anji", "email": "pittaanji9390@gmail.com", "phone": "9390376865", "dept": "IT", "desg": "Python Developer", "doj": "2026-04-08"},
    {"name": "Gaddam Vasavi", "email": "vasavigaddam36@gmail.com", "phone": "6301882155", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-06"},
    {"name": "Gada Satya Sai Mani Venkatesh", "email": "satyasaigada@gmail.com", "phone": "9676209419", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-13"},
    {"name": "Ballagiri Divya", "email": "divyaballagiri@gmail.com", "phone": "8143825389", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-09"},
    {"name": "Lingamallu Saikumar", "email": "saikumarlingamallu2003@gmail.com", "phone": "9542692748", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-01"},
    {"name": "Narra Dhanunjay", "email": "narradhanunjay5002@gmail.com", "phone": "7032848359", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-01"},
    {"name": "Jayhind Yadav", "email": "jayhind01022003@gmail.com", "phone": "6393496909", "dept": "IT", "desg": "Python Developer", "doj": "2026-04-14"},
    {"name": "Tangi Sandhyarani", "email": "sandhyarani25my@gmail.com", "phone": "7780547490", "dept": "IT", "desg": "Frontend Developer", "doj": "2026-07-20"},
    {"name": "Sativada Sravani", "email": "sathivadasravani@gmail.com", "phone": "9515187383", "dept": "IT", "desg": "Python Developer", "doj": "2026-04-29"},
    {"name": "Shaik Rajiya", "email": "shaikrajiya1890@gmail.com", "phone": "6300907733", "dept": "IT", "desg": "SQL Developer", "doj": "2026-06-29"},
    {"name": "Boppudi Bhanu Satya Prakash", "email": "boppudibhanu123@gmail.com", "phone": "8309533031", "dept": "IT", "desg": "Java Developer", "doj": "2026-06-19"},
    {"name": "Karna Deepthi Reddy", "email": "deepthireddy6303@gmail.com", "phone": "6303751699", "dept": "IT", "desg": "SQL Developer", "doj": "2026-06-29"},
    {"name": "Shahbaz Alam", "email": "sbzalam2025@gmail.com", "phone": "7079619717", "dept": "IT", "desg": "Python Developer", "doj": "2026-04-29"},
    {"name": "Pullagura Sneha", "email": "snehapullagura@gmail.com", "phone": "8500439794", "dept": "IT", "desg": "Python Developer", "doj": "2026-07-09"},
    {"name": "Shaik Mujavar Moulali", "email": "skmmoulali27@gmail.com", "phone": "9908801330", "dept": "IT", "desg": "Data Analyst", "doj": "2026-07-06"},
    {"name": "V. Rohith Kumar", "email": "rohithvuppula@gmail.com", "phone": "8328186045", "dept": "IT", "desg": "SQL Developer", "doj": "2026-04-08"},
    {"name": "Bathika Dileep", "email": "bathikadileep@gmail.com", "phone": "9391434950", "dept": "IT", "desg": "SQL Developer", "doj": "2026-04-08"},
    {"name": "Tinglikar Tejaswar", "email": "ttejaswar1234@gmail.com", "phone": "9849910189", "dept": "IT", "desg": "Cyber Security Analyst", "doj": "2026-07-06"},
    {"name": "Boddu Srijay Vamshi", "email": "srijay3959@gmail.com", "phone": "7993276837", "dept": "IT", "desg": "Cyber Security Analyst", "doj": "2026-07-06"},
    {"name": "Shaik Meera Jasmine", "email": "jashusk786@gmail.com", "phone": "8985429675", "dept": "IT", "desg": "Cyber Security Analyst", "doj": "2026-07-22"}
]

def add_employees():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    
    # Ensure phone column exists in employees table
    try:
        c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone VARCHAR(30)")
        conn.commit()
    except Exception as e:
        conn.rollback()

    password = "Password123!"
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Get Zoning Team group conversation ID if exists
    c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
    z_row = c.fetchone()
    z_id = z_row[0] if z_row else None

    added_list = []
    
    try:
        for idx, emp in enumerate(new_employees_data, start=101):
            name = emp["name"]
            email = emp["email"].lower().strip()
            phone = emp["phone"]
            dept = emp["dept"]
            desg = emp["desg"]
            doj = emp["doj"]
            emp_id = f"ELVIQ_EMP{idx}"

            # Check if user already exists
            c.execute("SELECT id FROM users WHERE email = %s", (email,))
            row = c.fetchone()
            if row:
                user_id = row[0]
                c.execute(
                    "UPDATE users SET name = %s, password = %s, role = 'employee', portal = 'elevateiq' WHERE id = %s",
                    (name, hashed_pw, user_id)
                )
                print(f"Updated existing user: {name} ({email})")
            else:
                c.execute(
                    "INSERT INTO users (name, email, password, role, portal) VALUES (%s, %s, %s, 'employee', 'elevateiq') RETURNING id",
                    (name, email, hashed_pw)
                )
                user_id = c.fetchone()[0]
                print(f"Created new user: {name} ({email})")

            # Check if employee record exists
            c.execute("SELECT id FROM employees WHERE user_id = %s", (user_id,))
            e_row = c.fetchone()
            if e_row:
                c.execute(
                    "UPDATE employees SET employee_id = %s, phone = %s, department = %s, designation = %s, date_of_joining = %s, status = 'Active' WHERE id = %s",
                    (emp_id, phone, dept, desg, doj, e_row[0])
                )
            else:
                c.execute(
                    "INSERT INTO employees (user_id, employee_id, phone, department, designation, date_of_joining, status) VALUES (%s, %s, %s, %s, %s, %s, 'Active')",
                    (user_id, emp_id, phone, dept, desg, doj)
                )

            # Enroll in Zoning Team group chat
            if z_id:
                c.execute(
                    "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (z_id, user_id)
                )

            added_list.append({
                "name": name,
                "email": email,
                "emp_id": emp_id,
                "phone": phone,
                "dept": dept,
                "desg": desg,
                "doj": doj,
                "password": password
            })

        conn.commit()
        print(f"\nSuccessfully added/updated {len(added_list)} employees in database!")
    except Exception as e:
        conn.rollback()
        print(f"Error adding employees: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    add_employees()
