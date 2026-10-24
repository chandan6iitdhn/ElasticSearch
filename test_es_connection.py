import os
from elasticsearch import Elasticsearch

client = Elasticsearch("https://localhost:9200",
                       basic_auth=(os.environ["ES_USERNAME"], os.environ["ES_PASSWORD"]),
                       verify_certs=False, # for local development only
                       )


def compare_analyzers(client, input_text):
    try:
        analyzers = [
            "standard",
            "whitespace",
            "keyword"
        ]

        results = {}

        for analyzer in analyzers:
            # TODO 1: Call the Elasticsearch analyze API
            response = client.indices.analyze(
                analyzer=analyzer,
                text=input_text
            )

            # TODO 2: Extract tokens from response
            tokens = []

            for item in response["tokens"]:
                tokens.append(item["token"])

            # TODO 3: Store tokens under analyzer name
            results[analyzer] = tokens

        return results

    except Exception as e:
        raise e

    finally:
        client.close()

def setup_study_index(client):

    index_name = "studies_custom_v2"

    settings = {
        "analysis": {
            "analyzer": {
                "study_analyzer": {
                    "type": "custom",

                    # TODO 1: Configure tokenizer
                    "tokenizer": "standard",

                    # TODO 2: Configure token filters
                    "filter": ["lowercase", "english_stop", "english_stemmer"]
                }
            },
            "filter": {
                "english_stop": {
                    "type": "stop",
                    "stopwords": "_english_"
                },

                "english_stemmer": {
                    "type": "stemmer",
                    "language": "english"
                }
            }
        }
    }

    mappings = {
        "properties": {
            "study_id": {
                "type": "keyword"
            },
            "title": {
                "type": "text",
                "analyzer": "study_analyzer"
            },
            "status": {
                "type": "keyword"
            },
            "participant_count": {
                "type": "integer"
            }
        }
    }

    # TODO 6: Create index
    response = client.indices.create(
        index=index_name,
        settings=settings,
        mappings=mappings
    )

    return response


def get_tokens(client):
    response = client.indices.analyze(
        index="studies_custom_v2",
        analyzer="study_analyzer",
        text="The Diabetes Treatments"
    )

    tokens = [
        item["token"]
        for item in response["tokens"]
    ]

    return tokens


# input_text = "Diabetes Treatment Study"
client.indices.delete(index="studies_custom_v2")
print(setup_study_index(client))
print(get_tokens(client))
