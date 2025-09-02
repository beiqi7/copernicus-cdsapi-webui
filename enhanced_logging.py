"""
增强的日志记录模块
提供结构化日志、性能监控和安全审计功能
"""

import logging
import logging.handlers
import json
import time
import traceback
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
import os


class StructuredFormatter(logging.Formatter):
    """结构化日志格式器"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # 添加额外的上下文信息
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False, indent=None)


class SecurityAuditLogger:
    """安全审计日志记录器"""
    
    def __init__(self, log_file='security_audit.log'):
        self.logger = logging.getLogger('security_audit')
        self.logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def log_login_attempt(self, ip_address: str, user_agent: str, success: bool):
        """记录登录尝试"""
        self.logger.info("Login attempt", extra={
            'extra_data': {
                'event_type': 'login_attempt',
                'ip_address': ip_address,
                'user_agent': user_agent,
                'success': success
            }
        })
    
    def log_rate_limit_violation(self, ip_address: str, endpoint: str, attempts: int):
        """记录限流违规"""
        self.logger.warning("Rate limit violation", extra={
            'extra_data': {
                'event_type': 'rate_limit_violation',
                'ip_address': ip_address,
                'endpoint': endpoint,
                'attempts': attempts
            }
        })
    
    def log_suspicious_activity(self, ip_address: str, activity: str, details: Dict[str, Any]):
        """记录可疑活动"""
        self.logger.warning("Suspicious activity detected", extra={
            'extra_data': {
                'event_type': 'suspicious_activity',
                'ip_address': ip_address,
                'activity': activity,
                'details': details
            }
        })
    
    def log_file_access(self, ip_address: str, file_path: str, action: str, success: bool):
        """记录文件访问"""
        self.logger.info("File access", extra={
            'extra_data': {
                'event_type': 'file_access',
                'ip_address': ip_address,
                'file_path': file_path,
                'action': action,
                'success': success
            }
        })


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger('performance')
        self.metrics = {}
        self._lock = threading.Lock()
    
    def record_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录性能指标"""
        with self._lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = []
            
            self.metrics[metric_name].append({
                'value': value,
                'timestamp': datetime.now().isoformat(),
                'tags': tags or {}
            })
            
            # 保留最近100个数据点
            if len(self.metrics[metric_name]) > 100:
                self.metrics[metric_name] = self.metrics[metric_name][-100:]
    
    def get_metric_stats(self, metric_name: str) -> Dict[str, Any]:
        """获取指标统计信息"""
        with self._lock:
            if metric_name not in self.metrics or not self.metrics[metric_name]:
                return {}
            
            values = [m['value'] for m in self.metrics[metric_name]]
            return {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'latest': values[-1]
            }
    
    def log_performance_summary(self):
        """记录性能摘要"""
        with self._lock:
            for metric_name, data in self.metrics.items():
                if data:
                    stats = self.get_metric_stats(metric_name)
                    self.logger.info(f"Performance metric: {metric_name}", extra={
                        'extra_data': {
                            'metric_name': metric_name,
                            'stats': stats
                        }
                    })


class EnhancedLogger:
    """增强的日志记录器"""
    
    def __init__(self, app_name: str = 'copernicus_app'):
        self.app_name = app_name
        self.security_logger = SecurityAuditLogger()
        self.performance_monitor = PerformanceMonitor()
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 应用日志
        app_logger = logging.getLogger(self.app_name)
        app_logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            f'{self.app_name}.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        app_logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        app_logger.addHandler(console_handler)
        
        # 错误日志
        error_handler = logging.handlers.RotatingFileHandler(
            f'{self.app_name}_errors.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        app_logger.addHandler(error_handler)
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """获取日志记录器"""
        logger_name = f"{self.app_name}.{name}" if name else self.app_name
        return logging.getLogger(logger_name)
    
    def log_request(self, request_info: Dict[str, Any]):
        """记录请求信息"""
        logger = self.get_logger('requests')
        logger.info("HTTP request", extra={
            'extra_data': {
                'event_type': 'http_request',
                **request_info
            }
        })
    
    def log_download_start(self, params: Dict[str, Any], op_id: str):
        """记录下载开始"""
        logger = self.get_logger('downloads')
        logger.info("Download started", extra={
            'extra_data': {
                'event_type': 'download_start',
                'op_id': op_id,
                'params': params
            }
        })
    
    def log_download_complete(self, op_id: str, filename: str, file_size: float, duration: float):
        """记录下载完成"""
        logger = self.get_logger('downloads')
        logger.info("Download completed", extra={
            'extra_data': {
                'event_type': 'download_complete',
                'op_id': op_id,
                'filename': filename,
                'file_size_mb': file_size,
                'duration_seconds': duration
            }
        })
        
        # 记录性能指标
        self.performance_monitor.record_metric('download_duration', duration, {'op_id': op_id})
        self.performance_monitor.record_metric('file_size', file_size, {'op_id': op_id})
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """记录错误"""
        logger = self.get_logger('errors')
        logger.error(f"Error occurred: {str(error)}", extra={
            'extra_data': {
                'event_type': 'error',
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {}
            }
        }, exc_info=True)
    
    def monitor_function_performance(self, func):
        """性能监控装饰器"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger = self.get_logger('performance')
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(f"Function {func.__name__} completed", extra={
                    'extra_data': {
                        'event_type': 'function_performance',
                        'function_name': func.__name__,
                        'duration_seconds': duration,
                        'success': True
                    }
                })
                
                self.performance_monitor.record_metric(
                    f'function_duration.{func.__name__}',
                    duration
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(f"Function {func.__name__} failed", extra={
                    'extra_data': {
                        'event_type': 'function_performance',
                        'function_name': func.__name__,
                        'duration_seconds': duration,
                        'success': False,
                        'error': str(e)
                    }
                })
                
                raise
        
        return wrapper


def create_request_logger(logger: EnhancedLogger):
    """创建请求日志中间件"""
    def log_request():
        from flask import request, g
        
        g.request_start_time = time.time()
        
        # 记录请求信息
        request_info = {
            'method': request.method,
            'url': request.url,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'content_length': request.content_length,
            'referrer': request.referrer
        }
        
        logger.log_request(request_info)
    
    def log_response(response):
        from flask import g
        if hasattr(g, 'request_start_time'):
            duration = time.time() - g.request_start_time
            logger.performance_monitor.record_metric('request_duration', duration)
        
        return response
    
    return log_request, log_response


# 全局日志实例
enhanced_logger = EnhancedLogger()


def setup_logging_for_app(app):
    """为Flask应用设置日志"""
    # 设置请求日志
    log_request, log_response = create_request_logger(enhanced_logger)
    app.before_request(log_request)
    app.after_request(log_response)
    
    # 设置应用日志记录器
    app.logger = enhanced_logger.get_logger('app')
    app.security_logger = enhanced_logger.security_logger
    app.performance_monitor = enhanced_logger.performance_monitor
    
    return enhanced_logger
