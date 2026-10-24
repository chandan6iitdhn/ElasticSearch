# Day 3 — Elasticsearch Setup, Inspection, and Mapping Fundamentals

## 1. Verify Elasticsearch Environment

### Check Docker container

```bash
docker ps
```

Confirms whether the Elasticsearch container `es01` is running and whether port `9200` is exposed.

### Check cluster health

```bash
curl --insecure --user elastic \
  'https://localhost:9200/_cluster/health?pretty'
```

### Check index health

```bash
curl --insecure --user elastic \
  'https://localhost:9200/_cat/indices/studies?v'
```

### Health statuses

- **Green:** All primary and replica shards are allocated.
- **Yellow:** Primary shards are allocated, but one or more replicas are unassigned.
- **Red:** At least one primary shard is unassigned, potentially making some data unavailable.

In our single-node setup, `studies` is yellow because its primary shard and replica cannot be allocated to the same node.

Cluster health describes the overall cluster; index health describes a particular index.

```bash
curl --insecure --user elastic \
  'https://localhost:9200/_cluster/health/studies?pretty'
```

## 2. What Is an Elasticsearch Mapping?

A **mapping defines how Elasticsearch interprets and indexes document fields**.

It is conceptually similar to a schema in PostgreSQL, although Elasticsearch mappings serve additional purposes related to search behavior.

Example study document:

```json
{
  "study_id": "ST001",
  "title": "Diabetes Treatment Study",
  "status": "Completed",
  "participant_count": 250
}
```

Recommended field types:

| Field | Mapping type | Purpose |
|---|---|---|
| `study_id` | `keyword` | Exact identifier matching |
| `title` | `text` | Full-text search |
| `status` | `keyword` | Exact-value filtering |
| `participant_count` | `integer` | Numeric comparisons and sorting |

### Why mappings matter

Mappings determine how values are indexed and which operations are suitable for a field.

For example, a title should support searching individual words, while a status field should support exact filtering.

## 3. Dynamic Mapping vs Explicit Mapping

### Dynamic mapping

Elasticsearch can infer field types automatically when documents are indexed.

For example:

```json
{
  "title": "Diabetes Treatment Study",
  "participant_count": 250
}
```

Elasticsearch may infer `title` as `text` with a `keyword` multi-field and `participant_count` as an integer.

Dynamic mapping is convenient for experimentation, but the inferred types may not match the application's intended search behavior.

### Explicit mapping

Explicit mapping defines field types before indexing documents.

It makes search behavior predictable and documents the application's intended data model.

**Important:** An existing field's type generally cannot be changed in place. Changing a field from `text` to `keyword` usually requires creating a new index with the desired mapping and reindexing the data.

## 4. `text` vs `keyword`

### `text`

Designed for full-text search.

Text is analyzed during indexing. With the standard analyzer, for example:

`Diabetes Treatment Study`

may be tokenized into:

- `diabetes`
- `treatment`
- `study`

Example query:

```json
{
  "query": {
    "match": {
      "title": "diabetes"
    }
  }
}
```

This can find a document whose full title is `Diabetes Treatment Study`.

### `keyword`

Designed for exact values, categorical data, identifiers, sorting, and aggregations.

The entire value is indexed as one term, rather than being split into individual words by the usual full-text analyzer.

Example filter:

```json
{
  "query": {
    "term": {
      "status": "Completed"
    }
  }
}
```

Without a normalizer, `Completed` and `completed` are different values for a keyword field.

### Comparison

| Feature | `text` | `keyword` |
|---|---|---|
| Main purpose | Full-text search | Exact-value operations |
| Tokenization | Usually yes | No full-text tokenization |
| Typical query | `match` | `term` |
| Exact categorical filtering | Usually use a keyword subfield | Yes |
| Sorting and aggregations | Usually use a keyword subfield | Yes |

**Remember:** `match` analyzes its search input according to the field's search analyzer. `term` looks for an exact indexed term and does not analyze the input in the same way.

## 5. Multi-fields

Our existing index was created without an explicit mapping.

When we inspected it, Elasticsearch returned:

```json
{
  "properties": {
    "status": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  }
}
```

This means the `status` field has two indexed representations:

- `status`: a `text` field for full-text search.
- `status.keyword`: a `keyword` field for exact matching and other keyword operations.

The same pattern appeared for `study_id` and `title`.

For example, this exact filter can work with the current mapping:

```json
{
  "query": {
    "term": {
      "status.keyword": "Completed"
    }
  }
}
```

The `ignore_above: 256` setting means strings longer than the configured threshold are not indexed into that keyword subfield.

Multi-fields provide multiple ways to search the same original value without changing the stored JSON value.

## 6. Inspect Mappings with Python

Using the official Elasticsearch Python client:

```python
mapping = client.indices.get_mapping(index="studies")

print(mapping["studies"]["mappings"])
```

This retrieves the mapping for the existing `studies` index.

The response showed that `status`, `study_id`, and `title` were all dynamically mapped as `text` fields with `keyword` multi-fields.

## 7. Recommended Mapping for Our Study Search API

Our intended design is:

- `study_id` → `keyword`
- `title` → `text`
- `status` → `keyword`
- `participant_count` → `integer`

Why?

- Study IDs must match exact identifiers.
- Titles must support word-based search.
- Statuses must support exact filtering, such as `Completed` and `In Progress`.
- Participant counts must support numeric comparisons and sorting.

We will define this mapping explicitly in the next session.

## 8. Interview Revision

**Q: What is an Elasticsearch mapping?**

A: A mapping defines the data types and indexing behavior of fields in Elasticsearch documents.

**Q: What is the difference between `text` and `keyword`?**

A: `text` is designed for analyzed full-text search. `keyword` is designed for exact-value operations, sorting, and aggregations.

**Q: What is dynamic mapping?**

A: Dynamic mapping allows Elasticsearch to infer field types when documents are indexed.

**Q: What is a multi-field?**

A: A multi-field indexes the same original field in multiple ways, such as `text` and `keyword`.

**Q: Can we change an existing field from `text` to `keyword` directly?**

A: Generally, no. Create a new index with the correct mapping and reindex the documents.

**Q: Why is our index yellow?**

A: We have one Elasticsearch node and one configured replica per primary shard. Elasticsearch cannot allocate a replica to the same node as its primary.

## Key Takeaways

1. Mappings influence how Elasticsearch indexes and searches data.
2. Use `text` for full-text fields such as titles.
3. Use `keyword` for identifiers and categorical fields such as status.
4. Dynamic mapping is convenient, but explicit mappings improve predictability.
5. Inspect mappings with `client.indices.get_mapping()`.
6. Correcting a field's type generally requires a new index and reindexing.
7. Yellow health in our single-node setup does not automatically mean search is unavailable.
