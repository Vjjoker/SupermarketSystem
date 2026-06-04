import psycopg2

def get_conn():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="15432",
            dbname="supermarket",
            user="appuser",            # 临时改为 omm
            password="123456St$" # 这里需要填你容器启动时设置的密码
        )
        return conn
    except Exception as e:
        print(f"Error: 无法连接。详情: {e}")
        return None