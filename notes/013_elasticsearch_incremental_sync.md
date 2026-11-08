# Day 13 — PostgreSQL → Elasticsearch Incremental Synchronization

## Objective
Keep an Elasticsearch search index synchronized with changes in PostgreSQL without rebuilding the entire index every run.

## 1. Source of truth and synchronization
- **PostgreSQL** is the source of truth; **Elasticsearch** is a derived search projection.
- A one-time bulk import does not automatically propagate inserts, updates, or deletes.
- **Full sync:** reprocess all rows; useful for initialization/rebuilds.
- **Incremental sync:** process changes since a recorded checkpoint; more efficient for regular runs.

## 2. Detecting changes
Add an `updated_at` column and ensure application updates maintain it (PostgreSQL does not automatically update it).

```sql
ALTER TABLE studies
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

Basic bounded incremental query:

```sql
SELECT study_id, title, status, participant_count, updated_at, is_deleted
FROM studies
WHERE updated_at > %s
  AND updated_at <= %s
ORDER BY updated_at, study_id;
```

- The lower bound `>` is exclusive; upper bound `<=` is inclusive.
- A bounded window limits which changes are processed in a run, but **does not by itself prevent missed late-committing transactions**.
- A timestamp-only checkpoint needs care with equal timestamps, transaction visibility, and concurrent workers.
- For real systems, use consistent timezone semantics (prefer `TIMESTAMPTZ` with UTC-aware datetimes).

## 3. Batch processing and Bulk API
- Use a PostgreSQL named/server-side cursor and `fetchmany(batch_size)` to avoid loading the entire table into memory.
- For 1,200 changed rows with batch size 500: **three batches (500, 500, 200)**.
- Generate Elasticsearch actions with stable document IDs:

```python
{
    "_op_type": "index",
    "_index": "studies_v3",
    "_id": study["study_id"],
    "_source": {
        "study_id": study["study_id"],
        "title": study["title"],
        "status": study["status"],
        "participant_count": study["participant_count"],
    },
}
```

- Use `elasticsearch.helpers.bulk` for batched indexing.
- Inspect both successful operation counts and per-item errors; retry eligible transient failures such as 429/503 with backoff.
- A stable `_id` makes replay of an `index` action replace an existing document instead of creating a duplicate document.

## 4. Persistent checkpoints
Store a durable position in PostgreSQL:

```sql
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    sync_name VARCHAR(100) PRIMARY KEY,
    last_sync_time TIMESTAMP NOT NULL
);

INSERT INTO sync_checkpoints (sync_name, last_sync_time)
VALUES ('studies_elasticsearch', '1970-01-01 00:00:00')
ON CONFLICT (sync_name) DO NOTHING;
```

Basic coordinator flow:
1. Read last checkpoint.
2. Establish an upper synchronization boundary.
3. Fetch and bulk-index eligible changes.
4. **Only after all required indexing operations succeed**, persist the new checkpoint.
5. On failure, keep the old checkpoint so the next run replays changes.

The exercise implementation used a wall-clock upper boundary and a bounded `updated_at` query. **This is instructional, not fully production-safe**: a transaction can assign `updated_at` before the upper boundary but commit after the query, causing its change to be missed after checkpoint advancement.

## 5. Failure recovery and at-least-once delivery
- If indexing fails halfway through, do not advance the checkpoint.
- If indexing succeeds but saving the checkpoint fails, replay records next run.
- Replays with stable `_id` avoid duplicate documents (though they may cause additional versioned writes).
- This pattern approximates **at-least-once processing**, not exactly-once end-to-end synchronization.
- Retrying an already-deleted document may produce a `404`; handle this as an acceptable already-deleted outcome where appropriate.

## 6. Handling deletions
Hard deletes remove the PostgreSQL row, so ordinary `SELECT ... WHERE updated_at ...` cannot discover them.

Soft-delete approach:

```sql
ALTER TABLE studies
ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;

UPDATE studies
SET is_deleted = TRUE,
    updated_at = CURRENT_TIMESTAMP
WHERE study_id = 'ST000005';
```

Generate an Elasticsearch `delete` action for soft-deleted records:

```python
{
    "_op_type": "delete",
    "_index": "studies_v3",
    "_id": study["study_id"],
}
```

For active records, generate the usual `index` action. Other deletion-capture approaches include deletion logs, transactional outbox, and CDC.

## 7. Production considerations
- **Commit-order correctness:** `updated_at` is not a reliable commit-order cursor. Consider PostgreSQL logical replication/CDC or a carefully designed transactional outbox.
- **Concurrency:** prevent overlapping workers from independently advancing the same checkpoint (e.g., advisory locks).
- **Ordering/ties:** define a deterministic cursor and checkpoint scheme, not just a timestamp if equal values can occur.
- **Monitoring:** track synchronization lag, duration, last success, indexed/deleted counts, and failures.
- **Reconciliation:** periodically detect mismatches between PostgreSQL and Elasticsearch and support a full rebuild.
- **Operational safety:** manage permanent failures explicitly; do not silently advance past failed records.

## 8. Hands-on results
- First checkpoint read: `1970-01-01 00:00:00`.
- First integrated run: 1,000 indexed, 0 failures, checkpoint advanced.
- Second run without PostgreSQL changes: 0 indexed, 0 failures, checkpoint advanced.
- Confirmed the behavior of exclusive/inclusive time boundaries and why late commits can be missed.

## Interview revision
**Q: Why not rebuild the Elasticsearch index on every update?** Incremental sync avoids redundant reads and indexing operations.

**Q: What happens if Elasticsearch succeeds but the checkpoint write fails?** The next run replays changes; stable document IDs prevent duplicate documents.

**Q: How do you propagate deletes?** Soft-delete flag plus timestamp and ES delete actions, or an explicit deletion-event/CDC mechanism.

**Q: Is a bounded `updated_at` query fully reliable?** No. Late-committing transactions and timestamp ties can cause missed changes; use a commit-aware change stream or a stronger design.

**Q: What is the source of truth?** PostgreSQL; Elasticsearch is a rebuildable derived index.
