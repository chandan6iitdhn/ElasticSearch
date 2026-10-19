import os
from elasticsearch import Elasticsearch

client = Elasticsearch("https://localhost:9200",
                       basic_auth=(os.environ["ES_USERNAME"], os.environ["ES_PASSWORD"]),
                       verify_certs=False, # for local development only
                       )

try:
    # create the index if it doesn't already exist
    if not client.indices.exists(index="studies"):
        client.indices.create(index="studies")

    # store one study document in the index
    response = client.index(
        index="studies",
        id="ST001",
        document={
            "study_id": "ST001",
            "title": "Diabetes Treatment Study",
            "status": "Completed",
        }
    )
    # print("Indexing result: ", response["result"])

    document = client.get(index="studies", id="ST001")
    print("Document ID: ", document["_id"])
    print("Document source: ", document["_source"])

    search_response = client.search(
        index="studies",
        query={
            "match": {
                "title": "Diabetes"
            }
        },
    )

    for hit in search_response["hits"]["hits"]:
        print("ID: ", hit["_id"])
        print("Score: ", hit["_score"])
        print("Document: ", hit["_source"])
finally:
    client.close()