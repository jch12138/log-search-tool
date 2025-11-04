"""SSH connection management implementation (migrated)."""

import paramiko
import threading
import time
import logging
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, Future
from app.config.system_settings import Settings
from app.services.utils.encoding import EncodingDetector, smart_decode

logger = logging.getLogger(__name__)


class SSHConnection:
	"""Encapsulates a single SSH connection with thread-safe exec."""

	def __init__(self, ssh_config: Dict[str, Any]):
		self.config = ssh_config
		self.client: Optional[paramiko.SSHClient] = None
		self.connected = False
		self.last_used = time.time()
		self.lock = threading.Lock()
		self._settings = Settings()
		self._remote_encoding: Optional[str] = None  # 缓存远程编码

	def connect(self) -> bool:
		try:
			self.client = paramiko.SSHClient()
			self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			params = {
				'hostname': self.config['host'],
				'port': self.config.get('port', 22),
				'username': self.config['username'],
				'timeout': self._settings.SSH_TIMEOUT
			}
			if 'password' in self.config:
				params['password'] = self.config['password']
			self.client.connect(**params)
			self.connected = True
			self.last_used = time.time()
			logger.info(f"SSH连接成功: {self.config['host']}")
			
			# 检测远程服务器的编码环境
			self._detect_remote_encoding()
			
			return True
		except Exception as e:  # pragma: no cover - network dependent
			logger.error(f"SSH连接失败 {self.config.get('host')}: {e}")
			self.connected = False
			if self.client:
				self.client.close()
				self.client = None
			return False

	def _detect_remote_encoding(self):
		"""检测远程服务器的默认编码"""
		try:
			# 生成缓存键
			cache_key = f"{self.config['host']}:{self.config.get('port', 22)}:{self.config['username']}"
			
			# 检查缓存
			cached = EncodingDetector.get_cached_encoding(cache_key)
			if cached:
				self._remote_encoding = cached
				logger.debug(f"使用缓存的编码: {cached} (主机: {self.config['host']})")
				return
			
			# 执行 locale 命令检测编码
			stdin, stdout, stderr = self.client.exec_command("locale | grep LC_CTYPE", timeout=5)
			output = stdout.read().decode('ascii', errors='ignore').strip()
			
			# 使用 EncodingDetector 解析
			self._remote_encoding = EncodingDetector.detect_from_locale(output)
			
			# 缓存结果
			EncodingDetector.cache_encoding(cache_key, self._remote_encoding)
			
			logger.info(f"检测到远程编码: {self._remote_encoding} (主机: {self.config['host']})")
		except Exception as e:
			# 检测失败时默认 UTF-8
			logger.warning(f"无法检测远程编码，使用 UTF-8: {e}")
			self._remote_encoding = 'utf-8'

	def execute_command(self, command: str, timeout: int | None = None) -> tuple[str, str, int]:
		if not self.connected or not self.client:
			raise RuntimeError("SSH连接未建立")
		with self.lock:
			_effective_timeout = timeout if timeout is not None else self._settings.SSH_TIMEOUT
			stdin, stdout, stderr = self.client.exec_command(command, timeout=_effective_timeout)
			raw_out = stdout.read() or b""
			raw_err = stderr.read() or b""
			
			# 使用智能解码，传入检测到的编码作为首选
			out, encoding_used = smart_decode(raw_out, preferred_encoding=self._remote_encoding)
			err, _ = smart_decode(raw_err, preferred_encoding=self._remote_encoding)
			
			# 如果实际使用的编码与检测的不同，记录日志
			if encoding_used != self._remote_encoding:
				logger.debug(f"实际使用编码 {encoding_used} 与检测编码 {self._remote_encoding} 不同")
			
			exit_code = stdout.channel.recv_exit_status()
			self.last_used = time.time()
			return out, err, exit_code

	def is_alive(self) -> bool:
		if not self.connected or not self.client:
			return False
		try:
			transport = self.client.get_transport()
			return bool(transport and transport.is_active())
		except Exception:
			return False

	def close(self):
		if self.client:
			try:
				self.client.close()
			except Exception:
				pass
		self.client = None
		self.connected = False


class SSHConnectionManager:
	"""Lightweight connection pool with periodic cleanup."""

	def __init__(self, max_connections: int = 20):
		self.connections: Dict[str, SSHConnection] = {}
		self.max_connections = max_connections
		self.lock = threading.Lock()
		self.executor = ThreadPoolExecutor(max_workers=10)
		self._start_cleanup_thread()

	def _connection_key(self, cfg: Dict[str, Any]) -> str:
		return f"{cfg['host']}:{cfg.get('port', 22)}:{cfg['username']}"

	def get_connection(self, cfg: Dict[str, Any]) -> Optional[SSHConnection]:
		key = self._connection_key(cfg)
		with self.lock:
			if key in self.connections:
				conn = self.connections[key]
				if conn.is_alive():
					return conn
				conn.close()
				del self.connections[key]
			if len(self.connections) >= self.max_connections:
				self._cleanup_old_connections()
			conn = SSHConnection(cfg)
			if conn.connect():
				self.connections[key] = conn
				return conn
			return None

	def execute_command_async(self, cfg: Dict[str, Any], command: str) -> Future:
		def _run():
			conn = self.get_connection(cfg)
			if not conn:
				raise RuntimeError(f"无法连接到 {cfg.get('host')}")
			return conn.execute_command(command)
		return self.executor.submit(_run)

	def _cleanup_old_connections(self):
		now = time.time()
		stale = [k for k, c in self.connections.items() if now - c.last_used > 300]
		for k in stale:
			conn = self.connections.pop(k, None)
			if conn:
				conn.close()
				logger.info(f"清理老旧连接: {k}")

	def _start_cleanup_thread(self):  # pragma: no cover - background
		def loop():
			while True:
				time.sleep(60)
				with self.lock:
					self._cleanup_old_connections()
		threading.Thread(target=loop, daemon=True).start()

	def close_all(self):
		with self.lock:
			for c in self.connections.values():
				c.close()
			self.connections.clear()
		self.executor.shutdown(wait=True)

	def get_stats(self) -> Dict[str, Any]:
		with self.lock:
			total = len(self.connections)
			active = sum(1 for c in self.connections.values() if c.is_alive())
			return {
				'total_connections': total,
				'active_connections': active,
				'max_connections': self.max_connections
			}

__all__ = [
	'SSHConnection', 'SSHConnectionManager'
]
