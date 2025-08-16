#!/usr/bin/env python3
"""
Copernicus Data Download Application
启动脚本
"""

import os
import sys
from era5 import app, download_manager

def main():
    """主函数"""
    # 设置环境变量
    env = os.environ.get('FLASK_ENV', 'development')
    
    print(f"启动 Copernicus 数据下载系统...")
    print(f"环境: {env}")
    print(f"下载目录: {app.config.get('DOWNLOAD_DIR', 'downloads')}")
    print(f"清理间隔: {app.config.get('CLEANUP_INTERVAL', 300)} 秒")
    
    try:
        # 启动应用
        app.run(
            host=app.config.get('HOST', '0.0.0.0'),
            port=int(app.config.get('PORT', 5000)),
            debug=app.config.get('DEBUG', False)
        )
    except KeyboardInterrupt:
        print("\n正在关闭应用...")
        # 清理资源
        if hasattr(download_manager, 'cleanup_expired_files'):
            download_manager.cleanup_expired_files()
        print("应用已关闭")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 