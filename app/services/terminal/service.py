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
from app.services.utils.encoding import decode_bytes, smart_decode

def _smart_decode_chunk(data: bytes, last_good: str | None, forced: str | None):
	return smart_decode(data, last_good=last_good, forced=forced)


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
	session_history: Optional[List[Dict[str, Any]]] = None

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

	def create_terminal(self, host: str, port: int = 22, username: str = "", password: str = "", private_key: str = "", initial_command: str = "", env_init: bool = True) -> TerminalSession:
		"""Create an interactive terminal (SSH) session.

		env_init=True combines:
		  1) Re-exec login shell (-l) to load profile scripts.
		  2) Conditional UTF-8 locale setup if LANG is empty/C/POSIX.
		Markers: __AUTO_LOCALE_SET:<loc> or __AUTO_LOCALE_SKIP for diagnostics.
		"""
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
				'encoding': 'utf-8',          # last successful detected encoding
				'forced_encoding': None,       # user override via API
				'env_init': env_init,
				'last_locale': None,
				'lock': threading.Lock(),
				'created_at': datetime.now(),
			}
			self.session_info[terminal_id] = session
		# 连接日志
		self._logger.info("[terminal] session created: %s (session=%s) user=%s host=%s port=%s", terminal_id, session_id, username, host, port)
		threading.Thread(target=self._output_reader, args=(terminal_id,), daemon=True).start()
		# 环境初始化：登录 shell + 条件 locale
		if env_init:
			try:
				# 合并：先条件 locale，输出标记，再 exec 登录 shell；exec 后续命令不会执行，因此 locale 逻辑必须放在 exec 之前
				_init_cmd = (
					"# init env: conditional locale + login shell\n"
					"CUR=$(echo $LANG); "
					"if [ -z \"$CUR\" ] || [ \"$CUR\" = C ] || [ \"$CUR\" = POSIX ]; then "
					"LOC=$(locale -a 2>/dev/null | grep -i -E 'UTF-8|utf8' | head -n1); "
					"if [ -n \"$LOC\" ]; then export LANG=$LOC LC_CTYPE=$LOC LC_ALL=$LOC; echo __AUTO_LOCALE_SET:$LOC; else echo __AUTO_LOCALE_SKIP; fi; "
					"else echo __AUTO_LOCALE_SKIP; fi; "
					"if command -v getent >/dev/null 2>&1; then USHELL=$(getent passwd $(whoami) | cut -d: -f7); fi; "
					"if [ -z \"$USHELL\" ]; then USHELL=\"$SHELL\"; fi; "
					"if [ -z \"$USHELL\" ]; then if command -v bash >/dev/null 2>&1; then USHELL=bash; elif command -v sh >/dev/null 2>&1; then USHELL=sh; fi; fi; "
					"if [ -n \"$USHELL\" ]; then exec -a -${USHELL##*/} $USHELL -l; fi\n"
				)
				channel.send(_init_cmd.encode('utf-8', errors='ignore'))
				# 给新登录 shell 少量时间初始化
				time.sleep(2.0)
			except Exception:
				pass
		if initial_command:
			time.sleep(1)
			self.send_command(terminal_id, initial_command)
		return session

	def set_locale(self, terminal_id: str, locale: str | None = None, auto: bool = False) -> dict:
		"""Set locale for the remote shell session (best-effort).

		If auto=True, attempt to pick a UTF-8 locale available on the remote host.
		Stores last attempted locale in session dict for inspection.
		"""
		with self._lock:
			sd = self.sessions.get(terminal_id)
		if not sd:
			raise ValueError("终端会话不存在")
		channel = sd['channel']
		chosen = locale
		cmd = None
		if auto:
			cmd = (
				"LOC=$(locale -a 2>/dev/null | grep -i -E 'UTF-8|utf8' | head -n1); "
				"if [ -n \"$LOC\" ]; then export LANG=$LOC LC_CTYPE=$LOC LC_ALL=$LOC; echo __SET_LOCALE:$LOC; else echo __SET_LOCALE:FAILED; fi\n"
			)
		elif locale:
			cmd = f"export LANG={locale} LC_CTYPE={locale} LC_ALL={locale}; echo __SET_LOCALE:{locale}\n"
		if cmd:
			try:
				channel.send(cmd.encode('utf-8', errors='ignore'))
				chosen = chosen or 'auto'
			except Exception as e:  # pragma: no cover
				chosen = f"failed:{e}"  # record failure
		with self._lock:
			sd['last_locale'] = chosen
		return {'terminal_id': terminal_id, 'locale': chosen}

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
			enc = sd.get('forced_encoding') or sd.get('encoding') or 'utf-8'
			sd['channel'].send(command.encode(enc, errors='ignore'))
			si.last_activity = datetime.now().isoformat() + 'Z'
			si.command_count += 1
			if si.session_history is None:
				si.session_history = []
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
			enc = sd.get('forced_encoding') or sd.get('encoding') or 'utf-8'
			sd['channel'].send(data.encode(enc, errors='ignore'))
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
		last_good = sd.get('encoding', 'utf-8')
		while True:
			if channel.closed:
				break
			try:
				if channel.recv_ready():
					data = channel.recv(8192)
					if not data:
						break
					# We decode per chunk to adjust encoding dynamically if needed
					forced = sd.get('forced_encoding')
					text, detected = _smart_decode_chunk(data, last_good, forced)
					if not forced and detected and detected != last_good:
						last_good = detected
						with self._lock:
							# persist last successful encoding
							sd['encoding'] = detected
					# Locale marker parsing
					if '__AUTO_LOCALE_SET:' in text or '__SET_LOCALE:' in text:
						marker = None
						for line in text.splitlines():
							if line.startswith('__AUTO_LOCALE_SET:'):
								marker = line.split(':',1)[1].strip(); break
							if line.startswith('__SET_LOCALE:'):
								marker = line.split(':',1)[1].strip(); break
						if marker:
							with self._lock:
								sd['last_locale'] = marker
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
