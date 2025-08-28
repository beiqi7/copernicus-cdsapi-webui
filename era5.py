from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session
try:
    import cdsapi
    CDSAPI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"cdsapi 导入失败: {e}")
    CDSAPI_AVAILABLE = False
import threading
import time
import logging
import os
import hashlib
import uuid
from datetime import datetime, timedelta
import shutil
from werkzeug.utils import secure_filename
import json
from config import config
from collections import deque

def create_app():
    """创建Flask应用的工厂函数"""
    # 获取环境配置
    try:
        env = os.environ.get('FLASK_ENV', 'development')
        app_config = config[env]
    except Exception as e:
        # 使用默认配置
        from config import DevelopmentConfig
        app_config = DevelopmentConfig()
    
    app = Flask(__name__)
    app.config.from_object(app_config)
    
    # 配置下载目录
    app.DOWNLOAD_DIR = app_config.DOWNLOAD_DIR
    app.TEMP_LINKS_FILE = app_config.TEMP_LINKS_FILE
    app.DOWNLOAD_INDEX_FILE = getattr(app_config, 'DOWNLOAD_INDEX_FILE', 'download_index.json')
    app.CLEANUP_INTERVAL = app_config.CLEANUP_INTERVAL
    
    return app

# 创建应用实例
app = create_app()

class RateLimiter:
    """简单的基于内存的滑动窗口限流器"""
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.ip_to_timestamps = {}
        self._lock = threading.Lock()

    def allow(self, identifier: str):
        now = time.time()
        with self._lock:
            dq = self.ip_to_timestamps.get(identifier)
            if dq is None:
                dq = deque()
                self.ip_to_timestamps[identifier] = dq
            # 移除窗口外的时间
            cutoff = now - self.window_seconds
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) < self.max_requests:
                dq.append(now)
                return True, 0
            # 计算还需等待的秒数（直到最早的一次离开窗口）
            retry_after = max(0, int(self.window_seconds - (now - dq[0])))
            return False, retry_after

def _client_identifier():
    # 优先取代理头（如部署在反代后），否则取 remote_addr
    ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not ip:
        ip = request.remote_addr or 'unknown'
    return ip

# 初始化限流器：每个客户端（按IP）每分钟最多2次
try:
    if not hasattr(app, 'rate_limiter'):
        app.rate_limiter = RateLimiter(max_requests=2, window_seconds=60)
except Exception as _e:
    logging.error(f"初始化限流器失败: {_e}")

@app.before_request
def apply_rate_limit():
    """仅限制提交下载的 POST / 请求"""
    try:
        if request.method == 'POST' and request.endpoint == 'index':
            allowed, retry_after = getattr(app, 'rate_limiter', None).allow(_client_identifier()) if hasattr(app, 'rate_limiter') else (True, 0)
            if not allowed:
                response = jsonify({
                    'success': False,
                    'message': '请求过于频繁：单用户每分钟最多2次，请稍后重试',
                    'retry_after': retry_after
                })
                return response, 429, {'Retry-After': str(retry_after)}
    except Exception as _e:
        # 出现异常时不阻断请求，但记录错误
        logging.error(f"限流检查失败: {_e}")
        return None

def get_download_manager():
    """安全地获取下载管理器实例"""
    if hasattr(app, 'download_manager'):
        return app.download_manager
    return None

def initialize_app():
    """初始化应用配置"""
    # 获取环境配置
    env = os.environ.get('FLASK_ENV', 'development')
    
    # 配置日志
    logging.basicConfig(
        filename='era5_app.log', 
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 确保下载目录存在
    try:
        os.makedirs(app.DOWNLOAD_DIR, exist_ok=True)
        logging.info(f"下载目录已创建/确认: {app.DOWNLOAD_DIR}")
    except Exception as e:
        logging.error(f"创建下载目录失败: {e}")
        raise

# 文件大小阈值和过期时间配置（单位：小时）
# 小文件下载快，过期时间短；大文件下载慢，给更多时间
FILE_SIZE_THRESHOLDS = {
    'tiny': {'max_size_mb': 10, 'expiry_hours': 2},        # 小于10MB，2小时过期
    'small': {'max_size_mb': 50, 'expiry_hours': 4},       # 10-50MB，4小时过期
    'medium': {'max_size_mb': 200, 'expiry_hours': 8},     # 50-200MB，8小时过期
    'large': {'max_size_mb': 500, 'expiry_hours': 12},     # 200-500MB，12小时过期
    'xlarge': {'max_size_mb': 1000, 'expiry_hours': 24},  # 500MB-1GB，24小时过期
    'huge': {'max_size_mb': float('inf'), 'expiry_hours': 48}  # 大于1GB，48小时过期
}

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

class DownloadManager:
    def __init__(self):
        self.temp_links = self.load_temp_links()
        self.cleanup_thread = None
        # 延迟启动清理线程，避免构造函数中的问题
        self.download_index = self.load_download_index()
    
    def load_temp_links(self):
        """加载临时链接信息"""
        try:
            if os.path.exists(app.TEMP_LINKS_FILE):
                with open(app.TEMP_LINKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"加载临时链接文件失败: {e}")
        return {}
    
    def save_temp_links(self):
        """保存临时链接信息"""
        try:
            with open(app.TEMP_LINKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.temp_links, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存临时链接文件失败: {e}")
    
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
        self.save_temp_links()
        
        return link_id, expiry_hours
    
    def get_expiry_hours(self, file_size_mb):
        """根据文件大小获取过期时间"""
        for category, config in FILE_SIZE_THRESHOLDS.items():
            if file_size_mb <= config['max_size_mb']:
                return config['expiry_hours']
        return FILE_SIZE_THRESHOLDS['xlarge']['expiry_hours']
    
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
            self.save_temp_links()
    
    def cleanup_expired_files(self):
        """清理过期文件"""
        current_time = datetime.now()
        expired_links = []
        
        for link_id, link_info in self.temp_links.items():
            expiry_time = datetime.fromisoformat(link_info['expires_at'])
            
            # 检查是否过期或达到最大下载次数
            if (current_time > expiry_time or 
                link_info['download_count'] >= link_info['max_downloads']):
                
                expired_links.append(link_id)
                
                # 删除文件
                try:
                    if os.path.exists(link_info['file_path']):
                        os.remove(link_info['file_path'])
                        logging.info(f"删除过期文件: {link_info['filename']}")
                except Exception as e:
                    logging.error(f"删除文件失败 {link_info['filename']}: {e}")
        
        # 从临时链接中移除
        for link_id in expired_links:
            del self.temp_links[link_id]
        
        if expired_links:
            self.save_temp_links()
            logging.info(f"清理了 {len(expired_links)} 个过期链接")
    
    def start_cleanup_thread(self):
        """启动清理线程"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return  # 线程已经在运行
        
        try:
            def cleanup_loop():
                while True:
                    try:
                        self.cleanup_expired_files()
                        time.sleep(app.CLEANUP_INTERVAL)
                    except Exception as e:
                        logging.error(f"清理线程错误: {e}")
                        time.sleep(app.CLEANUP_INTERVAL)
            
            self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
            self.cleanup_thread.start()
            logging.info("清理线程已启动")
        except Exception as e:
            logging.error(f"启动清理线程失败: {e}")
            # 不抛出异常，让应用继续运行

    def load_download_index(self):
        try:
            if os.path.exists(app.DOWNLOAD_INDEX_FILE):
                with open(app.DOWNLOAD_INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"加载下载索引失败: {e}")
        return {}
    
    def save_download_index(self):
        try:
            with open(app.DOWNLOAD_INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.download_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存下载索引失败: {e}")
    
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
        import hashlib
        payload = json.dumps(norm, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def check_cached(self, params: dict):
        sig = self._signature_for_params(params)
        info = self.download_index.get(sig)
        if not info:
            return None
        path = info.get('file_path')
        if path and os.path.exists(path):
            return info
        return None
    
    def add_to_cache(self, params: dict, filename: str, file_size_mb: float):
        sig = self._signature_for_params(params)
        record = {
            'filename': filename,
            'file_path': os.path.join(app.DOWNLOAD_DIR, filename),
            'file_size_mb': file_size_mb,
            'created_at': datetime.now().isoformat()
        }
        self.download_index[sig] = record
        self.save_download_index()

# 应用导入时初始化，兼容旧版 Flask 无 before_first_request
try:
	initialize_app()
	if not hasattr(app, 'download_manager') or app.download_manager is None:
		app.download_manager = DownloadManager()
		app.download_manager.start_cleanup_thread()
		logging.info("下载管理器已初始化")
except Exception as e:
	logging.error(f"应用初始化失败: {e}")

# 移除模块级别的实例创建
# download_manager = DownloadManager()

def download_ecmwf_data(params):
    """下载ECMWF数据"""
    if not CDSAPI_AVAILABLE:
        logging.error("cdsapi 不可用，无法下载数据")
        return None, None
    
    try:
        c = cdsapi.Client()
        dataset = "reanalysis-era5-pressure-levels"
        result = c.retrieve(dataset, params)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{params['pressure_level'][0]}_{params['year'][0]}_{params['month'][0]}_{params['day'][0]}_{timestamp}.nc"
        file_path = os.path.join(app.DOWNLOAD_DIR, filename)
        
        # 下载文件
        result.download(file_path)
        
        # 获取文件大小
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        logging.info(f"数据下载成功: {filename}, 大小: {file_size_mb:.2f}MB")
        return filename, file_size_mb
        
    except Exception as e:
        logging.error(f"API调用失败: {e}")
        return None, None

def download_with_timeout(params):
    """带超时的下载"""
    result = [None, None]
    
    def target():
        result[0], result[1] = download_ecmwf_data(params)
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=300)  # 5分钟超时
    
    if thread.is_alive():
        logging.warning("下载超时")
        return None, None
    
    return result[0], result[1]

# 挂载应用级别的进度与下载管理器
try:
    if not hasattr(app, 'progress_manager'):
        app.progress_manager = ProgressManager()
except Exception as _e:
    logging.error(f"初始化进度管理器失败: {_e}")

# 简单的日志处理器：解析关键行更新进度（尽力而为，容错）
class CDSProgressLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            pm = getattr(app, 'progress_manager', None)
            op_id = getattr(app, 'current_op_id', None)
            if not pm or not op_id:
                return
            lower = msg.lower()
            if 'request id is ' in lower:
                # 提取 Request ID
                start = lower.find('request id is ')
                req = msg[start + len('Request ID is '):].strip()
                pm.set_request_id(op_id, req)
            elif 'status has been updated to accepted' in lower:
                pm.set_status(op_id, 'accepted')
            elif 'status has been updated to running' in lower:
                pm.set_status(op_id, 'running')
            elif 'status has been updated to successful' in lower:
                pm.set_status(op_id, 'successful')
                pm.complete(op_id)
            # 解析类似 "XX.nc:  48%|" 的进度百分比
            else:
                if '%|' in msg or '%' in msg:
                    import re
                    m = re.search(r'(\d{1,3})%\|', msg)
                    if not m:
                        m = re.search(r'(\d{1,3})%[^\d]', msg)
                    if m:
                        pct = int(m.group(1))
                        pm.set_fraction(op_id, pct / 100.0)
        except Exception:
            pass

# 确保处理器只添加一次
if not any(isinstance(h, CDSProgressLogHandler) for h in logging.getLogger().handlers):
    logging.getLogger().addHandler(CDSProgressLogHandler())

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # 获取表单数据（全部按多选读取）
            product_type = request.form.getlist('product_type') or ['reanalysis']
            variable = request.form.getlist('variable') or ['geopotential']
            pressure_level = request.form.getlist('pressure_level') or ['500']
            year = request.form.getlist('year')
            month = request.form.getlist('month')
            day = request.form.getlist('day')
            time_value = request.form.getlist('time')
            # 从前端传入的操作ID，用于跟踪进度
            op_id = request.form.get('op_id') or str(uuid.uuid4())
            app.current_op_id = op_id
            if hasattr(app, 'progress_manager'):
                app.progress_manager.init(op_id)
                app.progress_manager.set_status(op_id, 'submitted')
            params = {
                'product_type': product_type,
                'variable': variable,
                'pressure_level': pressure_level,
                'year': year,
                'month': month,
                'day': day,
                'time': time_value,
                'data_format': 'netcdf',
                'download_format': 'unarchived'
            }

            # 地理范围：默认全球；如果用户提供四个边界，则覆盖默认
            params['area'] = [90, -180, -90, 180]
            north = request.form.get('north')
            west = request.form.get('west')
            south = request.form.get('south')
            east = request.form.get('east')
            if all(v is not None and v != '' for v in [north, west, south, east]):
                params['area'] = [float(north), float(west), float(south), float(east)]

            logging.info(f"开始下载数据: {params}")
            
            # 下载前先查缓存
            download_mgr = get_download_manager()
            if download_mgr:
                cached = download_mgr.check_cached(params)
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

            # 下载文件
            downloaded_file, file_size_mb = download_with_timeout(params)

            if downloaded_file is None:
                return jsonify({
                    'success': False,
                    'message': '下载失败，请检查参数或稍后重试'
                }), 400

            # 写入缓存
            if download_mgr:
                download_mgr.add_to_cache(params, downloaded_file, file_size_mb)

            # 生成临时下载链接
            download_mgr = get_download_manager()
            if not download_mgr:
                return jsonify({
                    'success': False,
                    'message': '系统未正确初始化'
                }), 500
            link_id, expiry_hours = download_mgr.generate_temp_link(downloaded_file, file_size_mb)
            
            # 生成下载链接
            download_url = url_for('download_file', link_id=link_id)
            
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

        except Exception as e:
            logging.error(f"处理请求时发生错误: {e}")
            return jsonify({
                'success': False,
                'message': f'处理请求时发生错误: {str(e)}'
            }), 500

    return render_template('index.html')

# 新增：查询进度接口
@app.route('/api/progress/<op_id>')
def get_progress(op_id):
    pm = getattr(app, 'progress_manager', None)
    if not pm:
        return jsonify({'progress': 0, 'status': 'unknown'})
    return jsonify(pm.get(op_id))

@app.route('/download/<link_id>')
def download_file(link_id):
    """通过临时链接下载文件"""
    download_mgr = get_download_manager()
    if not download_mgr:
        return render_template('error.html', 
                             message="系统错误",
                             details="系统未正确初始化"), 500
    
    if not download_mgr.is_link_valid(link_id):
        return render_template('error.html', 
                             message="下载链接已过期或无效",
                             details="链接可能已过期、达到最大下载次数，或文件已被删除"), 410
    
    link_info = download_mgr.temp_links[link_id]
    
    try:
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
    download_mgr = get_download_manager()
    if not download_mgr:
        return jsonify({'valid': False, 'message': '系统未正确初始化'})
    
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

@app.route('/error')
def error():
    return render_template('error.html', 
                         message="发生错误",
                         details="请检查您的请求或稍后重试"), 500
