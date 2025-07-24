import pandas as pd
import db
import os

ONET_DIR = 'data/onet/db_29_3_text/'

def load_and_select(filename, table_name, column_map, engine):
    """
    Reads a tab-separated file, selects specific columns using the provided
    map, renames them, and loads them into a database table.
    """
    filepath = os.path.join(ONET_DIR, filename)
    print(f"Loading {filepath} into table '{table_name}'...")

    # Read the file using the header from the file itself
    df = pd.read_csv(filepath, sep='\t', encoding='latin1')

    # Keep only the columns we need, specified by the keys in column_map
    df_subset = df[list(column_map.keys())]

    # Rename the columns to our desired names
    df_subset = df_subset.rename(columns=column_map)

    # Save to the database
    df_subset.to_sql(table_name, con=engine, if_exists='replace', index=False)
    print(f"Loaded {len(df_subset)} rows into '{table_name}'.")

if __name__ == "__main__":
    engine = db.get_db_engine()

    # Define the columns we want to keep from each file and what to name them
    occupation_cols = {"O*NET-SOC Code": "soc_code", "Title": "title", "Description": "description"}
    skill_cols = {"O*NET-SOC Code": "soc_code", "Element ID": "element_id", "Element Name": "skill_name", "Scale ID": "scale_id", "Data Value": "value"}
    ability_cols = {"O*NET-SOC Code": "soc_code", "Element ID": "element_id", "Element Name": "ability_name", "Scale ID": "scale_id", "Data Value": "value"}
    activity_cols = {"O*NET-SOC Code": "soc_code", "Element ID": "element_id", "Element Name": "activity_name", "Scale ID": "scale_id", "Data Value": "value"}
    job_zone_cols = {"O*NET-SOC Code": "soc_code", "Job Zone": "job_zone"} # Also includes other columns we don't need

    # Load each table
    load_and_select("Occupation Data.txt", "occupations", occupation_cols, engine)
    load_and_select("Skills.txt", "skills", skill_cols, engine)
    load_and_select("Abilities.txt", "abilities", ability_cols, engine)
    load_and_select("Work Activities.txt", "work_activities", activity_cols, engine)
    load_and_select("Job Zones.txt", "job_zones", job_zone_cols, engine)

    print("\nO*NET data loading complete.")
