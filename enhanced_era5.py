#!/usr/bin/env python3
"""
Enhanced Copernicus Data Download Application
增强版 ERA5 数据下载应用，集成了所有安全和健壮性改进
"""

from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session, g
try:
    import cdsapi
    CDSAPI_AVAILABLE = True
except ImportError as e:
    import logging
    logging.warning(f"cdsapi 导入失败: {e}")
    CDSAPI_AVAILABLE = False

import threading
import time
import logging
import os
import hashlib
import uuid
import gc
import weakref
import atexit
from datetime import datetime, timedelta
import shutil
from werkzeug.utils import secure_filename
import json
from config import config
from collections import deque

# 导入增强模块
from error_handler import (
    create_error_handlers, ValidationError, DownloadError, RateLimitError, 
    SystemError, retry_on_failure, safe_execute, CircuitBreaker, log_performance
)
from input_validator import InputValidator, SecurityValidator
from enhanced_logging import setup_logging_for_app, enhanced_logger
from security_manager import SecurityManager, create_security_headers_middleware


def create_enhanced_app():
    """创建增强的Flask应用"""
    # 获取环境配置
    try:
        env = os.environ.get('FLASK_ENV', 'development')
        app_config = config[env]
    except Exception as e:
        from config import DevelopmentConfig
        app_config = DevelopmentConfig()
    
    app = Flask(__name__)
    app.config.from_object(app_config)
    
    # 配置应用目录
    app.DOWNLOAD_DIR = app_config.DOWNLOAD_DIR
    app.TEMP_LINKS_FILE = app_config.TEMP_LINKS_FILE
    app.DOWNLOAD_INDEX_FILE = getattr(app_config, 'DOWNLOAD_INDEX_FILE', 'download_index.json')
    app.CLEANUP_INTERVAL = app_config.CLEANUP_INTERVAL
    
    # 初始化安全管理器
    security_manager = SecurityManager(secret_key=app.config['SECRET_KEY'])
    security_manager.init_app(app)
    app.security_manager = security_manager
    
    # 设置安全头
    create_security_headers_middleware(app)
    
    # 设置错误处理器
    create_error_handlers(app)
    
    # 设置增强日志
    app.enhanced_logger = setup_logging_for_app(app)
    
    return app


# 创建应用实例
app = create_enhanced_app()


class EnhancedRateLimiter:
    """增强的限流器，带有更好的错误处理"""
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.ip_to_timestamps = {}
        self._lock = threading.RLock()

    def allow(self, identifier: str):
        now = time.time()
        try:
            with self._lock:
                dq = self.ip_to_timestamps.get(identifier)
                if dq is None:
                    dq = deque()
                    self.ip_to_timestamps[identifier] = dq
                
                # 清理过期时间戳
                cutoff = now - self.window_seconds
                while dq and dq[0] < cutoff:
                    dq.popleft()
                
                if len(dq) < self.max_requests:
                    dq.append(now)
                    return True, 0
                
                # 计算等待时间
                retry_after = max(0, int(self.window_seconds - (now - dq[0])))
                return False, retry_after
        except Exception as e:
            logging.error(f"限流器错误: {e}")
            return True, 0  # 出错时允许通过


def _get_client_identifier():
    """获取客户端标识符（更安全的方式）"""
    try:
        # 优先取代理头
        forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if forwarded_for and SecurityValidator.validate_ip_address(forwarded_for):
            return forwarded_for
        
        real_ip = request.headers.get('X-Real-IP', '').strip()
        if real_ip and SecurityValidator.validate_ip_address(real_ip):
            return real_ip
        
        remote_addr = request.remote_addr
        if remote_addr and SecurityValidator.validate_ip_address(remote_addr):
            return remote_addr
        
        return 'unknown'
    except Exception:
        return 'unknown'


# 初始化增强限流器
try:
    if not hasattr(app, 'rate_limiter'):
        app.rate_limiter = EnhancedRateLimiter(max_requests=2, window_seconds=60)
except Exception as e:
    logging.error(f"初始化限流器失败: {e}")


@app.before_request
def enhanced_rate_limit():
    """增强的限流检查"""
    try:
        if request.method == 'POST' and request.endpoint == 'index':
            if hasattr(app, 'rate_limiter'):
                client_id = _get_client_identifier()
                allowed, retry_after = app.rate_limiter.allow(client_id)
                
                if not allowed:
                    # 记录限流事件
                    if hasattr(app, 'security_manager'):
                        app.security_manager.log_security_event('rate_limit', {
                            'client_ip': client_id,
                            'retry_after': retry_after
                        })
                    
                    raise RateLimitError(
                        '请求过于频繁：单用户每分钟最多2次，请稍后重试',
                        retry_after=retry_after
                    )
    except RateLimitError:
        raise
    except Exception as e:
        logging.error(f"限流检查失败: {e}")


def get_enhanced_download_manager():
    """安全地获取下载管理器实例"""
    if hasattr(app, 'download_manager') and app.download_manager:
        return app.download_manager
    raise SystemError("下载管理器未初始化", component="DownloadManager")


def initialize_enhanced_app():
    """初始化增强应用配置"""
    env = os.environ.get('FLASK_ENV', 'development')
    
    # 配置结构化日志
    logging.basicConfig(
        level=logging.INFO if env == 'production' else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('era5_app_enhanced.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 确保下载目录存在
    try:
        os.makedirs(app.DOWNLOAD_DIR, exist_ok=True)
        logging.info(f"下载目录已创建/确认: {app.DOWNLOAD_DIR}")
    except Exception as e:
        logging.error(f"创建下载目录失败: {e}")
        raise SystemError(f"无法创建下载目录: {e}", component="FileSystem")


# 增强的下载管理器
class EnhancedDownloadManager:
    """增强的下载管理器，包含更好的资源管理和错误处理"""
    
    def __init__(self):
        self.temp_links = self.load_temp_links()
        self.cleanup_thread = None
        self.download_index = self.load_download_index()
        self._active_downloads = weakref.WeakSet()
        self._lock = threading.RLock()
        self._shutdown_flag = threading.Event()
        self._memory_check_interval = 60
        self._max_memory_usage = 1024 * 1024 * 1024  # 1GB
        self._last_gc_time = time.time()
        self._error_count = 0
        self._max_errors = 10
    
    @retry_on_failure(max_retries=3, delay=1)
    def load_temp_links(self):
        """加载临时链接信息（带重试）"""
        try:
            if os.path.exists(app.TEMP_LINKS_FILE):
                with open(app.TEMP_LINKS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 验证数据格式
                    if isinstance(data, dict):
                        return data
                    else:
                        logging.warning("临时链接文件格式无效，重新创建")
                        return {}
        except Exception as e:
            logging.error(f"加载临时链接文件失败: {e}")
            # 备份损坏的文件
            if os.path.exists(app.TEMP_LINKS_FILE):
                backup_name = f"{app.TEMP_LINKS_FILE}.backup.{int(time.time())}"
                try:
                    shutil.copy(app.TEMP_LINKS_FILE, backup_name)
                    logging.info(f"已备份损坏的临时链接文件到: {backup_name}")
                except Exception:
                    pass
        return {}
    
    def safe_save_temp_links(self):
        """安全保存临时链接信息"""
        try:
            # 先写入临时文件
            temp_file = f"{app.TEMP_LINKS_FILE}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.temp_links, f, ensure_ascii=False, indent=2)
            
            # 原子替换
            if os.path.exists(app.TEMP_LINKS_FILE):
                backup_file = f"{app.TEMP_LINKS_FILE}.bak"
                shutil.move(app.TEMP_LINKS_FILE, backup_file)
            
            shutil.move(temp_file, app.TEMP_LINKS_FILE)
            
            # 删除备份文件
            if os.path.exists(f"{app.TEMP_LINKS_FILE}.bak"):
                os.remove(f"{app.TEMP_LINKS_FILE}.bak")
                
        except Exception as e:
            logging.error(f"保存临时链接文件失败: {e}")
            raise
    
    def load_download_index(self):
        """加载下载索引"""
        return safe_execute(
            lambda: self._load_download_index_impl(),
            default_return={},
            log_error=True
        )
    
    def _load_download_index_impl(self):
        if os.path.exists(app.DOWNLOAD_INDEX_FILE):
            with open(app.DOWNLOAD_INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def cleanup_expired_files(self):
        """清理过期文件和内存优化"""
        current_time = datetime.now()
        expired_links = []
        
        try:
            with self._lock:
                for link_id, link_info in list(self.temp_links.items()):
                    try:
                        expiry_time = datetime.fromisoformat(link_info['expires_at'])
                        
                        if (current_time > expiry_time or 
                            link_info['download_count'] >= link_info['max_downloads']):
                            
                            expired_links.append(link_id)
                            self._safe_remove_file(link_info['file_path'], link_info['filename'])
                            
                    except Exception as e:
                        logging.error(f"处理链接 {link_id} 时发生错误: {e}")
                        expired_links.append(link_id)
                
                # 移除过期链接
                for link_id in expired_links:
                    self.temp_links.pop(link_id, None)
                
                if expired_links:
                    self.safe_save_temp_links()
                    logging.info(f"清理了 {len(expired_links)} 个过期链接")
            
            # 执行内存清理
            self._perform_memory_cleanup()
            
        except Exception as e:
            self._error_count += 1
            logging.error(f"清理过程中发生错误: {e}")
            
            if self._error_count > self._max_errors:
                logging.critical("清理错误次数过多，停止清理线程")
                self._shutdown_flag.set()
    
    def _safe_remove_file(self, file_path: str, filename: str):
        """安全删除文件"""
        try:
            if os.path.exists(file_path):
                if SecurityValidator.validate_file_path(file_path, app.DOWNLOAD_DIR):
                    os.remove(file_path)
                    logging.info(f"删除过期文件: {filename}")
                else:
                    logging.error(f"安全检查失败，拒绝删除文件: {file_path}")
        except Exception as e:
            logging.error(f"删除文件失败 {filename}: {e}")
    
    def _perform_memory_cleanup(self):
        """执行内存清理"""
        current_time = time.time()
        if current_time - self._last_gc_time > self._memory_check_interval:
            try:
                # 执行垃圾回收
                collected = gc.collect()
                if collected > 0:
                    logging.debug(f"垃圾回收清理了 {collected} 个对象")
                
                self._last_gc_time = current_time
                
            except Exception as e:
                logging.error(f"内存清理失败: {e}")
    
    def start_cleanup_thread(self):
        """启动增强的清理线程"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        try:
            def enhanced_cleanup_loop():
                logging.info("增强清理线程已启动")
                while not self._shutdown_flag.is_set():
                    try:
                        self.cleanup_expired_files()
                        self._shutdown_flag.wait(timeout=app.CLEANUP_INTERVAL)
                    except Exception as e:
                        logging.error(f"清理线程错误: {e}")
                        self._shutdown_flag.wait(timeout=app.CLEANUP_INTERVAL)
                
                logging.info("清理线程已安全关闭")
            
            self.cleanup_thread = threading.Thread(
                target=enhanced_cleanup_loop, 
                daemon=True, 
                name="EnhancedCleanupThread"
            )
            self.cleanup_thread.start()
            
        except Exception as e:
            logging.error(f"启动清理线程失败: {e}")
            raise SystemError(f"无法启动清理线程: {e}", component="DownloadManager")
    
    def shutdown(self):
        """优雅关闭下载管理器"""
        logging.info("正在关闭增强下载管理器...")
        self._shutdown_flag.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=10)
            if self.cleanup_thread.is_alive():
                logging.warning("清理线程未能在规定时间内关闭")
        
        # 最后一次清理
        safe_execute(self.cleanup_expired_files, log_error=True)
        logging.info("增强下载管理器已关闭")


# 应用初始化
try:
    initialize_enhanced_app()
    if not hasattr(app, 'download_manager') or app.download_manager is None:
        app.download_manager = EnhancedDownloadManager()
        app.download_manager.start_cleanup_thread()
        logging.info("增强下载管理器已初始化")
        
        # 注册关闭处理器
        def cleanup_on_exit():
            if hasattr(app, 'download_manager'):
                app.download_manager.shutdown()
        
        atexit.register(cleanup_on_exit)
        
except Exception as e:
    logging.error(f"增强应用初始化失败: {e}")
    raise


# 其他路由和功能保持与原文件相同，但使用增强的组件
@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    try:
        env = os.environ.get('FLASK_ENV', 'development')
        from config import config
        app_config = config[env]
        
        print(f"启动增强版 Copernicus 数据下载系统...")
        print(f"环境: {env}")
        print(f"下载目录: {app_config.DOWNLOAD_DIR}")
        print(f"服务器地址: http://{app_config.HOST}:{app_config.PORT}")
        
        app.run(
            host=app_config.HOST,
            port=app_config.PORT,
            debug=app_config.DEBUG,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n正在关闭应用...")
        if hasattr(app, 'download_manager'):
            app.download_manager.shutdown()
        print("应用已关闭")
    except Exception as e:
        print(f"启动失败: {e}")
        import sys
        sys.exit(1)
