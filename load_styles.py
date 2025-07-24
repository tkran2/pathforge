import pandas as pd
import db

STYLES_FILE = "data/onet/db_29_3_text/Work Styles.txt"

print("Starting O*NET Work Styles data load...")

# Load the raw text file
df = pd.read_csv(STYLES_FILE, sep='\t')

# CORRECTED: Use the correct 12 column names for this file
df.columns = ['soc_code', 'element_id', 'element_name', 'scale_id', 'value', 'n', 'standard_error', 'lower_ci_bound', 'upper_ci_bound', 'recommend_suppress', 'date', 'source']

# Keep only the rows that measure Work Style importance (scale_id = 'IM')
df = df[df['scale_id'] == 'IM']

# Rename the 'element_name' column to 'style_name' for clarity
df = df.rename(columns={'element_name': 'style_name'})

# Select only the columns we need for our new table
final_df = df[['soc_code', 'style_name', 'value']]
final_df = final_df.dropna()

# Get the database engine and save the data
engine = db.get_db_engine()
final_df.to_sql('work_styles', con=engine, if_exists='replace', index=False)

print(f"Successfully loaded {len(final_df)} rows into the 'work_styles' table.")
print("Data loading complete.")
