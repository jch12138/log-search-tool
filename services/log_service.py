"""
日志搜索服务

负责执行多主机并发日志搜索
"""

import os
import sys
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import SearchParams, SearchResult, HostResult
from .ssh_service import SSHConnectionManager
from .config_service import ConfigService
from .filename_resolver import resolve_log_filename

import re
import time
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import SearchParams, SearchResult, MultiHostSearchResult
from .ssh_service import SSHConnectionManager

logger = logging.getLogger(__name__)

class LogSearchService:
    """日志搜索服务"""
    
    def __init__(self):
        self.ssh_manager = SSHConnectionManager()
        # 缓存逆序命令，避免重复检测
        self._reverse_cmd_cache = {}
    
    def _get_reverse_command(self, ssh_config: Dict[str, Any]) -> str:
        """获取适合当前系统的逆序命令"""
        host = ssh_config.get('host', 'localhost')
        
        # 如果已经检测过，直接返回缓存结果
        if host in self._reverse_cmd_cache:
            return self._reverse_cmd_cache[host]
        
        try:
            # 尝试检测 tac 命令是否存在
            conn = self.ssh_manager.get_connection(ssh_config)
            if conn:
                stdout, stderr, exit_code = conn.execute_command("which tac", timeout=5)
                if exit_code == 0 and stdout.strip():
                    # tac 命令存在 (Linux)
                    reverse_cmd = "tac"
                else:
                    # tac 命令不存在，使用 sed 实现 (macOS/其他)
                    reverse_cmd = "sed '1!G;h;$!d'"
            else:
                # 连接失败，使用默认的 sed 方案
                reverse_cmd = "sed '1!G;h;$!d'"
        except Exception:
            # 检测失败，使用默认的 sed 方案
            reverse_cmd = "sed '1!G;h;$!d'"
        
        # 缓存结果
        self._reverse_cmd_cache[host] = reverse_cmd
        return reverse_cmd
    
    def search_multi_host(
        self, 
        log_config: Dict[str, Any], 
        search_params: SearchParams
    ) -> MultiHostSearchResult:
        """多主机搜索（统一接口）"""
        
        # 验证参数
        search_params.validate()
        
        ssh_configs = log_config.get('sshs', [])
        if not ssh_configs:
            raise ValueError("日志配置中没有SSH主机")
        
        log_name = log_config['name']
        log_path = log_config['path']
        
        # 并发搜索所有主机
        start_time = time.time()
        results = []
        
        if len(ssh_configs) == 1:
            # 单主机，直接执行
            result = self._search_single_host(
                ssh_configs[0], log_path, search_params, 0
            )
            results.append(result)
            parallel_execution = False
        else:
            # 多主机，并发执行
            with ThreadPoolExecutor(max_workers=min(len(ssh_configs), 10)) as executor:
                future_to_index = {
                    executor.submit(
                        self._search_single_host, 
                        ssh_config, 
                        log_path, 
                        search_params, 
                        i
                    ): i 
                    for i, ssh_config in enumerate(ssh_configs)
                }
                
                for future in as_completed(future_to_index):
                    try:
                        result = future.result(timeout=30)
                        results.append(result)
                    except Exception as e:
                        index = future_to_index[future]
                        ssh_config = ssh_configs[index]
                        logger.error(f"搜索失败 {ssh_config.get('host', 'unknown')}: {e}")
                        
                        # 创建失败结果
                        error_result = SearchResult(
                            host=ssh_config.get('host', 'unknown'),
                            ssh_index=index,
                            results=[f"[{ssh_config.get('host', 'unknown')}] 搜索失败: {str(e)}"],
                            total_results=1,
                            search_time=0.0,
                            search_result={
                                'content': '',
                                'file_path': '',
                                'keyword': search_params.keyword,
                                'total_lines': 0,
                                'search_time': 0.0,
                                'matches': []  # 添加空的matches数组
                            },
                            success=False,
                            error=str(e)
                        )
                        results.append(error_result)
            
            parallel_execution = True
        
        # 按ssh_index排序
        results.sort(key=lambda x: x.ssh_index)
        
        # 计算总结果
        total_results = sum(r.total_results for r in results if r.success)
        total_search_time = time.time() - start_time
        
        return MultiHostSearchResult(
            log_name=log_name,
            keyword=search_params.keyword,
            search_params={
                'keyword': search_params.keyword,
                'search_mode': search_params.search_mode,
                'context_span': search_params.context_span,
                'use_regex': search_params.use_regex
            },
            total_hosts=len(ssh_configs),
            hosts=results,
            total_results=total_results,
            total_search_time=total_search_time,
            parallel_execution=parallel_execution
        )
    
    def _search_single_host(
        self, 
        ssh_config: Dict[str, Any], 
        log_path: str, 
        search_params: SearchParams,
        ssh_index: int
    ) -> SearchResult:
        """单主机搜索"""
        
        start_time = time.time()
        host = ssh_config.get('host', 'unknown')
        
        try:
            # 构建搜索命令
            command = self._build_search_command(log_path, search_params, ssh_config)
            
            # 执行搜索
            conn = self.ssh_manager.get_connection(ssh_config)
            if not conn:
                raise Exception("SSH连接失败")
            
            stdout, stderr, exit_code = conn.execute_command(command, timeout=30)
            
            if exit_code != 0 and stderr:
                raise Exception(f"搜索命令执行失败: {stderr}")
            
            # 处理结果
            lines = stdout.strip().split('\n') if stdout.strip() else []
            # 过滤空行
            results = [line for line in lines if line.strip()]
            
            # 解析匹配结果为结构化数据
            matches = []
            line_number = 1
            for result_line in results:
                if result_line.strip():
                    # 尝试解析 grep -n 输出格式 (file:line:content 或 line:content)
                    if ':' in result_line:
                        parts = result_line.split(':', 2)
                        if len(parts) >= 2 and parts[0].isdigit():
                            # 格式: line:content
                            line_number = int(parts[0])
                            content = parts[1] if len(parts) == 2 else ':'.join(parts[1:])
                        elif len(parts) >= 3 and parts[1].isdigit():
                            # 格式: file:line:content
                            line_number = int(parts[1])
                            content = parts[2]
                        else:
                            # 无法解析行号，使用默认
                            content = result_line
                    else:
                        content = result_line
                    
                    matches.append({
                        'file_path': log_path,
                        'line_number': line_number,
                        'content': content
                    })
                    line_number += 1
            
            search_time = time.time() - start_time
            
            return SearchResult(
                host=host,
                ssh_index=ssh_index,
                results=results,
                total_results=len(results),
                search_time=search_time,
                search_result={
                    'content': stdout.strip(),
                    'file_path': log_path,
                    'keyword': search_params.keyword,
                    'total_lines': len(results),
                    'search_time': search_time,
                    'matches': matches  # 添加结构化的匹配数据
                },
                success=True,
                error=None
            )
            
        except Exception as e:
            search_time = time.time() - start_time
            return SearchResult(
                host=host,
                ssh_index=ssh_index,
                results=[f"[{host}] 搜索失败: {str(e)}"],
                total_results=1,
                search_time=search_time,
                search_result={
                    'content': '',
                    'file_path': '',
                    'keyword': search_params.keyword,
                    'total_lines': 0,
                    'search_time': search_time,
                    'matches': []  # 添加空的matches数组
                },
                success=False,
                error=str(e)
            )
    
    def _build_search_command(self, log_path: str, search_params: SearchParams, ssh_config: Dict[str, Any]) -> str:
        """构建搜索命令"""
        
        # 获取适合当前系统的逆序命令
        reverse_cmd = self._get_reverse_command(ssh_config)
        
        # 处理文件路径 - 支持多主机文件选择和通配符解析
        if search_params.use_file_filter:
            host = ssh_config.get('host', 'unknown')
            if search_params.selected_files and host in search_params.selected_files:
                # 优先使用多主机文件映射
                file_path = search_params.selected_files[host]
            elif search_params.selected_file:
                # 向后兼容：使用单一文件路径
                file_path = search_params.selected_file
            else:
                file_path = log_path
        else:
            file_path = log_path
        
        # 解析文件名通配符（如果包含通配符）
        if any(placeholder in file_path for placeholder in ['{YYYY}', '{MM}', '{DD}', '{N}']):
            try:
                resolved_path = resolve_log_filename(file_path)
                logger.info(f"文件名通配符解析: {file_path} -> {resolved_path}")
                file_path = resolved_path
            except Exception as e:
                logger.warning(f"文件名通配符解析失败: {file_path}, 错误: {e}")
                # 解析失败时继续使用原路径
        
        # 基础命令
        if search_params.search_mode == 'tail':
            # tail模式
            lines = max(100, search_params.context_span)
            command = f"tail -n {lines} '{file_path}'"
            # tail 模式的逆序处理 - 使用跨平台的方案
            if search_params.reverse_order:
                command += f" | {reverse_cmd}"
        else:
            # 关键词搜索模式（包括keyword和context）
            if not search_params.keyword:
                # 无关键词，显示最新内容
                command = f"tail -n 100 '{file_path}'"
                # 无关键词模式的逆序处理 - 使用跨平台的方案
                if search_params.reverse_order:
                    command += f" | {reverse_cmd}"
            else:
                # 关键词搜索
                if search_params.use_regex:
                    grep_cmd = "grep -nE"  # 添加 -n 显示行号
                else:
                    grep_cmd = "grep -nF"  # 添加 -n 显示行号
                
                # 根据搜索模式设置上下文行数
                if search_params.search_mode == 'context' and search_params.context_span > 0:
                    # context模式：显示匹配行的前后context_span行
                    grep_cmd += f" -C {search_params.context_span}"
                elif search_params.search_mode == 'keyword':
                    # keyword模式：只显示匹配行，不显示上下文
                    pass  # 不添加-C参数
                
                # 构建完整命令
                escaped_keyword = search_params.keyword.replace("'", "'\"'\"'")
                command = f"{grep_cmd} '{escaped_keyword}' '{file_path}'"
                
                # 关键词搜索的逆序和限制处理
                if search_params.reverse_order:
                    # 对于逆序，我们需要先取足够的行，然后逆序 - 使用跨平台的方案
                    command += f" | tail -n 10000 | {reverse_cmd}"
                else:
                    # 正序时直接限制行数
                    command += " | head -n 10000"
        
        return command
    
    def get_log_files(self, ssh_config: Dict[str, Any], log_path: str) -> List[Dict[str, Any]]:
        """获取日志目录下的所有文件，支持通配符解析"""
        try:
            # 检查是否包含通配符
            if any(placeholder in log_path for placeholder in ['{YYYY}', '{MM}', '{DD}', '{N}']):
                # 包含通配符，先解析一个示例路径来确定目录
                try:
                    resolved_path = resolve_log_filename(log_path)
                    log_dir = os.path.dirname(resolved_path)
                    logger.info(f"通过通配符解析确定目录: {log_path} -> {log_dir}")
                except Exception as e:
                    logger.warning(f"通配符解析失败，使用原路径: {e}")
                    log_dir = os.path.dirname(log_path)
            else:
                # 提取目录
                import os
                log_dir = os.path.dirname(log_path)
            
            # 构建文件列表命令 - 列出目录下所有文件，包含创建时间和修改时间
            # 兼容macOS和Linux的find命令
            command = f"""
            find '{log_dir}' -maxdepth 1 -type f -exec stat -f '%N\t%z\t%SB\t%Sm\t%N' -t '%Y-%m-%d %H:%M:%S' {{}} \\; 2>/dev/null || \\
            find '{log_dir}' -maxdepth 1 -type f -printf '%f\\t%s\\t%TY-%Tm-%Td %TH:%TM:%TS\\t%CY-%Cm-%Cd %CH:%CM:%CS\\t%p\\n' 2>/dev/null
            """
            
            conn = self.ssh_manager.get_connection(ssh_config)
            if not conn:
                raise Exception("SSH连接失败")

            stdout, stderr, exit_code = conn.execute_command(command)
            
            if exit_code != 0 or not stdout.strip():
                # 如果find命令失败，尝试简单的ls - 列出所有文件
                command = f"ls -la '{log_dir}'"
                stdout, stderr, exit_code = conn.execute_command(command)
                
                files = []
                host = ssh_config.get('host', 'unknown')
                
                for line in stdout.strip().split('\n'):
                    if not line.strip():
                        continue
                    
                    try:
                        # 解析ls -la输出
                        parts = line.split()
                        if len(parts) >= 9:
                            filename = parts[-1]
                            size_str = parts[4]
                            full_path = os.path.join(log_dir, filename)
                            
                            # 格式化文件大小
                            try:
                                size_bytes = int(size_str)
                            except ValueError:
                                size_bytes = 0
                            
                            modified_time = f"{parts[5]} {parts[6]} {parts[7]}"
                            
                            # 检查文件是否匹配通配符模式
                            is_match = self._check_wildcard_match(filename, log_path)
                            
                            files.append({
                                'filename': filename,
                                'full_path': full_path,
                                'size': size_bytes,  # 保持原始字节数
                                'birth_time': modified_time,  # ls命令无法获取创建时间，使用修改时间
                                'modified_time': modified_time,
                                'host': host,
                                'is_wildcard_match': is_match  # 标记是否匹配通配符
                            })
                    except (ValueError, IndexError):
                        continue
                        
                return files
            
            # 正常情况下解析find/stat输出
            files = []
            host = ssh_config.get('host', 'unknown')
            
            for line in stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    parts = line.split('\t')
                    if len(parts) >= 5:  # 更新为5个字段：filename, size, birth_time, modified_time, full_path
                        filename = os.path.basename(parts[0])  # 提取文件名
                        size_bytes = int(parts[1])
                        birth_time = parts[2]  # 创建时间
                        modified_time = parts[3]  # 修改时间
                        full_path = parts[4] if parts[4].startswith('/') else parts[0]
                        
                        # 检查文件是否匹配通配符模式
                        is_match = self._check_wildcard_match(filename, log_path)
                        
                        files.append({
                            'filename': filename,
                            'full_path': full_path,
                            'size': size_bytes,  # 保持原始字节数，让前端格式化
                            'birth_time': birth_time,
                            'modified_time': modified_time,
                            'host': host,
                            'is_wildcard_match': is_match  # 标记是否匹配通配符
                        })
                    elif len(parts) >= 4:  # 向后兼容旧格式
                        filename = os.path.basename(parts[0])
                        size_bytes = int(parts[1])
                        modified_time = parts[2]
                        full_path = parts[3] if parts[3].startswith('/') else parts[0]
                        
                        # 检查文件是否匹配通配符模式
                        is_match = self._check_wildcard_match(filename, log_path)
                        
                        files.append({
                            'filename': filename,
                            'full_path': full_path,
                            'size': size_bytes,
                            'birth_time': modified_time,  # 如果没有创建时间，使用修改时间
                            'modified_time': modified_time,
                            'host': host,
                            'is_wildcard_match': is_match  # 标记是否匹配通配符
                        })
                except (ValueError, IndexError):
                    # 解析失败，跳过这一行
                    continue
            
            return files
            
        except Exception as e:
            logger.error(f"获取文件列表失败 {ssh_config.get('host', 'unknown')}: {e}")
            return []
    
    def _check_wildcard_match(self, filename: str, pattern: str) -> bool:
        """
        检查文件名是否匹配通配符模式
        
        Args:
            filename: 实际文件名
            pattern: 包含通配符的模式
            
        Returns:
            是否匹配
        """
        # 如果模式中没有通配符，直接比较
        if not any(placeholder in pattern for placeholder in ['{YYYY}', '{MM}', '{DD}', '{N}']):
            return os.path.basename(pattern) == filename
        
        try:
            from .filename_resolver import FilenameResolver
            resolver = FilenameResolver()
            
            # 提取文件名部分的模式
            pattern_filename = os.path.basename(pattern)
            
            # 如果只有日期通配符，直接替换当前日期进行匹配
            if '{N}' not in pattern_filename:
                resolved_pattern = resolver._replace_date_placeholders(pattern_filename, datetime.now())
                return resolved_pattern == filename
            
            # 如果包含 {N} 通配符，需要检查格式是否匹配
            # 创建正则表达式来匹配
            regex_pattern = resolver._create_regex_from_pattern(pattern_filename)
            
            # 先替换日期通配符
            if any(placeholder in regex_pattern for placeholder in ['{YYYY}', '{MM}', '{DD}']):
                # 将日期通配符替换为对应的正则表达式
                current_date = datetime.now()
                date_replacements = {
                    r'\{YYYY\}': current_date.strftime('%Y'),
                    r'\{MM\}': current_date.strftime('%m'),
                    r'\{DD\}': current_date.strftime('%d')
                }
                for placeholder, value in date_replacements.items():
                    regex_pattern = regex_pattern.replace(placeholder, value)
            
            # 检查是否匹配
            import re
            return bool(re.match(regex_pattern, filename))
            
        except Exception as e:
            logger.warning(f"通配符匹配检查失败: {e}")
            return False
    
    def close(self):
        """关闭服务"""
        self.ssh_manager.close_all()
