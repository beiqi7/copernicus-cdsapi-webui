#!/bin/bash

# Copernicus Data Download System Startup Script
# Linux/Mac 启动脚本

set -e

echo "========================================"
echo "   Copernicus 数据下载系统启动脚本"
echo "========================================"
echo

# 检查Python环境
echo "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3环境，请先安装Python 3.7+"
    exit 1
fi

python3 --version

# 检查依赖包
echo "检查依赖包..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "安装依赖包..."
    pip3 install -r requirements.txt
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p downloads

# 设置权限
chmod +x run.py
chmod +x test_app.py

# 启动应用
echo "启动应用..."
echo "应用将在 http://localhost:5000 启动"
echo "按 Ctrl+C 停止应用"
echo

python3 run.py 