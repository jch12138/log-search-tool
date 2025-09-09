"""
数据模型定义

定义API中使用的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class LogConfig:
    """日志配置模型"""
    name: str
    path: str
    description: str = ""
    group: Optional[str] = None
    sshs: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'path': self.path,
            'description': self.description,
            'group': self.group,
            'sshs': self.sshs
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogConfig':
        """从字典创建实例"""
        return cls(
            name=data['name'],
            path=data['path'],
            description=data.get('description', ''),
            group=data.get('group'),
            sshs=data.get('sshs', [])
        )

@dataclass 
class SearchParams:
    """搜索参数模型"""
    keyword: str = ""
    search_mode: str = "keyword"  # keyword | context | tail
    context_span: int = 5
    use_regex: bool = False
    reverse_order: bool = False
    use_file_filter: bool = False
    selected_file: Optional[str] = None  # 保持向后兼容
    selected_files: Optional[Dict[str, str]] = None  # 新增：主机到文件的映射 {"host1": "file1", "host2": "file2"}
    
    def validate(self):
        """验证参数有效性"""
        errors = []
        
        # 验证 context_span
        if self.context_span < 0 or self.context_span > 50:
            errors.append(f"上下文行数必须在 0-50 之间，当前值: {self.context_span}")
        
        # 验证 search_mode
        valid_modes = ['keyword', 'context', 'tail']
        if self.search_mode not in valid_modes:
            errors.append(f"搜索模式必须是 {'/'.join(valid_modes)} 中的一种，当前值: {self.search_mode}")
        
        # 验证文件过滤设置
        if self.use_file_filter:
            if not self.selected_files and not self.selected_file:
                errors.append("启用文件过滤时必须指定要搜索的文件")
        
        # 如果有错误，抛出包含所有错误信息的异常
        if errors:
            raise ValueError("参数验证失败: " + "; ".join(errors))

@dataclass
class SearchResult:
    """单个主机的搜索结果"""
    host: str
    ssh_index: int
    results: List[str]
    total_results: int
    search_time: float
    search_result: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'host': self.host,
            'ssh_index': self.ssh_index,
            'results': self.results,
            'total_results': self.total_results,
            'search_time': self.search_time,
            'search_result': self.search_result,
            'success': self.success,
            'error': self.error
        }

@dataclass
class MultiHostSearchResult:
    """多主机搜索结果"""
    log_name: str
    keyword: str
    search_params: Dict[str, Any]
    total_hosts: int
    hosts: List[SearchResult]
    total_results: int
    total_search_time: float
    parallel_execution: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'log_name': self.log_name,
            'keyword': self.keyword,
            'search_params': self.search_params,
            'total_matches': self.total_results,  # 前端期望的字段名
            'search_time': self.total_search_time,  # 前端期望的字段名
            'hosts_searched': self.total_hosts,  # 前端期望的字段名
            'parallel_execution': self.parallel_execution,
            # 保留原始数据以便调试
            'hosts': [host.to_dict() for host in self.hosts],
            'total_hosts': self.total_hosts,
            'total_results': self.total_results,
            'total_search_time': self.total_search_time
        }

@dataclass
class HostResult:
    """单个主机执行结果"""
    host: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'host': self.host,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'execution_time': self.execution_time
        }

@dataclass
class FileInfo:
    """文件信息模型"""
    filename: str
    full_path: str
    size: str
    modified_time: str
    host: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'filename': self.filename,
            'full_path': self.full_path,
            'size': self.size,
            'modified_time': self.modified_time,
            'host': self.host
        }
