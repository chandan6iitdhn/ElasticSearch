-- Create a function to refresh updated_at
CREATE OR REPLACE FUNCTION update_studies_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Attach the function to studies table
DROP TRIGGER IF EXISTS trg_studies_updated_at ON studies;

CREATE TRIGGER trg_studies_updated_at
BEFORE UPDATE ON studies
FOR EACH ROW
EXECUTE FUNCTION update_studies_timestamp();