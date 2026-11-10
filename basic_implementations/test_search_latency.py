import time
from app.es_client import get_es_client

client = get_es_client()

try:
    start = time.perf_counter()

    response = client.search(
        index="studies_v3",
        query={
            "match": {
                "title": "cancer"
            }
        }
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    print("Elasticsearch took:", response["took"], "ms")
    print("Python client elapsed:", round(elapsed_ms, 2), "ms")

finally:
    client.close()