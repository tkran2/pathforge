# load_interests.py (Updated for PostgreSQL)
import pandas as pd
import db

INTERESTS_FILE = "data/onet/db_29_3_text/Interests.txt"
INTEREST_MAP = { "Realistic": "R", "Investigative": "I", "Artistic": "A", "Social": "S", "Enterprising": "E", "Conventional": "C" }

print("Starting O*NET Interests data load...")
df = pd.read_csv(INTERESTS_FILE, sep='\t')
df.columns = ['soc_code', 'element_id', 'element_name', 'scale_id', 'value', 'date', 'source']
df = df[df['scale_id'] == 'OI']
df['interest_name'] = df['element_name'].map(INTEREST_MAP)
final_df = df[['soc_code', 'interest_name', 'value']].dropna()

engine = db.get_db_engine()
final_df.to_sql('interests', con=engine, if_exists='replace', index=False)
print(f"Successfully loaded {len(final_df)} rows into the 'interests' table.")
