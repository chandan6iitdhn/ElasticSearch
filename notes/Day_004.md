# Day 4 — Elasticsearch Mappings, Documents, and Combined Queries

## 1. Explicit Mapping

A mapping defines how Elasticsearch interprets and indexes document fields.

Example:

```python
mapping = {
    "properties": {
        "study_id": {"type": "keyword"},
        "title": {"type": "text"},
        "status": {"type": "keyword"},
        "participant_count": {"type": "integer"}
    }
}
```

Common field types:

| Type | Typical use |
|---|---|
| `text` | Full-text search, such as titles and descriptions |
| `keyword` | Exact matching, identifiers, status, sorting |
| `integer` | Whole-number values |
| `long` | Large whole-number values |
| `date` | Dates and timestamps |
| `boolean` | True/false values |

Explicit mappings help ensure predictable search behavior.

## 2. Creating an Index Safely

```python
index_name = "studies_v2"

if not client.indices.exists(index=index_name):
    client.indices.create(
        index=index_name,
        mappings=mapping
    )
```

Check whether an index exists before creating it.

**Important:** Existing field types generally cannot be changed in place. The usual migration process is:

1. Create a new index with the desired mapping.
2. Reindex the existing documents.
3. Validate the new index.
4. Switch the application to the new index.
5. Keep the old index until it is safe to remove.

## 3. Inspecting a Mapping

```python
response = client.indices.get_mapping(
    index="studies_v2"
)

print(response["studies_v2"]["mappings"])
```

This verifies that Elasticsearch created the expected field definitions.

## 4. Indexing a Document

```python
client.index(
    index="studies_v2",
    id="ST001",
    document={
        "study_id": "ST001",
        "title": "Diabetes Treatment Study",
        "status": "Completed",
        "participant_count": 250
    },
    refresh="wait_for"
)
```

Key concepts:

- `index`: destination index.
- `id`: Elasticsearch document identifier (`_id`).
- `document`: JSON-like document content.
- `refresh="wait_for"`: waits until the document becomes searchable through a refresh.

The indexing response's `result` can be `created` or `updated`, depending on whether that document ID already existed.

## 5. Retrieving a Document

```python
document = client.get(
    index="studies_v2",
    id="ST001"
)

print(document["_id"])
print(document["_source"])
```

- `_id`: Elasticsearch's document identifier.
- `_source`: the stored document fields.

## 6. Searching with `match`

```python
response = client.search(
    index="studies_v2",
    query={
        "match": {
            "title": "diabetes"
        }
    }
)

print(response["hits"]["total"]["value"])
```

`match` is used for full-text search. Elasticsearch analyzes the search text according to the field's analyzer.

For example, `"Diabetes Treatment Study"` can match a search for `"diabetes"`.

## 7. Searching with `term`

```python
response = client.search(
    index="studies_v2",
    query={
        "term": {
            "status": "Completed"
        }
    }
)
```

`term` matches an exact indexed term without analyzing the supplied search value.

For status filters, use a `keyword` field so that `"Completed"` can be matched as an exact value.

## 8. Combining Queries with `bool`

Example:

```python
response = client.search(
    index="studies_v2",
    query={
        "bool": {
            "must": [
                {
                    "match": {
                        "title": "diabetes"
                    }
                }
            ],
            "filter": [
                {
                    "term": {
                        "status": "Completed"
                    }
                }
            ]
        }
    }
)
```

Both conditions must be satisfied for a document to be returned.

### `must` vs. `filter`

| Clause | Must match? | Affects relevance score? |
|---|---|---|
| `must` | Yes | Yes |
| `filter` | Yes | No |

### `match` vs. `term`

| Query | Behavior | Typical use |
|---|---|---|
| `match` | Analyzes text for full-text matching | Titles and descriptions |
| `term` | Matches an exact indexed term | Status and identifiers |

These are independent choices. There is no fixed rule that `must` must use `match` or `filter` must use `term`.

For example, both `must` + `term` and `filter` + `match` are valid combinations.

## 9. Practical Validation

Two documents were indexed:

| ID | Title | Status |
|---|---|---|
| ST001 | Diabetes Treatment Study | Completed |
| ST002 | Diabetes Prevention Study | In Progress |

The combined query searched for `diabetes` and filtered for `Completed`.

Expected result: **1 matching document — ST001.**

ST002 matches the title search but is excluded because its status is `In Progress`.

## 10. Key Takeaways

1. Mappings determine how fields are indexed and searched.
2. Use `text` for full-text search and `keyword` for exact-value fields.
3. Use `client.index()` to index or replace a document with a specified ID.
4. Use `client.get()` to retrieve a document by ID.
5. Use `match` for full-text queries and `term` for exact-term queries.
6. Use `bool` to combine multiple query conditions.
7. Use `must` when a condition should influence relevance scoring; use `filter` when it should constrain results without influencing scoring.
8. Keep PostgreSQL as the source of truth in our eventual Study Search API, with Elasticsearch serving as the search index.

### Interview Revision

**Q: How would you search for studies containing a keyword in the title while returning only completed studies?**

Use a `bool` query with `must` containing a `match` query on `title`, and `filter` containing a `term` query on `status`.

**Q: Why not use `must` for every condition?**

Filters express constraints that don't need to affect relevance scoring. They can also benefit from Elasticsearch's filter optimizations and caching where applicable.
