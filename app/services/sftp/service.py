"""SFTP file management service (migrated)."""

import os
import posixpath
import stat
import tempfile
import zipfile
import shutil
import time
import uuid
import paramiko
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from app.services.utils.encoding import decode_bytes

logger = logging.getLogger(__name__)


@dataclass
class SFTPConnection:
	connection_id: str
	connection_name: str
	host: str
	port: int
	username: str
	connected_at: str
	status: str = "active"


class SFTPService:
	def __init__(self):
		self.connections: Dict[str, Dict[str, Any]] = {}
		self.connection_info: Dict[str, SFTPConnection] = {}

	def _decode_filename(self, name: Any) -> str:
		if isinstance(name, str):
			return name
		if isinstance(name, bytes):
			return decode_bytes(name)
		return str(name)

	def connect(self, host: str, port: int = 22, username: str = "", password: str = "", connection_name: str = "") -> SFTPConnection:
		connection_id = f"conn_{uuid.uuid4().hex[:8]}"
		if not connection_name:
			connection_name = f"{host}:{port}"
		ssh_client = paramiko.SSHClient()
		ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh_client.connect(hostname=host, port=port, username=username, password=password, timeout=10)
		sftp_client = ssh_client.open_sftp()
		info = SFTPConnection(
			connection_id=connection_id,
			connection_name=connection_name,
			host=host,
			port=port,
			username=username,
			connected_at=datetime.now().isoformat() + 'Z'
		)
		self.connections[connection_id] = {'ssh': ssh_client, 'sftp': sftp_client, 'created_at': datetime.now()}
		self.connection_info[connection_id] = info
		return info

	def disconnect(self, connection_id: str) -> Dict[str, Any]:
		cd = self.connections.pop(connection_id, None)
		ci = self.connection_info.pop(connection_id, None)
		if not cd or not ci:
			raise ValueError("SFTP连接不存在")
		try:
			cd['sftp'].close()
			cd['ssh'].close()
		except Exception:
			pass
		return {"message": f"已断开连接 {connection_id}", "connection_id": connection_id}

	def get_connections(self) -> Dict[str, Any]:
		return {"connections": [asdict(c) for c in self.connection_info.values()], "total": len(self.connection_info)}

	def list_directory(self, connection_id: str, path: str = '.') -> Dict[str, Any]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		sftp = self.connections[connection_id]['sftp']
		home = sftp.getcwd() or '/'
		if not path or path in ('.', './'):
			remote_path = home
		elif path.startswith('~'):
			remote_path = posixpath.normpath(path.replace('~', home, 1))
		elif not path.startswith('/'):
			remote_path = posixpath.normpath(posixpath.join(home, path))
		else:
			remote_path = posixpath.normpath(path)
		try:
			sftp.stat(remote_path)
		except FileNotFoundError:
			remote_path = home
		try:
			entries = sftp.listdir_attr(remote_path)
		except UnicodeDecodeError as e:  # pragma: no cover - rare
			logger.warning(f"编码问题: {e}")
			return self._list_directory_via_ssh(connection_id, remote_path)
		items = []
		for it in entries:
			try:
				original = it.filename
				converted = self._decode_filename(original)
				item = {
					'name': converted,
					'original_name': original,
					'type': 'directory' if stat.S_ISDIR(it.st_mode) else 'file',
					'size': getattr(it, 'st_size', 0),
					'size_human': self._format_size(getattr(it, 'st_size', 0)),
					'modified_time': datetime.fromtimestamp(getattr(it, 'st_mtime', 0)).isoformat() + 'Z' if hasattr(it, 'st_mtime') else '',
					'permissions': oct(it.st_mode)[-3:] if hasattr(it, 'st_mode') else '',
					'is_directory': stat.S_ISDIR(it.st_mode) if hasattr(it, 'st_mode') else False
				}
				items.append(item)
			except Exception:
				continue
		items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
		return {
			'current_path': remote_path,
			'parent_path': posixpath.dirname(remote_path) if remote_path != '/' else None,
			'items': items,
			'total_items': len(items)
		}

	def _list_directory_via_ssh(self, connection_id: str, remote_path: str) -> Dict[str, Any]:  # pragma: no cover
		ssh = self.connections[connection_id]['ssh']
		# 不再强制 export LANG/LC_ALL，避免权限不足；直接 ls，必要时前端/解码逻辑兜底
		cmd = f"ls -la '{remote_path}'"
		_, stdout, stderr = None, *ssh.exec_command(cmd)[1:]
		output = stdout.read()
		lines = []
		for enc in ['utf-8', 'gb2312']:
			try:
				lines = output.decode(enc).strip().split('\n')[1:]
				break
			except Exception:
				continue
		items = []
		for line in lines:
			if not line.strip():
				continue
			parts = line.split()
			if len(parts) < 9:
				continue
			perms = parts[0]
			size = int(parts[4]) if parts[4].isdigit() else 0
			filename = ' '.join(parts[8:])
			if filename in ['.', '..']:
				continue
			is_dir = perms.startswith('d')
			items.append({
				'name': filename,
				'original_name': filename,
				'type': 'directory' if is_dir else 'file',
				'size': size,
				'size_human': self._format_size(size),
				'modified_time': '',
				'permissions': perms[1:],
				'is_directory': is_dir
			})
		items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
		return {
			'current_path': remote_path,
			'parent_path': posixpath.dirname(remote_path) if remote_path != '/' else None,
			'items': items,
			'total_items': len(items)
		}

	def download_file(self, connection_id: str, remote_path: str) -> Tuple[str, str]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		sftp = self.connections[connection_id]['sftp']
		filename = posixpath.basename(remote_path)
		tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
		tmp_path = tmp.name
		tmp.close()
		sftp.get(remote_path, tmp_path)
		return tmp_path, filename

	def batch_download(self, connection_id: str, paths: List[str]) -> Tuple[str, str]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		if not paths:
			raise ValueError("没有需要下载的文件")
		sftp = self.connections[connection_id]['sftp']
		staging = tempfile.mkdtemp(prefix='sftp_batch_')

		def fetch_dir(remote_dir: str, local_dir: str):
			os.makedirs(local_dir, exist_ok=True)
			for item in sftp.listdir_attr(remote_dir):
				rp = posixpath.join(remote_dir, item.filename)
				lp = os.path.join(local_dir, item.filename)
				if stat.S_ISDIR(item.st_mode):
					fetch_dir(rp, lp)
				else:
					try:
						sftp.get(rp, lp)
					except Exception:
						pass

		for rp in paths:
			rp = posixpath.normpath(rp)
			base = posixpath.basename(rp.rstrip('/')) or 'root'
			final = base
			count = 2
			while os.path.exists(os.path.join(staging, final)):
				final = f"{base}_{count}"
				count += 1
			target = os.path.join(staging, final)
			try:
				attr = sftp.stat(rp)
				if stat.S_ISDIR(attr.st_mode):
					fetch_dir(rp, target)
				else:
					sftp.get(rp, target)
			except Exception:
				continue
		zip_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
		zip_name = f"batch_{int(time.time())}.zip"
		with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
			for root, _, files in os.walk(staging):
				for f in files:
					ap = os.path.join(root, f)
					rp = os.path.relpath(ap, staging)
					zf.write(ap, rp)
		shutil.rmtree(staging, ignore_errors=True)
		return zip_path, zip_name

	def upload_file(self, connection_id: str, local_file_path: str, remote_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		sftp = self.connections[connection_id]['sftp']
		if filename is None:
			filename = os.path.basename(local_file_path)
		remote_file_path = posixpath.join(remote_path, filename)
		sftp.put(local_file_path, remote_file_path)
		size = os.path.getsize(local_file_path)
		return {"message": f"文件 {filename} 上传成功", "remote_path": remote_file_path, "file_size": size}

	def create_directory(self, connection_id: str, remote_path: str, dir_name: str) -> Dict[str, Any]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		sftp = self.connections[connection_id]['sftp']
		full = posixpath.join(remote_path, dir_name)
		sftp.mkdir(full)
		return {"message": f"目录 {dir_name} 创建成功", "full_path": full}

	def delete_item(self, connection_id: str, remote_path: str, is_directory: bool = False) -> Dict[str, Any]:
		if connection_id not in self.connections:
			raise ValueError("SFTP连接不存在")
		sftp = self.connections[connection_id]['sftp']
		if is_directory:
			sftp.rmdir(remote_path)
			t = 'directory'
		else:
			sftp.remove(remote_path)
			t = 'file'
		return {"message": '文件删除成功' if t == 'file' else '目录删除成功', "remote_path": remote_path, "type": t}

	def _format_size(self, size: int) -> str:
		if size == 0:
			return '0 B'
		units = ["B", "KB", "MB", "GB", "TB"]
		import math
		i = int(math.floor(math.log(size, 1024)))
		p = math.pow(1024, i)
		s = round(size / p, 2)
		return f"{s} {units[i]}"

	def cleanup(self):  # pragma: no cover
		for cid in list(self.connections.keys()):
			try:
				self.disconnect(cid)
			except Exception:
				pass

__all__ = ['SFTPService', 'SFTPConnection']
