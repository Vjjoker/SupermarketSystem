from db_conn import get_conn
import hashlib


def encrypt_password(password):
    return hashlib.md5(password.strip().encode('utf-8')).hexdigest()


def verify_user(username, password):
    conn = get_conn()
    cur = conn.cursor()

    username = username.strip()
    md5_password = encrypt_password(password)

    cur.execute(
        "SELECT user_id, role FROM public.users WHERE username=%s AND password=%s",
        (username, md5_password)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user


# auth.py 增加以下内容
def register_user(username, password, role, real_name):
    conn = get_conn()
    cur = conn.cursor()

    # 密码加密存储
    md5_password = encrypt_password(password)

    try:
        cur.execute(
            "INSERT INTO public.users (username, password, role, real_name) VALUES (%s, %s, %s, %s)",
            (username.strip(), md5_password, role, real_name)
        )
        conn.commit()
        success = True
    except Exception as e:
        print(f"注册失败: {e}")
        conn.rollback()
        success = False
    finally:
        cur.close()
        conn.close()
    return success