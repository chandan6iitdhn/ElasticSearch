# Day 2 — Elasticsearch Learning Notes

## Session 1: Elasticsearch Fundamentals and Internals

### 1. What is Elasticsearch?

Elasticsearch is a distributed search and analytics engine built on Apache Lucene. It is designed for fast full-text search, filtering, relevance scoring, aggregations, and retrieval of JSON documents.

In our Study Search API project:
- **PostgreSQL** will be the source of truth.
- **Elasticsearch** will provide a search-optimized index of study records.
- **Flask** will expose REST APIs for searching studies.

### 2. Core Terminology

- **Cluster:** One or more Elasticsearch nodes working together.
- **Node:** A running Elasticsearch instance.
- **Index:** A logical collection of documents, roughly comparable to a relational database table.
- **Document:** A JSON object stored in an index.
- **Field:** A key/value inside a document.
- **Mapping:** Defines how fields are interpreted, including their data types.
- **Primary shard:** Holds a portion of an index's data.
- **Replica shard:** A copy of a primary shard, providing redundancy and potentially additional search capacity.

### 3. `text` vs `keyword`

- `text`: Used for analyzed full-text search, such as searching study titles.
- `keyword`: Used for exact-value operations such as filtering, sorting, and aggregations.

Typical mapping choices:
- `title` → `text`
- `status` → `keyword`
- `study_id` → often `keyword`

Explicit mappings are important in production. We will define them in a later session.

### 4. How Search Works

Elasticsearch uses Lucene and an **inverted index** to find documents containing terms efficiently.

A high-level search lifecycle:
1. A client sends a search request.
2. Elasticsearch identifies the relevant shards.
3. The shards execute the query.
4. Elasticsearch combines and returns matching results.
5. Results may include relevance scores.

A document write is not necessarily searchable immediately. Elasticsearch's refresh mechanism makes recent changes visible to search.

### 5. Cluster Health

- **Green:** All primary and replica shards are allocated.
- **Yellow:** Primary shards are allocated, but one or more replicas are unassigned.
- **Red:** At least one primary shard is unavailable.

A single-node cluster can become yellow when an index requests replicas that cannot be allocated to the same node as its primary shard.

---

## Session 2: Docker, Elasticsearch Setup, and Python

### 1. Docker Concepts

- **Image:** A packaged template used to create containers.
- **Container:** A running or stopped instance created from an image.
- One image can create multiple containers.
- **Docker network:** Allows connected containers to communicate.
- **Docker Compose:** Will later help us define and run the API, Elasticsearch, and PostgreSQL together.

Useful commands:

```bash
docker context ls
docker context use default
docker info
docker run --rm hello-world
docker ps --filter name=es01
docker network inspect elastic
docker logs --tail 100 es01
```

We selected the working `default` Docker context because the previously selected `desktop-linux` socket was unavailable.

### 2. Elasticsearch Container

Our development environment uses:

- Elasticsearch image: `docker.elastic.co/elasticsearch/elasticsearch:9.5.5`
- Container name: `es01`
- Host port: `9200`
- Docker network: `elastic`
- Python client: `elasticsearch 9.5.1`

The container was started using:

```bash
docker run --name es01 \
  --net elastic \
  -p 9200:9200 \
  -it -m 1GB \
  docker.elastic.co/elasticsearch/elasticsearch:9.5.5
```

The existing container is running; do not recreate it unnecessarily.

### 3. Docker Networking: `localhost` vs `es01`

From the Ubuntu host:

```text
https://localhost:9200
```

This works because Docker publishes the container's port 9200 to the host.

From another container connected to the same Docker network:

```text
https://es01:9200
```

This uses Docker's container-name resolution.

**Important:** Inside a Flask container, `localhost` refers to the Flask container itself, not Elasticsearch.

Prefer the container name over a hard-coded IP address because the container's IP may change when it is recreated.

### 4. Authentication and TLS

Elasticsearch security is enabled in our setup.

We reset the password for the reserved `elastic` user after receiving an authentication error.

Best practices:
- Never hardcode passwords in Python source files.
- Never commit credentials to Git.
- Store credentials securely using environment variables or a secrets manager.
- Do not share passwords in chat or logs.

In PyCharm, configure environment variables through:

**Run → Edit Configurations → Environment variables**

We used the variable:

```text
ES_PASSWORD
```

Python reads it using:

```python
import os

password = os.environ["ES_PASSWORD"]
```

Our local test uses `verify_certs=False`, which disables TLS certificate verification and generates security warnings. This is only a learning shortcut. Production code should verify the Elasticsearch server certificate.

### 5. Check Elasticsearch Server and Health

Server information:

```bash
curl --insecure --user elastic \
  'https://localhost:9200/'
```

Cluster health:

```bash
curl --insecure --user elastic \
  'https://localhost:9200/_cluster/health?pretty'
```

Enter the password when prompted.

Important response fields:
- `version.number`: Elasticsearch server version.
- `cluster_name`: Cluster name.
- `status`: Current cluster health.
- `number_of_nodes`: Number of nodes.
- `unassigned_shards`: Shards that are not allocated.

Our cluster initially returned `green` with one node and three active primary shards.

### 6. Install the Official Python Client

With the project virtual environment active:

```bash
python -m pip install "elasticsearch>=9,<10"
python -m pip show elasticsearch
```

Our installed client version is `9.5.1`, compatible at the major-version level with the Elasticsearch `9.5.5` server.

### 7. Connect to Elasticsearch from Python

```python
import os

from elasticsearch import Elasticsearch

client = Elasticsearch(
    "https://localhost:9200",
    basic_auth=("elastic", os.environ["ES_PASSWORD"]),
    verify_certs=False,  # Local learning only
)

try:
    print("Connected:", client.info()["version"]["number"])
    print("Cluster health:", client.cluster.health()["status"])
finally:
    client.close()
```

Expected output included:

```text
Connected: 9.5.5
cluster health: green
```

This confirmed that Python could authenticate and communicate with Elasticsearch.

### 8. Create an Index and Store a Document

```python
if not client.indices.exists(index="studies"):
    client.indices.create(index="studies")

response = client.index(
    index="studies",
    id="ST001",
    document={
        "study_id": "ST001",
        "title": "Diabetes Treatment Study",
        "status": "Completed",
    },
    refresh="wait_for",
)

print("Indexing result:", response["result"])
```

Key concepts:
- `client.indices.create()` creates an index.
- `client.index()` stores a document.
- `id="ST001"` sets the Elasticsearch document ID.
- `document={...}` provides the JSON fields.
- `refresh="wait_for"` waits for a refresh so the document is searchable before the operation proceeds.

The first run returned:

```text
Indexing result: created
```

The second run returned:

```text
Indexing result: updated
```

Because the same document ID was reused, Elasticsearch updated the existing document instead of creating another document with a different ID.

In production, index creation and mappings should be handled by a setup or deployment step—not on every API request.

### 9. `_id` vs `_source`

Retrieve a document:

```python
document = client.get(index="studies", id="ST001")

print("Document ID:", document["_id"])
print("Document source:", document["_source"])
```

Example output:

```text
Document ID: ST001
Document source: {
    'study_id': 'ST001',
    'title': 'Diabetes Treatment Study',
    'status': 'Completed'
}
```

- `_id` is Elasticsearch's document identifier.
- `_source` contains the JSON document fields.

They are independent. For example, `_id` could be `doc-999` while `_source["study_id"]` is `ST205`.

For our project, using the PostgreSQL study ID as the Elasticsearch `_id` will give each study a predictable identifier.

### 10. Full-Text Search Using `match`

```python
response = client.search(
    index="studies",
    query={
        "match": {
            "title": "Diabetes"
        }
    },
)

for hit in response["hits"]["hits"]:
    print("ID:", hit["_id"])
    print("Score:", hit["_score"])
    print("Document:", hit["_source"])
```

Our search returned `ST001` because its title was `"Diabetes Treatment Study"`.

Important concepts:
- `client.search()` performs a search request.
- `match` is used for analyzed full-text search.
- `_score` is a query-dependent relevance score; a higher score generally indicates a stronger match within that query.
- Searching for `"Cancer"` returned no matching documents because the only document's title did not match that search term. This is not an error.

### 11. Inspect the Index

```bash
curl --insecure --user elastic \
  'https://localhost:9200/_cat/indices/studies?v'
```

Our output showed:

```text
health status index   pri rep docs.count docs.deleted
yellow open   studies   1   1          1            1
```

Interpretation:
- `studies`: The index name.
- `open`: The index is open for reads and writes.
- `pri = 1`: One primary shard.
- `rep = 1`: One replica configured per primary shard.
- `docs.count = 1`: One live document.
- `docs.deleted = 1`: An older document version was marked deleted after the same ID was updated.

Why is the index yellow?

Our cluster has only one node. Elasticsearch cannot allocate the replica to the same node that hosts its primary shard.

The index can still serve searches, but it does not have the configured replica. For our single-node learning environment, we can later configure zero replicas. Production availability planning should use an appropriate multi-node architecture.

---

## Production-Style Architecture

Our final Study Search API will separate responsibilities:

1. **PostgreSQL:** Source of truth for study records.
2. **Index setup:** Creates the Elasticsearch index and defines mappings.
3. **Indexing/synchronization service:** Handles inserts, updates, deletions, retries, and recovery.
4. **Search service:** Encapsulates Elasticsearch query logic.
5. **Flask REST API:** Exposes endpoints such as `GET /studies/search?q=diabetes`.
6. **Docker Compose:** Runs the application and its dependencies in a repeatable local environment.
7. **Testing and operations:** Covers error handling, integration tests, logging, health checks, and secure configuration.

The current script is a learning prototype. We'll refactor it into separate components as the project develops.

A real production deployment also requires workload testing, monitoring, access controls, backups, and infrastructure-specific review.

## Interview Revision — Key Takeaways

1. Elasticsearch stores JSON documents in indices and uses Lucene for core search functionality.
2. `text` is for analyzed full-text search; `keyword` is commonly used for exact-value operations.
3. `_id` and `_source` are separate.
4. `match` is used for full-text search; `term` is typically used for exact indexed values.
5. `created` indicates a new document ID; `updated` indicates an existing ID was indexed again.
6. Green means all shards are allocated; yellow means replicas can be unassigned while primaries remain available; red means a primary shard is unavailable.
7. From the host, use `localhost:9200`; from a peer container, use `es01:9200`.
8. PostgreSQL remains the source of truth; Elasticsearch is the derived search index.
9. `verify_certs=False` is not suitable for production.
10. Index setup and request-time indexing/searching should be separate responsibilities.
