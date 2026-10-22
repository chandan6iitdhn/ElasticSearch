# Elasticsearch — Day 7 Notes

## Session 1: Aggregation Fundamentals

### 1. What are aggregations?
Aggregations summarize documents matching an Elasticsearch query (similar to SQL `GROUP BY`, `AVG`, `SUM`, etc.). They can be used for analytics and dashboards.

```python
response = client.search(
    index="studies_v2",
    size=0,
    aggs={"by_status": {"terms": {"field": "status"}}}
)
```

- `size=0` suppresses individual search hits; it **does not** restrict which documents contribute to aggregations.
- Top-level `size` defaults to 10 hits; it is separate from `terms.size` (default 10 buckets).
- Aggregations are returned under `response["aggregations"]`.

### 2. Bucket aggregations: `terms`
A **bucket** is a logical group of documents meeting a criterion. A `terms` aggregation creates one bucket per distinct field value, with a `key` and `doc_count`.

```python
aggs={
    "by_status": {
        "terms": {"field": "status", "size": 10}
    }
}
```

Example response fragment:

```json
{"aggregations": {"by_status": {"buckets": [
  {"key": "Completed", "doc_count": 3},
  {"key": "In Progress", "doc_count": 2}
]}}}
```

- Aggregate on a `keyword` field such as `status`, not an analyzed `text` field.
- Bucket ordering can be set with `"order": {"_count": "desc"}` or `"order": {"_key": "asc"}`.
- Distributed `terms` aggregation counts may be approximate in some cases (especially for less-frequent terms across shards).

### 3. Metric aggregations
Common predefined metric aggregation types:

| Type | Meaning | Result |
|---|---|---|
| `avg` | Average numeric field | `value` |
| `sum` | Sum numeric field | `value` |
| `min` | Minimum numeric field | `value` |
| `max` | Maximum numeric field | `value` |

```python
response = client.search(
    index="studies_v2",
    size=0,
    aggs={
        "avg_participants": {"avg": {"field": "participant_count"}},
        "total_participants": {"sum": {"field": "participant_count"}},
        "min_participants": {"min": {"field": "participant_count"}},
        "max_participants": {"max": {"field": "participant_count"}}
    }
)

average = response["aggregations"]["avg_participants"]["value"]
```

`avg`, `min`, and `max` return `null`/Python `None` when there are no values; `sum` returns 0.

### 4. Queries and aggregation scope
A top-level query limits the documents considered by aggregations:

```python
response = client.search(
    index="studies_v2",
    size=0,
    query={"match": {"title": "diabetes"}},
    aggs={"by_status": {"terms": {"field": "status"}}}
)
```

A `match` query cannot be inserted directly as an aggregation type. To filter **within** aggregations, use a `filter` aggregation:

```python
aggs={
    "diabetes_studies": {
        "filter": {"match": {"title": "diabetes"}},
        "aggs": {
            "avg_participants": {"avg": {"field": "participant_count"}}
        }
    }
}
```

## Session 2: Counting, Nested Aggregations, Python

### 5. `value_count` versus `cardinality`

```python
aggs={
    "study_id_values": {"value_count": {"field": "study_id"}},
    "unique_study_ids": {"cardinality": {"field": "study_id"}}
}
```

- `value_count` counts values present in a field, not inherently the number of documents. It equals document count only if every document has exactly one value in that field.
- `cardinality` estimates the number of distinct values using HyperLogLog++; results can be approximate. `precision_threshold` tunes accuracy/memory (maximum supported 40,000).
- `value_count`, `cardinality`, `terms`, `avg`, etc. are predefined Elasticsearch aggregation **types**, not Python keywords. Aggregation names like `study_id_values` are user-defined.
- To count documents in a `terms` bucket, use `bucket["doc_count"]` directly.

### 6. Nested bucket + metric aggregation
Equivalent to SQL `GROUP BY status` with `AVG(participant_count)`:

```python
response = client.search(
    index="studies_v2",
    size=0,
    aggs={
        "by_status": {
            "terms": {"field": "status"},
            "aggs": {
                "avg_participants": {"avg": {"field": "participant_count"}}
            }
        }
    }
)

for bucket in response["aggregations"]["by_status"]["buckets"]:
    print(bucket["key"], bucket["doc_count"],
          bucket["avg_participants"]["value"])
```

Response hierarchy:

```text
response
└── aggregations
    └── by_status
        └── buckets (list)
            ├── key
            ├── doc_count
            └── avg_participants
                └── value
```

### 7. `term` versus `bool.filter`
Both can restrict matching documents for aggregations:

```python
query={"term": {"status": "Completed"}}
```

```python
query={"bool": {"filter": [{"term": {"status": "Completed"}}]}}
```

- `term` is an exact-value query, suitable for `keyword` fields.
- A direct `term` is in query context (can contribute to `_score`).
- `bool.filter` is filter context (no relevance scoring), useful for combining exact/range constraints and expressing analytics intent.
- With `size=0` and only aggregations, relevance scores are not used in the output.

### 8. Hands-on: analytics for one status

```python
def get_study_analytics(client, status):
    response = client.search(
        index="studies_v2",
        size=0,
        query={"bool": {"filter": [{"term": {"status": status}}]}},
        aggs={
            "total_studies": {"value_count": {"field": "study_id"}},
            "avg_participants": {"avg": {"field": "participant_count"}},
            "total_participants": {"sum": {"field": "participant_count"}},
            "min_participants": {"min": {"field": "participant_count"}},
            "max_participants": {"max": {"field": "participant_count"}}
        }
    )
    a = response["aggregations"]
    return {name: a[name]["value"] for name in (
        "total_studies", "avg_participants", "total_participants",
        "min_participants", "max_participants"
    )}
```

Assumption: `study_id` exists exactly once on every document. If not, `value_count` is not a reliable document count. An alternative is `hits.total.value` with `track_total_hits=True`.

### 9. Final hands-on: group matching titles by status

```python
def get_study_status_summary(client, query_text):
    response = client.search(
        index="studies_v2",
        size=0,
        query={"match": {"title": query_text}},
        aggs={
            "by_status": {
                "terms": {"field": "status"},
                "aggs": {
                    "avg_participants": {
                        "avg": {"field": "participant_count"}
                    }
                }
            }
        }
    )

    buckets = response["aggregations"]["by_status"]["buckets"]
    results = []
    for bucket in buckets:
        results.append({
            "status": bucket["key"],
            "study_count": bucket["doc_count"],
            "avg_participants": bucket["avg_participants"]["value"]
        })
    return results
```

For the **illustrative dataset** (not guaranteed to match your actual index):

| Status | Diabetes studies | Average participants |
|---|---:|---:|
| Completed | 2 | 275 |
| In Progress | 1 | 120 |

### 10. Interview revision / common mistakes

1. `size=0` hides hits, not aggregation results or their underlying documents.
2. `terms.size` limits number of returned **buckets**, not hits.
3. `terms` creates groups; `avg`/`sum`/`min`/`max` compute metrics.
4. Use `status` as a `keyword` field for `terms` and exact `term` queries.
5. Always include an aggregation **type**: `"avg_participants": {"avg": {"field": "participant_count"}}`.
6. Response key is `aggregations` (plural).
7. Metric values live under `["value"]`; bucket counts live under `["doc_count"]`.
8. `value_count` counts field values; `cardinality` estimates unique values.
9. `bool.filter` avoids relevance scoring for structured constraints.
10. A nested metric computes separately **within each bucket**.

**Day 7 status: both sessions completed.**
