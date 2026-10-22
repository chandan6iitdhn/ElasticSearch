import os
from elasticsearch import Elasticsearch

client = Elasticsearch("https://localhost:9200",
                       basic_auth=(os.environ["ES_USERNAME"], os.environ["ES_PASSWORD"]),
                       verify_certs=False, # for local development only
                       )

try:
    index_name = "studies_v2"

    # mapping = {
    #     "properties": {
    #         "study_id": {"type": "keyword"},
    #         "title": {"type": "text"},
    #         "status": {"type": "keyword"},
    #         "participant_count": {"type": "integer"},
    #     }
    # }
    #
    # if not client.indices.exists(index=index_name):
    #     client.indices.create(index=index_name, mappings=mapping)
    #     print("Created index: ", index_name)
    # else:
    #     print("Index already exists: ", index_name)
    #
    # index_creation_response = client.indices.get_mapping(index=index_name)
    # print(index_creation_response[index_name]["mappings"])
    #
    client.index(
        index="studies_v2",
        id="ST002",
        document={
            "study_id": "ST002",
            "title": "Diabetes Prevention Study",
            "status": "In Progress",
            "participant_count": 120,
        },
        refresh="wait_for",
    )

    print("Second document indexed")

    document = client.get(
        index=index_name,
        id="ST001",
    )
    # print("Document_id = ", document["_id"])
    # print("Document source = ", document["_source"])

    status_response = client.search(
        index=index_name,
        query={
            "term": {
                "status": "Completed"
            }
        },
    )

    text_response = client.search(
        index=index_name,
        query={
            "match": {
                "title": "diabetes"
            }
        },
    )

    combine_search_response = client.search(
        index="studies_v2",
        query={
            "bool": {
                "must": [
                    {
                        "match": {
                            "title": "diabetes"
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
    )
    # print("Status search matches: ", text_response["hits"]["total"]["value"])
    # print("Title search matches: ", text_response["hits"]["total"]["value"])
    print("combine search matches: ", combine_search_response["hits"]["total"]["value"])

    response = client.search(
        index="studies_v2",
        query={
            "bool": {
                "must": [
                    {
                        "multi_match":{
                            "query": "diabetes",
                            "fields": ["title^3", "description"]
                        }
                    }
                ],
                "filter": [
                    {
                        "term": {"status": "Completed"}
                    },
                ],
                "must_not": [
                    {
                        "term": {"is_deleted": True}
                     }
                ],
                "should": [
                    {
                        "match": {"title": "treatment"}
                    }
                ]
            }
        }
    )

    for hit in combine_search_response["hits"]["hits"]:
        print(hit["_source"])

finally:
    client.close()