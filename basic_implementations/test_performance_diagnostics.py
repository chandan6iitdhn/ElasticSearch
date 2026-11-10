import time
from app.es_client import get_es_client

client = get_es_client()

try:
    # Step 1: Measure query latency
    start = time.perf_counter()

    response = client.search(
        index="studies_v3",
        query={
            "match": {
                "title": "cancer"
            }
        },
        size=10
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    print("=== Search Performance ===")
    print("ES took:", response["took"], "ms")
    print("Python elapsed:", round(elapsed_ms, 2), "ms")

    # Step 2: Check cluster health
    health = client.cluster.health()

    print("\n=== Cluster Health ===")
    print("Status:", health["status"])
    print("Unassigned shards:", health["unassigned_shards"])

    # Step 3: Check node resources
    stats = client.nodes.stats(metric="jvm,process")

    for node in stats["nodes"].values():
        print("\n=== Node Resources ===")
        print("Node:", node["name"])
        print(
            "Heap used:",
            node["jvm"]["mem"]["heap_used_percent"],
            "%"
        )
        print(
            "CPU:",
            node["process"]["cpu"]["percent"],
            "%"
        )

finally:
    client.close()