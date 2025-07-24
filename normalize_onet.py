# normalize_onet.py (Updated for PostgreSQL)
import pandas as pd
import db

def normalize_table(table_name, engine):
    print(f"Processing table: {table_name}...")
    df = pd.read_sql_table(table_name, engine)
    
    index_cols = ['soc_code', 'element_id', 'skill_name'] if table_name == 'skills' else ['soc_code', 'element_id', 'ability_name']

    df_pivot = df.pivot_table(index=index_cols, columns='scale_id', values='value').reset_index()
    df_pivot.rename_axis(None, axis=1, inplace=True)

    df_pivot['IM'] = df_pivot['IM'].fillna(0)
    df_pivot['LV'] = df_pivot['LV'].fillna(0)
    df_pivot['score'] = df_pivot['IM'] * df_pivot['LV']
    
    new_table_name = f"{table_name}_normalized"
    df_pivot.to_sql(new_table_name, con=engine, if_exists='replace', index=False)
    print(f"Successfully created {new_table_name} with {len(df_pivot)} rows.")

if __name__ == "__main__":
    db_engine = db.get_db_engine()
    normalize_table("skills", db_engine)
    normalize_table("abilities", db_engine)
    print("\nO*NET normalization complete.")
