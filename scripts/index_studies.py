from psycopg2.extras import RealDictCursor
from app.db_client import get_db_connection
from elasticsearch import helpers, TransportError
from app.es_client import get_es_client

def fetch_studies_in_batches(batch_size=500):
    conn = get_db_connection()
    try:
        with conn.cursor(
            name="studies_batch_cursor", cursor_factory=RealDictCursor
        ) as cursor:
            cursor.itersize = batch_size
            cursor.execute("SELECT study_id, title, status, participant_count FROM studies ORDER BY study_id")
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
    finally:
        conn.close()


def transform_study(row):
    return {
        "study_id": row["study_id"],
        "title": row["title"],
        "status": row["status"],
        "participant_count": row["participant_count"]
    }


def generate_bulk_actions(studies, index_name="studies_v3"):
    for study in studies:
        if study.get("is_deleted", False):
            yield {
                "_op_type": "delete",
                "_index": index_name,
                "_id": study["study_id"]
            }
        else:
            document = transform_study(study)
            yield {
                "_op_type": "index",
                "_index": index_name,
                "_id": document["study_id"],
                "_source": document
            }


def create_studies_index(client):
    index_name = "studies_v3"

    if client.indices.exists(index=index_name):
        print(f"Index '{index_name}' already exists. Skipping creation.")
        return

    mappings = {
        "properties": {
            "study_id": {"type": "keyword"},
            "title": {"type": "text"},
            "status": {"type": "keyword"},
            "participant_count": {"type": "integer"}
        }
    }
    client.indices.create(index=index_name, mappings=mappings)
    print(f"Index '{index_name}' created successfully.")


def bulk_index_studies(batch_size=500):
    client = get_es_client()
    create_studies_index(client)

    total_success = 0
    total_failed = 0

    try:
        for batch_number, studies in enumerate(
            fetch_studies_in_batches(batch_size=batch_size), start=1
        ):
            actions = generate_bulk_actions(studies, index_name="studies_v3")
            success, errors = helpers.bulk(
                client, actions, chunk_size=batch_size, raise_on_error=False,
                max_retries=3, initial_backoff=2, max_backoff=30, retry_on_status=(429,503)
            )
            total_success += success
            total_failed += len(errors)
            print(f"Batch {batch_number}: "
                  f"Successful {success} , Failed {len(errors)}")

            for error in errors:
                print(f"Bulk indexing error: {error}")

    except TransportError as exc:
        print("Elasticsearch request failed:", exc)
        raise

    finally:
        client.close()

    print("\nIndexing completed")
    print("Total successful operations:", total_success)
    print("Total failed operations:", total_failed)

    if total_failed:
        raise RuntimeError(
            f"indexing finished with {total_failed} failed documents"
        )

if __name__ == "__main__":
    bulk_index_studies(batch_size=500)
    # client = get_es_client()
    # print(client.info())