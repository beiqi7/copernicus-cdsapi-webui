"""
安全管理模块
提供安全防护、访问控制和威胁检测功能
"""

import hashlib
import hmac
import time
import secrets
import threading
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
from datetime import datetime, timedelta
from flask import request, session
import logging


class SecurityConfig:
    """安全配置"""
    
    # CSRF保护
    CSRF_TOKEN_EXPIRY = 3600  # 1小时
    
    # 会话安全
    SESSION_TIMEOUT = 1800  # 30分钟
    SESSION_REGENERATE_INTERVAL = 300  # 5分钟
    
    # IP白名单/黑名单
    BLACKLIST_DURATION = 3600  # 1小时
    SUSPICIOUS_THRESHOLD = 10  # 可疑行为阈值
    
    # 文件安全
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS = {'.nc', '.netcdf', '.grib', '.grb'}
    
    # 请求安全
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_REQUESTS_PER_MINUTE = 60


class IPBlacklist:
    """IP黑名单管理器"""
    
    def __init__(self):
        self.blacklist = {}  # ip -> expiry_time
        self.suspicious_activity = defaultdict(list)  # ip -> [timestamps]
        self._lock = threading.Lock()
    
    def is_blacklisted(self, ip: str) -> bool:
        """检查IP是否在黑名单中"""
        with self._lock:
            if ip in self.blacklist:
                if time.time() < self.blacklist[ip]:
                    return True
                else:
                    # 过期的黑名单项，删除
                    del self.blacklist[ip]
            return False
    
    def add_to_blacklist(self, ip: str, duration: int = None):
        """添加IP到黑名单"""
        duration = duration or SecurityConfig.BLACKLIST_DURATION
        expiry_time = time.time() + duration
        
        with self._lock:
            self.blacklist[ip] = expiry_time
            logging.warning(f"IP {ip} 已添加到黑名单，持续时间: {duration}秒")
    
    def record_suspicious_activity(self, ip: str):
        """记录可疑活动"""
        current_time = time.time()
        
        with self._lock:
            # 添加当前时间戳
            self.suspicious_activity[ip].append(current_time)
            
            # 清理1小时前的记录
            cutoff_time = current_time - 3600
            self.suspicious_activity[ip] = [
                t for t in self.suspicious_activity[ip] 
                if t > cutoff_time
            ]
            
            # 检查是否达到可疑阈值
            if len(self.suspicious_activity[ip]) >= SecurityConfig.SUSPICIOUS_THRESHOLD:
                self.add_to_blacklist(ip)
                return True
        
        return False
    
    def get_suspicious_count(self, ip: str) -> int:
        """获取IP的可疑活动次数"""
        with self._lock:
            return len(self.suspicious_activity.get(ip, []))
    
    def cleanup_expired(self):
        """清理过期的黑名单项"""
        current_time = time.time()
        with self._lock:
            expired_ips = [
                ip for ip, expiry in self.blacklist.items()
                if current_time >= expiry
            ]
            for ip in expired_ips:
                del self.blacklist[ip]


class CSRFProtection:
    """CSRF保护"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode('utf-8')
    
    def generate_token(self, session_id: str) -> str:
        """生成CSRF令牌"""
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(16)
        
        # 创建消息
        message = f"{session_id}:{timestamp}:{nonce}"
        
        # 生成签名
        signature = hmac.new(
            self.secret_key,
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"{timestamp}:{nonce}:{signature}"
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """验证CSRF令牌"""
        try:
            parts = token.split(':')
            if len(parts) != 3:
                return False
            
            timestamp, nonce, signature = parts
            
            # 检查时间戳是否过期
            token_time = int(timestamp)
            if time.time() - token_time > SecurityConfig.CSRF_TOKEN_EXPIRY:
                return False
            
            # 重建消息并验证签名
            message = f"{session_id}:{timestamp}:{nonce}"
            expected_signature = hmac.new(
                self.secret_key,
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False


class RateLimitEnhanced:
    """增强的限流器"""
    
    def __init__(self):
        self.request_counts = defaultdict(deque)  # ip -> deque of timestamps
        self.blocked_until = {}  # ip -> blocked_until_timestamp
        self._lock = threading.Lock()
    
    def is_allowed(self, ip: str, limit: int = None, window: int = 60) -> Tuple[bool, int]:
        """检查是否允许请求"""
        limit = limit or SecurityConfig.MAX_REQUESTS_PER_MINUTE
        current_time = time.time()
        
        with self._lock:
            # 检查是否仍在阻止期间
            if ip in self.blocked_until:
                if current_time < self.blocked_until[ip]:
                    return False, int(self.blocked_until[ip] - current_time)
                else:
                    del self.blocked_until[ip]
            
            # 清理过期的请求记录
            requests = self.request_counts[ip]
            cutoff_time = current_time - window
            while requests and requests[0] < cutoff_time:
                requests.popleft()
            
            # 检查请求数量
            if len(requests) >= limit:
                # 阻止该IP 5分钟
                block_duration = 300
                self.blocked_until[ip] = current_time + block_duration
                logging.warning(f"IP {ip} 因超过限流阈值被阻止 {block_duration} 秒")
                return False, block_duration
            
            # 记录当前请求
            requests.append(current_time)
            return True, 0


class ThreatDetector:
    """威胁检测器"""
    
    # 可疑模式
    SUSPICIOUS_PATTERNS = [
        # SQL注入
        r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b)',
        # XSS
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        # 路径遍历
        r'\.\./.*\.\.',
        r'\.\.\\.*\.\.',
        # 命令注入
        r'[;&|`$\(\)]',
        # 文件包含
        r'(file://|http://|https://)',
    ]
    
    @classmethod
    def detect_threats(cls, data: str) -> List[str]:
        """检测威胁"""
        import re
        
        threats = []
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, data, re.IGNORECASE):
                threats.append(pattern)
        
        return threats
    
    @classmethod
    def is_suspicious_request(cls, request_data: dict) -> Tuple[bool, List[str]]:
        """检查请求是否可疑"""
        threats = []
        
        # 检查所有字符串值
        for key, value in request_data.items():
            if isinstance(value, str):
                detected = cls.detect_threats(value)
                threats.extend(detected)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        detected = cls.detect_threats(item)
                        threats.extend(detected)
        
        return len(threats) > 0, threats


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, app=None, secret_key: str = None):
        self.app = app
        self.blacklist = IPBlacklist()
        self.rate_limiter = RateLimitEnhanced()
        self.csrf_protection = CSRFProtection(secret_key) if secret_key else None
        self.threat_detector = ThreatDetector()
        self._setup_cleanup_thread()
    
    def _setup_cleanup_thread(self):
        """设置清理线程"""
        def cleanup_loop():
            while True:
                try:
                    self.blacklist.cleanup_expired()
                    time.sleep(300)  # 每5分钟清理一次
                except Exception as e:
                    logging.error(f"安全管理器清理失败: {e}")
                    time.sleep(300)
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
    
    def check_request_security(self, request_data: dict, client_ip: str) -> Tuple[bool, str]:
        """检查请求安全性"""
        # 检查IP黑名单
        if self.blacklist.is_blacklisted(client_ip):
            return False, "IP地址已被列入黑名单"
        
        # 检查限流
        allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
        if not allowed:
            self.blacklist.record_suspicious_activity(client_ip)
            return False, f"请求过于频繁，请等待 {retry_after} 秒"
        
        # 威胁检测
        is_suspicious, threats = self.threat_detector.is_suspicious_request(request_data)
        if is_suspicious:
            self.blacklist.record_suspicious_activity(client_ip)
            logging.warning(f"检测到可疑请求来自 {client_ip}: {threats}")
            return False, "检测到可疑输入"
        
        return True, ""
    
    def validate_file_security(self, filename: str, file_size: int) -> Tuple[bool, str]:
        """验证文件安全性"""
        # 检查文件大小
        if file_size > SecurityConfig.MAX_FILE_SIZE:
            return False, f"文件大小超过限制 ({SecurityConfig.MAX_FILE_SIZE} bytes)"
        
        # 检查文件扩展名
        import os
        _, ext = os.path.splitext(filename.lower())
        if ext not in SecurityConfig.ALLOWED_EXTENSIONS:
            return False, f"不允许的文件扩展名: {ext}"
        
        return True, ""
    
    def get_client_ip(self) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        return request.remote_addr or 'unknown'
    
    def log_security_event(self, event_type: str, details: dict):
        """记录安全事件"""
        client_ip = self.get_client_ip()
        logging.warning(f"安全事件 [{event_type}] 来自 {client_ip}: {details}")
    
    def init_app(self, app):
        """初始化Flask应用"""
        self.app = app
        
        @app.before_request
        def security_check():
            """请求前安全检查"""
            client_ip = self.get_client_ip()
            
            # 检查内容长度
            content_length = request.content_length
            if content_length and content_length > SecurityConfig.MAX_REQUEST_SIZE:
                self.log_security_event('oversized_request', {
                    'content_length': content_length,
                    'max_allowed': SecurityConfig.MAX_REQUEST_SIZE
                })
                return "请求过大", 413
            
            # 对POST请求进行额外检查
            if request.method == 'POST':
                try:
                    # 获取表单数据进行安全检查
                    form_data = request.form.to_dict(flat=False)
                    is_safe, message = self.check_request_security(form_data, client_ip)
                    
                    if not is_safe:
                        self.log_security_event('security_violation', {
                            'reason': message,
                            'form_data': {k: '***' for k in form_data.keys()}  # 不记录敏感数据
                        })
                        return f"安全检查失败: {message}", 403
                        
                except Exception as e:
                    logging.error(f"安全检查时发生错误: {e}")
                    # 不阻止请求，但记录错误
        
        return self


def create_security_headers_middleware(app):
    """创建安全头中间件"""
    
    @app.after_request
    def add_security_headers(response):
        """添加安全头"""
        # 防止点击劫持
        response.headers['X-Frame-Options'] = 'DENY'
        
        # 防止内容类型嗅探
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # XSS保护
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # 强制HTTPS（如果在生产环境）
        if app.config.get('ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # 内容安全策略
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        
        # 引用策略
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    return app
