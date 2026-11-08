-- create a table for studies with sample data
CREATE TABLE IF NOT EXISTS studies (
    id SERIAL PRIMARY KEY,
    study_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    participant_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- insert sample data into the studies table

INSERT INTO studies (
    study_id,
    title,
    status,
    participant_count
)
SELECT
    'ST' || LPAD(num::TEXT, 6, '0') AS study_id,

    CASE (num % 5)
        WHEN 0 THEN 'Diabetes Treatment Study'
        WHEN 1 THEN 'Cancer Research Study'
        WHEN 2 THEN 'Heart Disease Prevention Study'
        WHEN 3 THEN 'COVID-19 Vaccine Study'
        ELSE 'Hypertension Clinical Trial'
    END || ' - ' || num AS title,

    CASE
        WHEN num % 2 = 0 THEN 'Completed'
        ELSE 'In Progress'
    END AS status,

    50 + (num % 950) AS participant_count

FROM generate_series(1, 1000) AS num

ON CONFLICT (study_id) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    participant_count = EXCLUDED.participant_count;
