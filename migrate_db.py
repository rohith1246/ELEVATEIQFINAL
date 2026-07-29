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

    print("Connecting to Neon...")
    conn_neon = psycopg2.connect(neon_url)
    cur_neon = conn_neon.cursor(cursor_factory=DictCursor)

    print("Connecting to Local Hostinger VPS PostgreSQL...")
    conn_local = psycopg2.connect(local_url)
    cur_local = conn_local.cursor()

    cur_neon.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    tables = [r[0] for r in cur_neon.fetchall()]
    tables.sort(key=lambda t: 0 if t == 'users' else (1 if t == 'employees' else 2))
    print(f"Discovered {len(tables)} tables to migrate: {tables}")

    cur_local.execute("SET session_replication_role = 'replica';")

    for table in tables:
        print(f"Migrating table schema and rows: {table}...")
        cur_local.execute("SET session_replication_role = 'replica';")
        
        # Fetch column definitions from Neon
        cur_neon.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position;
        """, (table,))
        cols = cur_neon.fetchall()
        
        if not cols:
            print(f"No columns found for {table}. Skipping.")
            continue

        col_defs = []
        for col in cols:
            c_name = col['column_name']
            c_type = col['data_type']
            c_len = col['character_maximum_length']
            
            if c_type == 'ARRAY':
                t_str = 'text[]'
            elif c_type == 'USER-DEFINED':
                t_str = 'text'
            elif c_len and c_type in ('character varying', 'character'):
                t_str = f"VARCHAR({c_len})"
            else:
                t_str = c_type

            col_defs.append(f'"{c_name}" {t_str}')

        cur_local.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
        create_sql = f'CREATE TABLE "{table}" ({", ".join(col_defs)});'
        cur_local.execute(create_sql)
        conn_local.commit()
        cur_local.execute("SET session_replication_role = 'replica';")

        cur_neon.execute(f'SELECT * FROM "{table}"')
        rows = cur_neon.fetchall()
        if not rows:
            print(f"Table {table} is empty. Created empty schema.")
            continue

        columns = list(rows[0].keys())
        col_list = ", ".join([f'"{c}"' for c in columns])
        val_placeholders = ", ".join(["%s"] * len(columns))
        
        insert_query = f'INSERT INTO "{table}" ({col_list}) VALUES ({val_placeholders})'
        data_to_insert = [tuple(row) for row in rows]
        
        cur_local.executemany(insert_query, data_to_insert)
        conn_local.commit()
        print(f"Successfully migrated {len(rows)} rows for {table}.")

    cur_local.execute("SET session_replication_role = 'origin';")
    conn_local.commit()

    print("Resetting sequences...")
    for table in tables:
        cur_neon.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = 'id'
        """, (table,))
        if cur_neon.fetchone():
            try:
                cur_local.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id), 1)) FROM \"{table}\";")
                conn_local.commit()
            except Exception as seq_err:
                conn_local.rollback()

    print("Migration finished cleanly!")

if __name__ == "__main__":
    migrate()
