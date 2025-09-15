"""Log search service (migrated)."""

import os
import logging
import time
import re
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.models import SearchParams, SearchResult, MultiHostSearchResult
from app.services.ssh import SSHConnectionManager
from app.services.utils.encoding import decode_bytes
from app.services.utils.filename_resolver import resolve_log_filename

logger = logging.getLogger(__name__)


class LogSearchService:
	def __init__(self):
		self.ssh_manager = SSHConnectionManager()
		self._reverse_cmd_cache: Dict[str, str] = {}

	def _get_reverse_command(self, ssh_config: Dict[str, Any]) -> str:
		host = ssh_config.get('host', 'localhost')
		if host in self._reverse_cmd_cache:
			return self._reverse_cmd_cache[host]
		try:  # pragma: no cover - network
			conn = self.ssh_manager.get_connection(ssh_config)
			if conn:
				stdout, _, code = conn.execute_command("which tac", timeout=5)
				if code == 0 and stdout.strip():
					cmd = 'tac'
				else:
					cmd = "sed '1!G;h;$!d'"
			else:
				cmd = "sed '1!G;h;$!d'"
		except Exception:
			cmd = "sed '1!G;h;$!d'"
		self._reverse_cmd_cache[host] = cmd
		return cmd

	def search_multi_host(self, log_config: Dict[str, Any], search_params: SearchParams) -> MultiHostSearchResult:
		search_params.validate()
		sshs = log_config.get('sshs', [])
		if not sshs:
			raise ValueError("日志配置中没有SSH主机")
		log_name = log_config['name']
		# 顶层路径用于兼容，优先使用每个 ssh 下的 path
		legacy_path = log_config.get('path')
		start = time.time()
		results: List[SearchResult] = []
		if len(sshs) == 1:
			ssh0 = sshs[0]
			log_path0 = ssh0.get('path') or legacy_path or ''
			# 注入 ssh_index 以便前端使用 host|index 进行区分
			ssh0['ssh_index'] = 0
			results.append(self._search_single_host(ssh0, log_path0, search_params, 0))
			parallel = False
		else:
			with ThreadPoolExecutor(max_workers=min(len(sshs), 10)) as executor:  # pragma: no cover - concurrency
				fut_map = {}
				for i, cfg in enumerate(sshs):
					cfg['ssh_index'] = i
					fut = executor.submit(self._search_single_host, cfg, (cfg.get('path') or legacy_path or ''), search_params, i)
					fut_map[fut] = i
				for fut in as_completed(fut_map):
					i = fut_map[fut]
					cfg = sshs[i]
					try:
						results.append(fut.result(timeout=30))
					except Exception as e:
						logger.error(f"搜索失败 {cfg.get('host')}: {e}")
						results.append(SearchResult(host=cfg.get('host', 'unknown'), ssh_index=i, results=[f"[{cfg.get('host', 'unknown')}] 搜索失败: {e}"], total_results=1, search_time=0.0, search_result={'content': '', 'file_path': '', 'keyword': search_params.keyword, 'total_lines': 0, 'search_time': 0.0, 'matches': []}, success=False, error=str(e)))
			parallel = True
		results.sort(key=lambda r: r.ssh_index)
		total = sum(r.total_results for r in results if r.success)
		elapsed = time.time() - start
		return MultiHostSearchResult(log_name=log_name, keyword=search_params.keyword, search_params={'keyword': search_params.keyword, 'search_mode': search_params.search_mode, 'context_span': search_params.context_span, 'use_regex': search_params.use_regex}, total_hosts=len(sshs), hosts=results, total_results=total, total_search_time=elapsed, parallel_execution=parallel)

	def _search_single_host(self, ssh_config: Dict[str, Any], log_path: str, search_params: SearchParams, ssh_index: int) -> SearchResult:
		start = time.time()
		host = ssh_config.get('host', 'unknown')
		try:
			# 同时获取解析后的实际文件路径，避免下载时仍然携带占位符
			command, resolved_file_path = self._build_search_command(log_path, search_params, ssh_config)
			conn = self.ssh_manager.get_connection(ssh_config)
			if not conn:
				raise RuntimeError("SSH连接失败")
			stdout, stderr, code = conn.execute_command(command, timeout=30)
			if code != 0 and stderr:
				raise RuntimeError(f"搜索命令执行失败: {stderr}")
			if stdout:
				try:
					stdout.encode('utf-8')
				except Exception:
					stdout = decode_bytes(stdout.encode('latin-1', errors='ignore'))
			# 解析 grep 输出，移除行号/分隔符，保持与真实日志内容一致
			lines = stdout.strip().split('\n') if stdout.strip() else []
			results, matches = self._parse_grep_output(lines, resolved_file_path)
			# 后端行数限制（保护前端渲染性能）
			truncated = False
			original_total = len(results)
			from app.models import SearchParams as _SP  # 局部导入避免循环
			if isinstance(search_params, _SP) and search_params.max_lines:
				limit = search_params.max_lines
				if limit and len(results) > limit:
					# 需求：始终保留“最新”的日志行
					# 非 reverse_order：结果按时间正序 -> 取末尾 limit 条
					# reverse_order：结果已被反转（最新在前） -> 取前 limit 条
					if getattr(search_params, 'reverse_order', False):
						results = results[:limit]
						matches = matches[:limit]
					else:
						results = results[-limit:]
						matches = matches[-limit:]
					truncated = True
			elapsed = time.time() - start
			return SearchResult(
				host=host,
				ssh_index=ssh_index,
				results=results,
				total_results=len(results),
				search_time=elapsed,
				search_result={
					'content': stdout.strip(),
					'file_path': resolved_file_path,
					'keyword': search_params.keyword,
					'total_lines': len(results),
					'original_total_lines': original_total,
					'truncated': truncated,
					'search_time': elapsed,
					'matches': matches
				},
				success=True
			)
		except Exception as e:
			elapsed = time.time() - start
			return SearchResult(host=host, ssh_index=ssh_index, results=[f"[{host}] 搜索失败: {e}"], total_results=1, search_time=elapsed, search_result={'content': '', 'file_path': '', 'keyword': search_params.keyword, 'total_lines': 0, 'search_time': elapsed, 'matches': []}, success=False, error=str(e))

	def _build_search_command(self, log_path: str, search_params: SearchParams, ssh_config: Dict[str, Any]):
		reverse_cmd = self._get_reverse_command(ssh_config)
		if search_params.use_file_filter:
			host = ssh_config.get('host', 'unknown')
			# 允许使用 "host|ssh_index" 形式的键来区分同 IP 的多条 SSH 配置
			host_key = f"{host}|{ssh_config.get('ssh_index', ssh_config.get('index', ''))}"
			selected_files = search_params.selected_files or {}
			if selected_files:
				if host_key in selected_files:
					file_path = selected_files[host_key]
				elif host in selected_files:
					file_path = selected_files[host]
				else:
					file_path = log_path
			elif search_params.selected_file:
				file_path = search_params.selected_file
			else:
				file_path = log_path
		else:
			file_path = log_path
		if any(ph in file_path for ph in ['{YYYY}', '{MM}', '{DD}', '{N}']):
			try:
				conn = self.ssh_manager.get_connection(ssh_config)
				file_path = resolve_log_filename(file_path, ssh_conn=conn)
			except Exception as e:
				logger.warning(f"文件名通配符解析失败: {file_path} - {e}")
		# 对 .gz 压缩日志进行特殊处理：先解压再 grep / tail，避免乱码
		is_gz = file_path.endswith('.gz')
		decompress = f"gzip -dc '{file_path}'" if is_gz else None
		if search_params.search_mode == 'tail':
			lines = max(100, search_params.context_span)
			if is_gz:
				cmd = f"{decompress} | tail -n {lines}"
			else:
				cmd = f"tail -n {lines} '{file_path}'"
			if search_params.reverse_order:
				cmd += f" | {reverse_cmd}"
		else:
			if not search_params.keyword:
				# 仅展示最近 100 行
				if is_gz:
					cmd = f"{decompress} | tail -n 100"
				else:
					cmd = f"tail -n 100 '{file_path}'"
				if search_params.reverse_order:
					cmd += f" | {reverse_cmd}"
			else:
				grep_cmd = 'grep -nE' if search_params.use_regex else 'grep -nF'
				if search_params.search_mode == 'context' and search_params.context_span > 0:
					grep_cmd += f" -C {search_params.context_span}"
				escaped_keyword = search_params.keyword.replace("'", "'\"'\"'")
				if is_gz:
					# 管道方式：解压 -> grep -> (限制/反转)
					cmd = f"{decompress} | {grep_cmd} '{escaped_keyword}'"
				else:
					cmd = f"{grep_cmd} '{escaped_keyword}' '{file_path}'"
				if search_params.reverse_order:
					cmd += f" | tail -n 10000 | {reverse_cmd}"
				else:
					cmd += " | head -n 10000"
		# 返回命令和解析后的实际文件路径
		return cmd, file_path

	def get_log_files(self, ssh_config: Dict[str, Any], log_path: str) -> List[Dict[str, Any]]:
		try:
			log_dir = os.path.dirname(log_path) or '.'
			host = ssh_config.get('host', 'unknown')
			conn = self.ssh_manager.get_connection(ssh_config)
			if not conn:
				raise RuntimeError('SSH连接失败')
			linux_cmd = f"find '{log_dir}' -maxdepth 1 -type f -printf '%f\t%s\t%TY-%Tm-%Td %TH:%TM:%TS\t%CY-%Cm-%Cd %CH:%CM:%CS\t%p\n' 2>/dev/null"
			stdout, stderr, code = conn.execute_command(linux_cmd)
			if code == 0 and stdout.strip():
				return self._parse_linux_find_output(stdout, host)
			mac_cmd = f"find '{log_dir}' -maxdepth 1 -type f -exec stat -f '%N|%z|%SB|%Sm|%N' -t '%Y-%m-%d %H:%M:%S' {{}} \\; 2>/dev/null"
			stdout, stderr, code = conn.execute_command(mac_cmd)
			if code == 0 and stdout.strip():
				return self._parse_macos_stat_output(stdout, host)
			ls_cmd = f"ls -la '{log_dir}' | grep '^-'"
			stdout, stderr, code = conn.execute_command(ls_cmd)
			if code == 0 and stdout.strip():
				return self._parse_ls_output(stdout, log_dir, host)
			logger.warning(f"[{host}] 无法获取目录 {log_dir} 的文件列表")
			return []
		except Exception as e:  # pragma: no cover - network
			logger.error(f"[{ssh_config.get('host', 'unknown')}] 获取文件列表失败: {e}")
			return []

	def _parse_linux_find_output(self, stdout: str, host: str) -> List[Dict[str, Any]]:
		files: List[Dict[str, Any]] = []
		for line in stdout.strip().split('\n'):
			if not line.strip():
				continue
			parts = line.split('\t')
			if len(parts) >= 5:
				try:
					files.append({'filename': parts[0], 'full_path': parts[4], 'size': int(parts[1]), 'birth_time': parts[3], 'modified_time': parts[2], 'host': host})
				except Exception:
					continue
		return files

	def _parse_macos_stat_output(self, stdout: str, host: str) -> List[Dict[str, Any]]:
		files: List[Dict[str, Any]] = []
		for line in stdout.strip().split('\n'):
			if not line.strip():
				continue
			parts = line.split('|')
			if len(parts) >= 5:
				try:
					filename = os.path.basename(parts[0])
					files.append({'filename': filename, 'full_path': parts[4], 'size': int(parts[1]), 'birth_time': parts[2], 'modified_time': parts[3], 'host': host})
				except Exception:
					continue
		return files

	def _parse_ls_output(self, stdout: str, log_dir: str, host: str) -> List[Dict[str, Any]]:
		files: List[Dict[str, Any]] = []
		for line in stdout.strip().split('\n'):
			if not line.strip():
				continue
			parts = line.split()
			if len(parts) >= 9:
				filename = parts[-1]
				size_str = parts[4]
				try:
					size = int(size_str)
				except Exception:
					size = 0
				if len(parts) >= 8:
					month, day, time_or_year = parts[5], parts[6], parts[7]
					modified = f"{month} {day} {time_or_year}"
				else:
					modified = 'unknown'
				files.append({'filename': filename, 'full_path': os.path.join(log_dir, filename), 'size': size, 'birth_time': modified, 'modified_time': modified, 'host': host})
		return files

	def _parse_grep_output(self, lines: List[str], file_path: str) -> Tuple[List[str], List[Dict[str, Any]]]:
		"""Parse grep -n / -nC output removing line numbers & context separators.

		Supports patterns like:
		  123:actual log line
		  123-actual log line (before context)
		  123=actual log line (after context)
		And ignores lines that are exactly '--' (grep context separator).
		Returns cleaned lines and match metadata with original line numbers when available.
		"""
		clean_results: List[str] = []
		matches: List[Dict[str, Any]] = []
		line_num_pattern = re.compile(r'^(\d+)([:=\-])(.*)$')
		for raw in lines:
			if not raw.strip():
				continue
			if raw.strip() == '--':  # grep context separator
				continue
			orig_line_number = None
			content = raw
			m = line_num_pattern.match(raw)
			if m:
				try:
					orig_line_number = int(m.group(1))
					content = m.group(3)
				except Exception:
					orig_line_number = None
			# 再次剥离前导冒号/空白
			content = content.lstrip(':').lstrip()
			clean_results.append(content)
			matches.append({'file_path': file_path, 'line_number': orig_line_number, 'content': content})
		return clean_results, matches

	def close(self):  # pragma: no cover
		self.ssh_manager.close_all()

__all__ = ['LogSearchService']
