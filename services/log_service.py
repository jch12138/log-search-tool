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
from .encoding import decode_bytes
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
            
            final_command = command
            
            logger.debug(f"[{host}] 执行搜索命令: {final_command}")
            stdout, stderr, exit_code = conn.execute_command(final_command, timeout=30)
            
            if exit_code != 0 and stderr:
                raise Exception(f"搜索命令执行失败: {stderr}")
            
            # 统一使用 decode_bytes 进行 UTF-8 / GB2312 回退
            if stdout:
                try:
                    # 将当前字符串视为原始字节猜测解码可能错误，先尝试直接utf-8验证
                    stdout.encode('utf-8')
                except Exception:
                    # 退回到字节再解码策略
                    candidate_bytes = stdout.encode('latin-1', errors='ignore')
                    stdout = decode_bytes(candidate_bytes)
            
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
                # 获取SSH连接对象
                conn = self.ssh_manager.get_connection(ssh_config)
                resolved_path = resolve_log_filename(file_path, ssh_conn=conn)
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
    
    # 删除复杂的编码检测与转换辅助函数，仅保留UTF-8/GB2312回退机制
    
    def get_log_files(self, ssh_config: Dict[str, Any], log_path: str) -> List[Dict[str, Any]]:
        """获取日志目录下的所有文件
        
        Args:
            ssh_config: SSH连接配置
            log_path: 日志文件路径，将提取其目录部分
            
        Returns:
            文件信息列表，每个文件包含：filename, full_path, size, birth_time, modified_time, host
        """
        try:
            # 提取日志文件所在目录
            log_dir = os.path.dirname(log_path)
            if not log_dir:
                log_dir = '.'
            
            host = ssh_config.get('host', 'unknown')
            logger.debug(f"[{host}] 开始获取日志文件列表")
            logger.debug(f"[{host}] 原始日志路径: {log_path}")
            logger.debug(f"[{host}] 提取的目录: {log_dir}")
            
            conn = self.ssh_manager.get_connection(ssh_config)
            if not conn:
                logger.error(f"[{host}] SSH连接失败")
                raise Exception("SSH连接失败")
            
            logger.debug(f"[{host}] SSH连接成功")
            
            # 首先尝试使用Linux风格的命令
            linux_command = f"find '{log_dir}' -maxdepth 1 -type f -printf '%f\\t%s\\t%TY-%Tm-%Td %TH:%TM:%TS\\t%CY-%Cm-%Cd %CH:%CM:%CS\\t%p\\n' 2>/dev/null"
            logger.debug(f"[{host}] 尝试Linux命令: {linux_command}")
            
            stdout, stderr, exit_code = conn.execute_command(linux_command)
            logger.debug(f"[{host}] Linux命令结果 - exit_code: {exit_code}, stdout长度: {len(stdout) if stdout else 0}, stderr: {stderr[:100] if stderr else 'None'}")
            
            if exit_code == 0 and stdout.strip():
                # Linux命令成功，解析输出
                logger.debug(f"[{host}] Linux命令成功，开始解析输出")
                files = self._parse_linux_find_output(stdout, host)
                logger.debug(f"[{host}] Linux解析完成，找到 {len(files)} 个文件")
                return files
            
            # Linux命令失败，尝试macOS风格的命令
            # 使用管道符作为分隔符避免制表符转义问题
            macos_command = f"find '{log_dir}' -maxdepth 1 -type f -exec stat -f '%N|%z|%SB|%Sm|%N' -t '%Y-%m-%d %H:%M:%S' {{}} \\; 2>/dev/null"
            logger.debug(f"[{host}] Linux命令失败，尝试macOS命令: {macos_command}")
            
            stdout, stderr, exit_code = conn.execute_command(macos_command)
            logger.debug(f"[{host}] macOS命令结果 - exit_code: {exit_code}, stdout长度: {len(stdout) if stdout else 0}, stderr: {stderr[:100] if stderr else 'None'}")
            
            if exit_code == 0 and stdout.strip():
                # macOS命令成功，解析输出
                logger.debug(f"[{host}] macOS命令成功，开始解析输出")
                files = self._parse_macos_stat_output(stdout, host)
                logger.debug(f"[{host}] macOS解析完成，找到 {len(files)} 个文件")
                return files
            
            # 所有高级命令都失败，使用最基本的ls命令
            ls_command = f"ls -la '{log_dir}' | grep '^-'"
            logger.debug(f"[{host}] 高级命令都失败，尝试基本ls命令: {ls_command}")
            stdout, stderr, exit_code = conn.execute_command(ls_command)
            logger.debug(f"[{host}] ls命令结果 - exit_code: {exit_code}, stdout长度: {len(stdout) if stdout else 0}, stderr: {stderr[:100] if stderr else 'None'}")
            
            if exit_code == 0 and stdout.strip():
                logger.debug(f"[{host}] ls命令成功，开始解析输出")
                files = self._parse_ls_output(stdout, log_dir, host)
                logger.debug(f"[{host}] ls解析完成，找到 {len(files)} 个文件")
                return files
            
            logger.warning(f"[{host}] 无法获取目录 {log_dir} 的文件列表，所有命令都失败")
            return []
            
        except Exception as e:
            logger.error(f"[{ssh_config.get('host', 'unknown')}] 获取文件列表失败: {e}")
            logger.debug(f"[{ssh_config.get('host', 'unknown')}] 异常详情", exc_info=True)
            return []
    
    def _parse_linux_find_output(self, stdout: str, host: str) -> List[Dict[str, Any]]:
        """解析Linux find命令的输出"""
        files = []
        lines = stdout.strip().split('\n')
        logger.debug(f"[{host}] 开始解析Linux find输出，总行数: {len(lines)}")
        
        for i, line in enumerate(lines):
            if not line.strip():
                logger.debug(f"[{host}] 跳过空行 {i+1}")
                continue
            
            try:
                parts = line.split('\t')
                logger.debug(f"[{host}] 解析第{i+1}行，分割成{len(parts)}部分: {parts}")
                
                if len(parts) >= 5:
                    filename = parts[0]
                    size_bytes = int(parts[1])
                    modified_time = parts[2]
                    birth_time = parts[3]
                    full_path = parts[4]
                    
                    file_info = {
                        'filename': filename,
                        'full_path': full_path,
                        'size': size_bytes,
                        'birth_time': birth_time,
                        'modified_time': modified_time,
                        'host': host
                    }
                    files.append(file_info)
                    logger.debug(f"[{host}] 成功解析文件: {filename} (大小: {size_bytes})")
                else:
                    logger.debug(f"[{host}] 第{i+1}行格式不正确，部分数量不足: {len(parts)}")
            except (ValueError, IndexError) as e:
                logger.debug(f"[{host}] 解析Linux find输出失败: {line}, 错误: {e}")
                continue
        
        logger.debug(f"[{host}] Linux解析完成，成功解析 {len(files)} 个文件")
        return files
    
    def _parse_macos_stat_output(self, stdout: str, host: str) -> List[Dict[str, Any]]:
        """解析macOS stat命令的输出"""
        files = []
        lines = stdout.strip().split('\n')
        logger.debug(f"[{host}] 开始解析macOS stat输出，总行数: {len(lines)}")
        
        for i, line in enumerate(lines):
            if not line.strip():
                logger.debug(f"[{host}] 跳过空行 {i+1}")
                continue
            
            try:
                # 使用管道符分割，避免制表符转义问题
                parts = line.split('|')
                logger.debug(f"[{host}] 解析第{i+1}行，分割成{len(parts)}部分: {parts}")
                
                if len(parts) >= 5:
                    filename = os.path.basename(parts[0])
                    size_bytes = int(parts[1])
                    birth_time = parts[2]
                    modified_time = parts[3]
                    full_path = parts[4]
                    
                    file_info = {
                        'filename': filename,
                        'full_path': full_path,
                        'size': size_bytes,
                        'birth_time': birth_time,
                        'modified_time': modified_time,
                        'host': host
                    }
                    files.append(file_info)
                    logger.debug(f"[{host}] 成功解析文件: {filename} (大小: {size_bytes})")
                else:
                    logger.debug(f"[{host}] 第{i+1}行格式不正确，部分数量不足: {len(parts)}")
            except (ValueError, IndexError) as e:
                logger.debug(f"[{host}] 解析macOS stat输出失败: {line}, 错误: {e}")
                continue
        
        logger.debug(f"[{host}] macOS解析完成，成功解析 {len(files)} 个文件")
        return files
    
    def _parse_ls_output(self, stdout: str, log_dir: str, host: str) -> List[Dict[str, Any]]:
        """解析ls命令的输出"""
        files = []
        lines = stdout.strip().split('\n')
        logger.debug(f"[{host}] 开始解析ls输出，总行数: {len(lines)}")
        
        for i, line in enumerate(lines):
            if not line.strip():
                logger.debug(f"[{host}] 跳过空行 {i+1}")
                continue
            
            try:
                # 解析ls -la输出格式
                parts = line.split()
                logger.debug(f"[{host}] 解析第{i+1}行，分割成{len(parts)}部分: {parts}")
                
                if len(parts) >= 9:
                    filename = parts[-1]
                    size_str = parts[4]
                    full_path = os.path.join(log_dir, filename)
                    
                    # 尝试解析文件大小
                    try:
                        size_bytes = int(size_str)
                    except ValueError:
                        logger.debug(f"[{host}] 无法解析文件大小: {size_str}")
                        size_bytes = 0
                    
                    # 解析修改时间
                    if len(parts) >= 8:
                        # ls输出格式: month day time/year
                        month = parts[5]
                        day = parts[6]
                        time_or_year = parts[7]
                        modified_time = f"{month} {day} {time_or_year}"
                    else:
                        modified_time = "unknown"
                    
                    file_info = {
                        'filename': filename,
                        'full_path': full_path,
                        'size': size_bytes,
                        'birth_time': modified_time,  # ls命令无法获取创建时间
                        'modified_time': modified_time,
                        'host': host
                    }
                    files.append(file_info)
                    logger.debug(f"[{host}] 成功解析文件: {filename} (大小: {size_bytes})")
                else:
                    logger.debug(f"[{host}] 第{i+1}行格式不正确，部分数量不足: {len(parts)}")
            except (ValueError, IndexError) as e:
                logger.debug(f"[{host}] 解析ls输出失败: {line}, 错误: {e}")
                continue
        
        logger.debug(f"[{host}] ls解析完成，成功解析 {len(files)} 个文件")
        return files
    
    def close(self):
        """关闭服务"""
        self.ssh_manager.close_all()
