import os
import psycopg2

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=os.environ.get("PG_PORT", 5432),
        database=os.environ.get("PG_DATABASE", "mydatabase"),
        user=os.environ.get("PG_USERNAME", "myuser"),
        password=os.environ.get("PG_PASSWORD", "mypassword"),
        connect_timeout=10
    )
    return conn