from app.es_client import get_es_client

client = get_es_client()

try:
    client.indices.put_settings(
        index="studies_v3",
        settings={
            "index.search.slowlog.threshold.query.warn": "100ms"
        }
    )

    settings = client.indices.get_settings(
        index="studies_v3"
    )

    threshold = settings["studies_v3"]["settings"]["index"]["search"]["slowlog"]["threshold"]["query"]["warn"]

    print("Configured slow log threshold:", threshold)

finally:
    client.close()