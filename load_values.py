import pandas as pd
import sqlite3

DB_FILE = "jobs.db"
VALUES_FILE = "data/onet/db_29_3_text/Work Values.txt"

# This mapping uses the human-readable name from the file
VALUES_MAP = {
    "Achievement": "Achievement",
    "Independence": "Independence",
    "Recognition": "Recognition",
    "Relationships": "Relationships",
    "Support": "Support",
    "Working Conditions": "Working Conditions"
}

print("Starting O*NET Work Values data load...")

# Load the raw text file
df = pd.read_csv(VALUES_FILE, sep='\t')

# Correctly name all columns
df.columns = ['soc_code', 'element_id', 'element_name', 'scale_id', 'value', 'date', 'source']

# CORRECTED: Keep only the rows that measure Work Value extent (scale_id = 'EX')
df = df[df['scale_id'] == 'EX']

# Map the 'element_name' column to a consistent 'value_name'
df['value_name'] = df['element_name'].map(VALUES_MAP)

# Select only the columns we need for our new table
final_df = df[['soc_code', 'value_name', 'value']]
final_df = final_df.dropna()

# Save the cleaned data to the 'work_values' table in our SQLite database
with sqlite3.connect(DB_FILE) as conn:
    final_df.to_sql('work_values', conn, if_exists='replace', index=False)

print(f"Successfully loaded {len(final_df)} rows into the 'work_values' table.")
print("Data loading complete.")
