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


def download_ecmwf_data(params, op_id=None):
    """下载ECMWF数据（增强版）"""
    if not CDSAPI_AVAILABLE:
        raise SystemError("cdsapi 不可用，无法下载数据", component="CDS API")
    
    try:
        # 记录下载开始
        if hasattr(app, 'logger'):
            app.logger.info(f"开始下载数据: op_id={op_id}")
        
        c = cdsapi.Client()
        dataset = "reanalysis-era5-pressure-levels"
        
        # 设置当前操作 ID 用于进度跟踪
        if op_id:
            app.current_op_id = op_id
        
        result = c.retrieve(dataset, params)
        
        # 生成安全的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{params['pressure_level'][0]}_{params['year'][0]}_{params['month'][0]}_{params['day'][0]}_{timestamp}.nc"
        filename = InputValidator.sanitize_filename(base_filename)
        file_path = os.path.join(app.DOWNLOAD_DIR, filename)
        
        # 验证文件路径安全性
        if not SecurityValidator.validate_file_path(file_path, app.DOWNLOAD_DIR):
            raise ValidationError("文件路径不安全", field="file_path", value=file_path)
        
        # 下载文件
        result.download(file_path)
        
        # 获取文件大小并验证
        if not os.path.exists(file_path):
            raise DownloadError("下载的文件不存在", operation="file_check")
        
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # 验证文件大小
        if file_size_bytes == 0:
            os.remove(file_path)  # 删除空文件
            raise DownloadError("下载的文件为空", operation="file_validation")
        
        # 记录成功
        logging.info(f"数据下载成功: {filename}, 大小: {file_size_mb:.2f}MB")
        
        if hasattr(app, 'performance_monitor'):
            app.performance_monitor.record_metric('download_size_mb', file_size_mb)
        
        return filename, file_size_mb
        
    except Exception as e:
        logging.error(f"API调用失败: {e}")
        if isinstance(e, (ValidationError, DownloadError, SystemError)):
            raise
        raise DownloadError(f"ECMWF API 调用失败: {str(e)}", operation="api_call", params=params)


def download_with_timeout(params, op_id=None):
    """带超时的下载"""
    result = [None, None]
    
    def target():
        result[0], result[1] = download_ecmwf_data(params, op_id)
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=300)  # 5分钟超时
    
    if thread.is_alive():
        logging.warning("下载超时")
        return None, None
    
    return result[0], result[1]


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


# 进度管理器
class ProgressManager:
    """简单的内存进度管理器，key 为 op_id"""
    def __init__(self):
        self.op_to_progress = {}
        self.op_to_status = {}
        self.op_to_request_id = {}
    
    def init(self, op_id: str):
        self.op_to_progress[op_id] = 0
        self.op_to_status[op_id] = 'submitted'
        self.op_to_request_id[op_id] = None
    
    def set_status(self, op_id: str, status: str):
        self.op_to_status[op_id] = status
        # 将状态映射到大致百分比下限
        mapping = {
            'submitted': 1,
            'accepted': 10,
            'running': 35,
            'successful': 90,
            'failed': 100
        }
        base = mapping.get(status, 1)
        current = self.op_to_progress.get(op_id, 0)
        self.op_to_progress[op_id] = max(current, base)
    
    def set_fraction(self, op_id: str, frac: float):
        # frac: 0.0 - 1.0（例如 0.48）
        pct = int(max(0, min(100, round(frac * 100))))
        current = self.op_to_progress.get(op_id, 0)
        self.op_to_progress[op_id] = max(current, pct)
    
    def complete(self, op_id: str):
        self.op_to_status[op_id] = 'successful'
        self.op_to_progress[op_id] = 100
    
    def set_request_id(self, op_id: str, request_id: str):
        self.op_to_request_id[op_id] = request_id
    
    def get(self, op_id: str):
        return {
            'progress': self.op_to_progress.get(op_id, 0),
            'status': self.op_to_status.get(op_id, 'unknown'),
            'request_id': self.op_to_request_id.get(op_id)
        }

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
    
    def generate_temp_link(self, filename, file_size_mb):
        """生成临时下载链接"""
        # 生成唯一ID
        link_id = str(uuid.uuid4())
        
        # 根据文件大小确定过期时间
        expiry_hours = self.get_expiry_hours(file_size_mb)
        expiry_time = datetime.now() + timedelta(hours=expiry_hours)
        
        # 创建临时链接信息
        temp_link = {
            'filename': filename,
            'file_path': os.path.join(app.DOWNLOAD_DIR, filename),
            'file_size_mb': file_size_mb,
            'created_at': datetime.now().isoformat(),
            'expires_at': expiry_time.isoformat(),
            'download_count': 0,
            'max_downloads': 5  # 最多下载5次
        }
        
        self.temp_links[link_id] = temp_link
        self.safe_save_temp_links()
        
        return link_id, expiry_hours
    
    def get_expiry_hours(self, file_size_mb):
        """根据文件大小获取过期时间"""
        # 文件大小阈值和过期时间配置（单位：小时）
        file_size_thresholds = {
            'tiny': {'max_size_mb': 10, 'expiry_hours': 2},        # 小于10MB，2小时过期
            'small': {'max_size_mb': 50, 'expiry_hours': 4},       # 10-50MB，4小时过期
            'medium': {'max_size_mb': 200, 'expiry_hours': 8},     # 50-200MB，8小时过期
            'large': {'max_size_mb': 500, 'expiry_hours': 12},     # 200-500MB，12小时过期
            'xlarge': {'max_size_mb': 1000, 'expiry_hours': 24},  # 500MB-1GB，24小时过期
            'huge': {'max_size_mb': float('inf'), 'expiry_hours': 48}  # 大于1GB，48小时过期
        }
        
        for category, config in file_size_thresholds.items():
            if file_size_mb <= config['max_size_mb']:
                return config['expiry_hours']
        return file_size_thresholds['xlarge']['expiry_hours']
    
    def is_link_valid(self, link_id):
        """检查链接是否有效"""
        if link_id not in self.temp_links:
            return False
        
        link_info = self.temp_links[link_id]
        
        # 检查是否过期
        expiry_time = datetime.fromisoformat(link_info['expires_at'])
        if datetime.now() > expiry_time:
            return False
        
        # 检查下载次数
        if link_info['download_count'] >= link_info['max_downloads']:
            return False
        
        # 检查文件是否存在
        if not os.path.exists(link_info['file_path']):
            return False
        
        return True
    
    def increment_download_count(self, link_id):
        """增加下载次数"""
        if link_id in self.temp_links:
            self.temp_links[link_id]['download_count'] += 1
            self.safe_save_temp_links()
    
    def check_cached(self, params: dict):
        """检查缓存"""
        sig = self._signature_for_params(params)
        info = self.download_index.get(sig)
        if not info:
            return None
        path = info.get('file_path')
        if path and os.path.exists(path):
            return info
        return None
    
    def add_to_cache(self, params: dict, filename: str, file_size_mb: float):
        """添加到缓存"""
        sig = self._signature_for_params(params)
        record = {
            'filename': filename,
            'file_path': os.path.join(app.DOWNLOAD_DIR, filename),
            'file_size_mb': file_size_mb,
            'created_at': datetime.now().isoformat()
        }
        self.download_index[sig] = record
        self.save_download_index()
    
    def _signature_for_params(self, params: dict) -> str:
        # 生成与下载影响相关的签名（与顺序无关）
        keys = ['product_type','variable','pressure_level','year','month','day','time','area','data_format']
        norm = {}
        for k in keys:
            v = params.get(k)
            if isinstance(v, list):
                norm[k] = sorted(v)
            else:
                norm[k] = v
        payload = json.dumps(norm, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def save_download_index(self):
        """保存下载索引"""
        try:
            with open(app.DOWNLOAD_INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.download_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存下载索引失败: {e}")
    
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
    
    # 初始化进度管理器
    if not hasattr(app, 'progress_manager'):
        app.progress_manager = ProgressManager()
        logging.info("进度管理器已初始化")
    
    # 初始化下载管理器
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
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_time = time.time()
        client_ip = getattr(app, 'security_manager', type('obj', (object,), {'get_client_ip': lambda: request.remote_addr})).get_client_ip()
        
        try:
            # 验证输入参数
            form_data = {
                'product_type': request.form.getlist('product_type'),
                'variable': request.form.getlist('variable'),
                'pressure_level': request.form.getlist('pressure_level'),
                'year': request.form.getlist('year'),
                'month': request.form.getlist('month'),
                'day': request.form.getlist('day'),
                'time': request.form.getlist('time'),
                'north': request.form.get('north'),
                'south': request.form.get('south'),
                'west': request.form.get('west'),
                'east': request.form.get('east'),
                'op_id': request.form.get('op_id') or f"op_{uuid.uuid4().hex[:12]}"
            }
            
            # 使用增强的输入验证
            validated_params = InputValidator.validate_download_params(form_data)
            
            op_id = validated_params['op_id']
            app.current_op_id = op_id
            
            # 初始化进度管理
            if hasattr(app, 'progress_manager'):
                app.progress_manager.init(op_id)
                app.progress_manager.set_status(op_id, 'submitted')
            
            # 记录下载请求
            if hasattr(app, 'logger'):
                enhanced_logger.log_download_start(validated_params, op_id)
            
            logging.info(f"开始下载数据: op_id={op_id}, client_ip={client_ip}")
            
            # 下载前先查缓存
            download_mgr = get_enhanced_download_manager()
            if download_mgr:
                cached = download_mgr.check_cached(validated_params)
                if cached:
                    # 命中缓存，直接生成临时链接
                    link_id, expiry_hours = download_mgr.generate_temp_link(cached['filename'], cached['file_size_mb'])
                    download_url = url_for('download_file', link_id=link_id)
                    return jsonify({
                        'success': True,
                        'message': '命中缓存，已生成下载链接。',
                        'download_url': download_url,
                        'filename': cached['filename'],
                        'file_size_mb': round(cached['file_size_mb'], 2),
                        'expiry_hours': expiry_hours,
                        'link_id': link_id,
                        'op_id': op_id,
                        'request_id': getattr(app.progress_manager, 'op_to_request_id', {}).get(op_id)
                    })

            # 下载文件（传递 op_id 用于进度跟踪）
            downloaded_file, file_size_mb = download_with_timeout(validated_params, op_id)

            if downloaded_file is None:
                raise DownloadError("下载失败，请检查参数或稍后重试", operation="download_timeout")

            # 写入缓存
            if download_mgr:
                download_mgr.add_to_cache(validated_params, downloaded_file, file_size_mb)

            # 生成临时下载链接
            download_mgr = get_enhanced_download_manager()
            if not download_mgr:
                return jsonify({
                    'success': False,
                    'message': '系统未正确初始化'
                }), 500
            link_id, expiry_hours = download_mgr.generate_temp_link(downloaded_file, file_size_mb)
            
            # 生成下载链接
            download_url = url_for('download_file', link_id=link_id)
            
            # 记录下载完成
            duration = time.time() - start_time
            if hasattr(app, 'logger'):
                enhanced_logger.log_download_complete(op_id, downloaded_file, file_size_mb, duration)

            return jsonify({
                'success': True,
                'message': '数据下载完成！',
                'download_url': download_url,
                'filename': downloaded_file,
                'file_size_mb': round(file_size_mb, 2),
                'expiry_hours': expiry_hours,
                'link_id': link_id,
                'op_id': op_id,
                'request_id': getattr(app.progress_manager, 'op_to_request_id', {}).get(op_id)
            })

        except (ValidationError, DownloadError, RateLimitError, SystemError) as e:
            # 特定异常类型由错误处理器处理
            if hasattr(app, 'logger'):
                enhanced_logger.log_error(e, {'op_id': locals().get('op_id'), 'client_ip': client_ip})
            raise
        except Exception as e:
            # 未预期的异常
            logging.error(f"处理请求时发生未知错误: {e}")
            if hasattr(app, 'logger'):
                enhanced_logger.log_error(e, {'op_id': locals().get('op_id'), 'client_ip': client_ip})
            raise SystemError(f"处理请求时发生错误: {str(e)}", component="request_handler")

    return render_template('index.html')

@app.route('/api/progress/<op_id>')
def get_progress(op_id):
    """查询进度接口"""
    try:
        if hasattr(app, 'progress_manager'):
            return jsonify(app.progress_manager.get(op_id))
        else:
            return jsonify({'progress': 0, 'status': 'unknown'})
    except Exception as e:
        logging.error(f"获取进度失败: {e}")
        return jsonify({'progress': 0, 'status': 'error'})

@app.route('/download/<link_id>')
def download_file(link_id):
    """通过临时链接下载文件"""
    try:
        download_mgr = get_enhanced_download_manager()
        if not download_mgr.is_link_valid(link_id):
            return render_template('error.html', 
                                 message="下载链接已过期或无效",
                                 details="链接可能已过期、达到最大下载次数，或文件已被删除"), 410
        
        link_info = download_mgr.temp_links[link_id]
        
        # 增加下载次数
        download_mgr.increment_download_count(link_id)
        
        # 发送文件
        return send_file(
            link_info['file_path'],
            as_attachment=True,
            download_name=link_info['filename']
        )
    except Exception as e:
        logging.error(f"下载文件失败: {e}")
        return render_template('error.html', 
                             message="下载失败",
                             details="文件下载过程中发生错误"), 500

@app.route('/api/check_link/<link_id>')
def check_link_status(link_id):
    """检查链接状态"""
    try:
        download_mgr = get_enhanced_download_manager()
        if link_id not in download_mgr.temp_links:
            return jsonify({'valid': False, 'message': '链接不存在'})
        
        link_info = download_mgr.temp_links[link_id]
        is_valid = download_mgr.is_link_valid(link_id)
        
        if is_valid:
            expiry_time = datetime.fromisoformat(link_info['expires_at'])
            remaining_time = expiry_time - datetime.now()
            remaining_hours = max(0, remaining_time.total_seconds() / 3600)
            
            return jsonify({
                'valid': True,
                'filename': link_info['filename'],
                'file_size_mb': link_info['file_size_mb'],
                'remaining_hours': round(remaining_hours, 1),
                'download_count': link_info['download_count'],
                'max_downloads': link_info['max_downloads']
            })
        else:
            return jsonify({
                'valid': False,
                'message': '链接已过期或达到最大下载次数'
            })
    except Exception as e:
        logging.error(f"检查链接状态失败: {e}")
        return jsonify({'valid': False, 'message': '检查失败'})

@app.route('/error')
def error():
    return render_template('error.html', 
                         message="发生错误",
                         details="请检查您的请求或稍后重试"), 500


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
