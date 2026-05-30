-- 创建数据库（如果已创建可忽略）
-- CREATE DATABASE supermarket;

-- 用户信息表：存储员工账号、MD5加密密码及角色权限
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    real_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 商品信息表：记录超市库存及条码信息
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE,
    name VARCHAR(100),
    manufacturer VARCHAR(100),
    price DECIMAL(10,2),
    stock INT DEFAULT 0 CHECK (stock >= 0),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 销售记录表：关联用户与商品，记录每笔交易明细
CREATE TABLE IF NOT EXISTS sales (
    sale_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    quantity INT NOT NULL,
    total_price DECIMAL(10,2),
    salesperson_id INT REFERENCES users(user_id),
    sale_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);