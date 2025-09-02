#!/usr/bin/env python3
"""
快速修复脚本 - 解决Copernicus CDS API WebUI的常见问题
"""

import os
import sys
import shutil
import json

def fix_cds_api_config():
    """修复CDS API配置问题"""
    print("🔧 修复CDS API配置...")
    
    if not os.path.exists('config.py'):
        print("❌ 配置文件不存在")
        return False
    
    try:
        # 读取配置文件
        with open('config.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否包含CDS API配置
        if 'CDS_API_UID' not in content or 'CDS_API_KEY' not in content:
            print("⚠️ 配置文件中缺少CDS API配置")
            print("请手动编辑config.py添加以下配置：")
            print("CDS_API_UID = 'your-uid-here'")
            print("CDS_API_KEY = 'your-api-key-here'")
            return False
        
        print("✅ CDS API配置检查通过")
        return True
        
    except Exception as e:
        print(f"❌ 检查配置文件失败: {e}")
        return False

def fix_download_directory():
    """修复下载目录"""
    print("📁 修复下载目录...")
    
    try:
        os.makedirs('downloads', exist_ok=True)
        print("✅ 下载目录已创建/确认")
        return True
    except Exception as e:
        print(f"❌ 创建下载目录失败: {e}")
        return False

def fix_temp_files():
    """修复临时文件"""
    print("🗂️ 清理临时文件...")
    
    temp_files = ['temp_links.json', 'download_index.json']
    for file in temp_files:
        if os.path.exists(file):
            try:
                # 备份损坏的文件
                backup_name = f"{file}.backup.{int(os.path.getmtime(file))}"
                shutil.move(file, backup_name)
                print(f"✅ 已备份损坏文件: {file} -> {backup_name}")
            except Exception as e:
                print(f"⚠️ 备份文件失败: {file} - {e}")
    
    # 创建新的空文件
    for file in temp_files:
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            print(f"✅ 创建新文件: {file}")
        except Exception as e:
            print(f"❌ 创建文件失败: {file} - {e}")

def check_dependencies():
    """检查依赖"""
    print("📦 检查依赖...")
    
    required_packages = ['flask', 'cdsapi']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️ 缺失依赖: {', '.join(missing_packages)}")
        print("请运行以下命令安装：")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    print("🔧 Copernicus CDS API WebUI 快速修复工具")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 请先安装缺失的依赖")
        return
    
    # 修复CDS API配置
    if not fix_cds_api_config():
        print("\n❌ CDS API配置问题，请手动修复")
        return
    
    # 修复下载目录
    if not fix_download_directory():
        print("\n❌ 下载目录创建失败")
        return
    
    # 修复临时文件
    fix_temp_files()
    
    print("\n✅ 修复完成！")
    print("现在可以尝试启动应用：")
    print("python enhanced_era5.py")
    print("或")
    print("python start_simple.py")

if __name__ == '__main__':
    main()
