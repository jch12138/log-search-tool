"""Interactive terminal session management (migrated)."""

import threading
import time
import uuid
import codecs
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import paramiko
from app.services.utils.encoding import decode_bytes


@dataclass
class TerminalSession:
	terminal_id: str
	session_id: str
	host: str
	port: int
	username: str
	status: str
	created_at: str
	last_activity: str
	current_directory: str = "~"
	current_prompt: str = ""
	command_count: int = 0
	session_history: List[Dict[str, Any]] = None

	def __post_init__(self):
		if self.session_history is None:
			self.session_history = []


class TerminalService:
	def __init__(self, idle_timeout: int | None = None, check_interval: int = 30):
		self._logger = logging.getLogger(__name__)
		self.sessions: Dict[str, Dict[str, Any]] = {}
		self.session_info: Dict[str, TerminalSession] = {}
		self._lock = threading.Lock()
		self._idle_timeout = idle_timeout or 0  # 0 表示不启用
		self._check_interval = check_interval
		self._close_listeners = []  # callbacks(payload: dict)
		if self._idle_timeout > 0:
			threading.Thread(target=self._idle_reaper, daemon=True).start()

	def create_terminal(self, host: str, port: int = 22, username: str = "", password: str = "", private_key: str = "", initial_command: str = "") -> TerminalSession:
		terminal_id = f"term_{uuid.uuid4().hex[:8]}"
		session_id = f"session_{uuid.uuid4().hex[:6]}"
		if not (password or private_key):
			raise ValueError("必须提供密码或私钥")
		ssh_client = paramiko.SSHClient()
		ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		kwargs = {'hostname': host, 'port': port, 'username': username, 'timeout': 10}
		if password:
			kwargs['password'] = password
		else:  # pragma: no cover - rarely used branch
			from io import StringIO
			key_file = StringIO(private_key)
			try:
				kwargs['pkey'] = paramiko.RSAKey.from_private_key(key_file)
			except Exception:
				key_file.seek(0)
				kwargs['pkey'] = paramiko.ECDSAKey.from_private_key(key_file)
		ssh_client.connect(**kwargs)
		channel = ssh_client.invoke_shell(term='xterm-256color')
		channel.settimeout(0.0)
		session = TerminalSession(
			terminal_id=terminal_id,
			session_id=session_id,
			host=host,
			port=port,
			username=username,
			status="connected",
			created_at=datetime.now().isoformat() + "Z",
			last_activity=datetime.now().isoformat() + "Z",
		)
		with self._lock:
			self.sessions[terminal_id] = {
				'ssh_client': ssh_client,
				'channel': channel,
				'buffer': [],
				'decoder': codecs.getincrementaldecoder('utf-8')(),
				'encoding': 'utf-8',
				'lock': threading.Lock(),
				'created_at': datetime.now(),
			}
			self.session_info[terminal_id] = session
		# 连接日志
		self._logger.info("[terminal] session created: %s (session=%s) user=%s host=%s port=%s", terminal_id, session_id, username, host, port)
		threading.Thread(target=self._output_reader, args=(terminal_id,), daemon=True).start()
		try:
			channel.send("export LANG=C.UTF-8 LC_ALL=C.UTF-8\n")
		except Exception:
			pass
		if initial_command:
			time.sleep(1)
			self.send_command(terminal_id, initial_command)
		return session

	def get_terminals(self) -> Dict[str, Any]:
		with self._lock:
			items = [asdict(s) for s in self.session_info.values()]
			active = sum(1 for s in self.session_info.values() if s.status == 'connected')
			return {"terminals": items, "total_count": len(items), "active_count": active}

	def get_terminal(self, terminal_id: str) -> Optional[TerminalSession]:
		with self._lock:
			return self.session_info.get(terminal_id)

	def close_terminal(self, terminal_id: str) -> Dict[str, Any]:
		with self._lock:
			sd = self.sessions.pop(terminal_id, None)
			si = self.session_info.pop(terminal_id, None)
		if not sd or not si:
			raise ValueError("终端会话不存在")
		try:
			sd['channel'].close()
			sd['ssh_client'].close()
		except Exception:
			pass
		created_at = sd['created_at']
		closed_at = datetime.now()
		duration = closed_at - created_at
		payload = {
			'message': '终端会话已关闭',
			'terminal_id': terminal_id,
			'closed_at': closed_at.isoformat() + 'Z',
			'session_duration': str(duration).split('.')[0],
			'commands_executed': si.command_count
		}
		self._logger.info("[terminal] session closed: %s user=%s host=%s duration=%s commands=%s", terminal_id, si.username, si.host, payload['session_duration'], si.command_count)
		for cb in list(self._close_listeners):  # fire events
			try:
				cb(payload)
			except Exception:
				continue
		return payload

	def register_close_listener(self, callback):  # pragma: no cover - wiring
		if callable(callback):
			self._close_listeners.append(callback)

	def touch(self, terminal_id: str):  # pragma: no cover - realtime
		with self._lock:
			si = self.session_info.get(terminal_id)
			if si:
				si.last_activity = datetime.now().isoformat() + 'Z'

	def send_command(self, terminal_id: str, command: str):
		with self._lock:
			sd = self.sessions.get(terminal_id)
			si = self.session_info.get(terminal_id)
		if not sd or not si:
			raise ValueError("终端会话不存在")
		try:
			sd['channel'].send(command.encode(sd['encoding']))
			si.last_activity = datetime.now().isoformat() + 'Z'
			si.command_count += 1
			si.session_history.append({'timestamp': si.last_activity, 'command': command, 'output': ''})
		except Exception as e:
			si.status = 'error'
			raise RuntimeError(f"发送命令失败: {e}")

	def send_raw(self, terminal_id: str, data: str):  # pragma: no cover - realtime path
		"""发送原始按键/数据，不计入命令统计，用于交互式终端输入。"""
		if not data:
			return
		with self._lock:
			sd = self.sessions.get(terminal_id)
			si = self.session_info.get(terminal_id)
		if not sd or not si:
			raise ValueError("终端会话不存在")
		try:
			sd['channel'].send(data.encode(sd['encoding']))
			si.last_activity = datetime.now().isoformat() + 'Z'
		except Exception:
			si.status = 'error'

	def resize_terminal(self, terminal_id: str, cols: int, rows: int):  # pragma: no cover - UI path
		with self._lock:
			sd = self.sessions.get(terminal_id)
			si = self.session_info.get(terminal_id)
		if not sd or not si:
			raise ValueError("终端会话不存在")
		sd['channel'].resize_pty(width=cols, height=rows)
		si.last_activity = datetime.now().isoformat() + 'Z'

	def get_output(self, terminal_id: str) -> str:
		sd = self.sessions.get(terminal_id)
		if not sd:
			raise ValueError("终端会话不存在")
		with sd['lock']:
			if not sd['buffer']:
				return ''
			out = ''.join(sd['buffer'])
			sd['buffer'].clear()
		with self._lock:
			si = self.session_info.get(terminal_id)
			if si:
				si.last_activity = datetime.now().isoformat() + 'Z'
		return out

	def _output_reader(self, terminal_id: str):  # pragma: no cover - realtime thread
		sd = self.sessions.get(terminal_id)
		if not sd:
			return
		channel = sd['channel']
		decoder = sd['decoder']
		while True:
			if channel.closed:
				break
			try:
				if channel.recv_ready():
					data = channel.recv(8192)
					if not data:
						break
					try:
						text = decoder.decode(data)
					except Exception:
						text = decode_bytes(data)
					with sd['lock']:
						sd['buffer'].append(text)
				else:
					time.sleep(0.05)
			except Exception:
				time.sleep(0.1)
		try:
			tail = decoder.decode(b"", final=True)
		except Exception:
			tail = ""
		with sd['lock']:
			if tail:
				sd['buffer'].append(tail)
			sd['buffer'].append("\n[会话已结束]\n")
		with self._lock:
			si = self.session_info.get(terminal_id)
			if si:
				si.status = 'disconnected'

	def _idle_reaper(self):  # pragma: no cover - background cleaner
		while True:
			try:
				if self._idle_timeout <= 0:
					return
				cutoff = time.time() - self._idle_timeout
				victims = []
				with self._lock:
					for tid, si in list(self.session_info.items()):
						try:
							last = si.last_activity
							# ISO format with Z; parse quickly
							lt = last.split('.')[0].replace('Z','')
							# Fallback parse (YYYY-MM-DDTHH:MM:SS)
							import datetime as _dt
							ts = _dt.datetime.fromisoformat(lt).timestamp()
							if ts < cutoff:
								victims.append(tid)
						except Exception:
							continue
				for tid in victims:
					try:
						self.close_terminal(tid)
					except Exception:
						pass
			except Exception:
				pass
			time.sleep(self._check_interval)

__all__ = ['TerminalService', 'TerminalSession']
