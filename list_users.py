import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app.database import get_connection

conn = get_connection()
c = conn.cursor()
c.execute("SELECT id, name, email, role FROM users ORDER BY id")
rows = c.fetchall()
for r in rows:
    print(f"ID {r[0]}: {r[1]} ({r[2]}) - Role: {r[3]}")
c.close()
conn.close()
