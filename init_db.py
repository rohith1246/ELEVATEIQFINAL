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
        
    # Seed default courses if courses table is empty
    cursor.execute("SELECT COUNT(*) FROM courses")
    if cursor.fetchone()[0] == 0:
        print("Seeding default courses...")
        default_courses = [
            ('Full Stack Web Development', 'Beginner', '20 weeks', 45000, 60000, 4.8, 'layers'),
            ('Python for Backend Engineers', 'Beginner', '12 weeks', 28000, 35000, 4.7, 'code'),
            ('Java Enterprise Full Stack', 'Intermediate', '18 weeks', 42000, 52000, 4.6, 'coffee'),
            ('AI & Machine Learning Bootcamp', 'Advanced', '22 weeks', 65000, 82000, 4.9, 'brain'),
            ('Data Science Professional', 'Intermediate', '20 weeks', 52000, 65000, 4.7, 'chart'),
            ('Cloud & DevOps Engineering', 'Intermediate', '16 weeks', 48000, 58000, 4.6, 'cloud'),
            ('AWS Solutions Architect Prep', 'Advanced', '10 weeks', 32000, 40000, 4.8, 'server'),
            ('Cyber Security Fundamentals', 'Beginner', '14 weeks', 36000, 45000, 4.5, 'shield'),
            ('UI/UX Design Professional', 'Beginner', '12 weeks', 34000, 42000, 4.8, 'palette')
        ]
        for course in default_courses:
            cursor.execute(
                """
                INSERT INTO courses (title, level, duration, price, old_price, rating, icon)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                course
            )
        conn.commit()
        print(f"Seeded {len(default_courses)} default courses.")
        
    cursor.close()
    conn.close()
except Exception as e:
    print("An error occurred:", e)
