import os

class Config:
    """应用配置类"""
    
    # 基本配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    
    # 下载配置
    DOWNLOAD_DIR = 'downloads'
    TEMP_LINKS_FILE = 'temp_links.json'
    DOWNLOAD_INDEX_FILE = 'download_index.json'
    CLEANUP_INTERVAL = 300  # 5分钟清理一次
    
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
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 