"""Log search service.

Incremental refactor step 1:
 - Introduce module-level constants for magic numbers
 - Precompile frequently used regex
 - Remove unused imports
 - Keep behavior identical (no functional changes)
"""

import os
import logging
import time
import re
import shlex
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.models import SearchParams, SearchResult, MultiHostSearchResult
from app.services.ssh import SSHConnectionManager
from app.services.utils.encoding import smart_decode
from app.services.utils.filename_resolver import resolve_log_filename

logger = logging.getLogger(__name__)

# ---------------- Module constants (avoid magic numbers sprinkled in code) ----------------
REVERSE_CMD_DETECT_TIMEOUT = 5  # seconds for 'which tac'
SINGLE_HOST_TAIL_RECENT = 100   # default recent lines when no keyword
MAX_GREP_LINES_LIMIT = 10000    # cap for grep results (head/tail)
MIN_TAIL_LINES = 100            # minimum lines for tail mode
SEARCH_EXEC_TIMEOUT = 30        # remote command execution timeout

# Precompiled regex for grep output line numbers
LINE_NUM_RE = re.compile(r'^(\d+)([:=\-])(.*)$')


class LogSearchService:
	def __init__(self, shared_executor: Optional[ThreadPoolExecutor] = None, max_workers: Optional[int] = None):
		"""Create service.

		Parameters:
		shared_executor: externally managed ThreadPoolExecutor (no internal shutdown)
		max_workers: if provided (and no shared_executor), create internal executor capped 1..20
		"""
		self.ssh_manager = SSHConnectionManager()
		# Cache for reverse command detection per unique SSH endpoint (host, port, user)
		# Key format: "host|port|username" to avoid false sharing across differing accounts/ports
		self._reverse_cmd_cache: Dict[str, str] = {}
		self._external_executor = shared_executor is not None
		if shared_executor:
			self._executor = shared_executor
		else:
			if max_workers is None:
				max_workers = 10
			max_workers = max(1, min(20, max_workers))
			self._executor = ThreadPoolExecutor(max_workers=max_workers)

	def _get_reverse_command(self, ssh_config: Dict[str, Any]) -> str:
		host = ssh_config.get('host', 'localhost')
		port = ssh_config.get('port', 22)
		user = ssh_config.get('username') or ssh_config.get('user') or ''
		cache_key = f"{host}|{port}|{user}"
		if cache_key in self._reverse_cmd_cache:
			return self._reverse_cmd_cache[cache_key]
		try:  # pragma: no cover - network
			conn = self.ssh_manager.get_connection(ssh_config)
			if conn:
				stdout, _, code = conn.execute_command("which tac", timeout=REVERSE_CMD_DETECT_TIMEOUT)
				if code == 0 and stdout.strip():
					cmd = 'tac'
				else:
					cmd = "sed '1!G;h;$!d'"
			else:
				cmd = "sed '1!G;h;$!d'"
		except Exception:
			cmd = "sed '1!G;h;$!d'"
		self._reverse_cmd_cache[cache_key] = cmd
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
			# Reuse shared/internal executor
			fut_map = {}
			for i, cfg in enumerate(sshs):
				cfg['ssh_index'] = i
				fut = self._executor.submit(self._search_single_host, cfg, (cfg.get('path') or legacy_path or ''), search_params, i)
				fut_map[fut] = i
			for fut in as_completed(fut_map):  # pragma: no cover - concurrency timing nondeterministic
				i = fut_map[fut]
				cfg = sshs[i]
				try:
					results.append(fut.result(timeout=SEARCH_EXEC_TIMEOUT))
				except Exception as e:
					logger.error(f"搜索失败 {cfg.get('host')}: {e}")
					results.append(SearchResult(host=cfg.get('host', 'unknown'), ssh_index=i, results=[], total_results=0, search_time=0.0, search_result={'content': '', 'file_path': '', 'keyword': search_params.keyword, 'total_lines': 0, 'search_time': 0.0, 'matches': []}, success=False, error=str(e)))
			parallel = True
		results.sort(key=lambda r: r.ssh_index)
		total = sum(r.total_results for r in results if r.success)
		elapsed = time.time() - start
		# Aggregated truncation metadata (non-breaking additional field) – only hosts with success considered
		truncated_hosts = []
		original_total_all = 0
		for r in results:
			if r.success:
				info = r.search_result or {}
				orig = info.get('original_total_lines') or info.get('total_lines') or 0
				original_total_all += orig
				if info.get('truncated'):
					truncated_hosts.append({'host': r.host, 'ssh_index': r.ssh_index, 'original_total_lines': orig, 'after_truncation': r.total_results})
		any_truncated = len(truncated_hosts) > 0
		lines_after = total
		lines_reduced = 0
		if any_truncated:
			lines_reduced = sum(h['original_total_lines'] - h['after_truncation'] for h in truncated_hosts if h['original_total_lines'] is not None)
		aggregated_truncation = {
			'any_truncated': any_truncated,
			'truncated_hosts': truncated_hosts,
			'total_original_lines': original_total_all,
			'total_after_truncation': lines_after,
			'lines_reduced': lines_reduced
		}
		return MultiHostSearchResult(log_name=log_name, keyword=search_params.keyword, search_params={'keyword': search_params.keyword, 'search_mode': search_params.search_mode, 'context_span': search_params.context_span, 'use_regex': search_params.use_regex}, total_hosts=len(sshs), hosts=results, total_results=total, total_search_time=elapsed, parallel_execution=parallel, aggregated_truncation=aggregated_truncation)

	def _search_single_host(self, ssh_config: Dict[str, Any], log_path: str, search_params: SearchParams, ssh_index: int) -> SearchResult:
		start = time.time()
		host = ssh_config.get('host', 'unknown')
		try:
			# 同时获取解析后的实际文件路径，避免下载时仍然携带占位符
			command, resolved_file_path = self._build_search_command(log_path, search_params, ssh_config)
			conn = self.ssh_manager.get_connection(ssh_config)
			if not conn:
				raise RuntimeError("SSH连接失败")
			stdout, stderr, code = conn.execute_command(command, timeout=SEARCH_EXEC_TIMEOUT)
			if code != 0 and stderr:
				raise RuntimeError(f"搜索命令执行失败: {stderr}")
			# 标准输出编码处理：先直接使用；若检测到替换符或异常，再用 smart_decode
			encoding_used = 'utf-8'
			if stdout:
				try:
					stdout.encode('utf-8')  # 检测能否无损往返
				except Exception:
					decoded, enc_used = smart_decode(stdout.encode('latin-1', errors='ignore'))
					stdout = decoded
					encoding_used = enc_used
			elif not stdout:
				encoding_used = 'utf-8'
			lines = stdout.strip().split('\n') if stdout.strip() else []
			has_line_numbers = ('grep -n' in command)
			results, matches = self._parse_grep_output(lines, resolved_file_path, has_line_numbers=has_line_numbers)
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
					'matches': matches,
					'encoding_used': encoding_used
				},
				success=True
			)
		except Exception as e:
			elapsed = time.time() - start
			return SearchResult(host=host, ssh_index=ssh_index, results=[], total_results=0, search_time=elapsed, search_result={'content': '', 'file_path': '', 'keyword': search_params.keyword, 'total_lines': 0, 'search_time': elapsed, 'matches': []}, success=False, error=str(e))

	def _build_search_command(self, log_path: str, search_params: SearchParams, ssh_config: Dict[str, Any]):
		reverse_cmd = self._get_reverse_command(ssh_config)
		file_path = self._resolve_effective_file_path(log_path, search_params, ssh_config)
		file_path = self._expand_placeholders(file_path, ssh_config)
		quoted_file, is_gz, decompress = self._prepare_file_usage(file_path)
		# Build command
		cmd = self._compose_command(search_params, quoted_file, is_gz, decompress, reverse_cmd)
		return cmd, file_path

	def _resolve_effective_file_path(self, log_path: str, search_params: SearchParams, ssh_config: Dict[str, Any]) -> str:
		"""Determine file path considering file filter selections."""
		if search_params.use_file_filter:
			host = ssh_config.get('host', 'unknown')
			host_key = f"{host}|{ssh_config.get('ssh_index', ssh_config.get('index', ''))}"
			selected_files = search_params.selected_files or {}
			if selected_files:
				if host_key in selected_files:
					return selected_files[host_key]
				elif host in selected_files:
					return selected_files[host]
				else:
					return log_path
			elif search_params.selected_file:
				return search_params.selected_file
			else:
				return log_path
		return log_path

	def _expand_placeholders(self, file_path: str, ssh_config: Dict[str, Any]) -> str:
		if any(ph in file_path for ph in ['{YYYY}', '{MM}', '{DD}', '{N}']):
			try:
				conn = self.ssh_manager.get_connection(ssh_config)
				return resolve_log_filename(file_path, ssh_conn=conn)
			except Exception as e:
				logger.warning(f"文件名通配符解析失败: {file_path} - {e}")
				return file_path
		return file_path

	def _prepare_file_usage(self, file_path: str):
		quoted_file = shlex.quote(file_path)
		is_gz = file_path.endswith('.gz')
		decompress = f"gzip -dc {quoted_file}" if is_gz else None
		return quoted_file, is_gz, decompress

	def _tail_builder(self, is_gz: bool, decompress: Optional[str], quoted_file: str, n: int) -> str:
		if is_gz:
			return f"{decompress} | tail -n {n}"
		return f"tail -n {n} {quoted_file}"

	def _compose_command(self, search_params: SearchParams, quoted_file: str, is_gz: bool, decompress: Optional[str], reverse_cmd: str) -> str:
		# tail mode
		if search_params.search_mode == 'tail':
			lines = max(SINGLE_HOST_TAIL_RECENT, search_params.context_span)
			cmd = self._tail_builder(is_gz, decompress, quoted_file, lines)
			if search_params.reverse_order:
				cmd += f" | {reverse_cmd}"
			return cmd
		# non-tail
		if not search_params.keyword:
			cmd = self._tail_builder(is_gz, decompress, quoted_file, SINGLE_HOST_TAIL_RECENT)
			if search_params.reverse_order:
				cmd += f" | {reverse_cmd}"
			return cmd
		grep_cmd = 'grep -nE' if search_params.use_regex else 'grep -nF'
		if search_params.search_mode == 'context' and search_params.context_span > 0:
			grep_cmd += f" -C {search_params.context_span}"
		escaped_keyword = shlex.quote(search_params.keyword)
		if is_gz:
			cmd = f"{decompress} | {grep_cmd} {escaped_keyword}"
		else:
			cmd = f"{grep_cmd} {escaped_keyword} {quoted_file}"
		if search_params.reverse_order:
			cmd += f" | tail -n {MAX_GREP_LINES_LIMIT} | {reverse_cmd}"
		else:
			cmd += f" | head -n {MAX_GREP_LINES_LIMIT}"
		return cmd

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

	def _parse_grep_output(self, lines: List[str], file_path: str, has_line_numbers: bool = True) -> Tuple[List[str], List[Dict[str, Any]]]:
		"""Parse command output into clean lines and match metadata.

		If has_line_numbers is True (i.e., grep -n/-nC was used), remove the leading
		"<lineno><sep>" prefix where <sep> is one of ':', '-', '=' and skip grep's
		context separator lines "--". Otherwise, keep lines as-is to avoid stripping
		timestamps like "10:58:05.901" that naturally start with digits and a colon.

		Examples when has_line_numbers=True:
		  123:actual log line
		  123-actual log line (before context)
		  123=actual log line (after context)
		"""
		clean_results: List[str] = []
		matches: List[Dict[str, Any]] = []
		for raw in lines:
			if not raw.strip():
				continue
			if has_line_numbers and raw.strip() == '--':  # grep context separator
				continue
			orig_line_number = None
			content = raw
			if has_line_numbers:
				m = LINE_NUM_RE.match(raw)
				if m:
					try:
						orig_line_number = int(m.group(1))
						content = m.group(3)
					except Exception:
						orig_line_number = None
				# 再次剥离前导冒号/空白（仅在存在行号时需要）
				content = content.lstrip(':').lstrip()
			clean_results.append(content)
			matches.append({'file_path': file_path, 'line_number': orig_line_number, 'content': content})
		return clean_results, matches

	def close(self):  # pragma: no cover
		self.ssh_manager.close_all()
		# Only shutdown if we own the executor
		if hasattr(self, '_executor') and not self._external_executor:
			try:
				self._executor.shutdown(wait=True, cancel_futures=True)  # type: ignore[attr-defined]
			except Exception:
				pass

__all__ = ['LogSearchService']
