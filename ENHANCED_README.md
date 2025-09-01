# Enhanced Copernicus Data Download WebUI

增强版 Copernicus 数据下载 Web 界面，集成了全面的安全性、健壮性和性能优化。

## 🌟 新增功能特性

### 安全性增强
- **输入验证与清理**: 严格的参数验证，防止注入攻击
- **安全头部**: 完整的 HTTP 安全头部配置
- **IP 黑名单**: 自动检测和阻止可疑 IP
- **限流保护**: 防止过度请求和 DDoS 攻击
- **文件路径验证**: 防止路径遍历攻击
- **CSRF 保护**: 跨站请求伪造防护

### 错误处理与恢复
- **统一异常处理**: 分类处理不同类型的错误
- **重试机制**: 自动重试失败的操作
- **断路器模式**: 防止系统雪崩
- **优雅降级**: 部分功能失效时的备用方案

### 性能与资源管理
- **内存监控**: 自动垃圾回收和内存清理
- **连接池管理**: 优化数据库连接使用
- **异步处理**: 非阻塞的后台任务
- **缓存优化**: 智能缓存策略

### 日志与监控
- **结构化日志**: JSON 格式的详细日志记录
- **性能监控**: 函数执行时间和资源使用统计
- **安全审计**: 安全事件的完整记录
- **实时指标**: 系统运行状态监控

### 用户界面增强
- **表单验证**: 前端实时验证用户输入
- **错误处理**: 友好的错误提示和恢复建议
- **进度跟踪**: 增强的下载进度显示
- **超时处理**: 请求超时的优雅处理

## 📁 新增文件说明

### 核心模块
- `error_handler.py` - 统一异常处理和错误恢复
- `input_validator.py` - 输入验证和数据清理
- `enhanced_logging.py` - 增强的日志记录和监控
- `security_manager.py` - 安全管理和威胁检测
- `enhanced_era5.py` - 集成所有增强功能的主应用

### 配置文件
- `ENHANCED_README.md` - 本文档，详细的使用指南
- `requirements.txt` - 更新的依赖项列表

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd copernicus-cdsapi-webui

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置

```bash
# 复制配置文件
cp config_example.py config.py

# 编辑配置文件，设置您的 CDS API 密钥
nano config.py
```

### 3. 启动应用

#### 使用增强版本（推荐）
```bash
python enhanced_era5.py
```

#### 使用原版本
```bash
python era5.py
```

#### 使用启动脚本
```bash
python run.py
```

## ⚙️ 配置选项

### 安全配置
```python
# 在 config.py 中添加
class ProductionConfig(Config):
    # 安全密钥（生产环境必须更改）
    SECRET_KEY = 'your-very-secure-secret-key-here'
    
    # IP 黑名单设置
    BLACKLIST_DURATION = 3600  # 1小时
    SUSPICIOUS_THRESHOLD = 10  # 可疑行为阈值
    
    # 限流设置
    MAX_REQUESTS_PER_MINUTE = 60
    RATE_LIMIT_WINDOW = 60
```

### 性能配置
```python
# 内存管理
MAX_MEMORY_USAGE = 1024 * 1024 * 1024  # 1GB
MEMORY_CHECK_INTERVAL = 60  # 60秒

# 清理设置
CLEANUP_INTERVAL = 300  # 5分钟
```

### 日志配置
```python
# 日志级别
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# 日志文件
LOG_FILE = 'era5_app_enhanced.log'
SECURITY_LOG_FILE = 'security_audit.log'
```

## 🔒 安全特性详解

### 1. 输入验证
- 所有用户输入都经过严格验证
- 支持的参数类型和范围检查
- XSS 和 SQL 注入防护
- 文件路径安全验证

### 2. 访问控制
- IP 基础的访问限制
- 自动检测可疑活动
- 动态黑名单管理
- 请求频率限制

### 3. 数据保护
- 敏感信息脱敏
- 安全的文件操作
- 临时文件自动清理
- 数据传输加密（HTTPS）

## 📊 监控和日志

### 日志文件
- `era5_app_enhanced.log` - 应用主日志
- `security_audit.log` - 安全审计日志
- `era5_app_enhanced_errors.log` - 错误日志

### 监控指标
- 请求响应时间
- 内存使用情况
- 下载成功率
- 错误发生频率
- 安全事件统计

### 日志格式
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "level": "INFO",
  "logger": "app",
  "message": "Download completed",
  "extra": {
    "op_id": "op_abc123",
    "file_size_mb": 125.6,
    "duration_seconds": 45.2
  }
}
```

## 🛠️ 故障排除

### 常见问题

#### 1. 内存不足
```bash
# 检查内存使用
grep "内存使用" era5_app_enhanced.log

# 调整内存限制
# 在 config.py 中修改 MAX_MEMORY_USAGE
```

#### 2. 权限问题
```bash
# 确保下载目录有写权限
chmod 755 downloads/

# 检查日志文件权限
ls -la *.log
```

#### 3. CDS API 问题
```bash
# 验证 API 密钥
cdsapi verify-key

# 检查 API 状态
grep "cdsapi" era5_app_enhanced.log
```

#### 4. 网络连接问题
```bash
# 检查网络连接
ping cds.climate.copernicus.eu

# 查看连接错误
grep "网络错误" era5_app_enhanced.log
```

### 性能优化建议

1. **内存管理**
   - 定期重启应用（每24小时）
   - 监控内存使用趋势
   - 调整垃圾回收参数

2. **磁盘空间**
   - 定期清理下载目录
   - 监控磁盘使用情况
   - 配置日志轮转

3. **网络优化**
   - 使用 CDN 加速静态资源
   - 配置适当的超时时间
   - 启用 gzip 压缩

## 🔧 开发指南

### 添加新功能

1. **创建新的验证器**
```python
# 在 input_validator.py 中添加
@staticmethod
def validate_new_parameter(value):
    # 验证逻辑
    return cleaned_value
```

2. **添加新的错误类型**
```python
# 在 error_handler.py 中添加
class NewError(AppError):
    def __init__(self, message, context=None):
        super().__init__(message, "NEW_ERROR")
        self.context = context
```

3. **扩展日志记录**
```python
# 在 enhanced_logging.py 中添加
def log_new_event(self, event_data):
    logger = self.get_logger('new_events')
    logger.info("New event", extra={'extra_data': event_data})
```

### 测试

```bash
# 运行基本测试
python test_app.py

# 测试安全功能
python -m pytest tests/test_security.py

# 性能测试
python -m pytest tests/test_performance.py
```

## 📈 部署建议

### 生产环境部署

1. **使用 WSGI 服务器**
```bash
# 使用 Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 enhanced_era5:app

# 使用 uWSGI
pip install uwsgi
uwsgi --http :5000 --wsgi-file enhanced_era5.py --callable app
```

2. **反向代理配置（Nginx）**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # 安全头部
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
```

3. **系统服务配置**
```ini
# /etc/systemd/system/copernicus-app.service
[Unit]
Description=Copernicus Data Download WebUI
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/app
Environment=FLASK_ENV=production
ExecStart=/path/to/venv/bin/python enhanced_era5.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker 部署

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "enhanced_era5.py"]
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目遵循 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [ECMWF](https://www.ecmwf.int/) - 提供 ERA5 数据
- [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/) - 数据访问接口
- Flask 社区 - 优秀的 Web 框架

## 📞 支持与反馈

如果您遇到问题或有改进建议，请：

1. 查看 [故障排除](#故障排除) 部分
2. 搜索现有的 [Issues](https://github.com/your-repo/issues)
3. 创建新的 Issue 描述问题
4. 联系维护者获取帮助

---

**注意**: 这是一个增强版本，在原有功能基础上大幅提升了安全性、稳定性和性能。建议在生产环境中使用增强版本 `enhanced_era5.py`。
