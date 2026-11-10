import time
from elasticsearch import helpers
from app.es_client import get_es_client

INDEX_NAME = "studies_bulk_benchmark"


def generate_actions(total=1000):
    for i in range(total):
        yield {
            "_op_type": "index",
            "_index": INDEX_NAME,
            "_id": f"BENCH{i}",
            "_source": {
                "study_id": f"BENCH{i}",
                "title": f"Benchmark Study {i}",
                "status": "Completed"
            }
        }


def benchmark(client, chunk_size):
    start = time.perf_counter()

    success, errors = helpers.bulk(
        client,
        generate_actions(),
        chunk_size=chunk_size,
        raise_on_error=False
    )

    elapsed = time.perf_counter() - start

    print(f"Chunk size: {chunk_size}")
    print(f"Successful: {success}")
    print(f"Failed: {len(errors)}")
    print(f"Time: {elapsed:.3f} seconds")
    print("---")


def main():
    client = get_es_client()

    try:
        for chunk_size in [100, 500, 1000]:
            benchmark(client, chunk_size)
    finally:
        client.close()


if __name__ == "__main__":
    main()