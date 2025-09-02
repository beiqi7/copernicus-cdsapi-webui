#!/usr/bin/env python3
"""
Copernicus CDS API WebUI 配置和启动脚本
帮助用户快速配置和启动系统
"""

import os
import sys
import json
import subprocess
import platform
from pathlib import Path

def print_banner():
    """打印欢迎横幅"""
    print("=" * 70)
    print("🌍 Copernicus CDS API WebUI 配置和启动脚本")
    print("=" * 70)
    print("本脚本将帮助您：")
    print("1. 检查系统环境")
    print("2. 配置 CDS API 密钥")
    print("3. 安装依赖")
    print("4. 启动应用")
    print("=" * 70)

def check_python_version():
    """检查Python版本"""
    print("🐍 检查Python版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python版本过低: {version.major}.{version.minor}")
        print("   需要Python 3.8或更高版本")
        return False
    print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """检查依赖"""
    print("\n📦 检查依赖...")
    required_packages = ['flask', 'cdsapi']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
            missing_packages.append(package)
    
    return missing_packages

def install_dependencies(packages):
    """安装依赖"""
    if not packages:
        return True
    
    print(f"\n📥 安装缺失的依赖: {', '.join(packages)}")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + packages)
        print("✅ 依赖安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def get_cds_credentials():
    """获取CDS API凭据"""
    print("\n🔑 配置CDS API凭据")
    print("请访问 https://cds.climate.copernicus.eu/user 获取您的API密钥")
    print("登录后点击 'API key' 标签页")
    
    uid = input("请输入您的 UID: ").strip()
    key = input("请输入您的 API Key: ").strip()
    
    if not uid or not key:
        print("❌ UID和API Key不能为空")
        return None, None
    
    return uid, key

def create_config_file(uid, key):
    """创建配置文件"""
    print("\n⚙️ 创建配置文件...")
    
    config_content = f'''import os

class Config:
    """应用配置类"""
    
    # 基本配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    
    # CDS API 配置
    CDS_API_UID = os.environ.get('CDS_API_UID') or '{uid}'
    CDS_API_KEY = os.environ.get('CDS_API_KEY') or '{key}'
    
    # 下载配置
    DOWNLOAD_DIR = 'downloads'
    TEMP_LINKS_FILE = 'temp_links.json'
    DOWNLOAD_INDEX_FILE = 'download_index.json'
    CLEANUP_INTERVAL = 300  # 5分钟清理一次
    
    # 文件大小阈值和过期时间配置（单位：小时）
    FILE_SIZE_THRESHOLDS = {{
        'tiny': {{'max_size_mb': 10, 'expiry_hours': 2}},
        'small': {{'max_size_mb': 50, 'expiry_hours': 4}},
        'medium': {{'max_size_mb': 200, 'expiry_hours': 8}},
        'large': {{'max_size_mb': 500, 'expiry_hours': 12}},
        'xlarge': {{'max_size_mb': 1000, 'expiry_hours': 24}},
        'huge': {{'max_size_mb': float('inf'), 'expiry_hours': 48}}
    }}
    
    # 下载限制
    MAX_DOWNLOADS_PER_LINK = 5
    DOWNLOAD_TIMEOUT = 300  # 5分钟超时
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'era5_app.log'
    
    # 服务器配置
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = False

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'

# 配置字典
config = {{
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}}
'''
    
    try:
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        print("✅ 配置文件创建成功")
        return True
    except Exception as e:
        print(f"❌ 配置文件创建失败: {e}")
        return False

def create_downloads_directory():
    """创建下载目录"""
    print("\n📁 创建下载目录...")
    try:
        os.makedirs('downloads', exist_ok=True)
        print("✅ 下载目录创建成功")
        return True
    except Exception as e:
        print(f"❌ 下载目录创建失败: {e}")
        return False

def test_cds_connection(uid, key):
    """测试CDS连接"""
    print("\n🔍 测试CDS API连接...")
    try:
        import cdsapi
        os.environ['CDSAPI_URL'] = 'https://cds.climate.copernicus.eu/api/v2'
        os.environ['CDSAPI_KEY'] = f"{uid}:{key}"
        
        c = cdsapi.Client()
        print("✅ CDS API连接成功")
        return True
    except Exception as e:
        print(f"❌ CDS API连接失败: {e}")
        print("请检查您的UID和API Key是否正确")
        return False

def start_application():
    """启动应用"""
    print("\n🚀 启动应用...")
    print("应用将在 http://localhost:5000 启动")
    print("按 Ctrl+C 停止应用")
    
    try:
        # 检查是否有增强版本
        if os.path.exists('enhanced_era5.py'):
            print("使用增强版本启动...")
            subprocess.run([sys.executable, 'enhanced_era5.py'])
        elif os.path.exists('era5.py'):
            print("使用标准版本启动...")
            subprocess.run([sys.executable, 'era5.py'])
        else:
            print("❌ 未找到启动文件")
            return False
    except KeyboardInterrupt:
        print("\n\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print_banner()
    
    # 检查Python版本
    if not check_python_version():
        print("\n❌ 请升级Python版本后重试")
        return
    
    # 检查依赖
    missing_packages = check_dependencies()
    if missing_packages:
        if not install_dependencies(missing_packages):
            print("\n❌ 依赖安装失败，请手动安装后重试")
            return
    
    # 检查配置文件
    if not os.path.exists('config.py'):
        print("\n📝 首次运行，需要配置CDS API")
        uid, key = get_cds_credentials()
        if not uid or not key:
            print("❌ 配置失败")
            return
        
        if not create_config_file(uid, key):
            return
        
        if not test_cds_connection(uid, key):
            return
    else:
        print("\n✅ 配置文件已存在")
        # 尝试从配置文件读取凭据进行测试
        try:
            import config
            uid = config.config['default']().CDS_API_UID
            key = config.config['default']().CDS_API_KEY
            if uid != 'your-cds-uid-here' and key != 'your-cds-api-key-here':
                if not test_cds_connection(uid, key):
                    print("❌ 配置文件中的凭据无效，请重新配置")
                    return
            else:
                print("⚠️ 配置文件中的凭据未设置，请手动编辑config.py")
        except Exception as e:
            print(f"⚠️ 读取配置文件失败: {e}")
    
    # 创建下载目录
    create_downloads_directory()
    
    # 启动应用
    start_application()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("请检查错误信息并重试")
