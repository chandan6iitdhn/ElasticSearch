from app.es_client import get_es_client

client = get_es_client()

try:
    response = client.search(
        index="studies_v3",
        query={
            "bool": {
                "must": [
                    {
                        "match": {
                            "title": "Cancer"
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
        },
        profile=True
    )

    print("Search took: ", response['took'], "ms")

    shards = response["profile"]["shards"]
    for shard in shards:
        for search in shard.get("searches", []):
            for query in search.get("query", []):
                print("Query Type:", query["type"])
                print("Time (ns):", query["time_in_nanos"])
                print("Description:", query["description"])
                print("---")

finally:
    client.close()