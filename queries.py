# queries.py

def get_cosine_similarity_query() -> str:
    """
    Builds and returns a single, comprehensive SQL query to calculate job matches
    using Cosine Similarity for maximum accuracy.
    
    The formula for Cosine Similarity is: (A · B) / (||A|| * ||B||)
    Where:
    - A is the user's profile vector
    - B is the job's profile vector
    - A · B is the dot product of the two vectors
    - ||A|| and ||B|| are the magnitudes (Euclidean norms) of the vectors
    """
    
    # The user's profile vector will be passed in as a dictionary of parameters.
    # The query uses these parameters to calculate the similarity.
    
    return """
    WITH user_vector AS (
        -- Step 1: Create a temporary table from the user's normalized scores,
        -- which are passed in as parameters.
        -- We unpivot the parameters into rows for easier processing.
        SELECT 
            key as feature_name, 
            -- THE FIX: Explicitly cast the user's value from TEXT to a number.
            value::double precision as user_value
        FROM jsonb_each_text(%(user_vector_json)s::jsonb)
    ),
    dot_product_and_magnitudes AS (
        -- Step 2: For each job, calculate the components of the formula
        SELECT
            jpv.soc_code,
            -- A · B (Dot Product)
            SUM(jpv.normalized_value * uv.user_value) as dot_product,
            -- ||B||^2 (Squared Magnitude of Job Vector)
            SUM(POWER(jpv.normalized_value, 2)) as job_magnitude_sq,
            -- ||A||^2 (Squared Magnitude of User Vector)
            SUM(POWER(uv.user_value, 2)) as user_magnitude_sq
        FROM job_profile_vectors jpv
        JOIN user_vector uv ON jpv.feature_name = uv.feature_name
        GROUP BY jpv.soc_code
    )
    -- Step 3: Calculate the final Cosine Similarity score
    SELECT
        dpm.soc_code,
        o.title,
        -- The final formula: dot_product / (sqrt(job_mag) * sqrt(user_mag))
        (
            dpm.dot_product / 
            (SQRT(dpm.job_magnitude_sq) * SQRT(dpm.user_magnitude_sq))
        ) as match_score
    FROM dot_product_and_magnitudes dpm
    JOIN occupations o ON dpm.soc_code = o.soc_code
    -- Filter out any potential division-by-zero errors or non-matches
    WHERE 
        dpm.job_magnitude_sq > 0 AND dpm.user_magnitude_sq > 0
    ORDER BY match_score DESC
    LIMIT 10;
    """

