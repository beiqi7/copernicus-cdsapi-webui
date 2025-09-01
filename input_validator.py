"""
输入验证和数据清理模块
提供严格的输入验证、数据清理和安全检查
"""

import re
import logging
from typing import List, Union, Dict, Any, Optional, Tuple
from datetime import datetime
from error_handler import ValidationError


class InputValidator:
    """输入验证器类"""
    
    # 预定义的有效值
    VALID_PRODUCT_TYPES = ['reanalysis', 'ensemble_members', 'ensemble_mean', 'ensemble_spread']
    VALID_VARIABLES = [
        'divergence', 'fraction_of_cloud_cover', 'geopotential', 'ozone_mass_mixing_ratio',
        'potential_vorticity', 'relative_humidity', 'specific_cloud_ice_water_content',
        'specific_cloud_liquid_water_content', 'specific_humidity', 'specific_rain_water_content',
        'specific_snow_water_content', 'temperature', 'u_component_of_wind',
        'v_component_of_wind', 'vertical_velocity', 'vorticity'
    ]
    VALID_PRESSURE_LEVELS = [
        '1', '2', '3', '5', '7', '10', '20', '30', '50', '70', '100', '125', '150', '175',
        '200', '225', '250', '300', '350', '400', '450', '500', '550', '600', '650', '700',
        '750', '775', '800', '825', '850', '875', '900', '925', '950', '975', '1000'
    ]
    VALID_MONTHS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    VALID_DAYS = [f'{i:02d}' for i in range(1, 32)]
    VALID_TIMES = [f'{i:02d}:00' for i in range(24)]
    
    # 年份范围
    MIN_YEAR = 1940
    MAX_YEAR = datetime.now().year
    
    # 坐标范围
    MIN_LATITUDE = -90.0
    MAX_LATITUDE = 90.0
    MIN_LONGITUDE = -180.0
    MAX_LONGITUDE = 180.0
    
    @staticmethod
    def validate_required_list(value: Union[str, List[str]], field_name: str, valid_values: List[str]) -> List[str]:
        """验证必需的列表字段"""
        if not value:
            raise ValidationError(f"字段 {field_name} 不能为空", field=field_name)
        
        # 转换为列表
        if isinstance(value, str):
            value = [value]
        elif not isinstance(value, list):
            raise ValidationError(f"字段 {field_name} 必须是字符串或列表", field=field_name, value=str(value))
        
        # 验证每个值
        cleaned_values = []
        for v in value:
            if not isinstance(v, str):
                raise ValidationError(f"字段 {field_name} 包含非字符串值", field=field_name, value=str(v))
            
            v = v.strip()
            if not v:
                continue  # 跳过空值
            
            if v not in valid_values:
                raise ValidationError(f"字段 {field_name} 包含无效值: {v}", field=field_name, value=v)
            
            cleaned_values.append(v)
        
        if not cleaned_values:
            raise ValidationError(f"字段 {field_name} 没有有效值", field=field_name)
        
        return cleaned_values
    
    @staticmethod
    def validate_years(years: Union[str, List[str]]) -> List[str]:
        """验证年份"""
        if not years:
            raise ValidationError("年份不能为空", field="year")
        
        if isinstance(years, str):
            years = [years]
        
        cleaned_years = []
        for year in years:
            if not isinstance(year, str):
                year = str(year)
            
            year = year.strip()
            if not year:
                continue
            
            # 验证是否为数字
            if not year.isdigit():
                raise ValidationError(f"年份必须是数字: {year}", field="year", value=year)
            
            year_int = int(year)
            if year_int < InputValidator.MIN_YEAR or year_int > InputValidator.MAX_YEAR:
                raise ValidationError(
                    f"年份超出范围 ({InputValidator.MIN_YEAR}-{InputValidator.MAX_YEAR}): {year}",
                    field="year", value=year
                )
            
            cleaned_years.append(year)
        
        if not cleaned_years:
            raise ValidationError("没有有效的年份", field="year")
        
        return cleaned_years
    
    @staticmethod
    def validate_coordinate(value: Optional[str], coord_type: str) -> Optional[float]:
        """验证坐标值"""
        if not value or value.strip() == '':
            return None
        
        try:
            coord_value = float(value.strip())
        except ValueError:
            raise ValidationError(f"{coord_type}坐标必须是数字: {value}", field=coord_type.lower(), value=value)
        
        if coord_type.lower() in ['north', 'south']:
            if coord_value < InputValidator.MIN_LATITUDE or coord_value > InputValidator.MAX_LATITUDE:
                raise ValidationError(
                    f"{coord_type}坐标超出范围 ({InputValidator.MIN_LATITUDE}-{InputValidator.MAX_LATITUDE}): {coord_value}",
                    field=coord_type.lower(), value=str(coord_value)
                )
        elif coord_type.lower() in ['west', 'east']:
            if coord_value < InputValidator.MIN_LONGITUDE or coord_value > InputValidator.MAX_LONGITUDE:
                raise ValidationError(
                    f"{coord_type}坐标超出范围 ({InputValidator.MIN_LONGITUDE}-{InputValidator.MAX_LONGITUDE}): {coord_value}",
                    field=coord_type.lower(), value=str(coord_value)
                )
        
        return coord_value
    
    @staticmethod
    def validate_area_bounds(north: Optional[float], south: Optional[float], 
                           west: Optional[float], east: Optional[float]) -> Optional[List[float]]:
        """验证区域边界"""
        coords = [north, south, west, east]
        
        # 如果都为空，返回None（使用默认全球范围）
        if all(coord is None for coord in coords):
            return None
        
        # 如果部分为空，抛出错误
        if any(coord is None for coord in coords):
            raise ValidationError("区域坐标必须全部提供或全部留空")
        
        # 验证南北坐标关系
        if north <= south:
            raise ValidationError(f"北边界({north})必须大于南边界({south})")
        
        # 验证东西坐标关系（考虑跨越180度经线的情况）
        if west == east:
            raise ValidationError(f"东边界({east})不能等于西边界({west})")
        
        return [north, west, south, east]  # CDS API格式：[north, west, south, east]
    
    @staticmethod
    def validate_op_id(op_id: Optional[str]) -> str:
        """验证操作ID"""
        if not op_id:
            raise ValidationError("操作ID不能为空", field="op_id")
        
        op_id = op_id.strip()
        
        # 检查长度
        if len(op_id) < 5 or len(op_id) > 100:
            raise ValidationError("操作ID长度必须在5-100字符之间", field="op_id", value=op_id)
        
        # 检查格式（只允许字母、数字、下划线和连字符）
        if not re.match(r'^[a-zA-Z0-9_-]+$', op_id):
            raise ValidationError("操作ID只能包含字母、数字、下划线和连字符", field="op_id", value=op_id)
        
        return op_id
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除危险字符"""
        if not filename:
            raise ValidationError("文件名不能为空", field="filename")
        
        # 移除路径分隔符和其他危险字符
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*', '\0']
        cleaned = filename
        
        for char in dangerous_chars:
            cleaned = cleaned.replace(char, '_')
        
        # 移除控制字符
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32)
        
        # 限制长度
        if len(cleaned) > 255:
            cleaned = cleaned[:255]
        
        if not cleaned.strip():
            raise ValidationError("清理后的文件名为空", field="filename", value=filename)
        
        return cleaned.strip()
    
    @classmethod
    def validate_download_params(cls, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证完整的下载参数"""
        try:
            validated_params = {}
            
            # 验证必需的多选字段
            validated_params['product_type'] = cls.validate_required_list(
                form_data.get('product_type'), 'product_type', cls.VALID_PRODUCT_TYPES
            )
            
            validated_params['variable'] = cls.validate_required_list(
                form_data.get('variable'), 'variable', cls.VALID_VARIABLES
            )
            
            validated_params['pressure_level'] = cls.validate_required_list(
                form_data.get('pressure_level'), 'pressure_level', cls.VALID_PRESSURE_LEVELS
            )
            
            validated_params['year'] = cls.validate_years(form_data.get('year'))
            
            validated_params['month'] = cls.validate_required_list(
                form_data.get('month'), 'month', cls.VALID_MONTHS
            )
            
            validated_params['day'] = cls.validate_required_list(
                form_data.get('day'), 'day', cls.VALID_DAYS
            )
            
            validated_params['time'] = cls.validate_required_list(
                form_data.get('time'), 'time', cls.VALID_TIMES
            )
            
            # 验证坐标
            north = cls.validate_coordinate(form_data.get('north'), 'north')
            south = cls.validate_coordinate(form_data.get('south'), 'south')
            west = cls.validate_coordinate(form_data.get('west'), 'west')
            east = cls.validate_coordinate(form_data.get('east'), 'east')
            
            # 验证区域边界
            area = cls.validate_area_bounds(north, south, west, east)
            if area:
                validated_params['area'] = area
            else:
                validated_params['area'] = [90, -180, -90, 180]  # 默认全球范围
            
            # 验证操作ID
            validated_params['op_id'] = cls.validate_op_id(form_data.get('op_id'))
            
            # 设置固定参数
            validated_params['data_format'] = 'netcdf'
            validated_params['download_format'] = 'unarchived'
            
            return validated_params
            
        except ValidationError:
            raise
        except Exception as e:
            logging.error(f"验证参数时发生未知错误: {e}")
            raise ValidationError(f"参数验证失败: {str(e)}")


class SecurityValidator:
    """安全验证器"""
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_directory: str) -> bool:
        """验证文件路径是否安全（防止路径遍历攻击）"""
        import os
        
        try:
            # 规范化路径
            normalized_path = os.path.normpath(file_path)
            normalized_allowed = os.path.normpath(allowed_directory)
            
            # 检查是否在允许的目录内
            return normalized_path.startswith(normalized_allowed)
        except Exception:
            return False
    
    @staticmethod
    def validate_request_size(content_length: Optional[int], max_size: int = 1024 * 1024) -> bool:
        """验证请求大小"""
        if content_length is None:
            return True  # 无法确定大小时允许通过
        
        return content_length <= max_size
    
    @staticmethod
    def validate_ip_address(ip_address: str) -> bool:
        """验证IP地址格式"""
        import ipaddress
        
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def check_suspicious_patterns(text: str) -> List[str]:
        """检查可疑模式"""
        if not text:
            return []
        
        suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script标签
            r'javascript:',               # JavaScript URL
            r'on\w+\s*=',                # 事件处理器
            r'eval\s*\(',                # eval函数
            r'document\.',               # DOM操作
            r'window\.',                 # Window对象
            r'\.\./.*\.\.',              # 路径遍历
            r'[;\'"]\s*;',               # SQL注入尝试
        ]
        
        found_patterns = []
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found_patterns.append(pattern)
        
        return found_patterns
