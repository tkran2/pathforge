import sqlite3, pandas as pd, pathlib

DB = "jobs.db"
DATA_DIR = pathlib.Path("data/onet/db_29_3_text")

FILES = {
    # NOTE: we do NOT include "Job Zone" here because it isn't in this file
    "Occupation Data.txt": ("occupations", {
        "O*NET-SOC Code": "soc_code",
        "Title": "title",
        "Description": "description"
    }),
    "Skills.txt": ("skills", {
        "O*NET-SOC Code": "soc_code",
        "Element ID": "element_id",
        "Element Name": "skill_name",
        "Scale ID": "scale_id",
        "Data Value": "value"
    }),
    "Abilities.txt": ("abilities", {
        "O*NET-SOC Code": "soc_code",
        "Element ID": "element_id",
        "Element Name": "ability_name",
        "Scale ID": "scale_id",
        "Data Value": "value"
    }),
    "Work Activities.txt": ("work_activities", {
        "O*NET-SOC Code": "soc_code",
        "Element ID": "element_id",
        "Element Name": "activity_name",
        "Scale ID": "scale_id",
        "Data Value": "value"
    }),
    # Optional: we load Job Zone info from the separate file
    "Job Zones.txt": ("job_zones", {
        "O*NET-SOC Code": "soc_code",
        "Job Zone": "job_zone",
        "Typical Education Needed": "education_needed",
        "Related Experience": "related_experience",
        "Job Training": "job_training"
    })
}

def load_file(txt_name, table, colmap, conn):
    path = DATA_DIR / txt_name
    df = pd.read_csv(path, sep="\t", dtype=str)

    # Only keep columns that actually exist in this file
    keep_old = [c for c in colmap.keys() if c in df.columns]
    df = df[keep_old].rename(columns=colmap)

    df.to_sql(table, conn, if_exists="replace", index=False)
    print(f"Loaded {table}: {len(df)} rows (from {txt_name})")

if __name__ == "__main__":
    with sqlite3.connect(DB) as conn:
        for txt, (table, colmap) in FILES.items():
            load_file(txt, table, colmap, conn)
    print("All O*NET tables loaded.")

