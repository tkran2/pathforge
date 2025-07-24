from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3, datetime
from typing import Optional, Dict
from pydantic import BaseModel

DB = "jobs.db"
app = FastAPI()

# --- Pydantic Models ---
class Score(BaseModel): user_id: str; role: str; metric: str; value: float; ms: int
class InterestProfile(BaseModel): R: int; I: int; A: int; S: int; E: int; C: int
class ValuesProfile(BaseModel): values: Dict[str, int]

# --- Static Files & DB Helper ---
app.mount("/static", StaticFiles(directory="public"), name="static")
def get_db_connection():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- Endpoints ---
@app.get("/")
async def read_index(): return FileResponse('public/index.html')

# RE-ADDED: The /demand endpoint
@app.get("/demand")
def get_demand(role: str, region: Optional[str] = None):
    conn = get_db_connection()
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    query = "SELECT COUNT(*) FROM jobs WHERE LOWER(role) LIKE ? AND date >= ?"
    params = [f"%{role.lower()}%", seven_days_ago]
    if region:
        query += " AND LOWER(region) LIKE ?"
        params.append(f"%{region.lower()}%")
    count = conn.execute(query, tuple(params)).fetchone()[0]
    conn.close()
    return {"role": role, "region": region, "openings_last_7_days": count}

# RE-ADDED: The /skills endpoint
@app.get("/skills")
def get_skills_for_role(role: str):
    conn = get_db_connection()
    match = conn.execute("SELECT soc_code, title FROM occupations WHERE LOWER(title) LIKE ? LIMIT 1", (f"%{role.lower()}%",)).fetchone()
    if not match:
        conn.close()
        raise HTTPException(status_code=404, detail="Occupation not found for skills lookup")
    soc_code = match["soc_code"]
    ranked_skills = conn.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = ? ORDER BY score DESC LIMIT 20", (soc_code,)).fetchall()
    conn.close()
    return {"matches": [dict(match)], "skills": [dict(skill) for skill in ranked_skills]}

@app.post("/score")
def post_score(score: Score):
    conn = get_db_connection()
    conn.execute("INSERT INTO scores (user_id, role, metric, value, ms, created_at) VALUES (?, ?, ?, ?, ?, ?)", (score.user_id, score.role, score.metric, score.value, score.ms, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "success", "data": score}

@app.post("/save_interests/{user_id}")
def save_interests(user_id: str, profile: InterestProfile):
    conn = get_db_connection()
    conn.execute("DELETE FROM user_interests WHERE user_id = ?", (user_id,))
    for interest_name, score in profile.dict().items():
        conn.execute("INSERT INTO user_interests (user_id, interest_name, score) VALUES (?, ?, ?)", (user_id, interest_name, score))
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.dict()}

@app.post("/save_values/{user_id}")
def save_values(user_id: str, profile: ValuesProfile):
    conn = get_db_connection()
    conn.execute("DELETE FROM user_values WHERE user_id = ?", (user_id,))
    for value_name, score in profile.values.items():
        conn.execute("INSERT INTO user_values (user_id, value_name, score) VALUES (?, ?, ?)", (user_id, value_name, score))
    conn.commit()
    conn.close()
    return {"status": "success", "user_id": user_id, "saved_profile": profile.values}

@app.get("/matches/{user_id}")
def get_matches(user_id: str):
    conn = get_db_connection()
    user_aptitudes = {}
    rt_score = conn.execute("SELECT MIN(value) FROM scores WHERE user_id = ? AND metric = 'Reaction Time'", (user_id,)).fetchone()
    if rt_score and rt_score[0]: user_aptitudes['Reaction Time'] = rt_score[0]
    nf_score = conn.execute("SELECT MAX(value) FROM scores WHERE user_id = ? AND metric = 'Number Facility'", (user_id,)).fetchone()
    if nf_score and nf_score[0]: user_aptitudes['Number Facility'] = nf_score[0]
    so_score = conn.execute("SELECT MAX(value) FROM scores WHERE user_id = ? AND metric = 'Spatial Orientation'", (user_id,)).fetchone()
    if so_score and so_score[0]: user_aptitudes['Spatial Orientation'] = so_score[0]
    if not user_aptitudes: raise HTTPException(status_code=404, detail="No aptitude scores found.")
    normalized_aptitudes = {}
    for metric, raw_score in user_aptitudes.items():
        if metric in ['Number Facility', 'Spatial Orientation']: normalized_aptitudes[metric] = raw_score / 100.0
        elif metric == 'Reaction Time':
            best_rt, worst_rt = 150, 1000
            clamped_score = max(best_rt, min(raw_score, worst_rt))
            normalized_aptitudes[metric] = 1 - ((clamped_score - best_rt) / (worst_rt - best_rt))
    job_abilities = {}; all_abilities = conn.execute("SELECT soc_code, ability_name, score FROM abilities_normalized").fetchall()
    for row in all_abilities:
        if row['soc_code'] not in job_abilities: job_abilities[row['soc_code']] = {}
        job_abilities[row['soc_code']][row['ability_name']] = row['score']
    aptitude_scores = {}
    for soc_code, abilities in job_abilities.items():
        score = sum(onet_score * normalized_aptitudes.get(ability_name, 0) for ability_name, onet_score in abilities.items())
        if score > 0: aptitude_scores[soc_code] = score
    user_interests_rows = conn.execute("SELECT interest_name, score FROM user_interests WHERE user_id = ?", (user_id,)).fetchall()
    if not user_interests_rows: raise HTTPException(status_code=404, detail="No interest profile found.")
    user_interests = {row['interest_name']: row['score'] for row in user_interests_rows}
    job_interests = {}; all_interests = conn.execute("SELECT soc_code, interest_name, value FROM interests").fetchall()
    for row in all_interests:
        if row['soc_code'] not in job_interests: job_interests[row['soc_code']] = {}
        job_interests[row['soc_code']][row['interest_name'][0]] = row['value']
    interest_scores = {}
    for soc_code, interests in job_interests.items():
        score = sum(onet_score * user_interests.get(interest_name, 0) for interest_name, onet_score in interests.items())
        if score > 0: interest_scores[soc_code] = score
    user_values_rows = conn.execute("SELECT value_name, score FROM user_values WHERE user_id = ?", (user_id,)).fetchall()
    if not user_values_rows: raise HTTPException(status_code=404, detail="No work values profile found.")
    user_values = {row['value_name']: row['score'] for row in user_values_rows}
    job_values = {}; all_values = conn.execute("SELECT soc_code, value_name, value FROM work_values").fetchall()
    for row in all_values:
        if row['soc_code'] not in job_values: job_values[row['soc_code']] = {}
        job_values[row['soc_code']][row['value_name']] = row['value']
    value_scores = {}
    for soc_code, values in job_values.items():
        score = sum(onet_score * user_values.get(value_name, 0) for value_name, onet_score in values.items())
        if score > 0: value_scores[soc_code] = score
    final_scores = {}
    all_soc_codes = set(aptitude_scores.keys()) & set(interest_scores.keys()) & set(value_scores.keys())
    max_apt = max(aptitude_scores.values()) or 1; max_int = max(interest_scores.values()) or 1; max_val = max(value_scores.values()) or 1
    for soc_code in all_soc_codes:
        norm_apt = (aptitude_scores.get(soc_code, 0) / max_apt) * 100
        norm_int = (interest_scores.get(soc_code, 0) / max_int) * 100
        norm_val = (value_scores.get(soc_code, 0) / max_val) * 100
        final_scores[soc_code] = (0.5 * norm_apt) + (0.3 * norm_int) + (0.2 * norm_val)
    sorted_matches = sorted(final_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    top_soc_codes = [item[0] for item in sorted_matches]
    if not top_soc_codes: return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": []}
    placeholders = ','.join('?' for _ in top_soc_codes)
    query = f"SELECT soc_code, title FROM occupations WHERE soc_code IN ({placeholders})"
    occupations = conn.execute(query, top_soc_codes).fetchall()
    occupation_map = {row['soc_code']: row['title'] for row in occupations}
    final_results = []
    for soc_code, score in sorted_matches:
        final_results.append({"title": occupation_map.get(soc_code, "Unknown Title"), "soc_code": soc_code, "match_score": round(score, 2)})
    conn.close()
    return {"user_profile": {**user_aptitudes, **user_interests, **user_values}, "matches": final_results}

@app.get("/job_details/{user_id}/{soc_code}")
def get_job_details(user_id: str, soc_code: str):
    conn = get_db_connection()
    job_info = conn.execute("SELECT title, description FROM occupations WHERE soc_code = ?", (soc_code,)).fetchone()
    if not job_info: raise HTTPException(status_code=404, detail="Job not found.")
    top_skills = conn.execute("SELECT skill_name, score FROM skills_normalized WHERE soc_code = ? ORDER BY score DESC LIMIT 5", (soc_code,)).fetchall()
    job_interests = conn.execute("SELECT interest_name, value FROM interests WHERE soc_code = ? ORDER BY value DESC LIMIT 3", (soc_code,)).fetchall()
    job_values = conn.execute("SELECT value_name, value FROM work_values WHERE soc_code = ? ORDER BY value DESC LIMIT 3", (soc_code,)).fetchall()
    user_interests = {row['interest_name']: row['score'] for row in conn.execute("SELECT interest_name, score FROM user_interests WHERE user_id = ?", (user_id,)).fetchall()}
    user_values = {row['value_name']: row['score'] for row in conn.execute("SELECT value_name, score FROM user_values WHERE user_id = ?", (user_id,)).fetchall()}
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    demand_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE role LIKE ? AND date >= ?", (f"%{job_info['title']}%", seven_days_ago)).fetchone()[0]
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
