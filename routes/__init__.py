"""
路由模块

导入并注册所有API路由蓝图
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from .logs import logs_bp
from .config import config_bp
from .connections import connections_bp
from .terminals import terminals_bp
from .sftp import sftp_bp
from .servers import servers_bp

def register_routes(app: Flask):
    """注册所有API路由"""
    
    # API前缀
    api_prefix = app.config.get('API_PREFIX', '/api/v1')
    
    # 注册各功能模块的路由
    app.register_blueprint(logs_bp, url_prefix=api_prefix)
    app.register_blueprint(config_bp, url_prefix=api_prefix)
    app.register_blueprint(connections_bp, url_prefix=api_prefix)
    app.register_blueprint(terminals_bp, url_prefix=api_prefix)
    app.register_blueprint(sftp_bp, url_prefix=api_prefix)
    app.register_blueprint(servers_bp, url_prefix=api_prefix)
    
    # 健康检查接口
    @app.route(f'{api_prefix}/health', methods=['GET'])
    def health_check():
        """API健康检查"""
        from services import ConfigService
        from config import Config
        
        try:
            # 检查配置文件
            config_service = ConfigService(Config.CONFIG_FILE_PATH)
            config = config_service.load_config()
            
            return {
                'success': True,
                'data': {
                    'status': 'healthy',
                    'version': '1.0.0',
                    'logs_configured': len(config.get('logs', [])),
                    'api_prefix': api_prefix,
                    'uptime': 'N/A'
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': {
                    'code': 'INTERNAL',
                    'message': f'健康检查失败: {str(e)}'
                }
            }, 500
    
    # 根路径 - 前端页面
    @app.route('/')
    def index():
        """前端日志搜索页面"""
        return render_template('index.html')

    # 配置编辑页面 - 已隐藏，不开放给用户手动配置
    # @app.route('/config')
    # def config_page():
    #     """日志配置编辑页面"""
    #     return render_template('config.html')
    
    # SFTP 文件管理页面
    @app.route('/sftp')
    def sftp_page():
        """SFTP 文件管理页面"""
        return render_template('sftp.html')
    
    # 在线终端页面
    @app.route('/terminals')
    def terminals_page():
        """在线终端页面"""
        return render_template('terminals.html')
    
    # 前端健康检查
    @app.route('/health')
    def frontend_health():
        """前端健康检查"""
        try:
            # 检查API服务是否正常
            from services import ConfigService
            from config import Config
            
            config_service = ConfigService(Config.CONFIG_FILE_PATH)
            config = config_service.load_config()
            
            return {
                'frontend': True,
                'api': True,
                'logs_configured': len(config.get('logs', []))
            }
        except Exception as e:
            return {
                'frontend': True,
                'api': False,
                'error': str(e)
            }, 500
