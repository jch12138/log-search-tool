"""YAML configuration management service (migrated)."""

import os
import yaml
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from app.models import LogConfig

logger = logging.getLogger(__name__)


class ConfigService:
	def __init__(self, config_path: str):
		self.config_path = config_path
		self._ensure_config_exists()

	def _ensure_config_exists(self):
		cfg_dir = os.path.dirname(self.config_path)
		os.makedirs(cfg_dir, exist_ok=True)
		if not os.path.exists(self.config_path):
			self._create_default_config()

	def _create_default_config(self):
		default = {
			'logs': [],
			'settings': {
				'search_mode': 'keyword',
				'context_span': 10,
				'max_results': 1000
			}
		}
		self.save_config(default)
		logger.info(f"创建默认配置文件: {self.config_path}")

	def load_config(self) -> Dict[str, Any]:
		try:
			with open(self.config_path, 'r', encoding='utf-8') as f:
				return yaml.safe_load(f) or {}
		except Exception as e:  # pragma: no cover - disk error
			logger.error(f"加载配置失败: {e}")
			return {'logs': [], 'settings': {}}

	def save_config(self, config: Dict[str, Any]):
		self._validate_config(config)
		if os.path.exists(self.config_path):
			self._backup_config()
		with open(self.config_path, 'w', encoding='utf-8') as f:
			yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
		logger.info("配置保存成功")

	def _validate_config(self, config: Dict[str, Any]):
		if not isinstance(config, dict):
			raise ValueError("配置必须是字典格式")
		logs = config.get('logs', [])
		if not isinstance(logs, list):
			raise ValueError("logs 必须是列表")
		for i, log in enumerate(logs):
			if not isinstance(log, dict):
				raise ValueError(f"logs[{i}] 必须是字典")
			for field in ['name', 'path']:
				if field not in log:
					raise ValueError(f"logs[{i}] 缺少必需字段: {field}")
			sshs = log.get('sshs', [])
			if not isinstance(sshs, list):
				raise ValueError(f"logs[{i}].sshs 必须是列表")
			for j, ssh in enumerate(sshs):
				if not isinstance(ssh, dict):
					raise ValueError(f"logs[{i}].sshs[{j}] 必须是字典")
				for field in ['host', 'port', 'username']:
					if field not in ssh:
						raise ValueError(f"logs[{i}].sshs[{j}] 缺少必需字段: {field}")

	def _backup_config(self):  # pragma: no cover - I/O
		ts = datetime.now().strftime('%Y%m%d_%H%M%S')
		backup = f"{self.config_path}.backup_{ts}"
		try:
			import shutil
			shutil.copy2(self.config_path, backup)
			logger.info(f"配置已备份到: {backup}")
			return backup
		except Exception as e:
			logger.warning(f"备份配置失败: {e}")
			return None

	def get_logs(self) -> List[LogConfig]:
		cfg = self.load_config()
		out = []
		for ld in cfg.get('logs', []):
			try:
				out.append(LogConfig.from_dict(ld))
			except Exception as e:
				logger.warning(f"解析日志配置失败: {e}")
		return out

	def get_log_by_name(self, name: str, group: Optional[str] = None) -> Optional[LogConfig]:
		for log in self.get_logs():
			if log.name == name and (group is None or log.group == group):
				return log
		return None

	def get_log_by_unique_key(self, name: str, group: Optional[str] = None, path: Optional[str] = None) -> Optional[LogConfig]:
		for log in self.get_logs():
			if log.name == name and log.group == group and (path is None or log.path == path):
				return log
		return None

	def get_log_summary(self) -> List[Dict[str, Any]]:
		summary = []
		for log in self.get_logs():
			summary.append({
				'name': log.name,
				'path': log.path,
				'ssh_count': len(log.sshs),
				'description': log.description,
				'group': log.group
			})
		return summary

	def get_log_detail(self, name: str) -> Optional[Dict[str, Any]]:
		log = self.get_log_by_name(name)
		if not log:
			return None
		ssh_configs = []
		for ssh in log.sshs:
			sc = ssh.copy()
			if 'password' in sc:
				sc['password'] = '***'
			ssh_configs.append(sc)
		return {
			'name': log.name,
			'path': log.path,
			'description': log.description,
			'group': log.group,
			'ssh_configs': ssh_configs,
			'ssh_count': len(ssh_configs)
		}

__all__ = ['ConfigService']
