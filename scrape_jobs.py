import requests, sqlite3, datetime, urllib.parse
from bs4 import BeautifulSoup

DB      = "jobs.db"
ROLE    = "CNC machinist"
REGION  = "Illinois"

URL = (
    "https://www.indeed.com/jobs?"
    + urllib.parse.urlencode({"q": ROLE, "l": REGION})
)

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                role TEXT,
                date TEXT
            )
        """)

def fetch_and_store():
    html = requests.get(URL, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    listings = soup.select("a.tapItem")  # very rough selector
    today = datetime.date.today().isoformat()

    with sqlite3.connect(DB) as conn:
        for _ in listings[:50]:  # limit to first 50 hits
            conn.execute(
                "INSERT INTO jobs(role, date) VALUES (?, ?)",
                (ROLE.lower(), today)
            )

if __name__ == "__main__":
    init_db()
    fetch_and_store()
    print("Scrape complete!")
