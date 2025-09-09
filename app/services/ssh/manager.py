"""SSH connection management implementation (migrated)."""

import paramiko
import threading
import time
import logging
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, Future
from app.services.utils.encoding import decode_bytes

logger = logging.getLogger(__name__)


class SSHConnection:
	"""Encapsulates a single SSH connection with thread-safe exec."""

	def __init__(self, ssh_config: Dict[str, Any]):
		self.config = ssh_config
		self.client: Optional[paramiko.SSHClient] = None
		self.connected = False
		self.last_used = time.time()
		self.lock = threading.Lock()

	def connect(self) -> bool:
		try:
			self.client = paramiko.SSHClient()
			self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			params = {
				'hostname': self.config['host'],
				'port': self.config.get('port', 22),
				'username': self.config['username'],
				'timeout': 30
			}
			if 'password' in self.config:
				params['password'] = self.config['password']
			self.client.connect(**params)
			self.connected = True
			self.last_used = time.time()
			logger.info(f"SSH连接成功: {self.config['host']}")
			return True
		except Exception as e:  # pragma: no cover - network dependent
			logger.error(f"SSH连接失败 {self.config.get('host')}: {e}")
			self.connected = False
			if self.client:
				self.client.close()
				self.client = None
			return False

	def execute_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
		if not self.connected or not self.client:
			raise RuntimeError("SSH连接未建立")
		with self.lock:
			stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
			raw_out = stdout.read() or b""
			raw_err = stderr.read() or b""
			out = decode_bytes(raw_out)
			err = decode_bytes(raw_err)
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
