"""
错误处理和异常管理模块
提供统一的异常处理、错误记录和恢复机制
"""

import logging
import traceback
import time
from functools import wraps
from flask import jsonify, render_template, request
from datetime import datetime


class AppError(Exception):
    """应用基础异常类"""
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()


class ValidationError(AppError):
    """输入验证异常"""
    def __init__(self, message, field=None, value=None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
        self.value = value


class DownloadError(AppError):
    """下载相关异常"""
    def __init__(self, message, operation=None, params=None):
        super().__init__(message, "DOWNLOAD_ERROR")
        self.operation = operation
        self.params = params


class RateLimitError(AppError):
    """限流异常"""
    def __init__(self, message, retry_after=None):
        super().__init__(message, "RATE_LIMIT_ERROR")
        self.retry_after = retry_after


class SystemError(AppError):
    """系统错误异常"""
    def __init__(self, message, component=None):
        super().__init__(message, "SYSTEM_ERROR")
        self.component = component


def retry_on_failure(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts >= max_retries:
                        logging.error(f"函数 {func.__name__} 重试 {max_retries} 次后仍然失败: {e}")
                        raise
                    
                    logging.warning(f"函数 {func.__name__} 第 {attempts} 次尝试失败: {e}, {current_delay}秒后重试")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
            return None
        return wrapper
    return decorator


def safe_execute(func, default_return=None, log_error=True):
    """安全执行函数，捕获异常并返回默认值"""
    try:
        return func()
    except Exception as e:
        if log_error:
            logging.error(f"安全执行失败 {func.__name__ if hasattr(func, '__name__') else str(func)}: {e}")
            logging.debug(traceback.format_exc())
        return default_return


def create_error_handlers(app):
    """为Flask应用创建统一的错误处理器"""
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        """处理验证错误"""
        logging.warning(f"验证错误: {error.message} - 字段: {error.field}, 值: {error.value}")
        
        if request.is_json or request.content_type == 'application/json':
            return jsonify({
                'success': False,
                'error_code': error.error_code,
                'message': error.message,
                'field': error.field,
                'timestamp': error.timestamp.isoformat()
            }), 400
        
        return render_template('error.html',
                             message="输入验证失败",
                             details=error.message), 400
    
    @app.errorhandler(DownloadError)
    def handle_download_error(error):
        """处理下载错误"""
        logging.error(f"下载错误: {error.message} - 操作: {error.operation}")
        
        if request.is_json or request.content_type == 'application/json':
            return jsonify({
                'success': False,
                'error_code': error.error_code,
                'message': error.message,
                'operation': error.operation,
                'timestamp': error.timestamp.isoformat()
            }), 500
        
        return render_template('error.html',
                             message="下载失败",
                             details=error.message), 500
    
    @app.errorhandler(RateLimitError)
    def handle_rate_limit_error(error):
        """处理限流错误"""
        logging.warning(f"限流错误: {error.message} - 重试时间: {error.retry_after}")
        
        response = jsonify({
            'success': False,
            'error_code': error.error_code,
            'message': error.message,
            'retry_after': error.retry_after,
            'timestamp': error.timestamp.isoformat()
        })
        response.status_code = 429
        if error.retry_after:
            response.headers['Retry-After'] = str(error.retry_after)
        return response
    
    @app.errorhandler(SystemError)
    def handle_system_error(error):
        """处理系统错误"""
        logging.error(f"系统错误: {error.message} - 组件: {error.component}")
        
        if request.is_json or request.content_type == 'application/json':
            return jsonify({
                'success': False,
                'error_code': error.error_code,
                'message': "系统暂时不可用，请稍后重试",
                'timestamp': error.timestamp.isoformat()
            }), 500
        
        return render_template('error.html',
                             message="系统错误",
                             details="系统暂时不可用，请稍后重试"), 500
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """处理404错误"""
        if request.is_json:
            return jsonify({
                'success': False,
                'error_code': 'NOT_FOUND',
                'message': '请求的资源不存在'
            }), 404
        
        return render_template('error.html',
                             message="页面不存在",
                             details="您访问的页面不存在"), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """处理500错误"""
        logging.error(f"内部服务器错误: {error}")
        logging.debug(traceback.format_exc())
        
        if request.is_json:
            return jsonify({
                'success': False,
                'error_code': 'INTERNAL_ERROR',
                'message': '服务器内部错误'
            }), 500
        
        return render_template('error.html',
                             message="服务器错误",
                             details="服务器遇到了内部错误"), 500
    
    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        """处理未捕获的异常"""
        logging.error(f"未处理的异常: {error}")
        logging.debug(traceback.format_exc())
        
        if request.is_json:
            return jsonify({
                'success': False,
                'error_code': 'UNKNOWN_ERROR',
                'message': '发生未知错误'
            }), 500
        
        return render_template('error.html',
                             message="未知错误",
                             details="发生了未知错误，请稍后重试"), 500


class CircuitBreaker:
    """断路器模式实现，防止系统雪崩"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise SystemError("服务暂时不可用（断路器开启）", component=func.__name__)
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self):
        """检查是否应该尝试重置断路器"""
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """成功时重置断路器"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """失败时更新断路器状态"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logging.warning(f"断路器开启，失败次数: {self.failure_count}")


def log_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logging.info(f"函数 {func.__name__} 执行时间: {execution_time:.2f}秒")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"函数 {func.__name__} 执行失败，耗时: {execution_time:.2f}秒, 错误: {e}")
            raise
    return wrapper
