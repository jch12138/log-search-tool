"""文件名通配符解析服务 (migrated)"""

import os
import re
from datetime import datetime
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FilenameResolver:
    def __init__(self):
        self.date_placeholders = {
            '{YYYY}': '%Y',
            '{MM}': '%m',
            '{DD}': '%d'
        }

    def resolve_filename(self, filename_pattern: str, target_date: Optional[datetime] = None, ssh_conn=None) -> str:
        if target_date is None:
            target_date = datetime.now()
        resolved_pattern = self._replace_date_placeholders(filename_pattern, target_date)
        if '{N}' in resolved_pattern:
            if ssh_conn is None:
                raise ValueError("处理切片通配符 {N} 需要提供 SSH 连接对象")
            return self._resolve_slice_placeholder(resolved_pattern, ssh_conn)
        logger.info(f"文件名模式 '{filename_pattern}' 解析为 '{resolved_pattern}'")
        return resolved_pattern

    def _replace_date_placeholders(self, pattern: str, date: datetime) -> str:
        for placeholder, fmt in self.date_placeholders.items():
            if placeholder in pattern:
                pattern = pattern.replace(placeholder, date.strftime(fmt))
        return pattern

    def _resolve_slice_placeholder(self, pattern: str, ssh_conn) -> str:
        directory = os.path.dirname(pattern) or '.'
        filename_pattern = os.path.basename(pattern)
        glob_pattern = filename_pattern.replace('{N}', '*')
        directory_unix = directory.replace('\\', '/')
        full_glob_pattern = f"{directory_unix}/{glob_pattern}" if directory_unix != '.' else glob_pattern
        matching_files = self._find_remote_files(full_glob_pattern, ssh_conn)
        if not matching_files:
            default_filename = pattern.replace('{N}', '0')
            logger.warning(f"未找到匹配的文件，返回默认文件名: {default_filename}")
            return default_filename
        max_n = -1
        best_file = None
        regex_pattern = self._create_regex_from_pattern(filename_pattern)
        for file_path in matching_files:
            filename = os.path.basename(file_path)
            match = re.match(regex_pattern, filename)
            if match:
                try:
                    n_val = int(match.group(1))
                    if n_val > max_n:
                        max_n = n_val
                        best_file = file_path
                except ValueError:
                    continue
        if best_file:
            logger.info(f"找到最新的切片文件: {best_file} (N={max_n})")
            return best_file
        logger.warning(f"未找到有效N值，返回第一个匹配文件: {matching_files[0]}")
        return matching_files[0]

    def _create_regex_from_pattern(self, pattern: str) -> str:
        escaped = re.escape(pattern)
        regex = escaped.replace(r'\{N\}', r'(\d+)')
        return f'^{regex}$'

    def _find_remote_files(self, glob_pattern: str, ssh_conn) -> List[str]:
        try:
            unix_glob = glob_pattern.replace('\\', '/')
            directory = unix_glob.rsplit('/', 1)[0] if '/' in unix_glob else '.'
            filename_pattern = unix_glob.rsplit('/', 1)[-1]
            dir_check_cmd = f"test -d '{directory}' && echo 'dir_exists' || echo 'dir_not_exists'"
            stdout, _, _ = ssh_conn.execute_command(dir_check_cmd, timeout=5)
            if 'dir_not_exists' in stdout:
                return []
            if '*' in filename_pattern or '?' in filename_pattern:
                escaped_pattern = filename_pattern.replace("'", "'\"'\"'")
                cmd = f"find '{directory}' -maxdepth 1 -name '{escaped_pattern}' -type f 2>/dev/null || true"
            else:
                full_path = f"{directory}/{filename_pattern}" if directory != '.' else filename_pattern
                cmd = f"test -f '{full_path}' && echo '{full_path}' || true"
            stdout, _, _ = ssh_conn.execute_command(cmd, timeout=10)
            if stdout.strip():
                return [line.strip() for line in stdout.strip().split('\n') if line.strip()]
            return []
        except Exception:
            return []

filename_resolver = FilenameResolver()

def resolve_log_filename(filename_pattern: str, target_date: Optional[datetime] = None, ssh_conn=None) -> str:
    return filename_resolver.resolve_filename(filename_pattern, target_date, ssh_conn)

def validate_log_filename_pattern(pattern: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    invalids = re.findall(r'\{[^}]+\}', pattern)
    valid = {'{YYYY}', '{MM}', '{DD}', '{N}'}
    for ph in invalids:
        if ph not in valid:
            errors.append(f"无效的占位符: {ph}")
    if pattern.count('{N}') > 1:
        errors.append(f"切片占位符{{N}}只能出现一次，当前出现了{pattern.count('{N}')}次")
    if not pattern.strip():
        errors.append("文件名模式不能为空")
    return len(errors) == 0, errors

__all__ = [
    'resolve_log_filename',
    'validate_log_filename_pattern',
    'FilenameResolver'
]
