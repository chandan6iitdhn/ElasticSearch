"""Incrementally copy updated study records from PostgreSQL into Elasticsearch."""

from psycopg2.extras import RealDictCursor
from app.db_client import get_db_connection
from datetime import datetime, timedelta
from elasticsearch import helpers
from app.es_client import get_es_client
from scripts.index_studies import generate_bulk_actions


# Read changed records in bounded batches to avoid loading the full table at once.
def fetch_updated_studies(last_sync_time, current_sync_time, batch_size=500):
    conn = get_db_connection()
    try:
        with conn.cursor(
            name="incremental_study_cursor", cursor_factory=RealDictCursor
        ) as cursor:
            cursor.itersize = batch_size
            cursor.execute(
               """
               select study_id, title, status, participant_count, updated_at, is_deleted from studies where 
               updated_at > %s and updated_at<= %s order by updated_at, study_id
               """, (last_sync_time, current_sync_time)
            )
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
    finally:
        conn.close()


# Bulk-index each batch and fail the run if any documents could not be indexed.
def incremental_sync(last_sync_time, current_sync_time, batch_size=500):
    client = get_es_client()
    total_success = 0
    total_failed = 0

    try:
        for batch_number, studies in enumerate(fetch_updated_studies(last_sync_time, current_sync_time, batch_size), start=1):
            actions = generate_bulk_actions(studies, index_name="studies_v3")
            success, errors = helpers.bulk(
                client, actions, chunk_size=batch_size, raise_on_error=False,
                max_retries=3, retry_on_status=(429, 503)
            )
            total_success += success
            total_failed += len(errors)
            print(f"Batch {batch_number}: successful={success}, failed={len(errors)}")

            for error in errors:
                print("Indexing Error:", error)

        print("Total successful:", total_success)
        print("Total failed:", total_failed)

        if total_failed:
            raise RuntimeError(f"{total_failed} documents failed indexing")

    finally:
        client.close()


# Checkpoint helpers allow a scheduled sync to resume from its last saved timestamp.
def get_last_checkpoint():
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT last_sync_time
                FROM sync_checkpoints
                WHERE sync_name = %s
            """, ("studies_elasticsearch",))

            row = cursor.fetchone()

            if row is None:
                raise RuntimeError("Checkpoint not initialized")

            return row[0]
    finally:
        conn.close()


def save_checkpoint(checkpoint):
    conn = get_db_connection()

    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE sync_checkpoints
                    SET last_sync_time = %s
                    WHERE sync_name = %s
                """, (
                    checkpoint,
                    "studies_elasticsearch"
                ))

                if cursor.rowcount != 1:
                    raise RuntimeError("Checkpoint not found")
    finally:
        conn.close()


def run_incremental_sync():
    last_checkpoint = get_last_checkpoint()
    print("Last checkpoint:", last_checkpoint)

    # capture an upper boundary before processing
    current_checkpoint = datetime.now().replace(tzinfo=None)
    incremental_sync(last_sync_time=last_checkpoint, current_sync_time=current_checkpoint, batch_size=500)
    save_checkpoint(current_checkpoint)
    print("New checkpoint:", current_checkpoint)


if __name__ == "__main__":
    # Use a small lookback window so recent updates are included in this run.
    run_incremental_sync()
