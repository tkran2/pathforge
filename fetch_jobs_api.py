import sys, os, sqlite3, datetime
import httpx
from dotenv import load_dotenv

DB = "jobs.db"

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs(
                role   TEXT,
                region TEXT,
                date   TEXT
            )
        """)

def fetch_and_store(role: str, region: str):
    load_dotenv()  # loads RAPIDAPI_KEY from .env
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError("RAPIDAPI_KEY missing. Put it in .env or export it.")

    url = "https://jsearch.p.rapidapi.com/search"
    params = {"query": f"{role} in {region}", "page": 1, "num_pages": 1}
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    r = httpx.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = data.get("data", [])

    today = datetime.date.today().isoformat()
    with sqlite3.connect(DB) as conn:
        for _ in results[:50]:
            conn.execute(
                "INSERT INTO jobs(role, region, date) VALUES (?,?,?)",
                (role.lower(), region.lower(), today)
            )

    print(f"Inserted {min(50, len(results))} rows for '{role}' / '{region}'")

if __name__ == "__main__":
    role   = sys.argv[1] if len(sys.argv) > 1 else "CNC machinist"
    region = sys.argv[2] if len(sys.argv) > 2 else "Illinois"
    init_db()
    fetch_and_store(role, region)
