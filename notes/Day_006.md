# Elasticsearch — Day 6 Consolidated Notes

**Status:** Session 1 and Session 2 completed  
**Project:** Flask + PostgreSQL + Elasticsearch Study Search API  
**Index:** `studies_v2`

## Session 1 — Elasticsearch Query DSL

### 1. Query Context vs Filter Context

- **Query context:** Determines whether a document matches and calculates relevance (`_score`).
- **Filter context:** Determines whether a document matches without contributing to relevance scoring.
- `must` and `should` clauses operate in query context; `filter` and `must_not` operate in filter context.
- `match` and `term` are query types; `must` and `filter` are clauses within a `bool` query. A standalone `match` query also scores results.

```python
query = {
    "bool": {
        "must": [{"match": {"title": "diabetes"}}],
        "filter": [{"term": {"status": "Completed"}}]
    }
}
```

**If `must` and `filter` are swapped:** Both conditions are still required, but scoring changes: `term` on `status` contributes a score, while `match` on `title` no longer contributes. `term` queries can score when executed in query context.

### 2. Boolean Query Clauses

| Clause | Meaning | Contributes to score? |
|---|---|---|
| `must` | Required match | Yes |
| `filter` | Required match | No |
| `should` | Optional boost or required depending on `minimum_should_match` | Yes when matched |
| `must_not` | Excludes matching documents | No |

**`should` default:** If the `bool` query contains a `must` or `filter`, `minimum_should_match` defaults to `0`; otherwise, when there are `should` clauses, it defaults to `1`. Set `minimum_should_match` explicitly to require optional clauses. This applies to each `bool` query independently.

```python
query = {
    "bool": {
        "must": [{"match": {"title": "diabetes"}}],
        "filter": [{"term": {"status": "Completed"}}],
        "should": [{"match": {"title": "treatment"}}],
        "must_not": [{"term": {"is_deleted": True}}]
    }
}
```

Here `treatment` is optional and can increase relevance. Documents with `is_deleted=True` are excluded; documents missing that field are not automatically excluded.

### 3. `match` vs `match_phrase`

- `match` analyzes the query and matches terms; its default operator for multiple terms is `OR`.
- `match_phrase` analyzes the query and requires matching token positions in order; default `slop=0`.
- `slop` permits positional movement; it is not universally identical to counting intervening words.

```python
{"match": {"title": "diabetes treatment"}}

{"match_phrase": {"title": "diabetes treatment"}}

{"match_phrase": {
    "title": {"query": "diabetes treatment", "slop": 1}
}}
```

With a standard analyzer, `Diabetes Advanced Treatment Study` does not match the phrase at `slop=0`, but can match at `slop=1`.

### 4. `multi_match` and Field Boosting

Search the same text across multiple fields:

```python
query = {
    "multi_match": {
        "query": "diabetes treatment",
        "fields": ["title^3", "description"]
    }
}
```

- `title^3` boosts matches in `title` relative to `description`.
- Boosting is not a guarantee of ranking: BM25 and other scoring factors still matter.
- `fields` must be **inside** the `multi_match` object.
- Ensure `description` exists and is mapped as searchable `text` for meaningful results.

### 5. Combined Query Example

```python
response = client.search(
    index="studies_v2",
    query={
        "bool": {
            "must": [{
                "multi_match": {
                    "query": "diabetes",
                    "fields": ["title^3", "description"]
                }
            }],
            "filter": [{"term": {"status": "Completed"}}],
            "must_not": [{"term": {"is_deleted": True}}],
            "should": [{"match": {"title": "treatment"}}]
        }
    }
)
```

## Session 2 — Pagination, Sorting and Source Filtering

### 1. Pagination with `from_` and `size`

- Elasticsearch defaults: `from=0`, `size=10`.
- Python client uses `from_` because `from` is a Python keyword.
- For one-based page numbering: `offset = (page - 1) * page_size`.

```python
page = 4
page_size = 25
offset = (page - 1) * page_size  # 75

response = client.search(
    index="studies_v2",
    query={"match": {"title": "diabetes"}},
    from_=offset,
    size=page_size
)
```

Page 4 returns up to 25 results after skipping 75. By default, `from + size` cannot exceed the index's `index.max_result_window` (usually 10,000). For deep pagination, consider `search_after`, typically with a Point in Time (PIT). Deterministic sorting matters for pagination.

### 2. Sorting

- Full-text searches normally sort by `_score` descending when no explicit sort is supplied.
- Explicit field sorting replaces relevance-first ordering unless `_score` is included.
- Sort conditions are evaluated left to right; later fields break ties.

```python
sort = [
    {"participant_count": {"order": "desc"}},
    {"study_id": {"order": "asc"}}
]
```

`integer` and `keyword` fields support sorting. An analyzed `text` field does **not** normally support sorting directly. Define a `keyword` multi-field to sort alphabetically:

```python
"title": {
    "type": "text",
    "fields": {"keyword": {"type": "keyword"}}
}
```

Then sort by `title.keyword`. If adding the subfield to an existing mapping, existing documents must be reprocessed/reindexed to populate it.

### 3. `_source` Filtering

`_source` holds the original JSON document (when enabled). Source filtering controls which fields are returned, **not** which fields remain indexed or stored.

```python
response = client.search(
    index="studies_v2",
    query={"match_all": {}},
    source=["study_id", "title", "status"]
)
```

Equivalent inclusion-only style:

```python
response = client.search(
    index="studies_v2",
    query={"match_all": {}},
    source_includes=["study_id", "title", "status"]
)
```

Exclusion can also be combined with inclusion:

```python
response = client.search(
    index="studies_v2",
    query={"match_all": {}},
    source_includes=["study_id", "title", "status"],
    source_excludes=["status"]
)
# Returned _source includes study_id and title, not status.
```

`source=[...]` can also be combined with `source_excludes=[...]`. Excluded fields are removed from the response selection. Filtering reduces payload size, but Elasticsearch may still need to read the stored `_source`. It is not an authorization/security boundary.

### 4. Final Hands-on Function

```python
def search_studies(client, query_text, status, page=1, page_size=10):
    if page < 1:
        raise ValueError("page must be >= 1")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    offset = (page - 1) * page_size
    if offset + page_size > 10000:
        raise ValueError("Requested page exceeds the default result window")

    es_query = {
        "bool": {
            "must": [{"match": {"title": query_text}}],
            "filter": [{"term": {"status": status}}]
        }
    }

    response = client.search(
        index="studies_v2",
        query=es_query,
        from_=offset,
        size=page_size,
        sort=[
            {"participant_count": {"order": "desc"}},
            {"study_id": {"order": "asc"}}
        ],
        source=["study_id", "title", "status"]
    )

    return [hit["_source"] for hit in response["hits"]["hits"]]


studies = search_studies(
    client,
    query_text="diabetes",
    status="Completed",
    page=2,
    page_size=5
)
print(studies)
```

**Assumptions:** `study_id` is a unique sortable `keyword`, `participant_count` is an `integer`, and `status` is a `keyword`, as in the current mapping. The 10,000 check assumes the default result-window configuration. Sorting by participant count means results are **not primarily ordered by relevance**. A robust API would also handle ES errors and return pagination metadata such as total hits if needed.

## Mistakes Corrected During Practice

1. `"term": {"status": "status"}` filters for the literal text `status`; use `"term": {"status": status}` to reference the Python argument.
2. Search hits wrap document fields in `_source`: use `hit["_source"]`, not `hit["title"]`.
3. In `multi_match`, put `fields` inside the `multi_match` object.
4. `source`/`source_includes` only change response fields, not the stored document.
5. `match` does not require a surrounding `bool.must` to score results.

## Interview Quick Revision

**Q: Is scoring controlled by `match` or `must`?**  
Both query type and context matter. A `match` can score standalone or inside `must`; inside `filter`, its score does not contribute.

**Q: What is the difference between `must` and `filter`?**  
Both require a match; `must` contributes to scoring, `filter` does not.

**Q: Is `should` always optional?**  
No. The default `minimum_should_match` depends on whether the same `bool` query has `must` or `filter` clauses, and can be explicitly set.

**Q: How does `match_phrase` differ from `match`?**  
Phrase matching uses token positions and order, while `match` typically matches analyzed terms without requiring adjacency.

**Q: What does `title^3` mean?**  
A relative boost for the title field, not a guaranteed 3:1 final score ratio.

**Q: Why use `from_`?**  
`from` is reserved in Python; the client exposes the Elasticsearch `from` option as `from_`.

**Q: Can you sort directly on `text`?**  
Not normally; use a sortable `keyword` subfield.

**Q: Does `_source` filtering delete excluded fields?**  
No, it only controls response contents.

**Q: Why is `study_id` useful as a secondary sort?**  
It can break ties and give a deterministic order, assuming unique values.

## Day 6 Completion Checklist

- [x] Query vs filter context
- [x] `must`, `filter`, `should`, `must_not`
- [x] `minimum_should_match`
- [x] `match` vs `match_phrase`, `slop`
- [x] `multi_match` and field boosts
- [x] `from_` / `size` pagination
- [x] Relevance and field sorting
- [x] `_source` selection and exclusions
- [x] Final Python search function

**Next:** Day 7 — continue the Study Search API learning plan.
