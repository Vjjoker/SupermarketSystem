import os
import psycopg2


def get_conn():
    try:
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "15432"),
                dbname=os.getenv("DB_NAME", "supermarket"),
                user=os.getenv("DB_USER", "appuser"),
                password=os.getenv("DB_PASSWORD", "123456St$")
            )

        return conn
    except Exception as e:
        print(f"Error: 无法连接。详情: {e}")
        return None