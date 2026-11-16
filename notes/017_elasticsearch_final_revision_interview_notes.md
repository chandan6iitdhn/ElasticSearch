# Day 17 — Elasticsearch Final Revision & Interview Notes

**Course:** Elasticsearch with Python, Flask, PostgreSQL and Docker  
**Session:** Compressed final revision (45 minutes)  
**Status:** Completed — Day 17 of 17  
**Final assessment:** 5/5 (100%)

## 1. Core Elasticsearch concepts

| Concept | Key point |
|---|---|
| Inverted index | Maps analyzed terms to documents containing them for efficient full-text search. |
| Mapping | Declares field types (`text`, `keyword`, `integer`, `date`, etc.). |
| Analyzer | Applies character filters, tokenization, and token filters during text analysis. |
| Primary shard | Partition of an Elasticsearch index. |
| Replica shard | Copy of a primary shard; can serve reads and support failover. |
| Query context | Determines matching documents and may calculate relevance (`_score`). |
| Filter context | Matches documents without relevance scoring for the filter clause. |

### Typical mapping

```json
{
  "properties": {
    "study_id": {"type": "keyword"},
    "title": {"type": "text"},
    "status": {"type": "keyword"},
    "participant_count": {"type": "integer"}
  }
}
```

Use `text` for analyzed full-text search; `keyword` for exact values, sorting and aggregations. A single-node cluster with all primaries assigned but unassigned replicas is typically **yellow**, not red.

### Query with relevance and filtering

```json
GET studies_v3/_search
{
  "query": {
    "bool": {
      "must": [{"match": {"title": "diabetes treatment"}}],
      "filter": [{"term": {"status": "Active"}}]
    }
  },
  "size": 10
}
```

## 2. Typo tolerance and boosting

Use fuzzy matching to tolerate misspellings:

```json
GET studies_v3/_search
{
  "query": {
    "match": {
      "title": {
        "query": "Diabtes Treatment",
        "fuzziness": "AUTO"
      }
    }
  }
}
```

Default `AUTO` edit distances: 0 for 0–2-character terms, 1 for 3–5, and 2 for longer terms. Edit distance is applied to analyzed terms, not necessarily to an entire phrase as one unit.

Combine exact phrase boosting with typo tolerance:

```json
GET studies_v3/_search
{
  "query": {
    "bool": {
      "should": [
        {"match_phrase": {"title": {"query": "Diabetes Treatment", "boost": 5}}},
        {"match": {"title": {"query": "Diabetes Treatment", "fuzziness": "AUTO"}}}
      ],
      "minimum_should_match": 1
    }
  }
}
```

In `multi_match`, `title^5` is field-boost syntax:

```json
{
  "multi_match": {
    "query": "diabetes",
    "fields": ["title^5", "description^2"],
    "fuzziness": "AUTO"
  }
}
```

**Note:** `description` was not part of the demonstrated `studies_v3` mapping; add and populate it before using this example in the project. Boosting changes relative relevance weight; it does not guarantee a particular final score or rank.

## 3. Slow search API: find the bottleneck first

Illustrative measurements:

| Metric | Time |
|---|---:|
| Total Flask request | 3,000 ms |
| Python Elasticsearch client call | 2,850 ms |
| Elasticsearch response `took` | 40 ms |

The client call has ~2,810 ms beyond Elasticsearch's reported search-processing time. Investigate network, TLS/connection setup, connection pooling, retries, timeouts and client overhead before rewriting the query.

```python
from time import perf_counter

start = perf_counter()
result = client.search(index="studies_v3", body=search_body)
client_ms = (perf_counter() - start) * 1000
print("Client call (ms):", round(client_ms, 2))
print("ES took (ms):", result["took"])
```

Useful diagnostics:

```http
GET _cluster/health
GET _nodes/stats
GET _cat/shards/studies_v3?v
GET studies_v3/_search
```

The Search Profile API (`"profile": true`) reveals query execution detail but introduces overhead and does not measure the whole API request.

## 4. Production troubleshooting: PostgreSQL vs Elasticsearch counts

Scenario: PostgreSQL has 10,000 rows, Elasticsearch has 9,850 documents. **Do not assume 150 documents are missing.** Soft-deleted records should remain in PostgreSQL but be absent from search.

```sql
SELECT
    COUNT(*) AS total_studies,
    COUNT(*) FILTER (WHERE is_deleted = FALSE) AS active_studies,
    COUNT(*) FILTER (WHERE is_deleted = TRUE) AS deleted_studies
FROM studies;
```

If 9,850 studies are active and 150 soft-deleted, the index count may be correct. Otherwise:

1. Verify the intended index or alias and compare active study IDs, not just totals.
2. Inspect bulk-operation errors, logs, and the sync checkpoint.
3. Identify missing or stale documents and reindex safely using `_id = study_id`.
4. Verify document IDs and field values; counts alone are insufficient.
5. Repair the root cause and schedule periodic reconciliation.

Checkpoint inspection:

```sql
SELECT sync_name, last_sync_time
FROM sync_checkpoints
WHERE sync_name = 'studies_elasticsearch';
```

A record whose `updated_at` precedes an already-advanced checkpoint may not be picked up by a normal incremental run. Re-running blindly or advancing the checkpoint does not repair missed data.

**Definitions:** Retry = repeat a failed operation; recovery = restore after failure; reconciliation = compare authoritative source and search projection; idempotency = safe repeated application without unintended additional effects.

## 5. Senior system design: 10 million records

Illustrative requirements: 10M studies, 1,000 peak queries/sec, target search latency under 200 ms, approximately five-second freshness. These are goals requiring workload testing, not guaranteed by a particular architecture.

```text
Clients
  |
Python/Flask API -----> Elasticsearch cluster (search)
  |
PostgreSQL (authoritative writes)
  |
Transactional outbox / CDC
  |
Durable event consumer / sync worker -----> Elasticsearch cluster
```

- **PostgreSQL** is the transactional source of truth.
- **Elasticsearch** is a derived search index.
- **Transactional outbox or CDC** captures committed changes reliably.
- **Workers** apply inserts, updates and deletes using stable document IDs.
- **Durable retry, backoff, dead-letter handling and monitoring** address temporary and persistent failures.
- **Ordering/version checks** prevent stale events overwriting newer state.
- **Reconciliation** detects and repairs divergence.
- **Refresh interval** affects when successful indexing becomes visible to searches.

Do not directly assume a PostgreSQL commit and an Elasticsearch index request form one atomic transaction; they do not. An outbox records an event within the PostgreSQL transaction, allowing eventual delivery even if Elasticsearch is temporarily unavailable.

Scale based on measured document sizes, search/indexing workloads, shard sizes, hardware, and failure requirements. Replicas and multiple nodes support availability. For deep pagination, consider point-in-time (PIT) with `search_after`. Use versioned indices and aliases for controlled mapping changes.

### Production safeguards still to implement

- Persist Elasticsearch data on durable volumes and plan snapshots/backups. The previously inspected `es01` container had no mounted volume: **do not delete or recreate it before a safe data migration**.
- Prevent overlapping sync jobs and checkpoint regression.
- Avoid missing late-committing database transactions: consider CDC/outbox rather than timestamp-only capture.
- Handle an already-absent document's delete `404` as an acceptable outcome only for an expected delete operation.
- Ensure full reindexing respects `is_deleted`, so deleted documents are not accidentally resurrected.
- Use structured logging, alerts, integration tests, and index reconciliation.

## 6. Final interview assessment — Answers and rationale

| # | Topic | User answer | Result | Core rationale |
|---|---|---|---|---|
| 1 | Search architecture | B | Correct | PostgreSQL source of truth; Elasticsearch for search. |
| 2 | Shard failover | C | Correct | Available in-sync replica can be promoted to primary. |
| 3 | Incompatible mapping change | D | Correct | Build versioned index, validate, then safely switch alias. |
| 4 | Reliable sync during ES outage | A | Correct | Outbox/CDC with durable event handling and retries. |
| 5 | Slow API, fast ES `took` | C | Correct | Investigate network, connection setup, retries and client overhead. |

**Score: 5/5 (100%).** This demonstrates understanding of the assessed architectural and troubleshooting concepts, not a guarantee of production proficiency across every Elasticsearch workload.

## 7. Quick interview responses

**Why Elasticsearch rather than only PostgreSQL?** For applications needing flexible analyzed full-text search, relevance ranking, typo tolerance, and scalable search; keep PostgreSQL for transactional integrity.

**What does `^` mean?** In field lists such as `multi_match.fields`, `title^5` boosts title matches relative to other fields; it does not guarantee exact final score multiplication.

**How do you handle typos?** Use `match` with `fuzziness: "AUTO"`; boost exact or phrase matches to prioritize stronger matches.

**What if Elasticsearch is down after PostgreSQL commits?** Persist change events using a transactional outbox or CDC, retry delivery, preserve ordering/version correctness, and reconcile.

**What if a primary shard node fails?** An available in-sync replica can be promoted to primary; without an available shard copy, availability may be affected.

**How do you change an incompatible mapping?** Create a new index with the desired mapping, populate and validate it, catch up concurrent changes, and atomically switch an alias.

**How do you debug a slow search endpoint?** Measure end-to-end API time, client-call duration and ES `took`, then investigate the slowest segment using logs, metrics and profiling.

## 8. Course completion and next steps

**17/17 days complete.** The course included inverted indexing, mappings, analyzers, Query DSL, relevance, fuzziness, shards/replicas, Docker-based Elasticsearch, Flask/Python search APIs, PostgreSQL bulk and incremental synchronization, soft deletes, checkpoints, failure recovery and system design.

Recommended next learning priority: **8-day Strawberry GraphQL (Python)** course for API development, followed by the dedicated Docker course. Production hardening of the Elasticsearch project can be continued separately.
