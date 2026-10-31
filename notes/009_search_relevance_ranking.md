# Elasticsearch — Day 9: Search Relevance and Ranking

## Session 1 — Relevance and BM25

### `_score` and BM25
- Full-text queries (`match`, `multi_match`, `match_phrase`) can produce relevance scores (`_score`). Higher generally means a better match *for that query*.
- **Term frequency (TF):** repeated occurrences can increase score, with diminishing returns.
- **Inverse document frequency (IDF):** rarer terms generally carry more weight.
- **Field-length normalization:** shorter fields can score higher, all else equal.
- BM25 default parameters commonly include `k1=1.2` (TF saturation) and `b=0.75` (length normalization).
- Scores depend on index statistics, query, and analyzer; do not treat them as absolute probabilities.

### Boolean query scoring
- `must`: required and contributes to score when it contains scoring queries.
- `should`: can contribute additional score; `minimum_should_match` controls required matches.
- `filter`: required but does **not** contribute to score.
- `must_not`: excludes matches and does not contribute to score.
- A direct top-level `match` is sufficient for a single search condition; `bool` combines clauses.

```python
response = client.search(
    index="studies_v2",
    query={
        "bool": {
            "must": [{"match": {"title": "diabetes"}}],
            "should": [{"match": {"title": "treatment"}}],
            "filter": [{"term": {"status": "Completed"}}],
        }
    },
)
```

### Boosting
- Boost a field with `"title^3"` inside `multi_match.fields`.
- Boost a clause with `"boost": 3` inside its query parameters.
- A boost factor of 3 does not guarantee a threefold final score.

```python
response = client.search(
    index="studies_v2",
    query={"multi_match": {
        "query": "diabetes treatment",
        "fields": ["title^3", "description"],
    }},
)
```

**Mapping note:** `description` must be appropriately mapped/indexed and populated to contribute matches. The original practice index may not have this field.

### Explain relevance

```python
response = client.search(
    index="studies_v2",
    query={"match": {"title": "diabetes"}},
    explain=True,
)
for hit in response["hits"]["hits"]:
    print(hit["_score"], hit.get("_explanation"))
```

Use `explain=True` for debugging, not routinely in production because of overhead.

### Session 1 implementation

```python
def search_studies_by_relevance(client, search_text, status=None):
    query = {
        "bool": {
            "must": [{"multi_match": {
                "query": search_text,
                "fields": ["title^3", "description"],
            }}]
        }
    }
    if status is not None:
        query["bool"]["filter"] = [{"term": {"status": status}}]

    response = client.search(
        index="studies_v2", size=10, explain=True, query=query
    )
    return [
        {
            "study_id": hit["_source"]["study_id"],
            "title": hit["_source"]["title"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]
```

**Important:** Elasticsearch hit `_id` is not necessarily the same as the application's `_source.study_id`.

## Session 2 — Advanced Relevance Tuning

### Phrase matching
- `match` is analyzed and, by default, can match any of the searched terms.
- `match_phrase` requires terms in order and adjacent positions by default (`slop=0`).
- Combine broad and phrase matches in `bool.should`; boost the phrase match to reward precision.

### Fuzzy matching
- `match` with `"fuzziness": "AUTO"` tolerates limited spelling errors using edit distance.
- Default AUTO thresholds: 1–2 characters → 0 edits; 3–5 → 1; 6+ → 2.
- Fuzziness can add query cost and false positives, especially for technical/medical terms.

```python
{"match": {"title": {"query": "diabtes", "fuzziness": "AUTO"}}}
```

### Prefix search and autocomplete
- `prefix` matches indexed terms beginning with a prefix; it is a term-level query, not analyzed like `match`.
- `match_phrase_prefix` analyzes text and treats the final token as a prefix while preserving phrase order.
- For scalable autocomplete, evaluate `search_as_you_type` or edge n-grams.

```python
{"match_phrase_prefix": {"title": {"query": "diabetes tre"}}}
```

### Combining scoring clauses
- `bool.should` sums scoring contributions from matching clauses; multiple matches can improve ranking.
- `minimum_should_match=1` explicitly requires at least one matching clause, even if filters are added later.
- Exact phrase (boost 5), all terms (boost 2), fuzzy match (default boost) balances precision and recall.

### Session 2 implementation — completed exercise

```python
def advanced_study_search(client, search_text, status=None):
    query = {
        "bool": {
            "should": [
                {"match_phrase": {"title": {
                    "query": search_text, "boost": 5
                }}},
                {"match": {"title": {
                    "query": search_text,
                    "operator": "and",
                    "boost": 2,
                }}},
                {"match": {"title": {
                    "query": search_text,
                    "fuzziness": "AUTO",
                }}},
            ],
            "minimum_should_match": 1,
        }
    }

    if status is not None:
        query["bool"]["filter"] = [{"term": {"status": status}}]

    response = client.search(
        index="studies_v2", size=10, explain=True, query=query
    )
    return [
        {
            "study_id": hit["_source"]["study_id"],
            "title": hit["_source"]["title"],
            "_score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]

# Example calls
# advanced_study_search(client, "diabetes treatment", "Completed")
# advanced_study_search(client, "diabtes")
```

### Query-body syntax reminder

```python
# Both valid:
client.search(index="studies_v2", query={"match": {"title": "diabetes"}})
client.search(index="studies_v2", body={"query": {"match": {"title": "diabetes"}}})

# Invalid: nested 'query' within the query= argument
# client.search(query={"query": {"match": {"title": "diabetes"}}})
```

## Interview quick revision
1. What influences BM25 scores? TF, IDF, field length; boost and analyzer behavior also matter.
2. Why use `filter` instead of `must` for status? Exact constraint without scoring.
3. How do you favor exact phrases without excluding broader matches? Boosted `match_phrase` alongside `match` in `should`.
4. How do you tolerate typos? `match` with `fuzziness: AUTO`.
5. How do you debug surprising ranking? `explain=True` and inspect `_explanation`.
6. What is the difference between `_id` and `study_id`? ES document metadata versus application field.

## Next — Day 10
Session 1: Kibana setup, Discover, Dev Tools, inspecting existing indices. Session 2: Flask + PostgreSQL project foundation.
