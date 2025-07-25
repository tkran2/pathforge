#!/bin/bash
set -e

# --- Load local environment variables from .env file if it exists ---
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
# --------------------------------------------------------------------

echo "--- Setting up database schema ---"

# NEW: Add the users table for authentication
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    hashed_password TEXT NOT NULL
);"

# Existing user data tables remain the same
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, role TEXT, metric TEXT,
    value REAL, ms INTEGER, created_at TIMESTAMPTZ DEFAULT NOW()
);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_interests (
    user_id TEXT NOT NULL, interest_name TEXT NOT NULL, score INTEGER NOT NULL,
    PRIMARY KEY (user_id, interest_name)
);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_values (
    user_id TEXT NOT NULL, value_name TEXT NOT NULL, score INTEGER NOT NULL,
    PRIMARY KEY (user_id, value_name)
);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_styles (
    user_id TEXT NOT NULL, style_name TEXT NOT NULL, score INTEGER NOT NULL,
    PRIMARY KEY (user_id, style_name)
);"

# Create the unified vector table for jobs
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS job_profile_vectors (
    soc_code TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    normalized_value REAL NOT NULL,
    PRIMARY KEY (soc_code, feature_name)
);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS occupations (
    soc_code TEXT PRIMARY KEY,
    title TEXT
);"


echo "--- Creating performance indexes ---"
psql "$DATABASE_URL" -c "CREATE INDEX IF NOT EXISTS idx_job_profile_vectors_soc_code ON job_profile_vectors (soc_code);"
psql "$DATABASE_URL" -c "CREATE INDEX IF NOT EXISTS idx_job_profile_vectors_feature_name ON job_profile_vectors (feature_name);"
psql "$DATABASE_URL" -c "CREATE INDEX IF NOT EXISTS idx_scores_user_id_metric ON scores (user_id, metric);"


# --- Smart Data Loading Check ---
ROW_COUNT=$(psql "$DATABASE_URL" -t -A -c "SELECT COUNT(*) FROM job_profile_vectors;" || echo "0")

if [ "$ROW_COUNT" -eq 0 ]; then
  echo "--- Vector table is empty. Running comprehensive normalization... (This will take a minute) ---"
  python normalize_all.py
else
  echo "--- Vector data already loaded. Skipping normalization. ---"
fi


echo "--- Database setup and data loading complete ---"

