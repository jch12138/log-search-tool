"""Application data models (migrated)."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class LogConfig:
    name: str
    # 顶层 path 改为可选，仅用于向后兼容；实际应在每个 ssh 配置下提供 path
    path: Optional[str] = None
    description: str = ""
    group: Optional[str] = None
    sshs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'name': self.name,
            'description': self.description,
            'group': self.group,
            'sshs': self.sshs
        }
        # 仅当提供了顶层 path（兼容旧配置）时才写回
        if self.path is not None:
            data['path'] = self.path
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogConfig':
        return cls(
            name=data['name'],
            path=data.get('path'),
            description=data.get('description', ''),
            group=data.get('group'),
            sshs=data.get('sshs', [])
        )


@dataclass
class SearchParams:
    keyword: str = ""
    search_mode: str = "keyword"
    context_span: int = 5
    use_regex: bool = False
    reverse_order: bool = False
    use_file_filter: bool = False
    selected_file: Optional[str] = None
    selected_files: Optional[Dict[str, str]] = None

    def validate(self):
        errors = []
        if self.context_span < 0 or self.context_span > 50:
            errors.append(f"上下文行数必须在 0-50 之间，当前值: {self.context_span}")
        valid_modes = ['keyword', 'context', 'tail']
        if self.search_mode not in valid_modes:
            errors.append(f"搜索模式必须是 {'/'.join(valid_modes)} 之一，当前值: {self.search_mode}")
    # 放宽文件过滤约束：允许未指定文件时后端使用默认路径
        if errors:
            raise ValueError("参数验证失败: " + "; ".join(errors))


@dataclass
class SearchResult:
    host: str
    ssh_index: int
    results: List[str]
    total_results: int
    search_time: float
    search_result: Dict[str, Any]
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
    log_name: str
    keyword: str
    search_params: Dict[str, Any]
    total_hosts: int
    hosts: List[SearchResult]
    total_results: int
    total_search_time: float
    parallel_execution: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_name': self.log_name,
            'keyword': self.keyword,
            'search_params': self.search_params,
            'total_matches': self.total_results,
            'search_time': self.total_search_time,
            'hosts_searched': self.total_hosts,
            'parallel_execution': self.parallel_execution,
            'hosts': [h.to_dict() for h in self.hosts],
            'total_hosts': self.total_hosts,
            'total_results': self.total_results,
            'total_search_time': self.total_search_time
        }


@dataclass
class HostResult:
    host: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'execution_time': self.execution_time
        }


@dataclass
class FileInfo:
    filename: str
    full_path: str
    size: str
    modified_time: str
    host: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'full_path': self.full_path,
            'size': self.size,
            'modified_time': self.modified_time,
            'host': self.host
        }

__all__ = [
    'LogConfig', 'SearchParams', 'SearchResult', 'MultiHostSearchResult',
    'HostResult', 'FileInfo'
]
