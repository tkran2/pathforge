import sqlite3, os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()  # loads DATABASE_URL from env
DATABASE_URL = os.getenv("DATABASE_URL")

# Define your tables and columns to migrate
TABLES = {
    "jobs":          ("role, region, date",              "TEXT, TEXT, TEXT"),
    "occupations":   ("soc_code, title, description", "TEXT, TEXT, TEXT, TEXT"),
    "skills":        ("soc_code, element_id, skill_name, scale_id, value", 
                      "TEXT, TEXT, TEXT, TEXT, REAL"),
    "abilities":     ("soc_code, element_id, ability_name, scale_id, value", 
                      "TEXT, TEXT, TEXT, TEXT, REAL"),
    "work_activities":("soc_code, element_id, activity_name, scale_id, value", 
                      "TEXT, TEXT, TEXT, TEXT, REAL"),
    "job_zones":     ("soc_code, job_zone",
                      "TEXT, TEXT, TEXT, TEXT, TEXT")
}

def migrate_table(table, cols, types, sl_conn, pg_cur):
    # 1) CREATE TABLE IF NOT EXISTS
    pg_cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join([f'{c} {t}' for c,t in zip(cols.split(', '), types.split(', '))])});")
    # 2) Read all rows from SQLite
    rows = sl_conn.execute(f"SELECT {cols} FROM {table};").fetchall()
    if not rows:
        print(f"→ {table}: no rows to migrate")
        return
    # 3) Bulk‐insert into Postgres
    tpl = "(" + ",".join(["%s"] * len(cols.split(", "))) + ")"
    execute_values(
        pg_cur,
        f"INSERT INTO {table}({cols}) VALUES %s",
        rows
    )
    print(f"→ Migrated {len(rows)} rows into {table}")

def main():
    # Open SQLite
    sl = sqlite3.connect("jobs.db")
    sl.row_factory = sqlite3.Row

    # Connect to Postgres
    pg = psycopg2.connect(DATABASE_URL)
    cur = pg.cursor()

    # Migrate each table
    for tbl, (cols, types) in TABLES.items():
        migrate_table(tbl, cols, types, sl, cur)
        pg.commit()

    cur.close()
    pg.close()
    sl.close()
    print("✅ All tables migrated.")

if __name__ == "__main__":
    main()

