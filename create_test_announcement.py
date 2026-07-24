import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def insert_announcement():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        title = "Testing Real-Time Notifications Feature 🚀"
        content = "This official company announcement is for testing our new real-time notifications engine. All employees will receive instant notifications and can click to view this announcement!"
        
        c.execute(
            "INSERT INTO announcements (title, content) VALUES (%s, %s) RETURNING id",
            (title, content)
        )
        new_id = c.fetchone()[0]
        conn.commit()

        print(f"\nAnnouncement #{new_id} created successfully!")
        print(f"Title: {title}")
        print(f"Content: {content}")
    except Exception as e:
        conn.rollback()
        print(f"Error creating announcement: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    insert_announcement()
