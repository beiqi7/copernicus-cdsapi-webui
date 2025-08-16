# 配置文件示例 - 复制此文件为 config.py 并根据需要修改

import os

class Config:
    """应用配置类 - 可根据实际需求调整"""
    
    # 基本配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    
    # 下载配置
    DOWNLOAD_DIR = 'downloads'
    TEMP_LINKS_FILE = 'temp_links.json'
    CLEANUP_INTERVAL = 300  # 5分钟清理一次
    
    # 文件大小阈值和过期时间配置（单位：小时）
    # 根据你的网络环境和用户需求调整这些值
    # 小文件下载快，过期时间短；大文件下载慢，给更多时间
    FILE_SIZE_THRESHOLDS = {
        # 微小文件：通常几秒到几分钟就能下载完
        'tiny': {'max_size_mb': 10, 'expiry_hours': 2},        # 小于10MB，2小时过期
        
        # 小文件：几分钟到十几分钟下载完
        'small': {'max_size_mb': 50, 'expiry_hours': 4},       # 10-50MB，4小时过期
        
        # 中等文件：可能需要半小时到1小时
        'medium': {'max_size_mb': 200, 'expiry_hours': 8},     # 50-200MB，8小时过期
        
        # 大文件：可能需要1-3小时下载
        'large': {'max_size_mb': 500, 'expiry_hours': 12},     # 200-500MB，12小时过期
        
        # 超大文件：可能需要3-6小时下载
        'xlarge': {'max_size_mb': 1000, 'expiry_hours': 24},  # 500MB-1GB，24小时过期
        
        # 巨型文件：可能需要6小时以上下载
        'huge': {'max_size_mb': float('inf'), 'expiry_hours': 48}  # 大于1GB，48小时过期
    }
    
    # 下载限制
    MAX_DOWNLOADS_PER_LINK = 5  # 每个链接最多下载次数
    DOWNLOAD_TIMEOUT = 300      # 下载超时时间（秒）
    
    # 日志配置
    LOG_LEVEL = 'INFO'          # DEBUG, INFO, WARNING, ERROR
    LOG_FILE = 'era5_app.log'
    
    # 服务器配置
    HOST = '0.0.0.0'           # 监听所有网络接口
    PORT = 5000                 # 端口号
    DEBUG = False               # 生产环境设为False
    
    # 高级配置
    MAX_CONCURRENT_DOWNLOADS = 3  # 最大并发下载数
    CHUNK_SIZE = 8192            # 文件传输块大小
    
    # 网络配置
    REQUEST_TIMEOUT = 30        # HTTP请求超时时间
    MAX_RETRIES = 3             # 最大重试次数

# 快速配置示例 - 根据你的需求选择

class FastExpiryConfig(Config):
    """快速过期配置 - 适合存储空间紧张的环境"""
    FILE_SIZE_THRESHOLDS = {
        'tiny': {'max_size_mb': 10, 'expiry_hours': 1},      # 1小时
        'small': {'max_size_mb': 50, 'expiry_hours': 2},     # 2小时
        'medium': {'max_size_mb': 200, 'expiry_hours': 4},   # 4小时
        'large': {'max_size_mb': 500, 'expiry_hours': 8},    # 8小时
        'xlarge': {'max_size_mb': 1000, 'expiry_hours': 12}, # 12小时
        'huge': {'max_size_mb': float('inf'), 'expiry_hours': 24} # 24小时
    }

class LongExpiryConfig(Config):
    """长期保存配置 - 适合网络较慢或用户需要更多时间的环境"""
    FILE_SIZE_THRESHOLDS = {
        'tiny': {'max_size_mb': 10, 'expiry_hours': 6},      # 6小时
        'small': {'max_size_mb': 50, 'expiry_hours': 12},    # 12小时
        'medium': {'max_size_mb': 200, 'expiry_hours': 24},  # 24小时
        'large': {'max_size_mb': 500, 'expiry_hours': 48},   # 48小时
        'xlarge': {'max_size_mb': 1000, 'expiry_hours': 72}, # 72小时
        'huge': {'max_size_mb': float('inf'), 'expiry_hours': 168} # 1周
    }

# 配置选择
# 取消注释你想要使用的配置类
# config_class = FastExpiryConfig      # 快速过期
# config_class = LongExpiryConfig      # 长期保存
config_class = Config                  # 默认配置（推荐）

# 应用配置
app_config = config_class() 