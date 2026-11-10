from app.es_client import get_es_client

client = get_es_client()

try:
    response = client.search(
        index="studies_v3",
        query={
            "match": {
                "title": "Cancer"
            }
        },
        source=["study_id", "title", "status"],
        size=5,
        track_total_hits=False
    )

    print("search took: ", response['took'], "ms")
    print("Returned documents:", len(response['hits']['hits']))

    for hit in response['hits']['hits']:
        print(hit['_source'])
finally:
    client.close()