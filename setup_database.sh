#!/bin/bash
set -e

# Create user data tables if they don't already exist
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS jobs (role TEXT, region TEXT, date TEXT);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS scores (id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, role TEXT, metric TEXT, value REAL, ms INTEGER, created_at TEXT);"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_interests (user_id TEXT NOT NULL, interest_name TEXT NOT NULL, score INTEGER NOT NULL, PRIMARY KEY (user_id, interest_name));"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_values (user_id TEXT NOT NULL, value_name TEXT NOT NULL, score INTEGER NOT NULL, PRIMARY KEY (user_id, value_name));"
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS user_styles (user_id TEXT NOT NULL, style_name TEXT NOT NULL, score INTEGER NOT NULL, PRIMARY KEY (user_id, style_name));"

# Run the data loading scripts
python load_onet.py
python normalize_onet.py
python load_interests.py
python load_values.py
python load_styles.py
