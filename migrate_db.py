import os
import sys
import psycopg2
from psycopg2.extras import DictCursor

def migrate():
    neon_url = "postgresql://neondb_owner:npg_cS5VsRvqxl9H@ep-icy-dust-ainl946k-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    local_url = os.getenv("DATABASE_URL", "postgresql://elevateiq:Password123!@127.0.0.1:5432/elevateiq")

    # Change working directory so relative file opens (e.g. open("schema.sql")) work correctly
    os.chdir("/var/www/elevateiq")

    # Set environment variables so database init scripts target local database
    os.environ["DATABASE_URL"] = local_url
    
    # Add paths so we can import elevateiq_app
    sys.path.insert(0, "/var/www/elevateiq")
    sys.path.insert(0, "/var/www/elevateiq/backend")

    # Clean local DB to resolve stale/outdated table schemas
    print("Resetting local database public schema...")
    try:
        conn_local_reset = psycopg2.connect(local_url)
        cur_local_reset = conn_local_reset.cursor()
        cur_local_reset.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public; GRANT ALL ON SCHEMA public TO postgres;")
        conn_local_reset.commit()
        conn_local_reset.close()
        print("Schema reset successful!")
    except Exception as reset_err:
        print(f"Schema reset warning: {reset_err}")

    # 1. Run local schema creation and seeding via init_db.py
    print("Initializing local schema and seeding defaults...")
    try:
        import init_db
    except Exception as init_err:
        print(f"init_db execution: {init_err}")

    # 2. Initialize Flask app to trigger creation of dynamic auth/token tables
    print("Initializing Flask app to create dynamic tables...")
    try:
        from elevateiq_app import create_app
        app = create_app()
    except Exception as app_err:
        print(f"Flask app init error: {app_err}")


    print("Connecting to Neon...")
    conn_neon = psycopg2.connect(neon_url)
    cur_neon = conn_neon.cursor(cursor_factory=DictCursor)

    print("Connecting to Local PostgreSQL...")
    conn_local = psycopg2.connect(local_url)
    cur_local = conn_local.cursor()

    # Disable constraints temporarily for bulk data loading
    cur_local.execute("SET session_replication_role = 'replica';")

    # Get list of tables
    cur_neon.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    tables = [r[0] for r in cur_neon.fetchall()]
    print(f"Discovered tables to migrate: {tables}")

    for table in tables:
        print(f"Migrating table: {table}...")
        # Clear existing data first to prevent duplicate key violations on re-run
        cur_local.execute(f"TRUNCATE TABLE {table} CASCADE;")
        
        cur_neon.execute(f"SELECT * FROM {table}")
        rows = cur_neon.fetchall()
        if not rows:
            print(f"Table {table} is empty. Skipping.")
            continue

        columns = list(rows[0].keys())
        col_list = ", ".join(columns)
        val_placeholders = ", ".join(["%s"] * len(columns))
        
        insert_query = f"INSERT INTO {table} ({col_list}) VALUES ({val_placeholders})"
        
        # Prepare rows for insert
        data_to_insert = [tuple(row) for row in rows]
        
        cur_local.executemany(insert_query, data_to_insert)
        print(f"Successfully migrated {len(rows)} rows for {table}.")

    # Restore constraints
    cur_local.execute("SET session_replication_role = 'origin';")
    conn_local.commit()
    print("All tables migrated successfully!")

    # Reset sequences for serial columns
    print("Resetting sequences...")
    for table in tables:
        # Check if the table has an 'id' column
        cur_neon.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = 'id'
        """, (table,))
        if cur_neon.fetchone():
            try:
                # Reset key generator sequence to max(id) + 1
                cur_local.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id), 1)) FROM {table};")
                conn_local.commit()
            except Exception as seq_err:
                print(f"Warning: Could not reset sequence for table {table}: {seq_err}")
                conn_local.rollback()

    print("Migration finished cleanly!")

if __name__ == "__main__":
    migrate()
