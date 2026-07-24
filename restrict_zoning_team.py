import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

OFFICIAL_ZONING_EMAILS = [
    "venkateshnaik9956@gmail.com",
    "naveenadudekula01@gmail.com",
    "riteshlingamallu8@gmail.com",
    "lingamallutharunmanikanta@gmail.com",
    "hashv153@gmail.com",
    "saidabeeshaik22@gmail.com",
    "admin@elevateiq.com"
]

def restrict_zoning_team():
    print("Connecting to database...")
    conn = get_connection()
    c = conn.cursor()
    try:
        # Find Zoning Team conversation ID
        c.execute("SELECT id FROM conversations WHERE type = 'group' AND name = 'Zoning Team'")
        z_row = c.fetchone()
        if not z_row:
            print("Zoning Team group chat not found!")
            return

        z_id = z_row[0]
        print(f"Found Zoning Team group (ID: {z_id})")

        # Delete all members from Zoning Team who are NOT in OFFICIAL_ZONING_EMAILS
        c.execute("""
            DELETE FROM conversation_members 
            WHERE conversation_id = %s 
              AND user_id NOT IN (
                  SELECT id FROM users WHERE LOWER(email) IN (%s, %s, %s, %s, %s, %s, %s)
              )
        """, (z_id, *[e.lower() for e in OFFICIAL_ZONING_EMAILS]))
        
        removed_count = c.rowcount
        print(f"Removed {removed_count} extra employees from Zoning Team.")

        # Ensure all 7 official members are enrolled
        for email in OFFICIAL_ZONING_EMAILS:
            c.execute("SELECT id FROM users WHERE LOWER(email) = %s", (email.lower(),))
            u_row = c.fetchone()
            if u_row:
                user_id = u_row[0]
                c.execute(
                    "INSERT INTO conversation_members (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (z_id, user_id)
                )

        conn.commit()

        # Display final list of members in Zoning Team
        c.execute("""
            SELECT u.name, u.email, u.role
            FROM conversation_members cm
            JOIN users u ON cm.user_id = u.id
            WHERE cm.conversation_id = %s
            ORDER BY u.name ASC
        """, (z_id,))
        final_members = c.fetchall()

        print(f"\nZoning Team now has strictly {len(final_members)} official members:")
        for m in final_members:
            print(f"  - {m[0]} ({m[1]}, {m[2]})")

        print("\nZoning Team membership restricted successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error restricting Zoning Team: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    restrict_zoning_team()
