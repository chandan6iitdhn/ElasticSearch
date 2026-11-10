import time
from app.es_client import get_es_client

client = get_es_client()

queries = {
    "Match Query": {
        "match": {
            "title": "cancer"
        }
    },
    "Wildcard Query": {
        "wildcard": {
            "title": {
                "value": "*cancer*"
            }
        }
    }
}

try:
    for name, query in queries.items():
        start = time.perf_counter()

        response = client.search(
            index="studies_v3",
            query=query,
            size=10
        )

        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        print(f"\n{name}")
        print("Elasticsearch took:", response["took"], "ms")
        print("Python elapsed:", round(elapsed_ms, 2), "ms")
        print("Total matches:", response["hits"]["total"]["value"])

finally:
    client.close()