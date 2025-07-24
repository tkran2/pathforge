import os
import psycopg2
from psycopg2.extras import DictCursor
from sqlalchemy import create_engine

# --- Production Settings (from Fly.io secrets) ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Local Development Settings (fallback) ---
if not DATABASE_URL:
    DB_NAME = "pathforge_db"
    DB_USER = "thomaskrane" # Your macOS username
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- SQLAlchemy Correction ---
# Tell SQLAlchemy to use the psycopg2 driver explicitly
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)


# For regular connections in FastAPI
def get_db_connection():
    # psycopg2 itself doesn't need the "+psycopg2" part
    conn_url = DATABASE_URL.replace("+psycopg2", "")
    conn = psycopg2.connect(conn_url)
    return conn

# For pandas .to_sql() functions
def get_db_engine():
    return create_engine(DATABASE_URL)
