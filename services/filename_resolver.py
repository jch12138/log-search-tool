"""
文件名通配符解析服务
支持日期通配符 {YYYY}, {MM}, {DD} 和切片通配符 {N}
"""

import os
import re
import glob
from datetime import datetime
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FilenameResolver:
    """文件名通配符解析器"""
    
    def __init__(self):
        self.date_placeholders = {
            '{YYYY}': '%Y',
            '{MM}': '%m', 
            '{DD}': '%d'
        }
    
    def resolve_filename(self, filename_pattern: str, target_date: Optional[datetime] = None, ssh_conn=None) -> str:
        """
        解析文件名模式，支持日期通配符和切片通配符
        
        Args:
            filename_pattern: 文件名模式，如 "app-{YYYY}-{MM}-{DD}-{N}.log"
            target_date: 目标日期，默认为当前日期
            ssh_conn: SSH连接对象，用于远程文件系统操作
            
        Returns:
            解析后的实际文件名
        """
        if target_date is None:
            target_date = datetime.now()
            
        # 第一步：替换日期通配符
        resolved_pattern = self._replace_date_placeholders(filename_pattern, target_date)
        
        # 第二步：处理切片通配符 {N}
        if '{N}' in resolved_pattern:
            if ssh_conn is None:
                raise ValueError("处理切片通配符 {N} 需要提供 SSH 连接对象")
            resolved_filename = self._resolve_slice_placeholder(resolved_pattern, ssh_conn)
        else:
            resolved_filename = resolved_pattern
            
        logger.info(f"文件名模式 '{filename_pattern}' 解析为 '{resolved_filename}'")
        return resolved_filename
    
    def _replace_date_placeholders(self, pattern: str, date: datetime) -> str:
        """替换日期通配符"""
        result = pattern
        for placeholder, format_code in self.date_placeholders.items():
            if placeholder in result:
                date_value = date.strftime(format_code)
                result = result.replace(placeholder, date_value)
                logger.debug(f"替换 {placeholder} -> {date_value}")
        return result
    
    def _resolve_slice_placeholder(self, pattern: str, ssh_conn) -> str:
        """
        解析切片通配符 {N}，找到N值最大的文件
        
        Args:
            pattern: 包含{N}的文件名模式
            ssh_conn: SSH连接对象，用于远程文件系统操作（必需）
            
        Returns:
            实际存在的文件名（N值最大的）
        """
        # 提取目录和文件名模式
        directory = os.path.dirname(pattern)
        if not directory:
            directory = '.'
        filename_pattern = os.path.basename(pattern)
        
        # 将{N}替换为通配符*来搜索文件
        glob_pattern = filename_pattern.replace('{N}', '*')
        
        # 统一使用Unix风格的路径分隔符（用于远程Linux服务器）
        if directory == '.':
            full_glob_pattern = glob_pattern
        else:
            # 确保使用Unix风格的路径分隔符
            directory_unix = directory.replace('\\', '/')
            full_glob_pattern = f"{directory_unix}/{glob_pattern}"
        
        logger.debug(f"搜索模式: {full_glob_pattern}")
        
        # 在远程服务器上查找匹配的文件
        matching_files = self._find_remote_files(full_glob_pattern, ssh_conn)
        
        if not matching_files:
            # 如果没有找到匹配的文件，返回N=0的默认文件名
            default_filename = pattern.replace('{N}', '0')
            logger.warning(f"未找到匹配的文件，返回默认文件名: {default_filename}")
            return default_filename
        
        # 提取N值并找到最大的
        max_n = -1
        best_file = None
        
        # 创建正则表达式来提取N值
        regex_pattern = self._create_regex_from_pattern(filename_pattern)
        
        for file_path in matching_files:
            filename = os.path.basename(file_path)
            match = re.match(regex_pattern, filename)
            if match:
                try:
                    n_value = int(match.group(1))
                    if n_value > max_n:
                        max_n = n_value
                        best_file = file_path
                    logger.debug(f"文件 {filename} 的N值: {n_value}")
                except ValueError:
                    logger.warning(f"无法解析文件 {filename} 中的N值")
                    continue
        
        if best_file:
            logger.info(f"找到最新的切片文件: {best_file} (N={max_n})")
            return best_file
        else:
            # 如果没有找到有效的N值，返回第一个匹配的文件
            default_file = matching_files[0]
            logger.warning(f"未找到有效的N值，返回第一个匹配文件: {default_file}")
            return default_file
    
    def _create_regex_from_pattern(self, pattern: str) -> str:
        """
        将文件名模式转换为正则表达式，用于提取N值
        
        Args:
            pattern: 文件名模式，如 "app-{N}.log"
            
        Returns:
            正则表达式字符串
        """
        # 转义特殊字符
        escaped_pattern = re.escape(pattern)
        
        # 将转义的{N}替换为捕获组
        regex_pattern = escaped_pattern.replace(r'\{N\}', r'(\d+)')
        
        # 完整匹配
        regex_pattern = f'^{regex_pattern}$'
        
        logger.debug(f"生成的正则表达式: {regex_pattern}")
        return regex_pattern
    
    def _find_remote_files(self, glob_pattern: str, ssh_conn) -> List[str]:
        """
        在远程服务器上查找匹配glob模式的文件
        
        Args:
            glob_pattern: glob模式，如 "./2025-09-08.*.log"
            ssh_conn: SSH连接对象
            
        Returns:
            匹配的文件路径列表
        """
        try:
            # 构建ls命令来查找匹配的文件
            # 确保glob_pattern使用Unix风格的路径分隔符
            unix_glob_pattern = glob_pattern.replace('\\', '/')
            
            # 创建远程命令来查找文件
            # 使用ls命令配合通配符
            command = f"ls {unix_glob_pattern} 2>/dev/null || true"
            
            logger.debug(f"远程搜索命令: {command}")
            
            stdout, stderr, exit_code = ssh_conn.execute_command(command, timeout=10)
            
            if stdout.strip():
                # 解析输出，每行一个文件
                files = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
                logger.debug(f"远程找到的文件: {files}")
                return files
            else:
                logger.debug("远程未找到匹配的文件")
                return []
                
        except Exception as e:
            logger.warning(f"远程文件搜索失败: {e}")
            return []
    
    def validate_pattern(self, pattern: str) -> Tuple[bool, List[str]]:
        """
        验证文件名模式的有效性
        
        Args:
            pattern: 文件名模式
            
        Returns:
            (is_valid, errors): 验证结果和错误信息列表
        """
        errors = []
        
        # 检查是否包含无效的占位符
        invalid_placeholders = re.findall(r'\{[^}]+\}', pattern)
        valid_placeholders = {'{YYYY}', '{MM}', '{DD}', '{N}'}
        
        for placeholder in invalid_placeholders:
            if placeholder not in valid_placeholders:
                errors.append(f"无效的占位符: {placeholder}")
        
        # 检查{N}是否出现多次
        n_count = pattern.count('{N}')
        if n_count > 1:
            errors.append(f"切片占位符{{N}}只能出现一次，当前出现了{n_count}次")
        
        # 检查文件路径是否有效
        if not pattern.strip():
            errors.append("文件名模式不能为空")
        
        return len(errors) == 0, errors


# 创建全局实例
filename_resolver = FilenameResolver()


def resolve_log_filename(filename_pattern: str, target_date: Optional[datetime] = None, ssh_conn=None) -> str:
    """
    便捷函数：解析日志文件名
    
    Args:
        filename_pattern: 文件名模式
        target_date: 目标日期，默认为当前日期
        ssh_conn: SSH连接对象，处理切片通配符{N}时必需
        
    Returns:
        解析后的文件名
        
    Raises:
        ValueError: 当文件名模式包含{N}但未提供ssh_conn时
    """
    return filename_resolver.resolve_filename(filename_pattern, target_date, ssh_conn)


def validate_log_filename_pattern(pattern: str) -> Tuple[bool, List[str]]:
    """
    便捷函数：验证日志文件名模式
    
    Args:
        pattern: 文件名模式
        
    Returns:
        (is_valid, errors): 验证结果和错误信息列表
    """
    return filename_resolver.validate_pattern(pattern)
