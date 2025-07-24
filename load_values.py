# load_values.py (Updated for PostgreSQL)
import pandas as pd
import db

VALUES_FILE = "data/onet/db_29_3_text/Work Values.txt"
VALUES_MAP = { "Achievement": "Achievement", "Independence": "Independence", "Recognition": "Recognition", "Relationships": "Relationships", "Support": "Support", "Working Conditions": "Working Conditions" }

print("Starting O*NET Work Values data load...")
df = pd.read_csv(VALUES_FILE, sep='\t')
df.columns = ['soc_code', 'element_id', 'element_name', 'scale_id', 'value', 'date', 'source']
df = df[df['scale_id'] == 'EX']
df['value_name'] = df['element_name'].map(VALUES_MAP)
final_df = df[['soc_code', 'value_name', 'value']].dropna()

engine = db.get_db_engine()
final_df.to_sql('work_values', con=engine, if_exists='replace', index=False)
print(f"Successfully loaded {len(final_df)} rows into the 'work_values' table.")

