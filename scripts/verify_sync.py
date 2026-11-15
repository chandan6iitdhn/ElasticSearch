from app.es_client import get_es_client


def verify_sync():
    client = get_es_client()

    try:
        result = client.get(
            index="studies_v3",
            id="ST_SYNC_TEST_001"
        )

        print("Document found in Elasticsearch")
        print("Document:", result["_source"])

    finally:
        client.close()


if __name__ == "__main__":
    verify_sync()