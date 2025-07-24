import pandas as pd
import sqlite3

DB_FILE = "jobs.db"
INTERESTS_FILE = "data/onet/db_29_3_text/Interests.txt"

# This mapping is now between the 'Element Name' and our desired name
INTEREST_MAP = {
    "Realistic": "Realistic",
    "Investigative": "Investigative",
    "Artistic": "Artistic",
    "Social": "Social",
    "Enterprising": "Enterprising",
    "Conventional": "Conventional"
}

print("Starting O*NET Interests data load...")

# Load the raw text file, specifying it's tab-separated
# We also tell it to skip the header row of the original file
df = pd.read_csv(INTERESTS_FILE, sep='\t', header=0)

# Correctly name all 7 columns
df.columns = ['soc_code', 'element_id', 'element_name', 'scale_id', 'value', 'date', 'source']

# Keep only the rows that measure the RIASEC score (scale_id = 'OI')
df = df[df['scale_id'] == 'OI']

# Map the element_name to a consistent interest_name
df['interest_name'] = df['element_name'].map(INTEREST_MAP)

# Select only the columns we need for our new table
final_df = df[['soc_code', 'interest_name', 'value']]

# Drop any rows where the mapping might have failed (e.g., the 'High-Point' rows)
final_df = final_df.dropna()

# Save the cleaned data to the 'interests' table in our SQLite database
with sqlite3.connect(DB_FILE) as conn:
    final_df.to_sql('interests', conn, if_exists='replace', index=False)

print(f"Successfully loaded {len(final_df)} rows into the 'interests' table.")
print("Data loading complete.")
