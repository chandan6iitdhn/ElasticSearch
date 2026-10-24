# Elasticsearch — Day 8 Consolidated Notes

## Learning outcomes
- Recall `term`, `match`, `bool`, and nested aggregations.
- Understand text analyzers, tokenization, and token filters.
- Compare `standard`, `whitespace`, and `keyword` analyzers.
- Understand stopwords, stemming, and their trade-offs for medical study search.
- Configure a custom analyzer in index settings and assign it to a mapped field.
- Verify analysis using the Elasticsearch Python client.

## Session 1 — Revision and Built-in Analyzers

### 1. Syntax revision

**Exact status match (`keyword` field):**

```python
query = {"term": {"status": "Completed"}}
```

**Title full-text search AND exact status filter:**

```python
query = {
    "bool": {
        "must": [{"match": {"title": "diabetes"}}],
        "filter": [{"term": {"status": "Completed"}}]
    }
}
```

Add another mandatory full-text condition with another dictionary in `must`:

```python
"must": [
    {"match": {"title": "diabetes"}},
    {"match": {"description": "treatment"}}
]
```

**Group studies by status and calculate the average participants per group:**

```python
aggs = {
    "by_status": {
        "terms": {"field": "status"},
        "aggs": {
            "avg_participants": {"avg": {"field": "participant_count"}}
        }
    }
}
```

`term` = exact-value query; `match` = analyzed full-text query; `terms` aggregation = buckets by field values. A top-level `query` restricts the documents that contribute to aggregations. `size=0` suppresses returned hits, not aggregations.

**Average participants for diabetes studies:**

```python
response = client.search(
    index="studies_v2",
    size=0,
    query={"match": {"title": "diabetes"}},
    aggs={"avg_participants": {"avg": {"field": "participant_count"}}}
)
print(response["aggregations"]["avg_participants"]["value"])
```

**Grouping by full title:** Since the original `title` mapping is `text`, a `terms` aggregation on `title.keyword` requires adding a `keyword` multi-field and reindexing existing data (or using a new index). Example mapping:

```python
"title": {
    "type": "text",
    "fields": {"keyword": {"type": "keyword"}}
}
```

Then group with `"terms": {"field": "title.keyword"}`. `terms` defaults to the top 10 buckets.

### 2. What is an analyzer?

An analyzer converts text into tokens used for search. Processing pipeline:

1. **Character filters** (optional): modify raw characters, e.g. strip HTML.
2. **Tokenizer** (exactly one): split text into tokens.
3. **Token filters** (zero or more, in specified order): lowercase, remove stopwords, stem, etc.

The built-in `standard` analyzer generally splits text into words and lowercases them. Example: `"Diabetes Treatment in Patients"` → `['diabetes', 'treatment', 'in', 'patients']`.

A `match` query analyzes the query text using the field's search analyzer. A `term` query does not analyze the input. Thus `match` against a standard-analyzed `title` can match `"DIABETES"` to the indexed token `diabetes`; `term` against a `keyword` field requires the exact indexed value (unless a normalizer is configured).

### 3. Built-in analyzer comparison

Input: `"The Diabetes Treatment Study"`

| Analyzer | Tokens | Notes |
|---|---|---|
| `standard` | `['the', 'diabetes', 'treatment', 'study']` | Splits and lowercases; does **not** remove stopwords by default |
| `whitespace` | `['The', 'Diabetes', 'Treatment', 'Study']` | Splits on whitespace; preserves case |
| `keyword` | `['The Diabetes Treatment Study']` | Entire input as one token |

**`keyword` analyzer vs `keyword` field:** the former is an analysis strategy producing one token; the latter is a mapping type optimized for exact matching, sorting, and aggregations. They are not interchangeable.

### 4. Python `_analyze` API

```python
def compare_analyzers(client, input_text):
    results = {}
    for analyzer in ["standard", "whitespace", "keyword"]:
        response = client.indices.analyze(
            analyzer=analyzer,
            text=input_text
        )
        results[analyzer] = [item["token"] for item in response["tokens"]]
    return results

print(compare_analyzers(client, "Diabetes Treatment Study"))
```

**Client lifecycle:** a function receiving an existing `client` should normally not call `client.close()`; the caller that creates/owns it should close it.

## Session 2 — Custom Analyzers, Stopwords, Stemming

### 1. Custom analyzer

Define a custom analyzer in **index settings**, then assign it to a `text` field in **mappings**. Merely defining an analyzer named `study_analyzer` does not automatically apply it to all fields. Without an explicit field analyzer or configured index default analyzer, a `text` field uses the standard analyzer.

**Token-filter order matters.** Use `lowercase` before an English stopword filter to normalize capitalization before stopword lookup.

### 2. Stopwords and stemming

- **Stopword removal:** eliminates common words such as `the`, `of`, `and` (according to the configured list). It may affect phrase-search behavior; test on medical terminology and meaningful phrases.
- **Stemming:** reduces words to stems; `studies` → `studi`, `treatments` → `treatment`, `diabetes` → `diabet` for the configured English stemmer.
- **Lemmatization:** linguistic normalization to a base word, e.g. `studies` → `study`; different from rule-based stemming.
- Aggressive stemming may reduce precision in medical search. Test real queries before production use.

### 3. Complete custom index setup (corrected)

```python
def setup_study_index(client):
    index_name = "studies_custom_v2"

    settings = {
        "analysis": {
            "analyzer": {
                "study_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "english_stop", "english_stemmer"]
                }
            },
            "filter": {
                "english_stop": {
                    "type": "stop",
                    "stopwords": "_english_"  # NOT "stop_words"
                },
                "english_stemmer": {
                    "type": "stemmer",
                    "language": "english"
                }
            }
        }
    }

    mappings = {
        "properties": {
            "study_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "study_analyzer"},
            "status": {"type": "keyword"},
            "participant_count": {"type": "integer"}
        }
    }

    return client.indices.create(
        index=index_name,
        settings=settings,
        mappings=mappings
    )
```

**Important correction:** `stopwords` is the documented Elasticsearch option, not `stop_words`. A successful index-creation response does not by itself prove every intended analysis setting took effect; test the analyzer output.

### 4. Verify tokens

```python
def get_tokens(client):
    response = client.indices.analyze(
        index="studies_custom_v2",
        analyzer="study_analyzer",
        text="The Diabetes Treatments"
    )
    return [item["token"] for item in response["tokens"]]

print(get_tokens(client))
# Observed: ['diabet', 'treatment']
```

Observed successful index creation:

```python
{'acknowledged': True, 'shards_acknowledged': True, 'index': 'studies_custom_v2'}
```

### 5. Updating analyzer settings and recreating an index

- Running `indices.create` again for an existing name fails with `resource_already_exists_exception`.
- Changes to the indexing analyzer of an existing field generally require a new index and reindexing.
- **Practice only:** if no important data is present, delete and recreate the index:

```python
client.indices.delete(index="studies_custom_v2")  # Deletes all indexed data!
setup_study_index(client)
print(get_tokens(client))
```

- Safer alternative: create `studies_custom_v3` and point verification to the new name.
- In production, use a new versioned index, reindex data, and switch an alias after validation.

### 6. TLS security warnings

Using `verify_certs=False` can produce `SecurityWarning` and `InsecureRequestWarning`. These are security warnings, not necessarily request failures. `exit code 0` indicates the Python process finished successfully. For production, configure the Elasticsearch HTTP CA certificate:

```python
import os
from elasticsearch import Elasticsearch

client = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", os.environ["ES_PASSWORD"]),
    ca_certs="/actual/path/to/http_ca.crt"
)
```

Do not use an invented certificate path; obtain the correct certificate from your deployment.

## Interview quick revision

1. **Analyzer pipeline?** Character filters → tokenizer → token filters.
2. **Does `standard` remove stopwords?** No, not by default.
3. **Does `match` always ignore case?** No; it depends on the analyzer.
4. **Difference between `term` and `terms` aggregation?** Exact query versus grouping into buckets.
5. **Why use `title.keyword` for terms aggregation?** Aggregate exact full titles, not analyzed text tokens.
6. **Where are custom analyzers defined?** Index settings, then referenced in field mappings (unless configured as the default).
7. **Does filter order matter?** Yes.
8. **What is a stem?** A normalized word form, not necessarily a dictionary word.
9. **Why avoid aggressive stemming in medical search?** Potential loss of distinctions and irrelevant matches.
10. **Why recreate an index?** Index-time analysis changes generally require rebuilding indexed tokens.

## 10-minute revision exercise for Day 9

Without looking at these notes:

1. Write a `bool` query requiring `match` on `title` and `term` on `status`.
2. Write `terms` by `status` with a nested `avg` of `participant_count`.
3. Write an `_analyze` call using the custom analyzer.
4. Explain the difference between defining an analyzer and assigning it to a field.

**Day 8 complete.** Next: Day 9, with syntax recall before new material.
