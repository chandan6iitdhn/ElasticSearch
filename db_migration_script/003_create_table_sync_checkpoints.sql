-- create table sync_checkpoints to track the last sync time for each sync process
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    sync_name VARCHAR(100) PRIMARY KEY,
    last_sync_time TIMESTAMP NOT NULL
);

-- insert initial checkpoint for studies_elasticsearch sync process
INSERT INTO sync_checkpoints (
    sync_name,
    last_sync_time
)
VALUES (
    'studies_elasticsearch',
    '1970-01-01 00:00:00'
)
ON CONFLICT (sync_name) DO NOTHING;