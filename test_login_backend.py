import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

def test_login():
    conn = get_connection()
    c = conn.cursor()
    try:
        user_id = 1
        refresh_hash = "test_hash"
        csrf_token = "test_csrf"
        print("Testing multi-statement execution...")
        c.execute("""
            DELETE FROM login_attempts WHERE user_id = %s;
            UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = %s AND revoked = FALSE;
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, NOW() + INTERVAL '7 days');
            INSERT INTO csrf_tokens (user_id, token) VALUES (%s, %s);
            UPDATE users SET last_seen = NOW() WHERE id = %s;
        """, (user_id, user_id, user_id, refresh_hash, user_id, csrf_token, user_id))
        conn.commit()
        print("Multi-statement executed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"EXACT ERROR: {type(e).__name__}: {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    test_login()
