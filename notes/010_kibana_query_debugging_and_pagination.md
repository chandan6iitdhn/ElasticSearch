# Elasticsearch — Day 10 Notes

## Session 1 — Kibana, Query DSL, and Aggregations

### 1. Kibana and cluster inspection
Kibana Dev Tools Console lets us execute Elasticsearch REST API requests. Elasticsearch performs indexing and searching; Kibana provides the interface.

```http
GET _cluster/health
GET _cat/indices?v
GET _cat/indices/studies*?v&h=index,health,pri,rep,docs.count,store.size
```

- Observed cluster health: **yellow**, with **zero unassigned primary shards**. On a single-node cluster, replica shards cannot be assigned to the same node as their primaries.
- The earlier high-disk-watermark problem was resolved after expanding the Ubuntu root filesystem; Elasticsearch and Kibana became usable.

### 2. Search results and Query DSL
```http
GET studies_v2/_search
{
  "query": {"match_all": {}}
}
```

- `hits.total.value`: number of matching documents.
- `hits.hits`: returned documents.
- `_source`: stored document content.
- `_score`: relevance score, when calculated.

### 3. Term, match, and bool queries
```http
GET studies_v2/_search
{
  "query": {
    "bool": {
      "must": [{"match": {"title": "Diabetes"}}],
      "filter": [{"term": {"status": "Completed"}}]
    }
  }
}
```

- `match`: analyzed full-text search.
- `term`: exact indexed-term matching; confirm the field mapping.
- `must`: required matching clause, participates in relevance scoring.
- `filter`: required condition, does not contribute to relevance scoring.
- In this index, `term` on `status` returned ST001, while `status.keyword` returned no results. Inspect mappings rather than assuming a `.keyword` subfield exists.

### 4. Aggregations: SQL GROUP BY equivalent
```http
GET studies_v2/_search
{
  "size": 0,
  "aggs": {
    "studies_by_status": {
      "terms": {"field": "status"},
      "aggs": {
        "avg_participants": {
          "avg": {"field": "participant_count"}
        }
      }
    }
  }
}
```

```sql
SELECT status, COUNT(*) AS study_count,
       AVG(participant_count) AS avg_participants
FROM studies
GROUP BY status;
```

| Status | Count | Average participants |
|---|---:|---:|
| Completed | 1 | 250 |
| In Progress | 1 | 120 |

- `size: 0` suppresses individual search hits, not aggregation results.
- `terms` creates buckets, each with `doc_count`.
- Nested `avg` calculates the metric separately for each bucket.

## Session 2 — Explain, Profile, Optimization, and Pagination

### 1. Explain API and BM25
```http
GET studies_v2/_explain/ST001
{
  "query": {"match": {"title": "Diabetes"}}
}
```

- Explains whether a specific document matches and how its score was computed.
- Observed score: `0.18232156`.
- Observed breakdown: `boost = 2.2`, `idf = 0.18232156`, `tf = 0.45454544`; score ≈ boost × idf × tf.
- IDF rises when a term is rarer across indexed documents, all else equal.
- BM25 also considers term frequency and field length.

### 2. Profile API
```http
GET studies_v2/_search
{
  "profile": true,
  "query": {"match": {"title": "Diabetes"}}
}
```

- Diagnoses where Elasticsearch spends execution time; unlike `_explain`, it focuses on execution, not a specific document's relevance calculation.
- Observed internal query type: `TermQuery` for `title:diabetes`.
- Observed profiled query time: `151532 ns` (~0.152 ms).
- Observed profiled fetch time: `332919 ns` (~0.333 ms).
- `1,000,000 ns = 1 ms`.
- `breakdown` contains operations such as `create_weight`, `build_scorer`, `next_doc`, and `score`.
- Profile timings do not include all request overhead and profiling itself adds overhead.

### 3. Source filtering
```http
GET studies_v2/_search
{
  "_source": ["study_id", "title"],
  "size": 10,
  "query": {"match": {"title": "Diabetes"}}
}
```

- Returned ST001 and ST002 with only `study_id` and `title` in `_source`.
- Reduces response payload but does not alter stored documents.
- Does not necessarily avoid internally loading the original `_source`.

### 4. Offset pagination: `from` and `size`
```http
GET studies_v2/_search
{
  "from": 0,
  "size": 1,
  "sort": [{"study_id": "asc"}],
  "query": {"match_all": {}}
}
```

- `from = (page - 1) × size`.
- Default `index.max_result_window` is 10,000, limiting `from + size`.
- Large offsets can be expensive because Elasticsearch must identify and order enough preceding results.
- Use a deterministic sort for stable paging.

### 5. `search_after` cursor pagination
First page:
```http
GET studies_v2/_search
{
  "size": 1,
  "query": {"match_all": {}},
  "sort": [{"study_id": "asc"}]
}
```
Returned ST001 with `"sort": ["ST001"]`.

Second page:
```http
GET studies_v2/_search
{
  "size": 1,
  "query": {"match_all": {}},
  "sort": [{"study_id": "asc"}],
  "search_after": ["ST001"]
}
```
Returned ST002 with `"sort": ["ST002"]`.

- `search_after` takes the **last hit's sort values**, not automatically its `_id`.
- First request needs `size` and `sort`, not a cursor or `from`.
- Backend returns results and a next-page cursor; frontend sends the cursor on the next request.
- Use the same query and sort order for subsequent pages, with a unique tie-breaker.
- For consistent pagination across index changes, use a Point in Time (PIT) with `search_after`.
- Cursor-based pagination is efficient for sequential browsing but does **not** support arbitrary page-number jumps without a previously known cursor or alternative design.

### 6. Mapping API versus Search API
```http
GET studies_v2/_mapping/field/study_id
```
Confirmed `study_id` is `keyword` and supports sorting. This mapping endpoint does **not** accept a JSON body.

```http
GET studies_v2/_search
{
  "size": 1,
  "query": {"match_all": {}},
  "sort": [{"study_id": "asc"}],
  "search_after": ["ST001"]
}
```
The Search API accepts search DSL in its request body. Some Elasticsearch GET endpoints accept bodies; others do not.

### 7. Production pagination design and deep-page jumps
- Shallow numbered pages: `from` + `size` within a bounded result window.
- Next/Previous or infinite scrolling: `search_after`, optionally retaining cursor history for backwards navigation.
- Direct jump from Page 1 to Page 900 (25 results/page) would require offset `22475`, beyond the default result window.
- `search_after` cannot calculate the Page 899 cursor from the page number alone.
- Caching a cursor only helps if it has already been obtained; PIT provides consistency, **not** random access.
- Increasing `max_result_window` may increase memory/CPU use and is not a default recommendation.
- Large search applications often restrict deep navigation or encourage refining the query; Google's exact internal pagination architecture is not public.

## Interview Quick Revision
1. `_explain`: Why did a particular document match and receive its score?
2. `profile: true`: Where did Elasticsearch spend search execution time?
3. `must` versus `filter`: Scoring versus non-scoring required conditions.
4. `terms` + nested `avg`: Group-by with per-group metrics.
5. `_source` filtering: Control returned fields.
6. `from` + `size`: Offset pagination; supports shallow random page access.
7. `search_after`: Efficient sequential cursor pagination.
8. PIT: Consistent index snapshot across pages.
9. Mapping API: Verify field types and sorting support.
10. Design pagination around user experience and scale, not just page numbers.
