import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def purge_test_groups():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Find group IDs for 'ZONING' and 'sql developer'
        c.execute("SELECT id, name FROM conversations WHERE type = 'group' AND (LOWER(name) LIKE '%zoning%' OR LOWER(name) LIKE '%sql developer%')")
        groups = c.fetchall()
        
        if not groups:
            print("No test groups found to purge.")
            return

        for g in groups:
            conv_id, name = g[0], g[1]
            print(f"Deleting test group '{name}' (ID: {conv_id})...")
            c.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
            c.execute("DELETE FROM conversation_members WHERE conversation_id = %s", (conv_id,))
            c.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))

        conn.commit()
        print("Successfully purged test chat groups!")
    except Exception as e:
        conn.rollback()
        print(f"Error purging groups: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    purge_test_groups()
