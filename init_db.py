import os
import secrets
import string
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

    import bcrypt

    def generate_strong_password():
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        return ''.join(secrets.choice(alphabet) for _ in range(16)) + secrets.choice("!@#$%&*")

    admin_password = os.getenv("ADMIN_PASSWORD", generate_strong_password())
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        print("Seeding default admin user...")
        hashed_password = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("System Administrator", "admin@elevateiq.com", hashed_password, "admin")
        )
        conn.commit()
        print("WARNING: Default admin credentials - Email: admin@elevateiq.com / Password: [REDACTED]")
        print("Set ADMIN_PASSWORD environment variable to use a custom admin password.")
        
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

    # Seed default company designations if table is empty
    cursor.execute("SELECT COUNT(*) FROM designations")
    if cursor.fetchone()[0] == 0:
        default_desgs = [
            'Software Engineer', 'Senior Software Engineer', 'Team Lead', 
            'Engineering Manager', 'Product Manager', 'UI/UX Designer', 
            'DevOps Engineer', 'QA Engineer', 'HR Specialist', 'HR Manager', 
            'Accountant', 'Business Analyst', 'Data Scientist', 'Senior Mentor', 
            'Customer Support Executive'
        ]
        for desg in default_desgs:
            cursor.execute("INSERT INTO designations (name) VALUES (%s) ON CONFLICT DO NOTHING", (desg,))
        conn.commit()
        print(f"Seeded {len(default_desgs)} default company designations.")

    # Ensure high-performance indexes exist on authentication & session tables
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_csrf_tokens_user_id ON csrf_tokens(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_user_id ON login_attempts(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_account_lockouts_user_id ON account_lockouts(user_id)")
    
    # Prune old stale login attempts and CSRF tokens to keep tables tiny and fast
    cursor.execute("DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '1 day'")
    cursor.execute("DELETE FROM csrf_tokens WHERE created_at < NOW() - INTERVAL '7 days'")
    cursor.execute("DELETE FROM users WHERE email = 'bathikadileep@gmail.com'")
    conn.commit()

    # Get course IDs
    cursor.execute("SELECT id, title FROM courses")
    courses_map = {row[1]: row[0] for row in cursor.fetchall()}

    # Seed enrollments for Aarav Mehta (62%, 38%, 21% course progress stats)
    for c_title, price in [('Full Stack Web Development', 45000), ('Python for Backend Engineers', 28000), ('UI/UX Design Professional', 34000)]:
        if c_title in courses_map:
            c_id = courses_map[c_title]
            cursor.execute("SELECT id FROM course_enrollments WHERE user_id = %s AND course_id = %s", (student_id, c_id))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO course_enrollments (user_id, course_id, price_paid, status) VALUES (%s, %s, %s, 'Active')",
                    (student_id, c_id, price)
                )
    conn.commit()

    # Seed assignments
    assignments_data = [
        ('Full Stack Web Development', 'Week 4 — REST API Patterns', 'Design and implement REST APIs for an e-commerce platform using Flask.', '2026-07-15 23:59:59'),
        ('Full Stack Web Development', 'Week 5 — Deployment & CI', 'Write a GitHub Actions workflow to run lint and unit tests on commit.', '2026-07-22 23:59:59'),
        ('Python for Backend Engineers', 'APIs & Auth Security', 'Secure REST endpoints using JWT tokens and role-based permissions.', '2026-07-18 23:59:59'),
        ('UI/UX Design Professional', 'Design Systems Lab', 'Create a reusable component library mockup in Figma following glassmorphism principles.', '2026-07-20 23:59:59')
    ]
    for c_title, title, desc, due in assignments_data:
        if c_title in courses_map:
            c_id = courses_map[c_title]
            cursor.execute("SELECT id FROM assignments WHERE course_id = %s AND title = %s", (c_id, title))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO assignments (course_id, title, description, due_date) VALUES (%s, %s, %s, %s)",
                    (c_id, title, desc, due)
                )
    conn.commit()

    # Seed assignment submissions for Aarav
    if 'Full Stack Web Development' in courses_map:
        fs_id = courses_map['Full Stack Web Development']
        cursor.execute("SELECT id FROM assignments WHERE course_id = %s AND title = %s", (fs_id, 'Week 4 — REST API Patterns'))
        assign_row = cursor.fetchone()
        if assign_row:
            a_id = assign_row[0]
            cursor.execute("SELECT id FROM assignment_submissions WHERE assignment_id = %s AND user_id = %s", (a_id, student_id))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO assignment_submissions (assignment_id, user_id, submission_text, file_path, grade, feedback, status)
                    VALUES (%s, %s, 'https://github.com/aaravmehta/ecommerce-rest-api', 'ecommerce_api_project.zip', 'Pending', 'Mentor review pending', 'Submitted')
                    """,
                    (a_id, student_id)
                )
                conn.commit()

    # Seed quizzes
    quizzes_data = [
        ('Full Stack Web Development', 'REST API Basics', 15),
        ('Full Stack Web Development', 'CI/CD Workflows', 20),
        ('Python for Backend Engineers', 'Decorators & Generators', 10)
    ]
    for c_title, title, dur in quizzes_data:
        if c_title in courses_map:
            c_id = courses_map[c_title]
            cursor.execute("SELECT id FROM quizzes WHERE course_id = %s AND title = %s", (c_id, title))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO quizzes (course_id, title, duration_minutes) VALUES (%s, %s, %s)",
                    (c_id, title, dur)
                )
    conn.commit()

    # Seed quiz questions for REST API Basics
    cursor.execute("SELECT q.id FROM quizzes q JOIN courses c ON q.course_id = c.id WHERE c.title = 'Full Stack Web Development' AND q.title = 'REST API Basics'")
    quiz_row = cursor.fetchone()
    if quiz_row:
        qz_id = quiz_row[0]
        cursor.execute("SELECT id FROM quiz_questions WHERE quiz_id = %s", (qz_id,))
        if not cursor.fetchone():
            questions = [
                ("Which HTTP method should be used to create a new resource?", "GET", "POST", "PUT", "DELETE", "B"),
                ("What does HTTP status code 201 mean?", "OK", "Created", "Accepted", "No Content", "B"),
                ("What is the primary format used in modern REST APIs?", "XML", "HTML", "JSON", "Plain Text", "C")
            ]
            for q_text, oa, ob, oc, od, ans in questions:
                cursor.execute(
                    "INSERT INTO quiz_questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (qz_id, q_text, oa, ob, oc, od, ans)
                )
            conn.commit()

    # Seed quiz attempts
    if quiz_row:
        qz_id = quiz_row[0]
        cursor.execute("SELECT id FROM quiz_attempts WHERE quiz_id = %s AND user_id = %s", (qz_id, student_id))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions) VALUES (%s, %s, 3, 3)",
                (qz_id, student_id)
            )
            conn.commit()

    # Seed course resources
    resources_data = [
        ('Full Stack Web Development', 'REST API Design Best Practices Guide', 'PDF', 'https://example.com/rest-best-practices.pdf'),
        ('Full Stack Web Development', 'Docker & Kubernetes Cheat Sheet', 'PDF', 'https://example.com/docker-cheatsheet.pdf'),
        ('Python for Backend Engineers', 'Decorators and Functional Programming Slides', 'Slides', 'https://example.com/python-decorators.pdf'),
        ('UI/UX Design Professional', 'Figma Glassmorphism Design System Template', 'Link', 'https://figma.com/file/glassmorphism-template')
    ]
    for c_title, title, r_type, url in resources_data:
        if c_title in courses_map:
            c_id = courses_map[c_title]
            cursor.execute("SELECT id FROM course_resources WHERE course_id = %s AND title = %s", (c_id, title))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO course_resources (course_id, title, resource_type, resource_url) VALUES (%s, %s, %s, %s)",
                    (c_id, title, r_type, url)
                )
    conn.commit()
    print("Student LMS seeding completed successfully!")
        
    cursor.close()
    conn.close()
except Exception as e:
    print("An error occurred during database init:", e)

