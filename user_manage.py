from db_conn import get_conn
from auth import encrypt_password


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, real_name, role, created_at FROM public.users ORDER BY user_id"
    )
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


def search_users(keyword):
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{keyword}%"

    
    cur.execute(
        "SELECT user_id, username, real_name, role, created_at FROM public.users "
        "WHERE username ILIKE %s OR real_name ILIKE %s OR role ILIKE %s ORDER BY user_id",
        (like, like, like)
    )
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


def add_user(username, password, role, real_name):
    conn = get_conn()
    cur = conn.cursor()
    md5_password = encrypt_password(password)
    try:
        cur.execute(
            "INSERT INTO public.users (username, password, role, real_name) VALUES (%s, %s, %s, %s)",
            (username.strip(), md5_password, role, real_name.strip())
        )
        conn.commit()
        return True, "添加成功"
    except Exception as e:
        conn.rollback()
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            return False, "用户名已存在"
        return False, f"添加失败: {e}"
    finally:
        cur.close()
        conn.close()


def delete_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM public.users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return False, "用户不存在"
        if user[0] == 'admin':
            return False, "不能删除管理员账号"
        cur.execute("DELETE FROM public.users WHERE user_id = %s", (user_id,))
        conn.commit()
        return True, "删除成功"
    except Exception as e:
        conn.rollback()
        return False, f"删除失败: {e}"
    finally:
        cur.close()
        conn.close()


def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, real_name, role FROM public.users WHERE user_id = %s",
        (user_id,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def update_user(user_id, username, role, real_name, password=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if password and password.strip():
            md5_password = encrypt_password(password)
            cur.execute(
                "UPDATE public.users SET username=%s, role=%s, real_name=%s, password=%s WHERE user_id=%s",
                (username.strip(), role, real_name.strip(), md5_password, user_id)
            )
        else:
            cur.execute(
                "UPDATE public.users SET username=%s, role=%s, real_name=%s WHERE user_id=%s",
                (username.strip(), role, real_name.strip(), user_id)
            )
        conn.commit()
        return True, "修改成功"
    except Exception as e:
        conn.rollback()
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            return False, "用户名已存在"
        return False, f"修改失败: {e}"
    finally:
        cur.close()
        conn.close()
