"""
配置服务类

负责处理YAML配置文件的读写和验证
"""

import os
import sys
import yaml
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import LogConfig

logger = logging.getLogger(__name__)

class ConfigService:
    """配置管理服务"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._ensure_config_exists()
    
    def _ensure_config_exists(self):
        """确保配置文件存在"""
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        if not os.path.exists(self.config_path):
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        default_config = {
            'logs': [],
            'settings': {
                'search_mode': 'keyword',
                'context_span': 10,
                'max_results': 1000
            }
        }
        self.save_config(default_config)
        logger.info(f"创建默认配置文件: {self.config_path}")
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            return config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {'logs': [], 'settings': {}}
    
    def save_config(self, config: Dict[str, Any]):
        """保存配置"""
        # 验证配置
        self._validate_config(config)
        
        # 备份现有配置
        if os.path.exists(self.config_path):
            self._backup_config()
        
        # 保存新配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logger.info("配置保存成功")
    
    def _validate_config(self, config: Dict[str, Any]):
        """验证配置格式"""
        if not isinstance(config, dict):
            raise ValueError("配置必须是字典格式")
        
        logs = config.get('logs', [])
        if not isinstance(logs, list):
            raise ValueError("logs 必须是列表")
        
        # 验证每个日志配置
        for i, log in enumerate(logs):
            if not isinstance(log, dict):
                raise ValueError(f"logs[{i}] 必须是字典")
            
            required_fields = ['name', 'path']
            for field in required_fields:
                if field not in log:
                    raise ValueError(f"logs[{i}] 缺少必需字段: {field}")
            
            # 验证SSH配置
            sshs = log.get('sshs', [])
            if not isinstance(sshs, list):
                raise ValueError(f"logs[{i}].sshs 必须是列表")
            
            for j, ssh in enumerate(sshs):
                if not isinstance(ssh, dict):
                    raise ValueError(f"logs[{i}].sshs[{j}] 必须是字典")
                
                ssh_required = ['host', 'port', 'username']
                for field in ssh_required:
                    if field not in ssh:
                        raise ValueError(f"logs[{i}].sshs[{j}] 缺少必需字段: {field}")
    
    def _backup_config(self):
        """备份配置文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.config_path}.backup_{timestamp}"
        
        try:
            import shutil
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"配置已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"备份配置失败: {e}")
            return None
    
    def get_logs(self) -> List[LogConfig]:
        """获取所有日志配置"""
        config = self.load_config()
        logs = []
        
        for log_data in config.get('logs', []):
            try:
                log_config = LogConfig.from_dict(log_data)
                logs.append(log_config)
            except Exception as e:
                logger.warning(f"解析日志配置失败: {e}")
                continue
        
        return logs
    
    def get_log_by_name(self, name: str) -> Optional[LogConfig]:
        """根据名称获取日志配置"""
        logs = self.get_logs()
        for log in logs:
            if log.name == name:
                return log
        return None
    
    def get_log_summary(self) -> List[Dict[str, Any]]:
        """获取日志配置摘要"""
        logs = self.get_logs()
        summary = []
        
        for log in logs:
            # 脱敏SSH密码
            ssh_count = len(log.sshs)
            summary.append({
                'name': log.name,
                'path': log.path,
                'ssh_count': ssh_count,
                'description': log.description,
                'group': log.group
            })
        
        return summary
    
    def get_log_detail(self, name: str) -> Optional[Dict[str, Any]]:
        """获取日志详细配置（脱敏）"""
        log = self.get_log_by_name(name)
        if not log:
            return None
        
        # 脱敏处理
        ssh_configs = []
        for ssh in log.sshs:
            ssh_copy = ssh.copy()
            if 'password' in ssh_copy:
                ssh_copy['password'] = '***'
            ssh_configs.append(ssh_copy)
        
        return {
            'name': log.name,
            'path': log.path,
            'description': log.description,
            'group': log.group,
            'ssh_configs': ssh_configs,
            'ssh_count': len(ssh_configs)
        }
