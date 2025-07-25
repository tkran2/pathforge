import datetime
import json
from typing import Optional, Dict, List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from psycopg2.extras import DictCursor
from jose import JWTError, jwt
from passlib.context import CryptContext

import db
import queries

# --- Security Configuration ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-super-secret-key-that-you-should-change"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# --- Pydantic Models ---
class User(BaseModel):
    username: str
class Token(BaseModel):
    access_token: str
    token_type: str
class TokenData(BaseModel):
    username: Optional[str] = None

class Score(BaseModel): value: float; ms: int
class InterestProfile(BaseModel): R: int; I: int; A: int; S: int; E: int; C: int
class ValuesProfile(BaseModel): values: Dict[str, int]
class StylesProfile(BaseModel): styles: Dict[str, int]

# --- Static Files ---
app.mount("/static", StaticFiles(directory="public"), name="static")

# --- Security and User Utility Functions ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data

# --- Authentication Endpoints ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
            user = cur.fetchone()
        if not user or not verify_password(form_data.password, user['hashed_password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['username']}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        if conn: db.return_db_connection(conn)

@app.post("/register", response_model=User)
async def register_user(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Username already registered")
            
            hashed_password = get_password_hash(form_data.password)
            cur.execute("INSERT INTO users (username, hashed_password) VALUES (%s, %s)",
                        (form_data.username, hashed_password))
        conn.commit()
        return {"username": form_data.username}
    finally:
        if conn: db.return_db_connection(conn)

# --- SECURED Endpoints ---
@app.get("/matches")
def get_matches(current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            user_vector = _get_and_normalize_user_vector(cur, user_id)
            params = {'user_vector_json': json.dumps(user_vector)}
            match_query = queries.get_cosine_similarity_query()
            cur.execute(match_query, params)
            matches = [dict(row) for row in cur.fetchall()]
            for match in matches:
                match['match_score'] = round(match['match_score'] * 100, 2)
            return {"matches": matches}
    finally:
        if conn: db.return_db_connection(conn)

# THE FIX: This endpoint is now correctly included in the file.
@app.post("/save_score/{metric}/{role}")
def save_score(metric: str, role: str, score_data: Score, current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO scores (user_id, role, metric, value, ms) VALUES (%s, %s, %s, %s, %s)",
                        (user_id, role, metric, score_data.value, score_data.ms))
        conn.commit()
        return {"status": "success"}
    finally:
        if conn: db.return_db_connection(conn)

@app.post("/save_interests")
def save_interests(profile: InterestProfile, current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        _save_profile_data(conn, user_id, "user_interests", profile.dict(), "interest")
        return {"status": "success"}
    finally:
        if conn: db.return_db_connection(conn)

@app.post("/save_values")
def save_values(profile: ValuesProfile, current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        _save_profile_data(conn, user_id, "user_values", profile.values, "value")
        return {"status": "success"}
    finally:
        if conn: db.return_db_connection(conn)

@app.post("/save_styles")
def save_styles(profile: StylesProfile, current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        _save_profile_data(conn, user_id, "user_styles", profile.styles, "style")
        return {"status": "success"}
    finally:
        if conn: db.return_db_connection(conn)

@app.get("/job_details/{soc_code}")
def get_job_details(soc_code: str, current_user: User = Depends(get_current_user)):
    user_id = current_user.username
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT title, description FROM occupations WHERE soc_code = %s", (soc_code,))
            job_info = cur.fetchone()
            if not job_info:
                raise HTTPException(status_code=404, detail="Job not found.")
            
            user_vector = _get_and_normalize_user_vector(cur, user_id)
            cur.execute("SELECT feature_name, normalized_value FROM job_profile_vectors WHERE soc_code = %s", (soc_code,))
            job_vector = {row['feature_name']: row['normalized_value'] for row in cur.fetchall()}

            comparison = {}
            for feature, user_score in user_vector.items():
                category, name = feature.split('_', 1)
                if category not in comparison:
                    comparison[category] = []
                comparison[category].append({
                    "name": name,
                    "user_score": round(user_score * 100, 1),
                    "job_score": round(job_vector.get(feature, 0) * 100, 1)
                })
            
            return {
                "title": job_info['title'],
                "description": job_info['description'],
                "profile_match": comparison
            }
    finally:
        if conn: db.return_db_connection(conn)


# --- Helper functions ---
def _save_profile_data(conn, user_id: str, table_name: str, data: dict, column_prefix: str):
    item_col_name = f"{column_prefix}_name"
    sql = (
        f"INSERT INTO {table_name} (user_id, {item_col_name}, score) "
        "VALUES (%s, %s, %s) "
        f"ON CONFLICT (user_id, {item_col_name}) "
        "DO UPDATE SET score = EXCLUDED.score;"
    )
    data_to_insert = [(user_id, name, score) for name, score in data.items()]
    with conn.cursor() as cur:
        cur.executemany(sql, data_to_insert)
    conn.commit()

def _get_and_normalize_user_vector(cur, user_id: str) -> dict:
    user_vector = {}
    cur.execute("SELECT metric, value FROM scores WHERE user_id = %s", (user_id,))
    raw_aptitudes = {row['metric']: row['value'] for row in cur.fetchall()}
    rt_score = raw_aptitudes.get('Reaction Time', 1000)
    best_rt, worst_rt = 150, 1000
    clamped_rt = max(best_rt, min(rt_score, worst_rt))
    user_vector['ability_Reaction Time'] = 1 - ((clamped_rt - best_rt) / (worst_rt - best_rt))
    for metric, value in raw_aptitudes.items():
        if metric in ['Number Facility', 'Spatial Orientation', 'Manual Dexterity']:
            user_vector[f'ability_{metric}'] = value / 100.0
    cur.execute("SELECT interest_name, score FROM user_interests WHERE user_id = %s", (user_id,))
    for row in cur.fetchall(): user_vector[f"interest_{row['interest_name']}"] = row['score'] / 2.0
    cur.execute("SELECT value_name, score FROM user_values WHERE user_id = %s", (user_id,))
    for row in cur.fetchall(): user_vector[f"value_{row['value_name']}"] = float(row['score'])
    cur.execute("SELECT style_name, score FROM user_styles WHERE user_id = %s", (user_id,))
    for row in cur.fetchall(): user_vector[f"style_{row['style_name']}"] = float(row['score'])
    if not user_vector: raise HTTPException(status_code=404, detail="User profile is incomplete.")
    return user_vector
