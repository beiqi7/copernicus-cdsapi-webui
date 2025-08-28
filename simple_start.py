#!/usr/bin/env python3
"""
最简单的启动方式 - 避免重复启动
"""

import os
import sys

def main():
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
        
        # 直接启动Flask应用，不导入其他模块
        from era5 import app
        app.run(
            host=app_config.HOST,
            port=app_config.PORT,
            debug=app_config.DEBUG,
            threaded=True
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