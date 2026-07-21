import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def purge_orphaned_chats():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Delete conversation_members for users that no longer exist in users table
        c.execute("""
            DELETE FROM conversation_members 
            WHERE user_id NOT IN (SELECT id FROM users)
        """)
        deleted_cm = c.rowcount
        print(f"Removed {deleted_cm} orphaned member entries of deleted users.")

        # 2. Delete DM conversations that have fewer than 2 active members remaining
        c.execute("""
            DELETE FROM conversations 
            WHERE type = 'dm' AND id IN (
                SELECT c.id FROM conversations c
                LEFT JOIN conversation_members cm ON c.id = cm.conversation_id
                JOIN users u ON cm.user_id = u.id
                WHERE c.type = 'dm'
                GROUP BY c.id
                HAVING COUNT(DISTINCT u.id) < 2
            )
        """)
        deleted_dm = c.rowcount
        print(f"Purged {deleted_dm} orphaned DM conversation rooms.")

        # 3. Clean messages belonging to non-existent conversations
        c.execute("""
            DELETE FROM messages 
            WHERE conversation_id NOT IN (SELECT id FROM conversations)
        """)
        deleted_msg = c.rowcount
        print(f"Purged {deleted_msg} orphaned messages.")

        conn.commit()
        print("Database chat tables sanitized successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error purging orphaned chats: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    purge_orphaned_chats()
