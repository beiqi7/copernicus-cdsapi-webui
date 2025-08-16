# Copernicus Data Download - Intelligent Download Management System

A Flask-based Copernicus data download web application with intelligent temporary link generation, automatic expiration cleanup, and file size optimization features.

## 🚀 New Features

### 1. Intelligent Temporary Link System
- Generates unique temporary download links instead of direct downloads
- Automatically sets different expiration times based on file size
- Supports up to 5 download attempts limit

### 2. Smart Expiration Strategy
- **Tiny files** (< 10MB): 2 hours expiration (fast downloads)
- **Small files** (10-50MB): 4 hours expiration
- **Medium files** (50-200MB): 8 hours expiration
- **Large files** (200-500MB): 12 hours expiration
- **Extra large files** (500MB-1GB): 24 hours expiration
- **Huge files** (> 1GB): 48 hours expiration (ample time for download)

### 3. Automatic Cleanup System
- Background thread automatically cleans expired files every 5 minutes
- Automatically deletes expired files or files that have reached download limits
- Frees up server storage space

### 4. Improved User Interface
- Modern Bootstrap interface
- Real-time download progress display
- File status information display
- Responsive design

## 📋 System Requirements

- Python 3.7+
- Flask 2.3+
- cdsapi 0.6+
- Sufficient disk space for temporary file storage

## 🛠️ Installation Steps

1. **Clone the project**
```bash
git clone <repository-url>
cd copernicus-cdsapi-webui-main
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure CDS API**
```bash
# Create .cdsapirc file in user directory
echo "url: https://cds.climate.copernicus.eu/api/v2" > ~/.cdsapirc
echo "key: YOUR-API-KEY" >> ~/.cdsapirc
```

4. **Run the application**
```bash
# Method 1: Direct execution
python run.py

# Method 2: Using Flask command
export FLASK_APP=era5.py
export FLASK_ENV=development
flask run
```

## 🔧 Configuration

### Environment Variables
- `FLASK_ENV`: Runtime environment (development/production)
- `SECRET_KEY`: Flask secret key
- `CDS_API_KEY`: Copernicus API key

### Configuration Files
Main configuration is in `config.py`:
- File expiration time strategy
- Cleanup interval settings
- Download limit configuration

#### Custom Expiration Strategy
You can adjust file expiration times based on actual needs:
- Copy `config_example.py` to `config.py`
- Choose quick expiration (save storage space) or long-term storage (give users more time)
- Adjust expiration times for each tier based on network environment

## 📁 Directory Structure

```
copernicus-cdsapi-webui-main/
├── era5.py              # Main application file
├── config.py            # Configuration file
├── run.py               # Startup script
├── requirements.txt     # Dependency list
├── templates/           # HTML templates
│   ├── index.html      # Main page
│   └── error.html      # Error page
├── downloads/           # Download files directory (auto-created)
├── temp_links.json     # Temporary link information (auto-created)
└── era5_app.log        # Application log (auto-created)
```

## 🎯 Usage

1. **Access the application**: Open browser and visit `http://localhost:5000`

2. **Select parameters**: Fill in data download parameters
   - Product type
   - Variable selection
   - Pressure level
   - Time range
   - Geographic area

3. **Start download**: Click "Start Download" button

4. **Get link**: System generates temporary download link
   - Display file information
   - Display expiration time
   - Provide download button

5. **Download file**: Click download button to get the file

## 🔒 Security Features

- Temporary links are unique
- Automatic expiration mechanism
- Download attempt limits
- File access control

## 📊 Monitoring and Logging

- Application log: `era5_app.log`
- Temporary link status: `temp_links.json`
- Real-time cleanup status monitoring

## 🔧 Configuration Examples

### Quick Expiration Configuration (Save Storage Space)
```python
# Suitable for environments with limited storage space
FILE_SIZE_THRESHOLDS = {
    'tiny': {'max_size_mb': 10, 'expiry_hours': 1},      # 1 hour
    'small': {'max_size_mb': 50, 'expiry_hours': 2},     # 2 hours
    'medium': {'max_size_mb': 200, 'expiry_hours': 4},   # 4 hours
    'large': {'max_size_mb': 500, 'expiry_hours': 8},    # 8 hours
    'xlarge': {'max_size_mb': 1000, 'expiry_hours': 12}, # 12 hours
    'huge': {'max_size_mb': float('inf'), 'expiry_hours': 24} # 24 hours
}
```

### Long-term Storage Configuration (Give Users More Time)
```python
# Suitable for slower networks or environments where users need more time
FILE_SIZE_THRESHOLDS = {
    'tiny': {'max_size_mb': 10, 'expiry_hours': 6},      # 6 hours
    'small': {'max_size_mb': 50, 'expiry_hours': 12},    # 12 hours
    'medium': {'max_size_mb': 200, 'expiry_hours': 24},  # 24 hours
    'large': {'max_size_mb': 500, 'expiry_hours': 48},   # 48 hours
    'xlarge': {'max_size_mb': 1000, 'expiry_hours': 72}, # 72 hours
    'huge': {'max_size_mb': float('inf'), 'expiry_hours': 168} # 1 week
}
```

## 🚨 Important Notes

1. **API Limits**: Be aware of Copernicus API usage limits
2. **Storage Space**: Ensure sufficient disk space
3. **Network Connection**: Stable network connection is important for downloads
4. **File Cleanup**: System automatically cleans expired files
5. **Expiration Strategy**: Adjust file expiration times based on actual needs

## 🆘 Troubleshooting

### Common Issues

1. **Download Failure**
   - Check API key configuration
   - Verify network connection
   - View application logs

2. **File Expired**
   - Check system time
   - View cleanup logs
   - Regenerate download link

3. **Insufficient Storage Space**
   - Check disk space
   - Manually clean download directory
   - Adjust expiration time strategy

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve this project.

## 📄 License

This project is licensed under the MIT License.

## 📞 Support

If you have questions, please check the log files or submit an Issue.
