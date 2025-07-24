# normalize_onet.py
import sqlite3
import pandas as pd

DB_FILE = "jobs.db"

def normalize_table(conn, table_name):
    """
    Reads an O*NET table, pivots it to combine Importance and Level,
    calculates a composite score, and saves it to a new table.
    """
    print(f"Processing table: {table_name}...")

    # Read the raw data
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

    # FIX: Explicitly convert the 'value' column to a numeric type
    # errors='coerce' will turn any non-numeric values into NaN (Not a Number)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')

    # Define primary attributes for the pivot index
    if table_name == 'skills':
        index_cols = ['soc_code', 'element_id', 'skill_name']
    elif table_name == 'abilities':
        index_cols = ['soc_code', 'element_id', 'ability_name']
    else:
        print(f"Skipping unsupported table: {table_name}")
        return

    # Pivot the table to get 'IM' (Importance) and 'LV' (Level) as columns
    df_pivot = df.pivot_table(
        index=index_cols,
        columns='scale_id',
        values='value'
    ).reset_index()

    # Fill NaNs that may result from pivoting
    df_pivot['IM'] = df_pivot['IM'].fillna(0)
    df_pivot['LV'] = df_pivot['LV'].fillna(0)

    # Calculate a composite score
    df_pivot['score'] = df_pivot['IM'] * df_pivot['LV']

    # Define the new table name
    new_table_name = f"{table_name}_normalized"

    # Save the cleaned data to the new table
    df_pivot.to_sql(new_table_name, conn, if_exists='replace', index=False)

    print(f"Successfully created {new_table_name} with {len(df_pivot)} rows.")

if __name__ == "__main__":
    with sqlite3.connect(DB_FILE) as conn:
        normalize_table(conn, "skills")
        normalize_table(conn, "abilities")
    print("\nO*NET normalization complete.")
