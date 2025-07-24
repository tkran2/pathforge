from fastapi import FastAPI, Query, Body
import sqlite3, datetime
from typing import Optional

DB = "jobs.db"
app = FastAPI()


# ---------- Helpers ----------
def get_count(role: str, region: Optional[str]) -> int:
    """Return number of postings in last 7 days for a role (and optional region)."""
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    query = "SELECT COUNT(*) FROM jobs WHERE role=? AND date>=?"
    params = [role.lower(), seven_days_ago]
    if region:
        query += " AND region=?"
        params.append(region.lower())

    with sqlite3.connect(DB) as conn:
        return conn.execute(query, params).fetchone()[0]


# ---------- Routes ----------
@app.get("/")
def root():
    return {"status": "PathForge API alive"}


@app.get("/demand")
def demand(
    role: str = Query(..., description="Job title, e.g. 'CNC machinist'"),
    region: Optional[str] = Query(None, description="Optional region, e.g. 'Illinois' or 'Chicago, IL'")
):
    count = get_count(role, region)
    return {"role": role, "region": region, "openings_last_7_days": count}


# Optional: score endpoint for later use
@app.post("/score")
def add_score(payload: dict = Body(...)):
    user = payload.get("user_id", "anon")
    score = int(payload.get("score", 0))
    time_ms = int(payload.get("time_ms", 0))

    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                score INTEGER,
                time_ms INTEGER,
                created_at TEXT
            )
        """)
        conn.execute(
            "INSERT INTO scores(user_id, score, time_ms, created_at) VALUES(?,?,?,?)",
            (user, score, time_ms, datetime.datetime.utcnow().isoformat())
        )

