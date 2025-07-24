import sys
import requests, sqlite3, datetime, urllib.parse
from bs4 import BeautifulSoup

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

def scrape(role: str, region: str):
    url = (
        "https://www.indeed.com/jobs?"
        + urllib.parse.urlencode({"q": role, "l": region})
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36"
    }
    html = requests.get(url, headers=headers, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    # Try multiple selectors because Indeed changes DOM often
    listings = soup.select("div.job_seen_beacon, a.tapItem, td.resultContent")

    print("URL:", url)
    print("Found", len(listings), "postings")

    today = datetime.date.today().isoformat()
    with sqlite3.connect(DB) as conn:
        for _ in listings[:50]:
            conn.execute(
                "INSERT INTO jobs(role, region, date) VALUES (?,?,?)",
                (role.lower(), region.lower(), today)
            )
    print("Inserted", min(50, len(listings)), "rows")

if __name__ == "__main__":
    role   = sys.argv[1] if len(sys.argv) > 1 else "CNC machinist"
    region = sys.argv[2] if len(sys.argv) > 2 else "Illinois"
    init_db()
    scrape(role, region)
