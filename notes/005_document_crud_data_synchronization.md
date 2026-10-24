# Day 5 — Elasticsearch Document Operations and Synchronization

## Session 1 — Document Operations

### 1. Index / replace
`client.index()` creates a document or replaces the entire `_source` for an existing ID. Fields omitted from the replacement disappear.

```python
client.index(index="studies_v2", id="ST001", document={
    "study_id": "ST001", "title": "Diabetes Treatment Study",
    "status": "Completed", "participant_count": 300
})
```

### 2. Partial update
`client.update()` with `doc` changes specified fields while preserving other fields. By default, the document must already exist.

```python
client.update(index="studies_v2", id="ST001", doc={"status": "Completed"})
```

### 3. Delete document vs index

```python
client.delete(index="studies_v2", id="ST001")  # one document
# DANGER: deletes the entire index and all its documents/mappings
# client.indices.delete(index="studies_v2")
```

Deleting a nonexistent document normally raises `NotFoundError` in the Python client.

### 4. Upsert
An upsert updates an existing document or creates one if missing.

```python
client.update(index="studies_v2", id="ST003",
              doc={"status": "In Progress"}, doc_as_upsert=True)
```

If missing, this creates a document with **only** the supplied `status`. To use different data for creation, provide `upsert={...}` instead of `doc_as_upsert=True`.

### 5. Bulk operations
The Bulk API batches multiple document operations in one HTTP request. It is **not atomic**: some items can succeed while others fail.

```python
operations = [
    {"index": {"_index": "studies_v2", "_id": "ST101"}},
    {"study_id": "ST101", "title": "Heart Disease Study", "status": "Completed", "participant_count": 500},
    {"update": {"_index": "studies_v2", "_id": "ST102"}},
    {"doc": {"status": "Completed"}},
    {"delete": {"_index": "studies_v2", "_id": "ST103"}},
]
response = client.bulk(operations=operations)
if response["errors"]:
    for item in response["items"]:
        result = next(iter(item.values()))
        if result.get("error"):
            print(result.get("_id"), result["error"])
```

Bulk `index` and `update` require a following data line; `delete` uses only an action line. Inspect failed items and retry only appropriate transient failures.

## Session 2 — PostgreSQL-to-Elasticsearch Synchronization

### 6. Source of truth and inconsistency
PostgreSQL is the authoritative database; Elasticsearch is a derived search index. A PostgreSQL update does **not** automatically propagate to Elasticsearch. If indexing fails or is delayed, search results can be stale.

### 7. Synchronization approaches
- **Direct/synchronous:** Update PostgreSQL, then Elasticsearch in the request flow. Simpler, but Elasticsearch latency/failure affects the request; the two commits are not one transaction.
- **Asynchronous:** Commit the PostgreSQL change and an outbox event in **one PostgreSQL transaction**; a worker reads events and updates Elasticsearch. Supports durable retries, but search can lag behind.
- **Batch reconciliation:** Periodically compare/rebuild the search index from PostgreSQL to repair missed changes.

### 8. Eventual consistency and refresh
Two distinct delays:
1. **Sync delay:** PostgreSQL commits before the worker sends an Elasticsearch update.
2. **Refresh delay:** Elasticsearch accepts an update before it becomes visible to `_search`.

```python
client.update(index="studies_v2", id="ST001",
              doc={"status": "Completed"}, refresh="wait_for")
```

`refresh="wait_for"` waits for a refresh to make the update searchable **before the API response returns**. It generally does not force an immediate refresh. `refresh=True` requests an immediate refresh. Refresh concerns search visibility, not the same thing as write durability. `refresh="wait_for"` cannot eliminate the earlier PostgreSQL-to-worker synchronization delay.

### 9. Retry and exponential backoff
Retry transient failures such as connection problems and some throttling errors; do not blindly retry permanent mapping/data errors. Use bounded exponential backoff, ideally with jitter, and preserve events durably across worker crashes.

```python
import time
from elasticsearch import ConnectionError as ESConnectionError, ConnectionTimeout

for attempt in range(3):
    try:
        client.update(index="studies_v2", id="ST001", doc={"status": "Completed"})
        break
    except (ESConnectionError, ConnectionTimeout):
        if attempt == 2:
            raise
        time.sleep(2 ** attempt)
```

This loop alone is **not** durable; an outbox or durable queue is needed for recovery after process crashes.

### 10. Idempotency
An operation is idempotent if repeated execution has the same intended final state as one execution.
- **Safer for retries:** `doc={"participant_count": 300}` (set authoritative value).
- **Not naturally idempotent:** increment count by 10 on every execution (may double-apply after a timeout).

Idempotency does **not** prevent older events from overwriting newer state.

### 11. External versioning and ordering
For complete-document indexing, an application-supplied monotonically increasing version can reject stale events:

```python
client.index(index="studies_v2", id="ST001",
             document={"study_id": "ST001", "status": "Completed", "participant_count": 350},
             version=7, version_type="external")
```

`external` accepts a version only if **strictly greater** than the stored version. An older or equal version produces HTTP 409 / `ConflictError`. Version numbers must be generated reliably by the source system. Treat stale conflicts differently from transient failures. This is an indexing strategy for full documents, not the same as partial `client.update()`.

### 12. Deletions and tombstones
An older delayed update can recreate a physically deleted document (**stale resurrection**). Elasticsearch retains physical-deletion version history only for a limited time. A versioned soft-deletion tombstone can preserve the latest version:

```python
client.index(index="studies_v2", id="ST001",
             document={"study_id": "ST001", "is_deleted": True},
             version=8, version_type="external")
```

Normal search must exclude tombstones:

```python
query = {"bool": {"filter": [{"term": {"is_deleted": False}}]}}
```

Explicitly map `is_deleted` as `boolean`. Documents missing the field are also excluded by that filter, so plan a migration/backfill for existing indexes. Retain tombstones as long as needed to reject delayed events, or use another durable deletion-ordering strategy.

## Interview review — 10 key takeaways
1. `index()` replaces an existing document's entire source; `update(doc=...)` merges selected fields.
2. `delete()` removes one document; `indices.delete()` removes the entire index.
3. `doc_as_upsert=True` creates from `doc` if missing; a separate `upsert` body can supply fuller creation data.
4. Bulk API can partially succeed; always inspect item errors.
5. PostgreSQL remains the source of truth; Elasticsearch is derived and may lag.
6. Transactional outbox + worker supports durable asynchronous synchronization.
7. `refresh="wait_for"` waits for search visibility, not database-to-index synchronization.
8. Retry transient failures with backoff/jitter and durable pending-event tracking.
9. Idempotent state-setting protects against duplicate processing; external versioning protects against stale event order.
10. Versioned tombstones or equivalent safeguards prevent stale resurrection after deletion.

**Course status:** Day 5 Sessions 1 and 2 completed; final knowledge check 5/5.
