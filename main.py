from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import datetime
from typing import Optional, Dict
from pydantic import BaseModel
from psycopg2.extras import DictCursor
import db # Import our new db module

app = FastAPI()

# --- Pydantic Models ---
class Score(BaseModel): user_id: str; role: str; metric: str; value: float; ms: int
class InterestProfile(BaseModel): R: int; I: int; A: int; S: int; E: int; C: int
class ValuesProfile(BaseModel): values: Dict[str, int]

# --- Static Files ---
app.mount("/static", StaticFiles(directory="public"), name="static")

# --- Endpoints (Updated for PostgreSQL) ---
@app.get("/")
async def read_index(): return FileResponse('public/index.html')

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

@app.get("/skills")
def get_skills_for_role(role: str):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT soc_code, title FROM occupations WHERE LOWER(title) LIKE %s LIMIT 1", (f"%{role.lower()}%",))
        match = cur.fetchone()
        if not match:
            conn.close()
            raise HTTPException(status_code=404, detail="Occupation not found for skills lookup")
        soc_code = match["soc_code"]
        cur.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = %s ORDER BY score DESC LIMIT 20", (soc_code,))
        ranked_skills = cur.fetchall()
    conn.close()
    return {"matches": [dict(match)], "skills": [dict(skill) for skill in ranked_skills]}

@app.post("/score")
def post_score(score: Score):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scores (user_id, role, metric, value, ms, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (score.user_id, score.role, score.metric, score.value, score.ms, datetime.datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()
    return {"status": "success", "data": score}

@app.post("/save_interests/{user_id}")
def save_interests(user_id: str, profile: InterestProfile):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_interests WHERE user_id = %s", (user_id,))
        for interest_name, score in profile.dict().items():
            cur.execute("INSERT INTO user_interests (user_id, interest_name, score) VALUES (%s, %s, %s)", (user_id, interest_name, score))
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.dict()}

@app.post("/save_values/{user_id}")
def save_values(user_id: str, profile: ValuesProfile):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_values WHERE user_id = %s", (user_id,))
        for value_name, score in profile.values.items():
            cur.execute("INSERT INTO user_values (user_id, value_name, score) VALUES (%s, %s, %s)", (user_id, value_name, score))
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.values}

@app.get("/matches/{user_id}")
def get_matches(user_id: str):
    conn = db.get_db_connection()
    with conn.cursor(cursor_factory=DictCursor) as cur:
        user_aptitudes = {}
        cur.execute("SELECT MIN(value) FROM scores WHERE user_id = %s AND metric = 'Reaction Time'", (user_id,)); rt_score = cur.fetchone()
        if rt_score and rt_score[0]: user_aptitudes['Reaction Time'] = rt_score[0]
        cur.execute("SELECT MAX(value) FROM scores WHERE user_id = %s AND metric = 'Number Facility'", (user_id,)); nf_score = cur.fetchone()
        if nf_score and nf_score[0]: user_aptitudes['Number Facility'] = nf_score[0]
        cur.execute("SELECT MAX(value) FROM scores WHERE user_id = %s AND metric = 'Spatial Orientation'", (user_id,)); so_score = cur.fetchone()
        if so_score and so_score[0]: user_aptitudes['Spatial Orientation'] = so_score[0]
        if not user_aptitudes: raise HTTPException(status_code=404, detail="No aptitude scores found.")

        normalized_aptitudes = {}
        for metric, raw_score in user_aptitudes.items():
            if metric in ['Number Facility', 'Spatial Orientation']: normalized_aptitudes[metric] = raw_score / 100.0
            elif metric == 'Reaction Time':
                best_rt, worst_rt = 150, 1000; clamped_score = max(best_rt, min(raw_score, worst_rt))
                normalized_aptitudes[metric] = 1 - ((clamped_score - best_rt) / (worst_rt - best_rt))

        cur.execute("SELECT soc_code, ability_name, score FROM abilities_normalized"); all_abilities = cur.fetchall()
        job_abilities = {}; 
        for row in all_abilities:
            if row['soc_code'] not in job_abilities: job_abilities[row['soc_code']] = {}
            job_abilities[row['soc_code']][row['ability_name']] = row['score']
        aptitude_scores = {soc: sum(s*normalized_aptitudes.get(a, 0) for a, s in abilities.items()) for soc, abilities in job_abilities.items()}

        cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,)); user_interests_rows = cur.fetchall()
        if not user_interests_rows: raise HTTPException(status_code=404, detail="No interest profile found.")
        user_interests = {row['interest_name']: row['score'] for row in user_interests_rows}
        cur.execute("SELECT soc_code, interest_name, value FROM interests"); all_interests = cur.fetchall()
        job_interests = {}
        for row in all_interests:
            if row['soc_code'] not in job_interests: job_interests[row['soc_code']] = {}
            job_interests[row['soc_code']][row['interest_name'][0]] = row['value']
        interest_scores = {soc: sum(s*user_interests.get(i, 0) for i, s in interests.items()) for soc, interests in job_interests.items()}

        cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,)); user_values_rows = cur.fetchall()
        if not user_values_rows: raise HTTPException(status_code=404, detail="No work values profile found.")
        user_values = {row['value_name']: row['score'] for row in user_values_rows}
        cur.execute("SELECT soc_code, value_name, value FROM work_values"); all_values = cur.fetchall()
        job_values = {}
        for row in all_values:
            if row['soc_code'] not in job_values: job_values[row['soc_code']] = {}
            job_values[row['soc_code']][row['value_name']] = row['value']
        value_scores = {soc: sum(s*user_values.get(v, 0) for v, s in values.items()) for soc, values in job_values.items()}

        final_scores = {}
        all_soc_codes = set(aptitude_scores.keys()) & set(interest_scores.keys()) & set(value_scores.keys())
        max_apt = max(aptitude_scores.values()) or 1; max_int = max(interest_scores.values()) or 1; max_val = max(value_scores.values()) or 1
        for soc_code in all_soc_codes:
            norm_apt = (aptitude_scores.get(soc_code, 0)/max_apt)*100
            norm_int = (interest_scores.get(soc_code, 0)/max_int)*100
            norm_val = (value_scores.get(soc_code, 0)/max_val)*100
            final_scores[soc_code] = (0.5 * norm_apt) + (0.3 * norm_int) + (0.2 * norm_val)

        sorted_matches = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)[:10]
        top_soc_codes = [item[0] for item in sorted_matches]
        if not top_soc_codes: return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": []}

        placeholders = ','.join(['%s'] * len(top_soc_codes))
        query = f"SELECT soc_code, title FROM occupations WHERE soc_code IN ({placeholders})"
        cur.execute(query, top_soc_codes); occupations = cur.fetchall()
        occupation_map = {row['soc_code']: row['title'] for row in occupations}

        final_results = []
        for soc_code, score in sorted_matches:
            final_results.append({"title": occupation_map.get(soc_code, "Unknown Title"), "soc_code": soc_code, "match_score": round(score, 2)})

    conn.close()
    return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": final_results}

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
