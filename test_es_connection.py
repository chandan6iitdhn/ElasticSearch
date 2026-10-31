import os
from elasticsearch import Elasticsearch

client = Elasticsearch("https://localhost:9200",
                       basic_auth=(os.environ["ES_USERNAME"], os.environ["ES_PASSWORD"]),
                       verify_certs=False, # for local development only
                       )


def search_studies_by_relevance(client, search_text, status=None):
    index = "studies_v2"
    query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": search_text,
                            "fields": ["title^3", "description"]
                        }
                    }
                ],
                "filter": []
            }
        }
    if status is not None:
        query["bool"]["filter"].append({"term": {"status": status}})
    search_resp = client.search(
        index=index,
        size=10,
        explain=True,
        query=query,
    )

    search_resp_hit = search_resp['hits']['hits']
    resp = []
    for hit in search_resp_hit:
        resp.append({
            "study_id": hit["_source"]['study_id'],
            "title": hit['_source']['title'],
            "_score": hit['_score']
        })
    return resp


def advanced_study_search(client, search_text, status=None):
    query = {
        "bool": {
            "should": [
                {
                    "match_phrase": {
                        "title": {
                            "query": search_text,
                            "boost": 5
                        },
                    }
                },
                {
                    "match": {
                        "title": {
                            "query": search_text,
                            "operator": "and",
                            "boost": 2
                        }
                    }
                },
                {
                    "match": {
                        "title": {
                            "query": search_text,
                            "fuzziness": "AUTO"
                        }
                    }
                }
            ],
            "minimum_should_match": 1,
        }
    }

    if status is not None:
        query["bool"]["filter"] = [{"term": {"status": status}}]


    search_result = client.search(
        index="studies_v2",
        size=10,
        explain=True,
        query=query,
    )
    # print(search_result)
    search_result_hit = search_result['hits']['hits']
    resp = []
    for hit in search_result_hit:
        resp.append({
            "study_id": hit["_source"]['study_id'],
            "title": hit['_source']['title'],
            "_score": hit['_score']
        })
    return resp


print(advanced_study_search(client, "diabetes", "Completed"))
# print(search_studies_by_relevance(client, "diabetes", "Completed"))
