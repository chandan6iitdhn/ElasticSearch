from app.db_client import get_db_connection


def test_connection():
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]

            print("PostgreSQL connected successfully!")
            print(version)

    finally:
        conn.close()


if __name__ == "__main__":
    test_connection()