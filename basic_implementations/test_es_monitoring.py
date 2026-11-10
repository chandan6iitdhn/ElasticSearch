from app.es_client import get_es_client

client = get_es_client()

try:
    health = client.cluster.health()

    print("Cluster status:", health["status"])
    print("Number of nodes:", health["number_of_nodes"])
    print("Active primary shards:", health["active_primary_shards"])
    print("Unassigned shards:", health["unassigned_shards"])

    stats = client.nodes.stats(metric="jvm,process")

    for node in stats["nodes"].values():
        print("Node:", node["name"])
        print(
            "JVM heap used:",
            node["jvm"]["mem"]["heap_used_percent"],
            "%"
        )
        print(
            "Process CPU:",
            node["process"]["cpu"]["percent"],
            "%"
        )

finally:
    client.close()