import os
import psycopg2
from psycopg2 import pool
from sqlalchemy import create_engine

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
IS_PRODUCTION = "fly.io" in os.getenv("FLY_APP_NAME", "")

# --- Local Development Settings (fallback) ---
if not DATABASE_URL:
    DB_NAME = "pathforge_db"
    DB_USER = "thomaskrane"  # Your macOS username
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Connection Pool ---
# Create a single connection pool for the entire application
# Min connections: 1, Max connections: 10
db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL)

def get_db_connection():
    """Gets a connection from the pool."""
    return db_pool.getconn()

def return_db_connection(conn):
    """Returns a connection to the pool."""
    db_pool.putconn(conn)

# --- SQLAlchemy Engine (for data loading scripts) ---
def get_db_engine():
    """
    Creates a SQLAlchemy engine.
    Note: SQLAlchemy has its own connection pooling.
    """
    # Use the correct dialect for SQLAlchemy
    sa_database_url = DATABASE_URL
    if sa_database_url.startswith("postgres://"):
        sa_database_url = sa_database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    return create_engine(sa_database_url)

