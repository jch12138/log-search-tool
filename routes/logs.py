"""
日志相关API路由

实现日志搜索和文件管理的API接口
"""

import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request
from middleware import api_response
from services import ConfigService, LogSearchService
from models import SearchParams
from config import Config

# 创建蓝图
logs_bp = Blueprint('logs', __name__)

# 初始化服务
config_service = ConfigService(Config.CONFIG_FILE_PATH)
search_service = LogSearchService()

# 创建logger
logger = logging.getLogger(__name__)

@logs_bp.route('/logs', methods=['GET'])
@api_response
def list_logs():
    """GET /api/v1/logs - 列出所有可用的日志配置
    
    查询参数：
    - include_ssh=true: 包含SSH连接信息，用于SFTP连接
    """
    include_ssh = request.args.get('include_ssh', '').lower() == 'true'
    
    if include_ssh:
        # 返回包含SSH连接信息的详细配置（原sftp/current-config功能）
        logs_summary = config_service.get_log_summary()
        log_configs = []
        
        for log in logs_summary:
            log_config = config_service.get_log_by_name(log['name'])
            if log_config and hasattr(log_config, 'sshs') and log_config.sshs:
                ssh_list = log_config.sshs
                for idx, ssh_config in enumerate(ssh_list):
                    # 生成唯一 connection_name
                    suffix = f"#{idx+1}" if len(ssh_list) > 1 else ""
                    connection_name = f"{log_config.name} - {ssh_config.get('host','unknown')}{suffix}"
                    
                    config_item = {
                        'log_name': log_config.name,
                        'connection_name': connection_name,
                        'host': ssh_config.get('host', ''),
                        'ip': ssh_config.get('host', ''),  # 简化处理，不做DNS解析
                        'port': ssh_config.get('port', 22),
                        'username': ssh_config.get('username', ''),
                        'password': '***',  # 脱敏处理
                        'log_path': log_config.path,
                        'ssh_index': idx,
                        'group': log_config.group
                    }
                    log_configs.append(config_item)
        
        return {
            'log_configs': log_configs,
            'total': len(log_configs)
        }
    else:
        # 返回基本的日志列表（原有功能）
        logs_summary = config_service.get_log_summary()
        return {
            'logs': logs_summary,
            'total': len(logs_summary)
        }

@logs_bp.route('/logs/<log_name>', methods=['GET'])
@api_response
def get_log_detail(log_name: str):
    """GET /api/v1/logs/{log_name} - 获取指定日志的详细配置信息"""
    log_detail = config_service.get_log_detail(log_name)
    
    if not log_detail:
        raise FileNotFoundError(f'未找到日志配置: {log_name}')
    
    return log_detail

@logs_bp.route('/logs/<log_name>/files', methods=['GET'])
@api_response
def get_log_files(log_name: str):
    """GET /api/v1/logs/{log_name}/files - 获取指定日志在所有主机上的文件列表"""
    log_config = config_service.get_log_by_name(log_name)
    if not log_config:
        raise FileNotFoundError(f'未找到日志配置: {log_name}')
    
    all_files = []
    for ssh_config in log_config.sshs:
        try:
            files = search_service.get_log_files(ssh_config, log_config.path)
            all_files.extend(files)
        except Exception as e:
            # 某个主机失败不影响其他主机
            continue
    
    return {
        'files': all_files,
        'log_name': log_name,
        'total_files': len(all_files)
    }

@logs_bp.route('/logs/<log_name>/search', methods=['POST'])
@api_response
def search_log(log_name: str):
    """POST /api/v1/logs/{log_name}/search - 日志搜索接口"""
    # 获取来源IP
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    # 获取日志配置
    log_config = config_service.get_log_by_name(log_name)
    if not log_config:
        raise FileNotFoundError(f'未找到日志配置: {log_name}')
    
    # 解析搜索参数
    data = request.get_json() or {}
    
    search_params = SearchParams(
        keyword=data.get('keyword', ''),
        search_mode=data.get('search_mode', 'keyword'),
        context_span=int(data.get('context_span', 5)),
        use_regex=bool(data.get('use_regex', False)),
        reverse_order=bool(data.get('reverse_order', False)),
        use_file_filter=bool(data.get('use_file_filter', False)),
        selected_file=data.get('selected_file'),  # 保持向后兼容
        selected_files=data.get('selected_files')  # 新增多主机文件选择
    )
    
    # 打印搜索日志
    logger.info(f"[SEARCH] IP: {client_ip} | Log: {log_name} | Keyword: '{search_params.keyword}' | Mode: {search_params.search_mode} | Regex: {search_params.use_regex} | Reverse: {search_params.reverse_order} | File Filter: {search_params.use_file_filter}")
    
    # 如果使用了文件过滤，记录选择的文件
    if search_params.use_file_filter:
        if search_params.selected_files:
            selected_info = ", ".join([f"{host}:{file}" for host, file in search_params.selected_files.items() if file])
            logger.info(f"[SEARCH] IP: {client_ip} | Selected files: {selected_info}")
        elif search_params.selected_file:
            logger.info(f"[SEARCH] IP: {client_ip} | Selected file: {search_params.selected_file}")
    
    # 执行搜索
    result = search_service.search_multi_host(
        log_config.to_dict(), 
        search_params
    )
    
    # 记录搜索结果统计
    logger.info(f"[SEARCH RESULT] IP: {client_ip} | Log: {log_name} | Matches: {result.total_results} | Search Time: {result.total_search_time:.3f}s | Hosts: {result.total_hosts}")
    
    return result.to_dict()
