import sqlite3, os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()  # reads DATABASE_URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# 1. Read from SQLite
sl = sqlite3.connect("jobs.db")
sl.row_factory = sqlite3.Row
rows = sl.execute("SELECT role, region, date FROM jobs").fetchall()
sl.close()

# 2. Connect to Postgres and create table
pg = psycopg2.connect(DATABASE_URL)
cur = pg.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    role   TEXT,
    region TEXT,
    date   TEXT
);
""")
pg.commit()

# 3. Bulk‐insert
values = [(r["role"], r["region"], r["date"]) for r in rows]
execute_values(cur,
    "INSERT INTO jobs(role, region, date) VALUES %s",
    values
)
pg.commit()
cur.close()
pg.close()

print(f"Migrated {len(rows)} rows into Postgres")


