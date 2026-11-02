import os
from elasticsearch import Elasticsearch

def get_es_client():
    client = Elasticsearch(hosts=[os.environ["ES_URL"]],
                           basic_auth=(os.environ["ES_USERNAME"], os.environ["ES_PASSWORD"]),
                           ca_certs=os.environ["ES_CA_CERT"],
                           request_timeout=10
                           )
    return client