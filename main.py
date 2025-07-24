from fastapi import FastAPI
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


# ---------- Endpoints ----------
@app.get("/")
def root():
    return {"status": "PathForge API alive"}


# Legacy path version (kept if you were using it)
@app.get("/demand/{role}")
def demand_path(role: str, region: Optional[str] = None):
    count = get_count(role, region)
    return {"role": role, "region": region, "openings_last_7_days": count}


# Query-param version (easier to call from frontend)
@app.get("/demand")
def demand(role: str, region: Optional[str] = None):
    count = get_count(role, region)
    return {"role": role, "region": region, "openings_last_7_days": count}


@app.get("/skills")
def skills(role: str):
    """
    Return top skills (by Data Value) for the best-matching O*NET occupation title.
    """
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row

        matches = conn.execute("""
            SELECT soc_code, title
            FROM occupations
            WHERE LOWER(title) LIKE ?
            ORDER BY title
            LIMIT 5
        """, (f"%{role.lower()}%",)).fetchall()

        if not matches:
            return {"matches": [], "skills": []}

        soc = matches[0]["soc_code"]

        rows = conn.execute("""
            SELECT skill_name, scale_id, value
            FROM skills
            WHERE soc_code=?
            ORDER BY CAST(value AS FLOAT) DESC
            LIMIT 20
        """, (soc,)).fetchall()

    return {
        "matches": [dict(m) for m in matches],
        "skills": [dict(r) for r in rows]
    }


@app.get("/role_info")
def role_info(role: str, region: str):
    """
    Return demand (last 7 days) + top O*NET skills for a role/region combo.
    """
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row

        # Demand
        demand_count = conn.execute("""
            SELECT COUNT(*) as c
            FROM jobs
            WHERE role=? AND region=? AND date>=?
        """, (role.lower(), region.lower(), seven_days_ago)).fetchone()["c"]

        # Skills (best O*NET match)
        matches = conn.execute("""
            SELECT soc_code, title
            FROM occupations
            WHERE LOWER(title) LIKE ?
            ORDER BY title
            LIMIT 5
        """, (f"%{role.lower()}%",)).fetchall()

        if matches:
            soc = matches[0]["soc_code"]
            skill_rows = conn.execute("""
                SELECT skill_name, scale_id, value
                FROM skills
                WHERE soc_code=?
                ORDER BY CAST(value AS FLOAT) DESC
                LIMIT 20
            """, (soc,)).fetchall()
            skills = [dict(r) for r in skill_rows]
        else:
            skills = []

    return {
        "role": role,
        "region": region,
        "openings_last_7_days": demand_count,
        "onet_matches": [dict(m) for m in matches],
        "top_skills": skills
    }

