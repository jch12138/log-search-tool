"""
日志相关API路由

实现日志搜索和文件管理的API接口
"""

import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, send_file
from middleware import api_response
from services import ConfigService, LogSearchService
from models import SearchParams
from config import Config
import tempfile
import io

# 创建蓝图
logs_bp = Blueprint('logs', __name__)

# 初始化服务
config_service = ConfigService(Config.CONFIG_FILE_PATH)
search_service = LogSearchService()

# 创建logger
logger = logging.getLogger(__name__)

def _handle_encoding_conversion(content: str, detected_encoding: str, host: str) -> str:
    """处理编码转换"""
    try:
        if not content:
            return content
        
        # 尝试不同的编码转换策略
        encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
        
        # 如果检测到了特定编码，优先尝试该编码
        if detected_encoding and detected_encoding != 'unknown':
            if detected_encoding not in encodings_to_try:
                encodings_to_try.insert(0, detected_encoding)
        
        for encoding in encodings_to_try:
            try:
                # 尝试用当前编码解码，然后用UTF-8编码
                if isinstance(content, str):
                    # 如果已经是字符串，先编码为字节再解码
                    decoded = content.encode('latin1').decode(encoding)
                else:
                    # 如果是字节，直接解码
                    decoded = content.decode(encoding)
                
                logger.debug(f"[{host}] 成功使用 {encoding} 编码转换内容")
                return decoded
            except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
                continue
        
        # 如果所有编码都失败，使用错误处理策略
        logger.warning(f"[{host}] 所有编码转换都失败，使用错误忽略策略")
        if isinstance(content, str):
            return content.encode('utf-8', errors='ignore').decode('utf-8')
        else:
            return content.decode('utf-8', errors='ignore')
            
    except Exception as e:
        logger.error(f"[{host}] 编码转换异常: {e}")
        return content  # 返回原始内容

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


@logs_bp.route('/logs/download', methods=['GET'])
def download_log_file():
    """GET /api/v1/logs/download - 下载日志文件
    
    查询参数：
    - host: 主机标识
    - file_path: 日志文件路径
    - log_name: 日志配置名称（可选，用于查找SSH配置）
    """
    host = request.args.get('host')
    file_path = request.args.get('file_path')
    log_name = request.args.get('log_name')
    
    if not host or not file_path:
        from flask import jsonify
        return jsonify({
            'success': False,
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': '缺少必要参数: host 和 file_path'
            }
        }), 400
    
    logger.info(f"下载请求 - Host: {host}, File: {file_path}")
    
    # 查找对应的SSH配置
    ssh_config = None
    
    if log_name:
        # 通过日志名称查找配置
        log_config = config_service.get_log_by_name(log_name)
        if log_config and hasattr(log_config, 'sshs'):
            for ssh in log_config.sshs:
                if ssh.get('host') == host:
                    ssh_config = ssh
                    break
    
    if not ssh_config:
        # 尝试从所有日志配置中查找匹配的主机
        logs_summary = config_service.get_log_summary()
        for log in logs_summary:
            log_config = config_service.get_log_by_name(log['name'])
            if log_config and hasattr(log_config, 'sshs'):
                for ssh in log_config.sshs:
                    if ssh.get('host') == host:
                        ssh_config = ssh
                        break
                if ssh_config:
                    break
    
    if not ssh_config:
        from flask import jsonify
        return jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': f'未找到主机 {host} 的SSH配置'
            }
        }), 404

    try:
        # 获取SSH连接
        from services.ssh_service import SSHConnectionManager
        ssh_manager = SSHConnectionManager()
        conn = ssh_manager.get_connection(ssh_config)
        
        if not conn:
            from flask import jsonify
            return jsonify({
                'success': False,
                'error': {
                    'code': 'CONNECTION_ERROR',
                    'message': 'SSH连接失败'
                }
            }), 500
        
        logger.info(f"SSH连接成功 - Host: {host}")
        
        # 执行命令获取文件内容
        command = f"cat '{file_path}'"
        logger.info(f"执行命令: {command}")
        
        # 先检测文件编码
        encoding_command = f"file -bi '{file_path}' 2>/dev/null || file '{file_path}' 2>/dev/null | grep -o 'charset=[^,]*' | cut -d= -f2 || echo 'unknown'"
        encoding_stdout, _, encoding_exit_code = conn.execute_command(encoding_command, timeout=10)
        
        detected_encoding = "unknown"
        if encoding_exit_code == 0 and encoding_stdout.strip():
            detected_encoding = encoding_stdout.strip().lower()
            logger.info(f"检测到文件编码: {detected_encoding}")
        
        # 根据检测结果调整读取命令
        if 'gbk' in detected_encoding or 'gb2312' in detected_encoding or 'gb18030' in detected_encoding:
            # 对于中文编码，设置UTF-8环境变量
            final_command = f"export LANG=zh_CN.UTF-8; export LC_ALL=zh_CN.UTF-8; {command}"
            logger.info(f"检测到中文编码 {detected_encoding}，使用UTF-8环境变量")
        else:
            final_command = command
        
        stdout, stderr, exit_code = conn.execute_command(final_command, timeout=60)
        
        logger.info(f"命令执行结果 - exit_code: {exit_code}, stdout长度: {len(stdout) if stdout else 0}")
        
        if exit_code != 0:
            logger.error(f"命令执行失败 - stderr: {stderr}")
            from flask import jsonify
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INTERNAL',
                    'message': f'读取文件失败: {stderr}'
                }
            }), 500
        
        if not stdout:
            logger.warning("文件内容为空")
            stdout = ""  # 允许空文件下载
        
        # 处理编码转换（如果需要）
        if detected_encoding != 'unknown' and ('gbk' in detected_encoding or 'gb2312' in detected_encoding or 'gb18030' in detected_encoding):
            stdout = _handle_encoding_conversion(stdout, detected_encoding, host)
        
        # 生成文件名
        import os
        from datetime import datetime
        file_name = os.path.basename(file_path) or 'log'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        download_filename = f"{host}_{file_name}_{timestamp}"
        
        # 确保文件名有扩展名
        if not download_filename.endswith('.log'):
            download_filename += '.log'
        
        logger.info(f"准备下载文件: {download_filename}, 大小: {len(stdout)} bytes")
        
        # 创建内存文件对象
        file_obj = io.BytesIO()
        file_obj.write(stdout.encode('utf-8'))
        file_obj.seek(0)
        
        logger.info(f"文件下载成功 - Host: {host}, File: {file_path}, Size: {len(stdout)} bytes")
        
        # 兼容不同版本的Flask
        import flask
        flask_version = tuple(map(int, flask.__version__.split('.')))
        
        if flask_version >= (2, 0, 0):
            # Flask 2.0+ 使用 download_name
            return send_file(
                file_obj,
                mimetype='text/plain',
                as_attachment=True,
                download_name=download_filename
            )
        else:
            # Flask 1.x 使用 attachment_filename
            from flask import Response
            response = Response(
                file_obj.getvalue(),
                mimetype='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename="{download_filename}"'
                }
            )
            return response
        
    except Exception as e:
        logger.error(f"下载文件失败 - Host: {host}, File: {file_path}, Error: {e}")
        logger.debug(f"下载文件异常详情", exc_info=True)
        from flask import jsonify
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'下载文件失败: {str(e)}'
            }
        }), 500
    finally:
        # 清理连接
        if 'ssh_manager' in locals():
            ssh_manager.close_all()
