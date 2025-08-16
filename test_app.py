#!/usr/bin/env python3
"""
测试脚本 - 验证Copernicus数据下载应用功能
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

def test_config():
    """测试配置加载"""
    print("测试配置加载...")
    try:
        from config import config, Config
        print("✓ 配置加载成功")
        print(f"  默认环境: {Config.DOWNLOAD_DIR}")
        print(f"  清理间隔: {Config.CLEANUP_INTERVAL} 秒")
        return True
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False

def test_download_manager():
    """测试下载管理器"""
    print("\n测试下载管理器...")
    try:
        from era5 import download_manager
        print("✓ 下载管理器初始化成功")
        
        # 测试临时链接生成
        test_filename = "test_file.nc"
        test_size_mb = 150.5
        
        link_id, expiry_hours = download_manager.generate_temp_link(test_filename, test_size_mb)
        print(f"✓ 临时链接生成成功: {link_id[:8]}...")
        print(f"  过期时间: {expiry_hours} 小时")
        
        # 测试链接有效性
        is_valid = download_manager.is_link_valid(link_id)
        print(f"✓ 链接有效性检查: {is_valid}")
        
        # 清理测试数据
        if link_id in download_manager.temp_links:
            del download_manager.temp_links[link_id]
            download_manager.save_temp_links()
        
        return True
    except Exception as e:
        print(f"✗ 下载管理器测试失败: {e}")
        return False

def test_file_operations():
    """测试文件操作"""
    print("\n测试文件操作...")
    try:
        # 创建测试目录
        test_dir = "test_downloads"
        os.makedirs(test_dir, exist_ok=True)
        
        # 创建测试文件
        test_file = os.path.join(test_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("测试文件内容")
        
        # 检查文件大小
        file_size = os.path.getsize(test_file)
        file_size_mb = file_size / (1024 * 1024)
        print(f"✓ 测试文件创建成功: {file_size_mb:.6f} MB")
        
        # 清理测试文件
        os.remove(test_file)
        os.rmdir(test_dir)
        print("✓ 测试文件清理成功")
        
        return True
    except Exception as e:
        print(f"✗ 文件操作测试失败: {e}")
        return False

def test_api_endpoints():
    """测试API端点"""
    print("\n测试API端点...")
    try:
        from era5 import app
        
        with app.test_client() as client:
            # 测试主页
            response = client.get('/')
            if response.status_code == 200:
                print("✓ 主页访问成功")
            else:
                print(f"✗ 主页访问失败: {response.status_code}")
                return False
            
            # 测试错误页面
            response = client.get('/error')
            if response.status_code == 500:
                print("✓ 错误页面访问成功")
            else:
                print(f"✗ 错误页面访问失败: {response.status_code}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ API端点测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("Copernicus 数据下载应用 - 功能测试")
    print("=" * 50)
    
    tests = [
        ("配置测试", test_config),
        ("下载管理器测试", test_download_manager),
        ("文件操作测试", test_file_operations),
        ("API端点测试", test_api_endpoints)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} 通过")
            else:
                print(f"✗ {test_name} 失败")
        except Exception as e:
            print(f"✗ {test_name} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！应用准备就绪。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置。")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 