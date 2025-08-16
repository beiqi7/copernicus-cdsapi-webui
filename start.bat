@echo off
chcp 65001 >nul
title Copernicus Data Download System

echo ========================================
echo    Copernicus 数据下载系统启动脚本
echo ========================================
echo.

echo 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python环境，请先安装Python 3.7+
    pause
    exit /b 1
)

echo 检查依赖包...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo 安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 错误: 依赖包安装失败
        pause
        exit /b 1
    )
)

echo 创建必要的目录...
if not exist "downloads" mkdir downloads

echo 启动应用...
echo 应用将在 http://localhost:5000 启动
echo 按 Ctrl+C 停止应用
echo.

python run.py

pause 