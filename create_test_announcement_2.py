import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def insert_announcement_2():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        title = "Upcoming Platform Upgrade & Feature Release ✨"
        content = "We are releasing exciting new platform updates today including real-time group chat, employee presence status, and instant click-to-redirect notifications!"
        
        c.execute(
            "INSERT INTO announcements (title, content) VALUES (%s, %s) RETURNING id",
            (title, content)
        )
        new_id = c.fetchone()[0]
        conn.commit()

        print(f"\nSecond Announcement #{new_id} created successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error creating announcement: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    insert_announcement_2()
