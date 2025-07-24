from fastapi import FastAPI
import sqlite3, datetime
app = FastAPI()

@app.get("/")
def root():
    return {"status": "PathForge API alive"}
DB = "jobs.db"

@app.get("/demand/{role}")
def demand(role: str):
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    with sqlite3.connect(DB) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE role=? AND date>=?",
            (role.lower(), seven_days_ago)
        ).fetchone()[0]
    return {"role": role, "openings_last_7_days": count}

