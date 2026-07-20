#!/usr/bin/env python3
"""
Utility script to purge dummy and test employee records from PostgreSQL.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL is not set in environment or .env file.")
    sys.exit(1)

def purge_dummy_employees():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    try:
        # Delete dummy employee seed "bathikadileep@gmail.com" and any test employee records
        cursor.execute("""
            DELETE FROM users 
            WHERE role = 'employee' 
              AND (
                email = 'bathikadileep@gmail.com' 
                OR email LIKE '%dummy%' 
                OR email LIKE '%test%'
                OR email LIKE '%example.com%'
              )
        """)
        deleted_count = cursor.rowcount
        conn.commit()
        print(f"Successfully removed {deleted_count} dummy employee record(s) from the database.")
    except Exception as e:
        conn.rollback()
        print(f"Error purging dummy employees: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    purge_dummy_employees()
