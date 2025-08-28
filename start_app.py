#!/usr/bin/env python3
"""
Copernicus Data Download Application
全新启动脚本 - 避免重复启动问题
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime, timedelta
import json
import uuid
import shutil

def main():
    """主函数"""
    print("启动 Copernicus 数据下载系统...")
    
    # 设置环境变量
    env = os.environ.get('FLASK_ENV', 'development')
    print(f"环境: {env}")
    
    try:
        # 导入配置
        from config import config
        app_config = config[env]
        
        print(f"下载目录: {app_config.DOWNLOAD_DIR}")
        print(f"清理间隔: {app_config.CLEANUP_INTERVAL} 秒")
        print(f"服务器地址: http://{app_config.HOST}:{app_config.PORT}")
        
        # 配置日志
        logging.basicConfig(
            filename='era5_app.log', 
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 确保下载目录存在
        os.makedirs(app_config.DOWNLOAD_DIR, exist_ok=True)
        
        # 导入Flask应用
        from era5 import app, DownloadManager, initialize_app
        
        # 初始化应用
        initialize_app()
        
        # 创建下载管理器实例
        app.download_manager = DownloadManager()
        
        # 启动清理线程
        app.download_manager.start_cleanup_thread()
        
        # 启动应用
        print("应用启动中...")
        app.run(
            host=app_config.HOST,
            port=app_config.PORT,
            debug=app_config.DEBUG
        )
        
    except KeyboardInterrupt:
        print("\n正在关闭应用...")
        print("应用已关闭")
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main() 