from db_conn import get_conn
import psycopg2.extras

_SCHEMA_READY = False


def ensure_product_schema():
    """为旧数据库补齐主管模块需要的新字段和进货记录表。"""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'products'
              AND column_name = 'purchase_price'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.products
                ADD COLUMN purchase_price DECIMAL(10,2) NOT NULL DEFAULT 0
            """)

        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'products'
              AND column_name = 'sale_price'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.products
                ADD COLUMN sale_price DECIMAL(10,2)
            """)

        cursor.execute("""
            UPDATE public.products
            SET sale_price = price
            WHERE sale_price IS NULL
        """)
        cursor.execute("""
            ALTER TABLE public.products
            ALTER COLUMN sale_price SET NOT NULL
        """)
        cursor.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'stock_in_records'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
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
                )
            """)

        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'sales'
              AND column_name = 'unit_cost'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.sales
                ADD COLUMN unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0
            """)

        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'sales'
              AND column_name = 'total_cost'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.sales
                ADD COLUMN total_cost DECIMAL(10,2) NOT NULL DEFAULT 0
            """)

        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'sales'
              AND column_name = 'total_profit'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.sales
                ADD COLUMN total_profit DECIMAL(10,2) NOT NULL DEFAULT 0
            """)

        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'sales'
              AND column_name = 'order_no'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE public.sales
                ADD COLUMN order_no VARCHAR(64)
            """)

        cursor.execute("""
            UPDATE public.sales s
            SET unit_cost = COALESCE(p.purchase_price, 0),
                total_cost = COALESCE(p.purchase_price, 0) * s.quantity,
                total_profit = s.total_price - COALESCE(p.purchase_price, 0) * s.quantity
            FROM public.products p
            WHERE s.product_id = p.product_id
              AND (
                  s.unit_cost = 0
                  OR s.total_cost = 0
                  OR s.total_profit = 0
              )
        """)
        cursor.execute("""
            UPDATE public.sales
            SET order_no = 'LEGACY-' || sale_id::text
            WHERE order_no IS NULL OR order_no = ''
        """)
        conn.commit()
        _SCHEMA_READY = True
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def get_all_products():
    """获取所有在售商品列表，并附带利润信息。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT
            product_id,
            code,
            name,
            manufacturer,
            purchase_price,
            sale_price,
            stock,
            (sale_price - purchase_price) AS unit_profit
        FROM public.products
        WHERE is_active = TRUE
        ORDER BY created_at DESC
    """)
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return products


def search_products(keyword):
    """主管端商品搜索，返回与商品列表一致的数据结构。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    like = f"%{keyword.strip()}%"
    cursor.execute("""
        SELECT
            product_id,
            code,
            name,
            manufacturer,
            purchase_price,
            sale_price,
            stock,
            (sale_price - purchase_price) AS unit_profit
        FROM public.products
        WHERE is_active = TRUE
          AND (name ILIKE %s OR code ILIKE %s OR manufacturer ILIKE %s)
        ORDER BY created_at DESC
    """, (like, like, like))
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return products


def _create_stock_in_record(cursor, product_id, add_stock, purchase_price, sale_price, manager_id):
    unit_profit = sale_price - purchase_price
    total_profit = unit_profit * add_stock
    cursor.execute("""
        INSERT INTO public.stock_in_records (
            product_id, add_quantity, purchase_price, sale_price,
            unit_profit, total_profit, manager_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (product_id, add_stock, purchase_price, sale_price, unit_profit, total_profit, manager_id))
    return unit_profit, total_profit


def add_product(code, name, manufacturer, purchase_price, sale_price, add_stock, manager_id):
    """新增商品；若条码已存在，则按补货处理。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        purchase_price = float(purchase_price)
        sale_price = float(sale_price)
        add_stock = int(add_stock)

        if add_stock <= 0:
            return False, "本次上架数量必须大于 0"
        if purchase_price < 0 or sale_price < 0:
            return False, "价格不能为负数"

        cursor.execute("""
            SELECT product_id, name, stock
            FROM public.products
            WHERE code = %s
            FOR UPDATE
        """, (code,))
        existing = cursor.fetchone()

        if existing:
            product_id = existing["product_id"]
            new_stock = existing["stock"] + add_stock
            cursor.execute("""
                UPDATE public.products
                SET name = %s,
                    manufacturer = %s,
                    purchase_price = %s,
                    sale_price = %s,
                    price = %s,
                    stock = %s,
                    is_active = TRUE
                WHERE product_id = %s
            """, (name, manufacturer, purchase_price, sale_price, sale_price, new_stock, product_id))
            unit_profit, _ = _create_stock_in_record(
                cursor, product_id, add_stock, purchase_price, sale_price, manager_id
            )
            conn.commit()
            return True, (
                f"商品 {name} 上架成功，本次新增 {add_stock} 件，"
                f"当前库存 {new_stock} 件，单件利润 {unit_profit:.2f} 元"
            )

        cursor.execute("""
            INSERT INTO public.products (
                code, name, manufacturer, price, purchase_price, sale_price, stock
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING product_id
        """, (code, name, manufacturer, sale_price, purchase_price, sale_price, add_stock))
        product_id = cursor.fetchone()["product_id"]
        unit_profit, _ = _create_stock_in_record(
            cursor, product_id, add_stock, purchase_price, sale_price, manager_id
        )
        conn.commit()
        return True, (
            f"商品 {name} 上架成功，本次新增 {add_stock} 件，"
            f"当前库存 {add_stock} 件，单件利润 {unit_profit:.2f} 元"
        )
    except ValueError:
        conn.rollback()
        return False, "请输入合法的价格和数量"
    except Exception as e:
        conn.rollback()
        return False, f"上架失败：{str(e)}"
    finally:
        cursor.close()
        conn.close()


def update_product(product_id, purchase_price, sale_price, add_stock, manager_id):
    """修改进货价/出货价，并按新增数量补货，不直接覆盖总库存。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        purchase_price = float(purchase_price)
        sale_price = float(sale_price)
        add_stock = int(add_stock)

        if add_stock < 0:
            return False, "本次补货数量不能小于 0"
        if purchase_price < 0 or sale_price < 0:
            return False, "价格不能为负数"

        cursor.execute("""
            SELECT name, stock
            FROM public.products
            WHERE product_id = %s
            FOR UPDATE
        """, (product_id,))
        product = cursor.fetchone()
        if not product:
            return False, "商品不存在"

        old_stock = product["stock"]
        new_stock = old_stock + add_stock
        cursor.execute("""
            UPDATE public.products
            SET purchase_price = %s,
                sale_price = %s,
                price = %s,
                stock = %s
            WHERE product_id = %s
        """, (purchase_price, sale_price, sale_price, new_stock, product_id))

        unit_profit = sale_price - purchase_price
        if add_stock > 0:
            _create_stock_in_record(
                cursor, product_id, add_stock, purchase_price, sale_price, manager_id
            )

        conn.commit()
        return True, (
            f"商品 {product['name']} 已更新，"
            f"本次新增 {add_stock} 件，当前库存 {new_stock} 件，单件利润 {unit_profit:.2f} 元"
        )
    except ValueError:
        conn.rollback()
        return False, "请输入合法的价格和数量"
    except Exception as e:
        conn.rollback()
        return False, f"更新失败：{str(e)}"
    finally:
        cursor.close()
        conn.close()


def delete_product(product_id):
    """逻辑下架商品。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE public.products
            SET is_active = FALSE
            WHERE product_id = %s
        """, (product_id,))
        conn.commit()
        return True, "商品已成功下架！"
    except Exception as e:
        conn.rollback()
        return False, f"下架失败：{str(e)}"
    finally:
        cursor.close()
        conn.close()


def get_inventory_stats():
    """获取主管首页库存统计。"""
    ensure_product_schema()
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_types,
                COUNT(CASE WHEN stock < 10 THEN 1 END) AS low_stock,
                COALESCE(SUM(sale_price * stock), 0) AS total_value,
                COALESCE(SUM((sale_price - purchase_price) * stock), 0) AS total_profit_potential
            FROM public.products
            WHERE is_active = TRUE
        """)
        stats = cursor.fetchone()
        return stats
    except Exception:
        return {
            'total_types': 0,
            'low_stock': 0,
            'total_value': 0,
            'total_profit_potential': 0
        }
    finally:
        cursor.close()
        conn.close()
