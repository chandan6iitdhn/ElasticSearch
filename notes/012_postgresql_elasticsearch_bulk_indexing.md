# Day 12 — PostgreSQL → Elasticsearch Bulk Indexing

## Goal
Build a repeatable indexing pipeline that reads studies from PostgreSQL in batches, transforms them into Elasticsearch documents, and indexes them using the Bulk API.

## Architecture
PostgreSQL (source of truth) → server-side cursor / batch fetch → document transformation → Elasticsearch bulk actions → `studies_v3`.

- PostgreSQL remains the authoritative database; Elasticsearch is a search-oriented projection.
- Batch processing avoids loading the entire source table into application memory.
- Reindexing with stable document IDs replaces existing documents rather than creating duplicates.
- For production rebuilds, build a versioned index and switch a search alias after validation. Account for writes that occur during rebuilding.

## Elasticsearch mapping

```python
client.indices.create(
    index="studies_v3",
    mappings={"properties": {
        "study_id": {"type": "keyword"},
        "title": {"type": "text"},
        "status": {"type": "keyword"},
        "participant_count": {"type": "integer"},
    }}
)
```

Use `indices.exists()` to avoid attempting to create an existing index. Note that an existing index's mapping must still be validated; skipping creation does not ensure the mapping matches expectations.

## PostgreSQL connection

```python
# app/db_client.py
import os
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", 5432)),
        dbname=os.environ["PG_DATABASE"],
        user=os.environ["PG_USERNAME"],
        password=os.environ["PG_PASSWORD"],
        connect_timeout=10,
    )
```

## Fetch rows in batches

```python
from psycopg2.extras import RealDictCursor
from app.db_client import get_db_connection

def fetch_studies_in_batches(batch_size=500):
    conn = get_db_connection()
    try:
        with conn.cursor(
            name="studies_batch_cursor",
            cursor_factory=RealDictCursor,
        ) as cursor:
            cursor.itersize = batch_size
            cursor.execute("""
                SELECT study_id, title, status, participant_count
                FROM studies
                ORDER BY study_id
            """)
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
    finally:
        conn.close()
```

- A named psycopg2 cursor is server-side and supports streaming.
- `fetchmany(500)` retrieves at most 500 records per iteration.
- `yield` pauses the generator between batches, so callers process one batch at a time.
- `enumerate(generator, start=1)` labels the first batch 1; it does not change the query offset.
- Fully consume or explicitly close the generator to release its database connection promptly.

## Transform rows and generate actions

```python
def transform_study(row):
    return {
        "study_id": row["study_id"],
        "title": row["title"],
        "status": row["status"],
        "participant_count": row["participant_count"],
    }

def generate_bulk_actions(studies, index_name="studies_v3"):
    for study in studies:
        document = transform_study(study)
        yield {
            "_op_type": "index",
            "_index": index_name,
            "_id": document["study_id"],
            "_source": document,
        }
```

`_op_type="index"` creates or replaces the document at a given `_id`; using `study_id` as `_id` makes reruns repeatable. `next(actions)` consumes exactly one action and advances the generator.

## Bulk indexing with error reporting and retries

```python
from elasticsearch import helpers, TransportError
from app.es_client import get_es_client

def create_studies_index(client):
    index_name = "studies_v3"
    if client.indices.exists(index=index_name):
        print(f"Index {index_name} already exists")
        return
    client.indices.create(
        index=index_name,
        mappings={"properties": {
            "study_id": {"type": "keyword"},
            "title": {"type": "text"},
            "status": {"type": "keyword"},
            "participant_count": {"type": "integer"},
        }},
    )

def bulk_index_studies(batch_size=500):
    client = get_es_client()
    total_success = 0
    total_failed = 0
    try:
        create_studies_index(client)
        for batch_number, studies in enumerate(
            fetch_studies_in_batches(batch_size), start=1
        ):
            actions = generate_bulk_actions(studies, "studies_v3")
            success, errors = helpers.bulk(
                client,
                actions,
                chunk_size=batch_size,
                raise_on_error=False,
                max_retries=3,
                initial_backoff=2,
                max_backoff=30,
                retry_on_status=(429, 503),
            )
            total_success += success
            total_failed += len(errors)
            print(f"Batch {batch_number}: Successful={success}, Failed={len(errors)}")
            for error in errors:
                print("Indexing error:", error)
        print("Total successful operations:", total_success)
        print("Total failed operations:", total_failed)
        if total_failed:
            raise RuntimeError(f"{total_failed} documents failed")
    except TransportError as exc:
        print("Elasticsearch request failed:", exc)
        raise
    finally:
        client.close()

if __name__ == "__main__":
    bulk_index_studies(batch_size=500)
```

### Failure handling
- Bulk requests can partially succeed: examine successful operation count and failed item details.
- `raise_on_error=False` returns item-level errors instead of raising `BulkIndexError` for those failures.
- `max_retries=3` retries eligible failed items up to three additional times; `initial_backoff=2`, `max_backoff=30` control exponential retry delays, **not** total job duration.
- `retry_on_status=(429, 503)` targets transient throttling/service-unavailable responses.
- Invalid data such as `participant_count="unknown"` with an integer mapping generally causes HTTP 400 and requires data correction; retries cannot fix it.
- Request/transport exceptions may interrupt the job after some documents have been indexed; use stable IDs, checkpointing, and recovery procedures in production.
- For very large jobs, `helpers.streaming_bulk()` avoids accumulating all error results.

## Verification

```bash
python -m scripts.index_studies
curl -k -u elastic 'https://localhost:9200/studies_v3/_count?pretty'
```

For this local exercise, `curl -k` bypasses TLS certificate verification; prefer `--cacert /path/to/http_ca.crt` for verified connections. The Python client uses the configured CA certificate.

**Observed results:** Two batches of 500, 1,000 successful operations, 0 failed; `_count` returned 1,000. A later rerun also completed with 1,000 successful operations and 0 failures, without a fresh count check.

If recently indexed documents are not visible to search/count immediately, Elasticsearch refresh behavior may be involved; for explicit test verification, call `client.indices.refresh(index="studies_v3")`.

## Troubleshooting encountered
- Python `AuthenticationException(401, 'security_exception')` indicated an incorrect Elasticsearch password in the PyCharm environment.
- `curl -k -u elastic https://localhost:9200` succeeded with the correct password, isolating the issue to the Python environment variables.
- Correcting `ES_PASSWORD` resolved authentication; no password reset was necessary.
- Do not print or share actual passwords. Confirm `ELASTICSEARCH_URL`, `ES_USERNAME`, `ES_PASSWORD`, and `ES_CA_CERT` in the active PyCharm run configuration.

## Interview revision questions
1. **Why bulk indexing?** Reduces per-document request overhead and improves throughput.
2. **Why a server-side cursor?** Streams large query results without loading the entire result set into client memory.
3. **`yield` vs `return`?** `yield` produces items lazily and preserves execution state between iterations.
4. **Why stable `_id`?** Repeated `index` operations replace the same document rather than creating duplicates.
5. **What is a partial bulk failure?** Some items succeed while others fail within the same bulk request; inspect item-level results.
6. **Which errors should be retried?** Transient conditions such as HTTP 429/503; not mapping errors caused by invalid data.
7. **Is bulk indexing transactional?** No; partial successes remain even if later items or requests fail.
8. **How do you rebuild safely?** Create a new versioned index, backfill, validate, reconcile concurrent writes, and atomically switch an alias.
9. **Why keep PostgreSQL as source of truth?** Elasticsearch is optimized for retrieval/search and can be rebuilt from authoritative records.
10. **How do you validate completion?** Check error counts, document counts, sampled records, mappings, and (where appropriate) refresh visibility.

## Day 12 completion
- Session 1: Architecture, mapping, Bulk API, reindexing, aliases.
- Session 2: PostgreSQL connection, batch fetching, transformation, bulk indexing, verification/error handling.
- Practical: 1,000 study records successfully indexed into `studies_v3`.

**Next:** Day 13 — PostgreSQL ↔ Elasticsearch synchronization and keeping search data up to date.
