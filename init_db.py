from db_conn import get_conn
from auth import encrypt_password  # 🤫 偷偷借用队友写好的加密函数


def setup_database():
    # 获取加密后的密码，完美配合队友的 auth.py
    encrypted_admin_pwd = encrypt_password('admin123')

    sql_commands = """
    -- 强行加上 public. 前缀，确保建在队友指定的房间里
    DROP TABLE IF EXISTS public.stock_in_records CASCADE;
    DROP TABLE IF EXISTS public.sales CASCADE;
    DROP TABLE IF EXISTS public.products CASCADE;
    DROP TABLE IF EXISTS public.users CASCADE;

    CREATE TABLE public.users (
        user_id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL,
        real_name VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE public.products (
        product_id SERIAL PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        manufacturer VARCHAR(100),
        price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
        purchase_price DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
        sale_price DECIMAL(10,2) NOT NULL CHECK (sale_price >= 0),
        stock INT DEFAULT 0 CHECK (stock >= 0),
        is_active BOOLEAN DEFAULT TRUE,  -- ✅ 新增：逻辑删除标记，TRUE表示在售，FALSE表示下架
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE public.sales (
        sale_id SERIAL PRIMARY KEY,
        product_id INT REFERENCES public.products(product_id),
        quantity INT NOT NULL CHECK (quantity > 0),
        total_price DECIMAL(10,2) NOT NULL,
        salesperson_id INT REFERENCES public.users(user_id),
        sale_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE public.stock_in_records (
        record_id SERIAL PRIMARY KEY,
        product_id INT REFERENCES public.products(product_id),
        add_quantity INT NOT NULL CHECK (add_quantity > 0),
        purchase_price DECIMAL(10,2) NOT NULL CHECK (purchase_price >= 0),
        sale_price DECIMAL(10,2) NOT NULL CHECK (sale_price >= 0),
        unit_profit DECIMAL(10,2) NOT NULL,
        total_profit DECIMAL(10,2) NOT NULL,
        manager_id INT REFERENCES public.users(user_id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    conn = get_conn()
    cursor = conn.cursor()

    try:
        print(">>> 正在执行建表指令 (写入 public 模式)...")
        cursor.execute(sql_commands)

        print(">>> 正在写入初始数据 (包含 MD5 加密密码)...")
        # 用参数化的方式，把加密后的密码塞进去
        insert_user_sql = """
        INSERT INTO public.users (username, password, role, real_name) 
        VALUES ('admin', %s, 'admin', '超级系统管理员');
        """
        cursor.execute(insert_user_sql, (encrypted_admin_pwd,))

        insert_product_sql = """
        INSERT INTO public.products (code, name, manufacturer, price, purchase_price, sale_price, stock)
        VALUES ('1001', '草莓味Hello Kitty软糖', '三丽鸥工坊', 15.50, 10.00, 15.50, 100);
        """
        cursor.execute(insert_product_sql)

        conn.commit()
        print("✅ 恭喜！数据库初始化彻底完成！请去运行 app.py 吧！")
    except Exception as e:
        print(f"❌ 糟糕，发生了错误: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    setup_database()
