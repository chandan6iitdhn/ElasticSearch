# Day 14 — Elasticsearch Performance Optimization and Troubleshooting

## Session 1 — Performance fundamentals

### 1. Query context vs filter context
- `bool.must` with `match` performs relevance-based full-text matching and contributes to scores.
- `bool.filter` with `term` restricts results without scoring and can benefit from caching.
- Example: `must: [{match: {title: 'cancer'}}]`, `filter: [{term: {status: 'Completed'}}]`.

### 2. Profile API
- Set `profile=True` in `client.search(...)` to inspect execution internals by shard.
- Read `response['profile']['shards']` for query breakdowns.
- `response['took']` measures Elasticsearch server-side search processing, not total Flask latency.
- Profiling adds overhead; use it diagnostically, not as a normal production setting.

### 3. Search optimizations
- Limit returned documents with `size` and returned fields with `_source` filtering.
- `track_total_hits=False` can reduce work when exact total counts are unnecessary.
- Avoid deep `from`/`size` pagination; use `search_after` with point-in-time (PIT) for consistent deep pagination.
- `_source` filtering primarily reduces returned payload; it does not necessarily avoid reading stored `_source`.

### 4. Bulk indexing
- Use `elasticsearch.helpers.bulk` with appropriate `chunk_size` (e.g. 500 as a starting point).
- Bulk operations reduce per-document request overhead; benchmark chunk sizes under comparable conditions.
- Test results on 1,000 stable IDs: chunk 100 = 0.870s, 500 = 0.054s, 1000 = 0.044s. These runs were not controlled benchmarks; the first likely included warm-up/index-creation overhead.
- Consider `refresh_interval` tuning for ingestion workloads, and restore desired settings afterward.

### 5. Cluster and node monitoring
- `client.cluster.health()` provides status, node count, active and unassigned shard counts.
- `client.nodes.stats(metric='jvm,process')` provides heap usage and process CPU.
- `_cat/indices` displays index health and counts; `_nodes/hot_threads` helps inspect busy threads.
- Green: all primary and replica shards assigned. Yellow: primaries assigned but some replicas unassigned. Red: at least one primary shard unassigned.
- In a single-node cluster, a replica cannot be allocated to the same node as its primary; five unassigned replicas can therefore produce Yellow health without indicating failed searches.
- `docs.deleted` in `_cat/indices` can represent superseded Lucene documents from updates, not application-level deletions.

## Session 2 — Practical troubleshooting

### 1. Measure the right latency
```python
import time
start = time.perf_counter()
response = client.search(index='studies_v3', query={'match': {'title': 'cancer'}})
client_ms = (time.perf_counter() - start) * 1000
print(response['took'], client_ms)
```
- Use `time.perf_counter()` for elapsed durations: it is high-resolution and monotonic.
- `datetime.now()` is for timestamps; wall-clock adjustments can distort elapsed-time measurements.
- Distinguish Flask end-to-end latency, Python Elasticsearch client elapsed time, and Elasticsearch `took`.
- Measurements: first call 25.03 ms client time, subsequent calls 14.79 and 14.08 ms; Elasticsearch `took` 1, 0, 0 ms. A reported `0 ms` is a resolution/rounding effect, not proof of zero work.

### 2. Search slow logs
```python
client.indices.put_settings(index='studies_v3', settings={
    'index.search.slowlog.threshold.query.warn': '100ms'
})
```
- Logs shard-level query phases exceeding the threshold at WARN level.
- Does not reject, optimize, or retry queries.
- Depending on container logging configuration, inspect Docker logs or Elasticsearch log files.
- The practical configuration was verified: `100ms`.

### 3. Expensive queries and patterns
- `match` is generally appropriate for analyzed, word-based full-text search.
- `wildcard` is for indexed-term character patterns (`*` = zero or more characters; `?` = one character).
- Leading wildcard patterns like `*cancer*` may be expensive. For simple beginnings, consider `prefix`; for frequent substring/autocomplete needs, consider appropriate mappings (`ngram`, `edge_ngram`, or specialized fields).
- `match` and `wildcard` are not semantically equivalent, even if they happen to return the same number of results.
- Test results: `match` ES took 0ms / Python 85.49ms; wildcard ES took 4ms / Python 5.58ms; both returned 200. The first client call likely incurred initialization overhead. Warm up, alternate order, repeat, and compare medians before drawing conclusions.

### 4. Resource and shard bottlenecks
- Monitor sustained heap pressure, garbage collection, CPU, hot threads, indexing load, and shard distribution.
- A single heap/CPU reading is not enough to diagnose a bottleneck.
- `client.nodes.stats(metric='jvm,process,indices')` exposes cumulative `indices.search.query_total` and `query_time_in_millis`.
- Observed: 1,086,481 query-phase operations, 2,215,259 ms cumulative query time, ~2.04 ms per recorded shard-level operation. This is a lifetime average, not recent latency.
- High shard counts can add overhead; avoid changing shard counts without workload evidence.

### 5. End-to-end performance diagnosis
1. Measure complete Flask request time.
2. Measure Python client call with `perf_counter()`.
3. Compare with Elasticsearch `response['took']`.
4. If ES processing is slow, investigate query profile, slow logs, CPU, heap/GC, indexing, shards.
5. If ES processing is fast but the API is slow, investigate Flask logic, middleware, database calls, serialization, network, TLS, and retries.
6. Change one thing at a time and measure again under comparable conditions.

Final practical snapshot: ES `took` 0 ms, Python elapsed 15.21 ms, Yellow cluster, five unassigned replicas, JVM heap 64%, process CPU 0%. No obvious bottleneck in this snapshot; trends and workload tests are needed for stronger conclusions.

## Interview revision checklist
- Explain query vs filter context and the role of relevance scoring.
- Explain `took` vs client elapsed vs full API latency.
- Know when to use Profile API and search slow logs.
- Explain `match`, `prefix`, and `wildcard`, including leading-wildcard cost.
- Explain why a single-node cluster can be Yellow.
- Describe diagnosing heap, GC, CPU, shards, and query bottlenecks.
- Explain fair benchmarking: warm-up, repeated runs, order variation, medians.
