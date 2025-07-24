# fetch_jobs_api.py (Updated for PostgreSQL)
import os
import sys
import httpx
from datetime import date
from dotenv import load_dotenv
import db

load_dotenv()
API_KEY = os.getenv("RAPIDAPI_KEY")

def fetch_jobs(role, region):
    url = "https://jsearch.p.rapidapi.com/search"
    querystring = {"query": f"{role} in {region}", "num_pages": "1", "page": "1"}
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    with httpx.Client() as client:
        response = client.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json().get("data", [])

def save_jobs(jobs_data, role, region):
    conn = db.get_db_connection()
    with conn.cursor() as cur:
        today = date.today().isoformat()
        for job in jobs_data:
            # Using %s for PostgreSQL
            cur.execute("INSERT INTO jobs (role, region, date) VALUES (%s, %s, %s)", (role, region, today))
    conn.commit()
    conn.close()
    print(f"Saved {len(jobs_data)} jobs for '{role}' in '{region}'.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fetch_jobs_api.py \"<role>\" \"<region>\"")
        sys.exit(1)

    role_arg = sys.argv[1]
    region_arg = sys.argv[2]

    try:
        jobs = fetch_jobs(role_arg, region_arg)
        if jobs:
            save_jobs(jobs, role_arg, region_arg)
        else:
            print("No jobs found for the given query.")
    except Exception as e:
        print(f"An error occurred: {e}")
