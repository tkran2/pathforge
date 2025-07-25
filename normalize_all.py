import pandas as pd
import db
import os

ONET_DIR = 'data/onet/db_29_3_text/'

def normalize_and_load():
    """
    A comprehensive script to process all O*NET data, normalize it to a 0-1 scale,
    and load it into a single, unified table for vector-based matching.
    """
    engine = db.get_db_engine()
    print("--- Starting comprehensive data normalization ---")

    # --- Step 1: Load Raw Data ---
    print("Loading raw O*NET files...")
    abilities_df = pd.read_csv(os.path.join(ONET_DIR, 'Abilities.txt'), sep='\t')
    interests_df = pd.read_csv(os.path.join(ONET_DIR, 'Interests.txt'), sep='\t')
    values_df = pd.read_csv(os.path.join(ONET_DIR, 'Work Values.txt'), sep='\t')
    styles_df = pd.read_csv(os.path.join(ONET_DIR, 'Work Styles.txt'), sep='\t')
    occupations_df = pd.read_csv(os.path.join(ONET_DIR, 'Occupation Data.txt'), sep='\t')[['O*NET-SOC Code', 'Title']]
    occupations_df = occupations_df.rename(columns={'O*NET-SOC Code': 'soc_code', 'Title': 'title'})
    
    # --- Step 2: Normalize and Transform Each Component ---

    def process_component(df, name_col, value_col, scale_id, prefix):
        # Filter for the 'Importance' scale and rename columns
        df_im = df[df['Scale ID'] == scale_id].copy()
        df_im = df_im[['O*NET-SOC Code', name_col, value_col]]
        df_im.columns = ['soc_code', 'feature_name', 'raw_score']
        
        # Normalize the score from 1-5 scale to 0-1 scale
        df_im['normalized_value'] = (df_im['raw_score'] - 1) / 4.0
        
        # Add a prefix to the feature name to avoid collisions (e.g., 'interest_Artistic')
        df_im['feature_name'] = prefix + '_' + df_im['feature_name']
        return df_im[['soc_code', 'feature_name', 'normalized_value']]

    print("Normalizing Abilities, Interests, Values, and Styles...")
    # O*NET Abilities are on a 1-5 Importance scale (IM) and 0-7 Level scale (LV)
    # We will use the normalized Importance score for our vector
    abilities_norm = process_component(abilities_df, 'Element Name', 'Data Value', 'IM', 'ability')
    
    # O*NET Interests are on a 1-5 Importance scale (OI)
    interests_norm = process_component(interests_df, 'Element Name', 'Data Value', 'OI', 'interest')

    # O*NET Work Values are on a 1-5 Importance scale (IM)
    values_norm = process_component(values_df, 'Element Name', 'Data Value', 'IM', 'value')

    # O*NET Work Styles are on a 1-5 Importance scale (IM)
    styles_norm = process_component(styles_df, 'Element Name', 'Data Value', 'IM', 'style')

    # --- Step 3: Combine into a Single DataFrame ---
    print("Combining all components into a single vector table...")
    combined_df = pd.concat([abilities_norm, interests_norm, values_norm, styles_norm], ignore_index=True)

    # --- Step 4: Load into Database ---
    print(f"Loading {len(occupations_df)} occupations...")
    occupations_df.to_sql('occupations', con=engine, if_exists='replace', index=False)

    print(f"Loading {len(combined_df)} job profile vectors...")
    combined_df.to_sql('job_profile_vectors', con=engine, if_exists='replace', index=False)
    
    print("--- Normalization and loading complete. ---")


if __name__ == "__main__":
    normalize_and_load()

