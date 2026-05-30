from datetime import datetime, timedelta
from uuid import uuid4

from db_conn import get_conn
from product_manage import ensure_product_schema


def search_products(keyword):
    """按名称/条码/厂商搜索可售商品。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{keyword.strip()}%"
    cur.execute(
        """
        SELECT product_id, code, name, manufacturer, sale_price, stock
        FROM public.products
        WHERE is_active = TRUE
          AND (name ILIKE %s OR code ILIKE %s OR manufacturer ILIKE %s)
        ORDER BY product_id
        """,
        (like, like, like)
    )
    products = cur.fetchall()
    cur.close()
    conn.close()
    return products


def _fetch_product_for_sale(cur, product_id):
    cur.execute(
        """
        SELECT product_id, name, sale_price, purchase_price, stock
        FROM public.products
        WHERE product_id = %s
        FOR UPDATE
        """,
        (product_id,)
    )
    return cur.fetchone()


def create_sale(product_id, quantity, salesperson_id):
    """兼容旧调用：单商品成交仍记为一笔订单。"""
    cart_items = [{'product_id': product_id, 'quantity': quantity}]
    success, msg, order_summary = create_sale_order(cart_items, salesperson_id)
    total_price = order_summary['total_price'] if order_summary else 0
    return success, msg, total_price


def create_sale_order(cart_items, salesperson_id):
    """将购物车中的多件商品一次性结算为一笔订单。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        normalized_items = []
        merged = {}

        for item in cart_items:
            product_id = int(item['product_id'])
            quantity = int(item['quantity'])
            if quantity <= 0:
                return False, "商品数量必须大于 0", None
            merged[product_id] = merged.get(product_id, 0) + quantity

        if not merged:
            return False, "购物车不能为空", None

        order_no = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
        total_price = 0
        total_cost = 0
        total_profit = 0
        receipt_items = []

        for product_id, quantity in merged.items():
            product = _fetch_product_for_sale(cur, product_id)
            if not product:
                return False, "存在已失效商品，请重新选择", None

            _, product_name, sale_price, purchase_price, stock = product
            if quantity > stock:
                return False, f"商品 {product_name} 库存不足，当前库存为 {stock}", None

            new_stock = stock - quantity
            cur.execute(
                "UPDATE public.products SET stock = %s WHERE product_id = %s",
                (new_stock, product_id)
            )

            item_total_price = sale_price * quantity
            item_total_cost = purchase_price * quantity
            item_total_profit = item_total_price - item_total_cost

            cur.execute(
                """
                INSERT INTO public.sales (
                    product_id, quantity, total_price, salesperson_id,
                    unit_cost, total_cost, total_profit, order_no
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    product_id, quantity, item_total_price, salesperson_id,
                    purchase_price, item_total_cost, item_total_profit, order_no
                )
            )

            total_price += item_total_price
            total_cost += item_total_cost
            total_profit += item_total_profit
            normalized_items.append((product_id, quantity))
            receipt_items.append({
                'product_name': product_name,
                'quantity': quantity,
                'subtotal': float(item_total_price)
            })

        conn.commit()
        return True, "订单结算成功", {
            'order_no': order_no,
            'items': receipt_items,
            'total_price': float(total_price),
            'total_cost': float(total_cost),
            'total_profit': float(total_profit),
            'item_count': sum(item['quantity'] for item in receipt_items),
            'product_count': len(receipt_items),
            'sale_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except ValueError:
        conn.rollback()
        return False, "请输入合法的商品和数量", None
    except Exception as e:
        conn.rollback()
        return False, f"销售失败: {e}", None
    finally:
        cur.close()
        conn.close()


def get_sales_today(salesperson_id):
    """查询当前销售员全部销售记录。"""
    return get_sales_by_date_range(
        salesperson_id,
        datetime.now().date().strftime('%Y-%m-%d'),
        datetime.now().date().strftime('%Y-%m-%d')
    )


def get_sales_week(salesperson_id):
    """查询当前销售员本周销售记录。"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return get_sales_by_date_range(salesperson_id, monday, today)


def get_sales_by_date_range(salesperson_id, start_date=None, end_date=None):
    """按时间范围查询销售明细，保留商品行级记录。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            s.sale_id,
            p.name,
            s.quantity,
            s.total_price,
            s.sale_time,
            s.order_no,
            s.total_profit
        FROM public.sales s
        JOIN public.products p ON s.product_id = p.product_id
        WHERE s.salesperson_id = %s
          AND s.sale_time >= %s::date
          AND s.sale_time < %s::date + INTERVAL '1 day'
        ORDER BY s.sale_time DESC, s.sale_id DESC
        """,
        (salesperson_id, start_date, end_date)
    )
    records = cur.fetchall()
    cur.close()
    conn.close()
    return records


def get_sales_order_summary_by_date_range(salesperson_id, start_date, end_date):
    """按订单汇总，供订单数和订单列表展示。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            s.order_no,
            MIN(s.sale_time) AS sale_time,
            COUNT(*) AS line_count,
            SUM(s.quantity) AS total_quantity,
            SUM(s.total_price) AS total_price,
            SUM(s.total_profit) AS total_profit
        FROM public.sales s
        WHERE s.salesperson_id = %s
          AND s.sale_time >= %s::date
          AND s.sale_time < %s::date + INTERVAL '1 day'
        GROUP BY s.order_no
        ORDER BY sale_time DESC
        """,
        (salesperson_id, start_date, end_date)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_today_stats(salesperson_id):
    """统计当前销售员今日营业额、订单数、利润。"""
    today = datetime.now().date().strftime('%Y-%m-%d')
    return get_salesperson_profit_by_date_range(salesperson_id, today, today)


def get_salesperson_profit_by_date_range(salesperson_id, start_date, end_date):
    """统计销售员在指定范围内的营业额、订单数、成本、利润。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COALESCE(SUM(total_price), 0) AS total_sales,
            COUNT(DISTINCT order_no) AS total_orders,
            COALESCE(SUM(total_cost), 0) AS total_cost,
            COALESCE(SUM(total_profit), 0) AS total_profit
        FROM public.sales
        WHERE salesperson_id = %s
          AND sale_time >= %s::date
          AND sale_time < %s::date + INTERVAL '1 day'
        """,
        (salesperson_id, start_date, end_date)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result  # (total_sales, total_orders, total_cost, total_profit)


def get_top_products_today(salesperson_id, start_date, end_date, limit=3):
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.name, SUM(s.quantity) AS total_qty
        FROM public.sales s
        JOIN public.products p ON s.product_id = p.product_id
        WHERE s.salesperson_id = %s
          AND s.sale_time >= %s::date
          AND s.sale_time < %s::date + INTERVAL '1 day'
        GROUP BY p.product_id, p.name
        ORDER BY total_qty DESC
        LIMIT %s
        """,
        (salesperson_id, start_date, end_date, limit)
    )
    top = cur.fetchall()
    cur.close()
    conn.close()
    return top


def get_all_sales_stats_by_date_range(start_date, end_date):
    """查询所有销售员在指定范围内的销售额统计。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.user_id,
            u.real_name,
            u.username,
            COALESCE(SUM(s.total_price), 0) AS total_sales,
            COUNT(DISTINCT s.order_no) AS order_count
        FROM public.users u
        LEFT JOIN public.sales s ON u.user_id = s.salesperson_id
            AND s.sale_time >= %s::date
            AND s.sale_time < %s::date + INTERVAL '1 day'
        WHERE u.role = 'sales'
        GROUP BY u.user_id, u.real_name, u.username
        ORDER BY total_sales DESC
        """,
        (start_date, end_date)
    )
    stats = cur.fetchall()
    cur.close()
    conn.close()
    return stats


def get_all_sales_top_products_by_date_range(start_date, end_date, limit=5):
    """查询所有销售员在指定范围内的畅销商品排行。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.name, SUM(s.quantity) AS total_quantity, SUM(s.total_price) AS total_sales
        FROM public.sales s
        JOIN public.products p ON s.product_id = p.product_id
        WHERE s.sale_time >= %s::date
          AND s.sale_time < %s::date + INTERVAL '1 day'
        GROUP BY p.product_id, p.name
        ORDER BY total_quantity DESC
        LIMIT %s
        """,
        (start_date, end_date, limit)
    )
    top = cur.fetchall()
    cur.close()
    conn.close()
    return top


def get_total_sales_by_date_range(start_date, end_date):
    """查询指定日期范围内的总销售额和总订单数。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COALESCE(SUM(total_price), 0) AS total_sales,
            COUNT(DISTINCT order_no) AS total_orders
        FROM public.sales
        WHERE sale_time >= %s::date
          AND sale_time < %s::date + INTERVAL '1 day'
        """,
        (start_date, end_date)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def get_total_profit_by_date_range(start_date, end_date):
    """查询指定日期范围内的总营业额、总成本、总利润。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            COALESCE(SUM(total_price), 0) AS total_sales,
            COALESCE(SUM(total_cost), 0) AS total_cost,
            COALESCE(SUM(total_profit), 0) AS total_profit
        FROM public.sales
        WHERE sale_time >= %s::date
          AND sale_time < %s::date + INTERVAL '1 day'
        """,
        (start_date, end_date)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def get_salesperson_rank(salesperson_id, start_date, end_date):
    """获取指定销售员的营业额排名。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        WITH sales_rank AS (
            SELECT
                u.user_id,
                COALESCE(SUM(s.total_price), 0) AS total_sales,
                RANK() OVER (ORDER BY COALESCE(SUM(s.total_price), 0) DESC) AS rank
            FROM public.users u
            LEFT JOIN public.sales s ON u.user_id = s.salesperson_id
                AND s.sale_time >= %s::date
                AND s.sale_time < %s::date + INTERVAL '1 day'
            WHERE u.role = 'sales'
            GROUP BY u.user_id
        )
        SELECT rank, total_sales
        FROM sales_rank
        WHERE user_id = %s
        """,
        (start_date, end_date, salesperson_id)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def get_salesperson_leaderboard(start_date, end_date, limit=10):
    """获取销售排行榜，按营业额排序。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.user_id,
            u.real_name,
            u.username,
            COALESCE(SUM(s.total_price), 0) AS total_sales,
            COUNT(DISTINCT s.order_no) AS order_count,
            RANK() OVER (ORDER BY COALESCE(SUM(s.total_price), 0) DESC) AS rank
        FROM public.users u
        LEFT JOIN public.sales s ON u.user_id = s.salesperson_id
            AND s.sale_time >= %s::date
            AND s.sale_time < %s::date + INTERVAL '1 day'
        WHERE u.role = 'sales'
        GROUP BY u.user_id, u.real_name, u.username
        ORDER BY total_sales DESC
        LIMIT %s
        """,
        (start_date, end_date, limit)
    )
    leaderboard = cur.fetchall()
    cur.close()
    conn.close()
    return leaderboard


def get_champion_info(start_date, end_date):
    """获取销冠信息，仍以营业额为准。"""
    ensure_product_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.user_id,
            u.real_name,
            u.username,
            COALESCE(SUM(s.total_price), 0) AS total_sales,
            COUNT(DISTINCT s.order_no) AS order_count
        FROM public.users u
        LEFT JOIN public.sales s ON u.user_id = s.salesperson_id
            AND s.sale_time >= %s::date
            AND s.sale_time < %s::date + INTERVAL '1 day'
        WHERE u.role = 'sales'
        GROUP BY u.user_id, u.real_name, u.username
        ORDER BY total_sales DESC
        LIMIT 1
        """,
        (start_date, end_date)
    )
    champion = cur.fetchone()
    cur.close()
    conn.close()
    return champion
