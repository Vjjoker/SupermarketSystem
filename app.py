import os
from flask import Flask, render_template, request, redirect, session, flash, url_for
from auth import verify_user, register_user
from user_manage import get_all_users, search_users, add_user, delete_user, get_user_by_id, update_user
from sale_manage import (
    search_products as sales_search_products,
    create_sale,
    create_sale_order,
    get_sales_today,
    get_sales_week,
    get_sales_by_date_range,
    get_sales_order_summary_by_date_range,
    get_today_stats,
    get_salesperson_profit_by_date_range,
    get_top_products_today,
    get_all_sales_stats_by_date_range,
    get_all_sales_top_products_by_date_range,
    get_total_sales_by_date_range,
    get_total_profit_by_date_range,
    get_salesperson_rank,
    get_salesperson_leaderboard,
    get_champion_info
)
from datetime import datetime
# from product_manage import get_all_products, add_product, update_product, delete_product
# 找到这一行并修改
from product_manage import (
    get_all_products,
    search_products as manager_search_products,
    add_product,
    update_product,
    delete_product,
    get_inventory_stats,
    ensure_product_schema
)
from db_conn import get_conn

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = verify_user(username, password)

        if user:
            session['user_id'] = user[0]
            session['role'] = user[1]

            if user[1] == 'admin':
                return redirect('/admin')
            elif user[1] == 'manager':
                return redirect('/manager')
            else:
                return redirect('/sales')

        return render_template('login.html', error="用户名或密码错误")

    return render_template('login.html')


@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect('/')
    keyword = request.args.get('keyword', '').strip()
    if keyword:
        users = search_users(keyword)
    else:
        users = get_all_users()
    return render_template('admin_dashboard.html', users=users, keyword=keyword)


@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add_user():
    if session.get('role') != 'admin':
        return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        real_name = request.form['real_name']
        success, msg = add_user(username, password, role, real_name)
        if success:
            flash(msg, 'success')
            return redirect('/admin')
        else:
            flash(msg, 'danger')
            return render_template('admin_add.html', username=username, role=role, real_name=real_name)
    return render_template('admin_add.html')


@app.route('/admin/edit/<int:user_id>', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if session.get('role') != 'admin':
        return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        real_name = request.form['real_name']
        password = request.form.get('password', '')
        success, msg = update_user(user_id, username, role, real_name, password)
        if success:
            flash(msg, 'success')
            return redirect('/admin')
        else:
            flash(msg, 'danger')
            user = (user_id, username, real_name, role)
            return render_template('admin_edit.html', user=user)
    user = get_user_by_id(user_id)
    if not user:
        flash('用户不存在', 'danger')
        return redirect('/admin')
    return render_template('admin_edit.html', user=user)


@app.route('/admin/delete/<int:user_id>')
def admin_delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect('/')
    success, msg = delete_user(user_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect('/admin')


# ========== 成员C 负责模块：超市管理员 (商品增删改查) ==========
@app.route('/manager')
def manager():
    # 1. 权限拦截
    if session.get('role') != 'manager':
        return redirect('/')

    ensure_product_schema()

    # 2. 获取搜索关键词
    keyword = request.args.get('keyword', '').strip()

    # 3. 根据关键词获取商品列表
    if keyword:
        products = manager_search_products(keyword)
    else:
        products = get_all_products()

    # 4. 获取仪表盘统计数据 (总品种, 预警数, 总价值)
    stats = get_inventory_stats()

    today_str = datetime.now().strftime('%Y-%m-%d')
    current_profit_stats = get_total_profit_by_date_range(today_str, today_str)

    # 5. 获取欢迎语姓名
    real_name = session.get('real_name', '超市主管')

    return render_template('manager_dashboard.html',
                           products=products,
                           stats=stats,
                           current_profit_stats=current_profit_stats,
                           real_name=real_name,
                           keyword=keyword)


@app.route('/manager/add_product', methods=['POST'])
def manager_add_product():
    if session.get('role') != 'manager':
        return redirect('/')

    code = request.form['code']
    name = request.form['name']
    manufacturer = request.form['manufacturer']
    purchase_price = request.form['purchase_price']
    sale_price = request.form['sale_price']
    add_stock = request.form['add_stock']
    manager_id = session.get('user_id')

    success, msg = add_product(
        code, name, manufacturer, purchase_price, sale_price, add_stock, manager_id
    )
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect('/manager')


@app.route('/manager/edit_product/<int:product_id>', methods=['POST'])
def manager_edit_product(product_id):
    if session.get('role') != 'manager':
        return redirect('/')

    purchase_price = request.form['purchase_price']
    sale_price = request.form['sale_price']
    add_stock = request.form['add_stock']
    manager_id = session.get('user_id')

    success, msg = update_product(
        product_id, purchase_price, sale_price, add_stock, manager_id
    )
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect('/manager')


@app.route('/manager/delete_product/<int:product_id>')
def manager_delete_product(product_id):
    if session.get('role') != 'manager':
        return redirect('/')

    success, msg = delete_product(product_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect('/manager')


# =========================================================

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    # 权限检查
    if session.get('role') != 'sales':
        return redirect('/')

    salesperson_id = session.get('user_id')
    print(f"DEBUG: salesperson_id = {salesperson_id}")  # 添加调试输出
    print(f"DEBUG: session = {session}")  # 添加调试输出

    cart = session.get('sales_cart', [])

    # ========== 处理销售下单（POST） ==========
    if request.method == 'POST':
        action = request.form.get('action', 'add_to_cart')

        if action == 'add_to_cart':
            product_id = request.form.get('product_id')
            quantity = request.form.get('quantity')

            if not product_id or not quantity:
                flash("请选择商品并输入数量", "danger")
                return redirect('/sales')

            try:
                product_id = int(product_id)
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError

                existing = next((item for item in cart if item['product_id'] == product_id), None)
                if existing:
                    existing['quantity'] += quantity
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT name, sale_price
                        FROM public.products
                        WHERE product_id = %s
                        """,
                        (product_id,)
                    )
                    row = cur.fetchone()
                    cur.close()
                    conn.close()
                    if not row:
                        flash("商品不存在", "danger")
                        return redirect('/sales')
                    cart.append({
                        'product_id': product_id,
                        'product_name': row[0],
                        'sale_price': float(row[1]),
                        'quantity': quantity
                    })

                session['sales_cart'] = cart
                flash("商品已加入当前订单", "success")
            except ValueError:
                flash("数量必须是大于 0 的整数", "danger")

        elif action == 'remove_from_cart':
            product_id = request.form.get('product_id')
            try:
                product_id = int(product_id)
                cart = [item for item in cart if item['product_id'] != product_id]
                session['sales_cart'] = cart
                flash("商品已从当前订单移除", "success")
            except (TypeError, ValueError):
                flash("移除商品失败", "danger")

        elif action == 'checkout':
            if not cart:
                flash("当前订单为空，请先加入商品", "danger")
                return redirect('/sales')

            success, msg, order_summary = create_sale_order(cart, salesperson_id)
            if success:
                session['last_sale'] = order_summary
                session.pop('sales_cart', None)
                flash(
                    f"{msg}，订单号：{order_summary['order_no']}，总金额：{order_summary['total_price']:.2f}",
                    "success"
                )
            else:
                flash(msg, "danger")

        return redirect('/sales')

    # ========== GET 请求：处理搜索和筛选 ==========
    # 1. 获取筛选参数
    filter_type = request.args.get('filter', 'today')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    from datetime import timedelta
    today = datetime.now().date()
    start = end = today

    if filter_type == 'today':
        start = end = today
        records = get_sales_by_date_range(salesperson_id, start, end)
    elif filter_type == 'week':
        monday = today - timedelta(days=today.weekday())
        start = monday
        end = today
        records = get_sales_by_date_range(salesperson_id, start, end)
    elif filter_type == 'custom' and start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        records = get_sales_by_date_range(salesperson_id, start, end)
    else:
        records = get_sales_today(salesperson_id)

    # 2. 统计数据
    # ① 今日统计（固定）
    today_amount, today_orders, today_cost, today_profit = get_today_stats(salesperson_id)

    # ② 当前筛选统计（用于列表/图表）
    total_amount, total_orders = today_amount, today_orders
    total_profit = today_profit

    profit_stats = get_salesperson_profit_by_date_range(salesperson_id, start, end)
    order_summaries = get_sales_order_summary_by_date_range(salesperson_id, start, end)
    if profit_stats:
        total_amount = profit_stats[0]
        total_orders = profit_stats[1]
        total_profit = profit_stats[3]

    # 3. 排行榜
    today = datetime.now().date()
    top_products = get_top_products_today(salesperson_id, today, today, limit=3)

    # 4. 商品搜索
    keyword = request.args.get('keyword', '').strip()
    products = sales_search_products(keyword) if keyword else sales_search_products('')

    sales_week = get_sales_by_date_range(salesperson_id, start, end)

    # 5. 取出小票信息（消费掉，避免重复弹窗）
    last_sale = session.pop('last_sale', None)
    cart = session.get('sales_cart', [])
    cart_total = sum(item['sale_price'] * item['quantity'] for item in cart)

    return render_template(
        'sales_dashboard.html',
        products=products,
        keyword=keyword,
        sales_records=records,
        order_summaries=order_summaries,
        sales_cart=cart,
        cart_total=cart_total,
        sales_week=sales_week,
        filter_type=filter_type,
        start_date=start_date,
        end_date=end_date,
        total_amount=total_amount,
        total_orders=total_orders,
        total_profit=total_profit,
        top_products=top_products,
        last_sale=last_sale  # ← 关键：传给小票弹窗脚本
    )


# ========== 新增：超市主管销售统计看板 ==========
@app.route('/manager/sales_stats')
def manager_sales_stats():
    if session.get('role') != 'manager':
        return redirect('/')

    # 获取筛选参数
    filter_type = request.args.get('filter', 'today')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    from datetime import timedelta
    today = datetime.now().date()

    # 根据筛选类型计算日期范围
    if filter_type == 'today':
        start_date = end_date = today.strftime('%Y-%m-%d')
    elif filter_type == 'week':
        monday = today - timedelta(days=today.weekday())
        start_date = monday.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif filter_type == 'custom' and start_date and end_date:
        pass  # 使用传入的日期
    else:
        start_date = end_date = today.strftime('%Y-%m-%d')

    # 获取统计数据
    total_stats = get_total_sales_by_date_range(start_date, end_date)
    profit_stats = get_total_profit_by_date_range(start_date, end_date)
    sales_stats = get_all_sales_stats_by_date_range(start_date, end_date)
    top_products = get_all_sales_top_products_by_date_range(start_date, end_date)

    # 计算总销售额和总订单数
    total_sales = total_stats[0] if total_stats else 0
    total_orders = total_stats[1] if total_stats else 0
    total_cost = profit_stats[1] if profit_stats else 0
    total_profit = profit_stats[2] if profit_stats else 0

    return render_template('manager_sales_stats.html',
                           filter_type=filter_type,
                           start_date=start_date,
                           end_date=end_date,
                           total_sales=total_sales,
                           total_cost=total_cost,
                           total_profit=total_profit,
                           total_orders=total_orders,
                           sales_stats=sales_stats,
                           top_products=top_products)


# ========== 新增：销售人员个人看板（含排行榜） ==========
@app.route('/sales/leaderboard')
def sales_leaderboard():
    if session.get('role') != 'sales':
        return redirect('/')

    salesperson_id = session.get('user_id')

    # 获取筛选参数
    filter_type = request.args.get('filter', 'today')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    from datetime import timedelta
    today = datetime.now().date()

    # 根据筛选类型计算日期范围
    if filter_type == 'today':
        start_date = end_date = today.strftime('%Y-%m-%d')
    elif filter_type == 'week':
        monday = today - timedelta(days=today.weekday())
        start_date = monday.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif filter_type == 'custom' and start_date and end_date:
        pass
    else:
        start_date = end_date = today.strftime('%Y-%m-%d')

    # 获取该销售人员的排名和个人销售额
    rank_info = get_salesperson_rank(salesperson_id, start_date, end_date)
    my_rank = rank_info[0] if rank_info else 0
    my_sales = rank_info[1] if rank_info else 0
    my_profit_stats = get_salesperson_profit_by_date_range(salesperson_id, start_date, end_date)
    my_orders = my_profit_stats[1] if my_profit_stats else 0
    my_cost = my_profit_stats[2] if my_profit_stats else 0
    my_profit = my_profit_stats[3] if my_profit_stats else 0

    # 获取排行榜
    leaderboard = get_salesperson_leaderboard(start_date, end_date, limit=10)

    # 获取销冠
    champion = get_champion_info(start_date, end_date)

    # 获取该销售人员自己的销售记录
    my_records = get_sales_by_date_range(salesperson_id, start_date, end_date)

    return render_template('sales_leaderboard.html',
                           filter_type=filter_type,
                           start_date=start_date,
                           end_date=end_date,
                           my_rank=my_rank,
                           my_sales=my_sales,
                           my_orders=my_orders,
                           my_cost=my_cost,
                           my_profit=my_profit,
                           leaderboard=leaderboard,
                           champion=champion,
                           my_records=my_records)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
