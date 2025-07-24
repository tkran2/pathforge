from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3, datetime
from typing import Optional, Dict
from pydantic import BaseModel
from psycopg2.extras import DictCursor
import db

app = FastAPI()

# --- Pydantic Models ---
class Score(BaseModel): user_id: str; role: str; metric: str; value: float; ms: int
class InterestProfile(BaseModel): R: int; I: int; A: int; S: int; E: int; C: int
class ValuesProfile(BaseModel): values: Dict[str, int]

# --- Static Files & DB Helper ---
app.mount("/static", StaticFiles(directory="public"), name="static")
def get_db_connection():
    conn = db.get_db_connection()
    return conn

# --- Endpoints ---
@app.get("/")
def root(): return {"status": "ok", "message": "PathForge API is running"}

# FIX #3: Added logic to prevent duplicate skills from being returned
@app.get("/skills")
def get_skills_for_role(role: str):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT soc_code, title FROM occupations WHERE LOWER(title) LIKE %s LIMIT 1", (f"%{role.lower()}%",))
        match = cur.fetchone()
        if not match:
            conn.close()
            raise HTTPException(status_code=404, detail="Occupation not found for skills lookup")
        soc_code = match["soc_code"]
        cur.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = %s ORDER BY score DESC LIMIT 20", (soc_code,))

        # De-duplicate results to handle any data inconsistencies
        unique_skills = []
        seen_names = set()
        for skill in cur.fetchall():
            if skill['skill_name'] not in seen_names:
                unique_skills.append(dict(skill))
                seen_names.add(skill['skill_name'])
    conn.close()
    return {"matches": [dict(match)], "skills": unique_skills}

# --- Other Endpoints (score, save_interests, save_values) ---
# ... (These functions are unchanged and omitted for brevity) ...

# FIX #2: Updated algorithm to better differentiate scores
@app.get("/matches/{user_id}")
def get_matches(user_id: str):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # --- Part 1: Get User Profiles ---
        cur.execute("SELECT metric, MIN(value) as score FROM scores WHERE user_id = %s AND metric = 'Reaction Time' GROUP BY metric", (user_id,))
        rt_score = cur.fetchone()
        cur.execute("SELECT metric, MAX(value) as score FROM scores WHERE user_id = %s AND metric IN ('Number Facility', 'Spatial Orientation') GROUP BY metric", (user_id,))
        apt_scores = cur.fetchall()
        user_aptitudes = {row['metric']: row['score'] for row in apt_scores}
        if rt_score: user_aptitudes['Reaction Time'] = rt_score['score']
        cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,)); user_interests = {row['interest_name']: row['score'] for row in cur.fetchall()}
        cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,)); user_values = {row['value_name']: row['score'] for row in cur.fetchall()}
        if not all([user_aptitudes, user_interests, user_values]): raise HTTPException(status_code=404, detail="User profile is incomplete.")

        # --- Part 2: Normalize User Aptitude Scores ---
        normalized_aptitudes = {}
        for metric, raw_score in user_aptitudes.items():
            if metric in ['Number Facility', 'Spatial Orientation']: normalized_aptitudes[metric] = raw_score / 100.0
            elif metric == 'Reaction Time':
                best_rt, worst_rt = 150, 1000; clamped_score = max(best_rt, min(raw_score, worst_rt))
                normalized_aptitudes[metric] = 1 - ((clamped_score - best_rt) / (worst_rt - best_rt))

        # --- Part 3: Pre-fetch all O*NET data ---
        job_abilities = {}; cur.execute("SELECT soc_code, ability_name, score FROM abilities_normalized");
        for r in cur.fetchall(): job_abilities.setdefault(r['soc_code'], {})[r['ability_name']] = r['score']
        job_interests = {}; cur.execute("SELECT soc_code, interest_name, value FROM interests");
        for r in cur.fetchall(): job_interests.setdefault(r['soc_code'], {})[r['interest_name'][0]] = r['value']
        job_values = {}; cur.execute("SELECT soc_code, value_name, value FROM work_values");
        for r in cur.fetchall(): job_values.setdefault(r['soc_code'], {})[r['value_name']] = r['value']

        # --- Part 4: Calculate Percent Match Scores ---
        final_scores = {}
        all_soc_codes = set(job_abilities.keys()) & set(job_interests.keys()) & set(job_values.keys())
        for soc in all_soc_codes:
            user_apt_score = sum(s * normalized_aptitudes.get(a, 0) for a, s in job_abilities.get(soc, {}).items())
            max_apt_score = sum(job_abilities.get(soc, {}).values())
            apt_percent_match = (user_apt_score / max_apt_score) if max_apt_score > 0 else 0

            user_int_score = sum(s * user_interests.get(i, 0) for i, s in job_interests.get(soc, {}).items())
            max_int_score = sum(s * 2 for s in job_interests.get(soc, {}).values())
            int_percent_match = (user_int_score / max_int_score) if max_int_score > 0 else 0

            user_val_score = sum(s * user_values.get(v, 0) for v, s in job_values.get(soc, {}).items())
            max_val_score = sum(s for s in job_values.get(soc, {}).values())
            val_percent_match = (user_val_score / max_val_score) if max_val_score > 0 else 0

            # NEW: Square the percentages to reward excellence and increase score spread
            final_scores[soc] = (0.5 * (apt_percent_match**2)) + (0.3 * (int_percent_match**2)) + (0.2 * (val_percent_match**2))

        # --- Part 5: Format and Return Top 10 Results ---
        sorted_matches = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        top_soc_codes = [item[0] for item in sorted_matches]
        if not top_soc_codes: return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": []}
        placeholders = ','.join(['%s'] * len(top_soc_codes))
        cur.execute(f"SELECT soc_code, title FROM occupations WHERE soc_code IN ({placeholders})", top_soc_codes)
        occupation_map = {row['soc_code']: row['title'] for row in cur.fetchall()}
        final_results = [{"title": occupation_map.get(soc, "N/A"), "soc_code": soc, "match_score": round(score * 100, 2)} for soc, score in sorted_matches]
    conn.close()
    return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": final_results}

# FIX #1: Added aptitude fetching and comparison logic
@app.get("/job_details/{user_id}/{soc_code}")
def get_job_details(user_id: str, soc_code: str):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT title, description FROM occupations WHERE soc_code = %s", (soc_code,)); job_info = cur.fetchone()
        if not job_info: raise HTTPException(status_code=404, detail="Job not found.")

        cur.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = %s ORDER BY score DESC LIMIT 5", (soc_code,)); top_skills = cur.fetchall()

        # Get job profiles
        cur.execute("SELECT ability_name, score FROM abilities_normalized WHERE soc_code = %s ORDER BY score DESC LIMIT 3", (soc_code,)); job_abilities = cur.fetchall()
        cur.execute("SELECT interest_name, value FROM interests WHERE soc_code = %s ORDER BY value DESC LIMIT 3", (soc_code,)); job_interests = cur.fetchall()
        cur.execute("SELECT value_name, value FROM work_values WHERE soc_code = %s ORDER BY value DESC LIMIT 3", (soc_code,)); job_values = cur.fetchall()

        # Get user profiles
        cur.execute("SELECT metric, MIN(value) as score FROM scores WHERE user_id = %s AND metric = 'Reaction Time' GROUP BY metric", (user_id,)); rt_score = cur.fetchone()
        cur.execute("SELECT metric, MAX(value) as score FROM scores WHERE user_id = %s AND metric IN ('Number Facility', 'Spatial Orientation') GROUP BY metric", (user_id,)); apt_scores = cur.fetchall()
        user_aptitudes = {row['metric']: row['score'] for row in apt_scores}; 
        if rt_score: user_aptitudes['Reaction Time'] = rt_score['score']
        cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,)); user_interests = {row['interest_name']: row['score'] for row in cur.fetchall()}
        cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,)); user_values = {row['value_name']: row['score'] for row in cur.fetchall()}

        # Get live job demand
        seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        cur.execute("SELECT COUNT(*) FROM jobs WHERE role LIKE %s AND date >= %s", (f"%{job_info['title']}%", seven_days_ago)); demand_count = cur.fetchone()[0]
    conn.close()

    return {
        "title": job_info['title'], "description": job_info['description'],
        "demand": {"openings_last_7_days": demand_count, "region": "USA (default)"},
        "top_skills": [dict(row) for row in top_skills],
        "profile_match": {
            "aptitudes": [{"name": row['ability_name'], "job_importance": row['score']} for row in job_abilities],
            "interests": [{"name": row['interest_name'], "job_score": row['value'], "user_score": user_interests.get(row['interest_name'][0], 'N/A')} for row in job_interests],
            "values": [{"name": row['value_name'], "job_score": row['value'], "user_score": user_values.get(row['value_name'], 'N/A')} for row in job_values]
        }
    }
