# Day 1 — Elasticsearch Fundamentals and How Search Works

## 1. Why Elasticsearch?

Elasticsearch is a distributed search and analytics engine built on Apache Lucene. It is designed to search large volumes of data efficiently and return ranked results.

### Why not use PostgreSQL for everything?

PostgreSQL is excellent for transactional data, relationships, constraints, and structured queries. Elasticsearch is optimized for full-text search, relevance ranking, and flexible search queries.

| Requirement | PostgreSQL | Elasticsearch |
|---|---|---|
| Store authoritative business data | Excellent | Usually not the source of truth |
| Relationships and transactions | Excellent | Limited compared with a relational database |
| Full-text search | Supported | A core strength |
| Relevance-based ranking | Available with full-text search features | Built into search |
| Flexible filtering | Excellent | Excellent |
| Search across large text fields | Supported | Optimized for search workloads |

**Our project architecture:** PostgreSQL stores the authoritative study data, while Elasticsearch stores a search-optimized copy.

## 2. What Is an Inverted Index?

An inverted index maps terms to the documents containing them.

Suppose we have these documents:

- D1: `Diabetes Treatment Study`
- D2: `Diabetes Prevention Study`
- D3: `Heart Disease Research`

A simplified inverted index could look like this:

| Term | Documents containing the term |
|---|---|
| diabetes | D1, D2 |
| treatment | D1 |
| prevention | D2 |
| heart | D3 |
| disease | D3 |
| research | D3 |

When someone searches for `diabetes`, Elasticsearch can locate documents associated with that term without scanning every document's complete text.

In a real Elasticsearch index, Lucene maintains richer structures, including term dictionaries, postings lists, and position information.

### Why is it useful?

An inverted index makes searching through large text collections much more efficient than repeatedly examining every document.

## 3. Analyzers and Tokenization

Before indexing text, Elasticsearch commonly processes it through an analyzer.

An analyzer generally consists of:

1. **Character filters** — optionally transform text before tokenization.
2. **Tokenizer** — splits text into tokens.
3. **Token filters** — optionally modify, remove, or normalize tokens.

Example input:

`The Diabetes Treatment Study`

A simplified analyzer might produce:

`["the", "diabetes", "treatment", "study"]`

Depending on the analyzer, it may also lowercase text or remove common words such as `the`.

This helps a search for `diabetes` match a document containing `Diabetes`.

**Important:** Analysis is configured for fields and query processing. Not every analyzer performs stemming or removes stop words.

## 4. How Elasticsearch Search Works

A simplified search lifecycle:

1. A document is submitted to Elasticsearch.
2. Elasticsearch processes fields according to their mappings and analyzers.
3. The document is indexed in Lucene.
4. A user submits a search query.
5. Elasticsearch analyzes the query where appropriate.
6. It finds matching documents using the index.
7. Matching documents may be scored and ranked.
8. Elasticsearch returns hits, scores, and document fields.

### Indexing versus searching

- **Indexing:** Preparing and adding a document to the search index.
- **Searching:** Finding documents that satisfy a query.
- **Retrieving:** Returning the requested document data.

Elasticsearch is near-real-time: an indexed document generally becomes searchable after a refresh, rather than necessarily being searchable immediately after the indexing request.

## 5. Relevance Scoring

A search can return multiple matching documents. Elasticsearch can assign a relevance score, exposed as `_score`, to help rank them.

For example, searching for `diabetes treatment` might return:

1. `Diabetes Treatment Study`
2. `Diabetes Prevention Study`

The first document may rank higher because its text better matches the query.

Elasticsearch uses the BM25 similarity algorithm by default for many standard text fields. It considers factors such as term frequency, how common a term is across documents, and document length.

The score is useful for ranking, but it should not be interpreted as a probability or a universal measure of correctness.

### Filtering versus scoring

- **Scoring:** Helps determine which matching documents rank higher.
- **Filtering:** Restricts results to documents satisfying a condition, such as `status = Completed`.

Our Study Search API will combine text relevance with exact-value filters.

## 6. End-to-End Study Search Architecture

Our target architecture is:

```text
Client
  |
  v
Flask REST API
  |
  v
Elasticsearch
  |
  v
Matching study documents
```

PostgreSQL remains the source of truth and supplies data to Elasticsearch through a synchronization or ETL process.

The API can eventually support requests such as:

`GET /studies/search?q=diabetes&status=Completed`

The API will translate the request into an Elasticsearch query and return matching studies.

## 7. Elasticsearch and Docker

We are running Elasticsearch locally in Docker as part of the learning project.

Important terms:

- **Docker image:** The packaged template used to create a container.
- **Container:** A running or stopped instance created from an image.
- **Docker network:** Allows containers on the same network to communicate.
- **Elasticsearch node:** A running Elasticsearch instance.
- **Cluster:** One or more Elasticsearch nodes working together.

A single-node cluster is sufficient for learning, although production clusters may use multiple nodes for resilience and scale.

## 8. Key Takeaways

1. Elasticsearch is optimized for search and analytics, while PostgreSQL remains the authoritative database in our project.
2. An inverted index maps terms to documents and supports efficient text retrieval.
3. Analyzers transform text into searchable tokens.
4. Elasticsearch can rank matching documents using relevance scoring, commonly BM25.
5. Indexing and searching are different operations.
6. Elasticsearch is near-real-time rather than necessarily immediately consistent for search visibility.
7. Flask will expose our search functionality through a REST API.
8. PostgreSQL-to-Elasticsearch synchronization will be an important part of the completed project.

## Interview Revision

**Q: Why use Elasticsearch alongside PostgreSQL?**

PostgreSQL handles authoritative transactional data and relational operations. Elasticsearch provides specialized full-text search, relevance ranking, and search-oriented filtering. Keeping PostgreSQL as the source of truth avoids treating the search index as the primary transactional database.

**Q: What is an inverted index?**

A data structure that maps terms to the documents in which they occur, allowing efficient retrieval of documents containing particular terms.

**Q: What is an analyzer?**

A component that processes text during indexing or querying, using character filters, tokenization, and token filters.

**Q: What is BM25?**

A relevance-scoring algorithm used to rank matching documents based on factors including term frequency, inverse document frequency, and document length.

**Q: Is Elasticsearch immediately consistent after indexing?**

Not necessarily for search. Documents typically become searchable after a refresh, so Elasticsearch is near-real-time.

**Q: Should Elasticsearch replace PostgreSQL in our project?**

No. PostgreSQL remains the source of truth; Elasticsearch is the derived search index.
