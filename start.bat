@echo off
chcp 65001 > nul
echo ========================================
echo   超市商品销售管理系统 启动中...
echo ========================================
echo.

echo 1. 检查 Docker 容器...
docker ps | find "opengauss" > nul
if errorlevel 1 (
    echo 启动 openGauss 容器...
    docker start opengauss
    timeout /t 5 /nobreak > nul
) else (
    echo openGauss 容器已在运行
)

echo.
echo 2. 等待数据库就绪...
timeout /t 2 /nobreak > nul

echo.
echo 3. 启动 Flask 应用...
echo.
echo ========================================
echo   系统启动成功！
echo   请在浏览器中访问: http://127.0.0.1:5000
echo   按 Ctrl+C 可停止系统
echo ========================================
echo.

cd /d D:\数据库实训\SupermarketSystem
.venv\Scripts\python app.py

pause