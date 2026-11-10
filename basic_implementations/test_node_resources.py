from app.es_client import get_es_client

client = get_es_client()

try:
    stats = client.nodes.stats(
        metric="jvm,process,indices"
    )

    for node in stats["nodes"].values():
        print("Node:", node["name"])

        jvm = node["jvm"]
        process = node["process"]
        indices = node["indices"]

        print(
            "JVM heap used:",
            jvm["mem"]["heap_used_percent"],
            "%"
        )

        print(
            "Process CPU:",
            process["cpu"]["percent"],
            "%"
        )

        print(
            "Search query count:",
            indices["search"]["query_total"]
        )

        print(
            "Search query time:",
            indices["search"]["query_time_in_millis"],
            "ms"
        )

finally:
    client.close()