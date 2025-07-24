import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import datetime
from typing import Optional, Dict
from pydantic import BaseModel
from psycopg2.extras import DictCursor

import db

app = FastAPI()

# serve your frontend
if not os.path.exists("public"):
    os.makedirs("public")
app.mount("/static", StaticFiles(directory="public"), name="static")


# --- Pydantic Models ---
class Score(BaseModel):
    user_id: str
    role: str
    metric: str
    value: float
    ms: int

class InterestProfile(BaseModel):
    R: int; I: int; A: int; S: int; E: int; C: int

class ValuesProfile(BaseModel):
    values: Dict[str, int]

# --- Endpoints ---

@app.get("/")
def root():
    return {"status": "ok", "message": "PathForge API is running"}

@app.get("/demand")
def get_demand(role: str, region: Optional[str] = None):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        query = "SELECT COUNT(*) FROM jobs WHERE LOWER(role) LIKE %s AND date >= %s"
        params = [f"%{role.lower()}%", seven_days_ago]
        if region:
            query += " AND LOWER(region) LIKE %s"
            params.append(f"%{region.lower()}%")
        cur.execute(query, tuple(params))
        count = cur.fetchone()[0]
    conn.close()
    return {"role": role, "region": region, "openings_last_7_days": count}

from fastapi import HTTPException
from psycopg2.extras import DictCursor

@app.get("/skills")
def get_skills_for_role(role: str):
    conn = db.get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # 1) find the best matching occupation
            cur.execute(
                """
                SELECT soc_code, title
                FROM occupations
                WHERE LOWER(title) LIKE %s
                LIMIT 1
                """,
                (f"%{role.lower()}%",)
            )
            match = cur.fetchone()
            if not match:
                raise HTTPException(404, f"No occupation found matching '{role}'")
            soc_code = match["soc_code"]

            # 2) pull its top–20 skills from your existing skills table
            cur.execute(
                """
                SELECT skill_name, value AS score
                FROM skills
                WHERE soc_code = %s
                ORDER BY value DESC
                LIMIT 20
                """,
                (soc_code,)
            )
            skills = cur.fetchall()

    finally:
        conn.close()

    return {
        "matches": [dict(match)],
        "skills": [dict(row) for row in skills]
    }


@app.post("/score")
def post_score(score: Score):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scores (user_id, role, metric, value, ms, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                score.user_id,
                score.role,
                score.metric,
                score.value,
                score.ms,
                datetime.datetime.utcnow().isoformat()
            )
        )
    conn.commit()
    conn.close()
    return {"status": "success", "data": score}

@app.post("/save_interests/{user_id}")
def save_interests(user_id: str, profile: InterestProfile):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_interests WHERE user_id = %s", (user_id,))
        for interest_name, val in profile.dict().items():
            cur.execute(
                "INSERT INTO user_interests (user_id, interest_name, score) VALUES (%s, %s, %s)",
                (user_id, interest_name, val)
            )
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.dict()}

@app.post("/save_values/{user_id}")
def save_values(user_id: str, profile: ValuesProfile):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_values WHERE user_id = %s", (user_id,))
        for value_name, val in profile.values.items():
            cur.execute(
                "INSERT INTO user_values (user_id, value_name, score) VALUES (%s, %s, %s)",
                (user_id, value_name, val)
            )
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.values}

@app.get("/matches/{user_id}")
def get_matches(user_id: str):
    """
    Calculates a holistic match score based on the user's PERCENTAGE MATCH
    to the ideal profile for each job across aptitudes, interests, and values.
    """
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # --- Part 1: Get User Profiles ---
        cur.execute("SELECT metric, MIN(value) as score FROM scores WHERE user_id = %s AND metric = 'Reaction Time' GROUP BY metric", (user_id,))
        rt_score = cur.fetchone()
        cur.execute("SELECT metric, MAX(value) as score FROM scores WHERE user_id = %s AND metric IN ('Number Facility', 'Spatial Orientation') GROUP BY metric", (user_id,))
        apt_scores = cur.fetchall()
        user_aptitudes = {row['metric']: row['score'] for row in apt_scores}
        if rt_score: user_aptitudes['Reaction Time'] = rt_score['score']

        cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,));
        user_interests = {row['interest_name']: row['score'] for row in cur.fetchall()}

        cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,));
        user_values = {row['value_name']: row['score'] for row in cur.fetchall()}

        if not all([user_aptitudes, user_interests, user_values]):
            raise HTTPException(status_code=404, detail="User profile is incomplete. Please complete all assessments.")

        # --- Part 2: Normalize User Aptitude Scores to a 0-1 scale ---
        normalized_aptitudes = {}
        for metric, raw_score in user_aptitudes.items():
            if metric in ['Number Facility', 'Spatial Orientation']: normalized_aptitudes[metric] = raw_score / 100.0
            elif metric == 'Reaction Time':
                best_rt, worst_rt = 150, 1000; clamped_score = max(best_rt, min(raw_score, worst_rt))
                normalized_aptitudes[metric] = 1 - ((clamped_score - best_rt) / (worst_rt - best_rt))

        # --- Part 3: Pre-fetch all O*NET data ---
        job_abilities = {}; cur.execute("SELECT soc_code, ability_name, score FROM abilities_normalized");
        for r in cur.fetchall():
            job_abilities.setdefault(r['soc_code'], {})[r['ability_name']] = r['score']

        job_interests = {}; cur.execute("SELECT soc_code, interest_name, value FROM interests");
        for r in cur.fetchall():
            job_interests.setdefault(r['soc_code'], {})[r['interest_name'][0]] = r['value']

        job_values = {}; cur.execute("SELECT soc_code, value_name, value FROM work_values");
        for r in cur.fetchall():
            job_values.setdefault(r['soc_code'], {})[r['value_name']] = r['value']

        # --- Part 4: Calculate Percent Match Scores ---
        final_scores = {}
        all_soc_codes = set(job_abilities.keys()) & set(job_interests.keys()) & set(job_values.keys())

        for soc in all_soc_codes:
            # Calculate user's actual score for this job
            user_apt_score = sum(s * normalized_aptitudes.get(a, 0) for a, s in job_abilities.get(soc, {}).items())
            user_int_score = sum(s * user_interests.get(i, 0) for i, s in job_interests.get(soc, {}).items())
            user_val_score = sum(s * user_values.get(v, 0) for v, s in job_values.get(soc, {}).items())

            # Calculate the max possible score for this job (for a "perfect" user)
            max_apt_score = sum(job_abilities.get(soc, {}).values())
            max_int_score = sum(s * 2 for s in job_interests.get(soc, {}).values()) # Max interest score is 2 ('Like')
            max_val_score = sum(s * 1 for s in job_values.get(soc, {}).values())   # Max value score is 1 (Chosen once)

            # Calculate the percent match for each category
            apt_percent_match = (user_apt_score / max_apt_score) * 100 if max_apt_score > 0 else 0
            int_percent_match = (user_int_score / max_int_score) * 100 if max_int_score > 0 else 0
            val_percent_match = (user_val_score / max_val_score) * 100 if max_val_score > 0 else 0

            # Weighted average of the percentages
            final_scores[soc] = (0.5 * apt_percent_match) + (0.3 * int_percent_match) + (0.2 * val_percent_match)

        # --- Part 5: Format and Return Top 10 Results ---
        sorted_matches = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)[:10]

        top_soc_codes = [item[0] for item in sorted_matches]
        if not top_soc_codes: return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": []}

        placeholders = ','.join(['%s'] * len(top_soc_codes))
        cur.execute(f"SELECT soc_code, title FROM occupations WHERE soc_code IN ({placeholders})", top_soc_codes)
        occupation_map = {row['soc_code']: row['title'] for row in cur.fetchall()}

        final_results = [{"title": occupation_map.get(soc, "N/A"), "soc_code": soc, "match_score": round(score, 2)} for soc, score in sorted_matches]

    conn.close()
    # Combine all user profiles for the response header
    full_user_profile = {**user_aptitudes, **user_interests, **user_values}
    return {"user_profile": full_user_profile, "matches": final_results}

@app.get("/job_details/{user_id}/{soc_code}")
def get_job_details(user_id: str, soc_code: str):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT title, description FROM occupations WHERE soc_code = %s", (soc_code,)); job_info = cur.fetchone()
        if not job_info: raise HTTPException(status_code=404, detail="Job not found.")
        cur.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = %s ORDER BY score DESC LIMIT 5", (soc_code,)); top_skills = cur.fetchall()
        cur.execute("SELECT interest_name, value FROM interests WHERE soc_code = %s ORDER BY value DESC LIMIT 3", (soc_code,)); job_interests = cur.fetchall()
        cur.execute("SELECT value_name, value FROM work_values WHERE soc_code = %s ORDER BY value DESC LIMIT 3", (soc_code,)); job_values = cur.fetchall()
        cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,)); user_interests = {row['interest_name']: row['score'] for row in cur.fetchall()}
        cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,)); user_values = {row['value_name']: row['score'] for row in cur.fetchall()}
        seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        cur.execute("SELECT COUNT(*) FROM jobs WHERE role LIKE %s AND date >= %s", (f"%{job_info['title']}%", seven_days_ago)); demand_count = cur.fetchone()[0]
    conn.close()
    return {
        "title": job_info['title'], "description": job_info['description'],
        "demand": {"openings_last_7_days": demand_count, "region": "USA (default)"},
        "top_skills": [dict(row) for row in top_skills],
        "profile_match": {
            "interests": [{"name": row['interest_name'], "job_score": row['value'], "user_score": user_interests.get(row['interest_name'][0], 'N/A')} for row in job_interests],
            "values": [{"name": row['value_name'], "job_score": row['value'], "user_score": user_values.get(row['value_name'], 'N/A')} for row in job_values]
        }
    }
