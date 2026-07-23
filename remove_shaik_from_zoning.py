import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def remove_from_zoning():
    conn = get_connection()
    c = conn.cursor()
    
    email = "jashusk786@gmail.com"
    
    try:
        # Get user ID
        c.execute("SELECT id, name FROM users WHERE LOWER(email) = %s", (email.lower(),))
        user_row = c.fetchone()
        if not user_row:
            print(f"User with email {email} not found!")
            return
        
        user_id, name = user_row
        
        # Get Zoning Team group chat ID
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
        z_row = c.fetchone()
        if not z_row:
            print("Zoning Team group chat not found.")
            return
        
        z_id = z_row[0]
        
        # Remove membership
        c.execute("DELETE FROM conversation_members WHERE conversation_id = %s AND user_id = %s", (z_id, user_id))
        deleted_count = c.rowcount
        conn.commit()
        
        if deleted_count > 0:
            print(f"Successfully removed {name} ({email}) from 'Zoning Team' group chat.")
        else:
            print(f"{name} ({email}) was not in 'Zoning Team' group chat.")

    except Exception as e:
        conn.rollback()
        print("Error removing from Zoning Team:", e)
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    remove_from_zoning()
