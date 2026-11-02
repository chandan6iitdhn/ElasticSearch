# Day 11 — Flask + Elasticsearch Search API

## Session 1 — Production Search API Design

### Architecture
- Flask route: parse and validate HTTP query parameters, return JSON and appropriate status codes.
- Service layer: build Elasticsearch Query DSL, execute searches, format results.
- Elasticsearch client module: configure and reuse connection settings.
- Prefer a clear separation of routing, search logic, and connection configuration.

### Dynamic Query DSL
- Use `bool.must` for full-text matches that contribute to relevance scoring.
- Use `bool.filter` for exact filters and ranges that do not contribute to relevance scoring.
- Use `match_all` when no search criteria are provided.
- Exact `term` filters require a suitable keyword-mapped field (for text fields, often `.keyword`).

### Sorting and Pagination
- Whitelist sortable fields and validate `asc`/`desc`.
- Field sorting can yield `_score: null` by default; use `track_scores` only if needed.
- Offset pagination: `from = (page - 1) * page_size`, `size = page_size`.
- Default Elasticsearch result window is commonly 10,000 (`index.max_result_window`); deep pagination should use `search_after` with PIT.
- Stable pagination requires deterministic sorting, ideally with a unique tie-breaker.

### Error Handling
- Return 400 for invalid client inputs, 503 when search infrastructure is unavailable, and 502 for upstream search errors as appropriate.
- Log detailed backend exceptions; avoid exposing internal exception details to API consumers.
- Validate numeric query parameters explicitly: Flask `request.args.get(..., type=int)` can silently return `None` on invalid input.

## Session 2 — Hands-on Flask + Elasticsearch Integration

### Project Layout
```text
ElasticSearch/
├── app/
│   ├── __init__.py
│   ├── es_client.py
│   ├── routes.py
│   └── search_service.py
├── basic_implementations/
│   └── test_query_builder.py
└── application.py
```

### 1. HTTPS Client Configuration
- Elasticsearch Docker container: `es01` (Elasticsearch 9.5.5), exposed on host port 9200.
- `curl -u elastic http://localhost:9200` produced `Empty reply from server` because the server expected HTTPS.
- `curl -k -u elastic https://localhost:9200` returned HTTP 200, confirming connectivity and credentials. `-k` is for local diagnosis only.
- PyCharm environment variables: `ELASTICSEARCH_URL=https://localhost:9200`, `ES_USERNAME`, `ES_PASSWORD`, and `ES_CA_CERT` pointing to a trusted CA certificate.

```python
import os
from elasticsearch import Elasticsearch

def get_es_client():
    return Elasticsearch(
        hosts=[os.environ['ELASTICSEARCH_URL']],
        basic_auth=(os.environ['ES_USERNAME'], os.environ['ES_PASSWORD']),
        ca_certs=os.environ['ES_CA_CERT'],
        request_timeout=10,
    )
```

### 2. Dynamic Query Builder
```python
def build_study_query(search_text=None, status=None, min_participants=None):
    must = []
    filters = []
    if search_text:
        must.append({'match': {'title': search_text}})
    if status:
        filters.append({'term': {'status': status}})
    if min_participants is not None:
        filters.append({'range': {'participant_count': {'gte': min_participants}}})
    if not must and not filters:
        return {'match_all': {}}
    bool_query = {}
    if must:
        bool_query['must'] = must
    if filters:
        bool_query['filter'] = filters
    return {'bool': bool_query}
```
- Tested text-only, status-only, no filters, and combined search/filter/range cases successfully.

### 3. Search Endpoint
- Route: `GET /api/studies/search`.
- Parameters: `q`, `status`, `min_participants`, `sort_by`, `order`, `page`, `page_size`.
- Service uses `client.search(index='studies_v2', body=search_body)`.
- Combined query returned `ST001` (Completed, 250 participants) as expected.

### 4. Clean Response and Offset Pagination
```python
search_body = {
    'query': build_study_query(search_text, status, min_participants),
    'from': (page - 1) * page_size,
    'size': page_size,
    'track_total_hits': True,
}
result = client.search(index='studies_v2', body=search_body)
total = result['hits']['total']['value']
response = {
    'total': total,
    'page': page,
    'page_size': page_size,
    'total_pages': (total + page_size - 1) // page_size,
    'studies': [hit['_source'] for hit in result['hits']['hits']],
}
```
- With two studies and `page_size=1`, page 1 returned ST001 and page 2 returned ST002; both reported `total=2`, `total_pages=2`.

### 5. Input Validation and Exceptions
```python
def parse_integer_param(name, default=None, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f'{name} must be an integer')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} must be <= {maximum}')
    return value
```
- Validate `page >= 1`, `1 <= page_size <= 100`, `min_participants >= 0`.
- For the default 10,000-result window, reject requests where `from + size > 10000` (equivalent to `page * page_size > 10000`).
- Catch Elasticsearch transport connection errors/timeouts and return 503; catch upstream API errors and return 502. Log the exception server-side.
- Test results: invalid `page`, `min_participants`, oversized `page_size`, and excessive result-window requests all returned HTTP 400; valid diabetes search returned HTTP 200 and both studies.

## Interview Revision Points
1. Why separate Flask routes from search services? Maintainability, testing, and separation of concerns.
2. `must` vs `filter`: scoring versus non-scoring constraints.
3. Why validate `sort_by`? Avoid unsupported fields and unpredictable or costly queries.
4. Why `track_total_hits=True`? Accurate pagination totals (potential performance cost).
5. Why `(page - 1) * page_size`? Convert one-based page numbers to zero-based offsets.
6. Why avoid deep `from`/`size` pagination? Elasticsearch must collect/skip earlier results; use PIT + `search_after` for deep traversal.
7. Why use HTTPS CA verification? Authenticate the server and protect credentials/data in transit.
8. Why not expose raw Elasticsearch errors? Avoid leaking implementation and infrastructure details.

## Follow-up Improvements
- Automated Flask and service tests with pytest, including simulated Elasticsearch outage and API errors (not yet tested).
- Deterministic sorting with a unique tie-breaker.
- Verify exact status field mapping (`keyword` versus `text`).
- Add connection reuse, structured logging, configuration management, and integration tests.
