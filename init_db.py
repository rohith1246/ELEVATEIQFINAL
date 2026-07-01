import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("Error: DATABASE_URL not found in environment.")
    exit(1)

print("Connecting to database...")
try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("Reading schema.sql...")
    with open("schema.sql", "r") as f:
        schema_sql = f.read()
        
    print("Creating tables...")
    cursor.execute(schema_sql)
    conn.commit()
    print("Tables created successfully!")
    
    # Check if admin user exists, if not seed it
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        import bcrypt
        print("Seeding default admin user...")
        hashed_password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("System Administrator", "admin@elevateiq.com", hashed_password, "admin")
        )
        conn.commit()
        print("Admin user seeded (admin@elevateiq.com / admin123)")
        
    cursor.close()
    conn.close()
except Exception as e:
    print("An error occurred:", e)
