import psycopg2
from psycopg2.extras import DictCursor
from sqlalchemy import create_engine

DB_NAME = "pathforge_db"
DB_USER = "thomaskrane" # Your macOS username
DB_HOST = "localhost"
DB_PORT = "5432"

# For regular connections in FastAPI
def get_db_connection():
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT)
    return conn

# For pandas .to_sql() functions
def get_db_engine():
    url = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)
