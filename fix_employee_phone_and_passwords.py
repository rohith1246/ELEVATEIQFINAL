import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

new_employees_data = [
    {"name": "Pendala Shiva", "email": "shivapendala9@gmail.com", "phone": "8008529416"},
    {"name": "Gandhi Komarala", "email": "komaralagandhi@gmail.com", "phone": "9959461095"},
    {"name": "Pitta Anji", "email": "pittaanji9390@gmail.com", "phone": "9390376865"},
    {"name": "Gaddam Vasavi", "email": "vasavigaddam36@gmail.com", "phone": "6301882155"},
    {"name": "Gada Satya Sai Mani Venkatesh", "email": "satyasaigada@gmail.com", "phone": "9676209419"},
    {"name": "Ballagiri Divya", "email": "divyaballagiri@gmail.com", "phone": "8143825389"},
    {"name": "Lingamallu Saikumar", "email": "saikumarlingamallu2003@gmail.com", "phone": "9542692748"},
    {"name": "Narra Dhanunjay", "email": "narradhanunjay5002@gmail.com", "phone": "7032848359"},
    {"name": "Jayhind Yadav", "email": "jayhind01022003@gmail.com", "phone": "6393496909"},
    {"name": "Tangi Sandhyarani", "email": "sandhyarani25my@gmail.com", "phone": "7780547490"},
    {"name": "Sativada Sravani", "email": "sathivadasravani@gmail.com", "phone": "9515187383"},
    {"name": "Shaik Rajiya", "email": "shaikrajiya1890@gmail.com", "phone": "6300907733"},
    {"name": "Boppudi Bhanu Satya Prakash", "email": "boppudibhanu123@gmail.com", "phone": "8309533031"},
    {"name": "Karna Deepthi Reddy", "email": "deepthireddy6303@gmail.com", "phone": "6303751699"},
    {"name": "Shahbaz Alam", "email": "sbzalam2025@gmail.com", "phone": "7079619717"},
    {"name": "Pullagura Sneha", "email": "snehapullagura@gmail.com", "phone": "8500439794"},
    {"name": "Shaik Mujavar Moulali", "email": "skmmoulali27@gmail.com", "phone": "9908801330"},
    {"name": "V. Rohith Kumar", "email": "rohithvuppula@gmail.com", "phone": "8328186045"},
    {"name": "Bathika Dileep", "email": "bathikadileep@gmail.com", "phone": "9391434950"},
    {"name": "Tinglikar Tejaswar", "email": "ttejaswar1234@gmail.com", "phone": "9849910189"},
    {"name": "Boddu Srijay Vamshi", "email": "srijay3959@gmail.com", "phone": "7993276837"}
]

def fix_phone_numbers():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Ensure both phone_number and phone columns exist
        c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone_number VARCHAR(30)")
        c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS phone VARCHAR(30)")

        # Sync phone numbers into employees table
        for emp in new_employees_data:
            email = emp["email"].lower().strip()
            phone = emp["phone"]

            c.execute("""
                UPDATE employees 
                SET phone_number = %s, phone = %s 
                WHERE user_id = (SELECT id FROM users WHERE LOWER(email) = %s LIMIT 1)
            """, (phone, phone, email))
            print(f"Updated phone for {emp['name']} -> {phone}")

        # Sync any null phone_number from phone and vice versa across all employees
        c.execute("UPDATE employees SET phone_number = phone WHERE (phone_number IS NULL OR phone_number = '') AND phone IS NOT NULL")
        c.execute("UPDATE employees SET phone = phone_number WHERE (phone IS NULL OR phone = '') AND phone_number IS NOT NULL")

        conn.commit()
        print("\nAll employee phone numbers updated and synchronized successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error syncing phone numbers: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    fix_phone_numbers()
