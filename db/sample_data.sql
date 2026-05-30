-- 密码：123456（MD5）
INSERT INTO users (username, password, role, real_name) VALUES
('admin', 'e10adc3949ba59abbe56e057f20f883e', 'admin', '系统管理员'),
('manager1', 'e10adc3949ba59abbe56e057f20f883e', 'manager', '管理员A'),
('sales1', 'e10adc3949ba59abbe56e057f20f883e', 'sales', '销售员A');

INSERT INTO products (code, name, manufacturer, price, stock) VALUES
('1001', '可口可乐', 'Coca-Cola', 3.5, 100),
('1002', '矿泉水', '农夫山泉', 2.0, 200);