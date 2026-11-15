# Day 16 — End-to-End Study Search API

## Status
Completed both sessions (10 sections). Core integration tests passed. Production hardening remains future work.

## Architecture
PostgreSQL (source of truth) → bulk/incremental sync → Elasticsearch (`studies_v3`) → Flask (`GET /api/studies/search`) → client.

## Session 1 — Search API

### 1. Architecture and API design
- Flask handles HTTP requests and validation; Elasticsearch performs search; PostgreSQL is authoritative for study data.
- Search endpoint: `GET /api/studies/search`.
- Supported parameters: `q`, `status`, `min_participants`, `sort_by`, `order`, `page`, `page_size`.
- ES connectivity health endpoint: `GET /api/health/elasticsearch`.

### 2. Query building
- Full-text title search: `match` query.
- Exact status filtering: `term` in `bool.filter`.
- Minimum participant count: `range` with `gte`.
- No search criteria: `match_all`.
- `must` influences relevance; `filter` restricts results without scoring.

### 3. Pagination and sorting
- Offset pagination: `from = (page - 1) * page_size`, `size = page_size`.
- Return `total`, `page`, `page_size`, `total_pages`, and `studies`.
- `total_pages = (total + page_size - 1) // page_size`.
- Validate `page >= 1`, `1 <= page_size <= 100`, and the Elasticsearch 10,000-result window. Note: the actual Elasticsearch window condition is `from + size <= 10000`; this is equivalent to `page * page_size <= 10000` for this implementation.
- Whitelist sortable fields (`participant_count`, `study_id`) and sort direction (`asc`, `desc`). A stable `study_id` tie-breaker helps avoid unstable page ordering.
- For deep pagination, consider `search_after` plus a point-in-time search instead of large `from` offsets.

### 4. Error handling and testing
- Invalid inputs return HTTP 400.
- Elasticsearch connection/timeouts return HTTP 503; Elasticsearch API failures return HTTP 502.
- No matches return HTTP 200 with `studies: []`.
- Verified: non-overlapping first/second pages, invalid page/page size, invalid sort, and empty search results.

## Session 2 — PostgreSQL Synchronization

### 1. Initial bulk indexing
- `scripts/index_studies.py` streams PostgreSQL rows in batches using a server-side cursor.
- `helpers.bulk()` indexes documents with `_id = study_id` to avoid duplicate documents on retries.
- Index mapping: `study_id` keyword, `title` text, `status` keyword, `participant_count` integer.
- Initial indexing must account for `is_deleted` in the SELECT. For a fresh index, skipping deleted records avoids unnecessary delete-404 errors. Confirm the script includes `is_deleted`; this code change was recommended but not verified.

### 2. Incremental sync and timestamps
- `scripts/incremental_sync.py` selects rows with `updated_at > last_sync_time AND updated_at <= current_sync_time`, ordered by `updated_at, study_id`.
- Checkpoint is stored in PostgreSQL `sync_checkpoints` under `studies_elasticsearch`.
- Checkpoint advances only after all reported bulk operations succeed.
- `DEFAULT CURRENT_TIMESTAMP` initializes `updated_at` on INSERT but does not automatically update it on UPDATE.
- Created a migration containing a PostgreSQL `BEFORE UPDATE` trigger that sets `NEW.updated_at = CURRENT_TIMESTAMP`.
- Verified trigger registration (`trg_studies_updated_at`, UPDATE, BEFORE) and verified the timestamp changes during an UPDATE test.
- Caveat: `CURRENT_TIMESTAMP` is fixed at transaction start; transaction/commit ordering can cause timestamp-watermark gaps. Host/DB clock differences are another concern.

### 3. Partial failures, retries, recovery
- Bulk API is not atomic across the entire batch: some documents may succeed while others fail.
- For partial failures, report failure and retain the old checkpoint; successful index operations may be repeated safely using stable `_id`.
- Retry transient HTTP 429/503 with backoff; fix persistent mapping/validation errors rather than retrying indefinitely.
- `index` is idempotent with the same `_id` and payload, but it does not prevent stale writes from overwriting newer writes.
- A delete of an already-missing document can return 404. Treat an expected delete-404 as an acceptable final state, while still rejecting unexpected failures; `helpers.streaming_bulk()` permits item-level inspection.
- Current script does not yet implement special handling for delete-404, a robust CDC mechanism, or overlap prevention.

### 4. End-to-end integration tests (verified)
- Inserted PostgreSQL test record `ST_SYNC_TEST_001` with title `Elasticsearch Incremental Sync Test`, status `Active`, participant count `50`.
- Confirmed it was eligible for sync relative to the saved checkpoint.
- Ran incremental sync: `successful=1`, `failed=0`, checkpoint advanced from `2026-11-08 18:13:04.967367` to `2026-11-15 22:26:27.827035`.
- Retrieved document by ID from Elasticsearch `studies_v3`, confirming its contents.
- Queried Flask endpoint and got one matching study with expected fields.
- Updated PostgreSQL study to `Completed`, participant count `150`; Flask returned updated values, confirming update propagation.
- Soft-deleted study by setting `is_deleted=TRUE`; Flask search returned `studies: []`, `total: 0`.
- Ensure `app/search_service.py` uses `studies_v3` (the original shared code used `studies_v2`; subsequent API results showed updated indexed data, but the exact final code was not re-shared).

### 5. Production-readiness checklist
- **Persistent storage:** Earlier `docker inspect es01 --format '{{json .Mounts}}'` returned `[]`, meaning no mounts. Existing data is in the container writable layer. Do **not** remove/recreate `es01` or run destructive volume cleanup before planning backup and safe migration.
- **Checkpoint correctness:** Timestamp-only synchronization can miss late-committing transactions. For stronger guarantees, consider PostgreSQL CDC/logical replication or transactional outbox.
- **Concurrency:** Prevent overlapping sync jobs (e.g., PostgreSQL advisory lock); protect checkpoint monotonicity and avoid stale writes.
- **Retry semantics:** Distinguish transient vs permanent errors and expected delete-404 outcomes.
- **Observability:** Structured logs, metrics for sync lag and failures, alerts, and dead-letter/reconciliation mechanisms.
- **Reconciliation:** Periodically compare source data and indexed documents, and plan safe full reindexing with aliases.
- **Security/operations:** Protect credentials and CA paths, manage backups, monitor disk usage and cluster health.

## Interview revision — key answers
1. **Why PostgreSQL plus Elasticsearch?** PostgreSQL is the authoritative transactional store; Elasticsearch provides scalable full-text search and relevance scoring.
2. **Why stable document IDs?** Repeated indexing replaces the same document instead of duplicating it.
3. **Why checkpoint after success?** A partial failure must not silently skip unindexed changes.
4. **Why a trigger for `updated_at`?** Column defaults do not automatically update timestamps on subsequent UPDATE statements.
5. **Why is idempotency insufficient for correctness?** Older operations can arrive after newer operations and overwrite current state.
6. **Why is delete-404 sometimes acceptable?** The desired final state—document absent—is already true.
7. **Why is a timestamp checkpoint imperfect?** Transaction commit order can differ from timestamp assignment/order, causing missed changes.
8. **What is the deployment risk without a Docker volume?** Removing/recreating the container can lose indexed data.

## Next
**Day 17 — Revision, Elasticsearch system design, troubleshooting, and interview preparation.**
