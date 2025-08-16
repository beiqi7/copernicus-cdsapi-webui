from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session
import cdsapi
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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# 配置日志
logging.basicConfig(filename='era5_app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 配置下载目录
DOWNLOAD_DIR = 'downloads'
TEMP_LINKS_FILE = 'temp_links.json'
CLEANUP_INTERVAL = 300  # 5分钟清理一次

# 确保下载目录存在
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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

class DownloadManager:
    def __init__(self):
        self.temp_links = self.load_temp_links()
        self.start_cleanup_thread()
    
    def load_temp_links(self):
        """加载临时链接信息"""
        try:
            if os.path.exists(TEMP_LINKS_FILE):
                with open(TEMP_LINKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"加载临时链接文件失败: {e}")
        return {}
    
    def save_temp_links(self):
        """保存临时链接信息"""
        try:
            with open(TEMP_LINKS_FILE, 'w', encoding='utf-8') as f:
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
            'file_path': os.path.join(DOWNLOAD_DIR, filename),
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
        def cleanup_loop():
            while True:
                try:
                    self.cleanup_expired_files()
                    time.sleep(CLEANUP_INTERVAL)
                except Exception as e:
                    logging.error(f"清理线程错误: {e}")
                    time.sleep(CLEANUP_INTERVAL)
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

# 创建下载管理器实例
download_manager = DownloadManager()

def download_ecmwf_data(params):
    """下载ECMWF数据"""
    c = cdsapi.Client()
    try:
        dataset = "reanalysis-era5-pressure-levels"
        result = c.retrieve(dataset, params)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{params['pressure_level'][0]}_{params['year'][0]}_{params['month'][0]}_{params['day'][0]}_{timestamp}.nc"
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # 获取表单数据
            product_type = request.form['product_type']
            variable = request.form.getlist('variable')
            pressure_level = request.form['pressure_level']
            year = request.form['year']
            month = request.form['month']
            day = request.form['day']
            time_value = request.form['time']
            geographical_area = request.form['geographical_area']

            if not variable:
                variable = ['geopotential']

            params = {
                'product_type': [product_type],
                'variable': variable,
                'pressure_level': [pressure_level],
                'year': [year],
                'month': [month],
                'day': [day],
                'time': [time_value],
                'data_format': 'netcdf',
                'download_format': 'unarchived'
            }

            if geographical_area == 'whole_available_region':
                params.pop('geographical_area', None)
            else:
                north = request.form['north']
                west = request.form['west']
                south = request.form['south']
                east = request.form['east']
                params['area'] = [float(north), float(west), float(south), float(east)]

            logging.info(f"开始下载数据: {params}")
            
            # 下载文件
            downloaded_file, file_size_mb = download_with_timeout(params)

            if downloaded_file is None:
                return jsonify({
                    'success': False,
                    'message': '下载失败，请检查参数或稍后重试'
                }), 400

            # 生成临时下载链接
            link_id, expiry_hours = download_manager.generate_temp_link(downloaded_file, file_size_mb)
            
            # 生成下载链接
            download_url = url_for('download_file', link_id=link_id)
            
            return jsonify({
                'success': True,
                'message': '数据下载完成！',
                'download_url': download_url,
                'filename': downloaded_file,
                'file_size_mb': round(file_size_mb, 2),
                'expiry_hours': expiry_hours,
                'link_id': link_id
            })

        except Exception as e:
            logging.error(f"处理请求时发生错误: {e}")
            return jsonify({
                'success': False,
                'message': f'处理请求时发生错误: {str(e)}'
            }), 500

    return render_template('index.html')

@app.route('/download/<link_id>')
def download_file(link_id):
    """通过临时链接下载文件"""
    if not download_manager.is_link_valid(link_id):
        return render_template('error.html', 
                             message="下载链接已过期或无效",
                             details="链接可能已过期、达到最大下载次数，或文件已被删除"), 410
    
    link_info = download_manager.temp_links[link_id]
    
    try:
        # 增加下载次数
        download_manager.increment_download_count(link_id)
        
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
    if link_id not in download_manager.temp_links:
        return jsonify({'valid': False, 'message': '链接不存在'})
    
    link_info = download_manager.temp_links[link_id]
    is_valid = download_manager.is_link_valid(link_id)
    
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

if __name__ == '__main__':
    logging.info("应用程序启动")
    app.run(debug=False, host='0.0.0.0', port=5000)
