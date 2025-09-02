#!/usr/bin/env python3
"""
简化版启动脚本 - 快速启动Copernicus CDS API WebUI
"""

import os
import sys
import subprocess

def main():
    print("🚀 启动Copernicus CDS API WebUI...")
    
    # 检查配置文件
    if not os.path.exists('config.py'):
        print("❌ 配置文件不存在，请先运行 setup_and_run.py 进行配置")
        return
    
    # 检查启动文件
    if os.path.exists('enhanced_era5.py'):
        print("✅ 使用增强版本启动...")
        subprocess.run([sys.executable, 'enhanced_era5.py'])
    elif os.path.exists('era5.py'):
        print("✅ 使用标准版本启动...")
        subprocess.run([sys.executable, 'era5.py'])
    else:
        print("❌ 未找到启动文件")
        print("请确保 enhanced_era5.py 或 era5.py 存在")

if __name__ == '__main__':
    main()
