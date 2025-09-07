#!/usr/bin/env python3
"""
Log Search API v1 - 主应用入口

基于Flask的日志搜索API服务
提供统一的RESTful接口用于日志搜索、配置管理和SSH连接管理
"""

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from middleware import register_error_handlers, setup_middleware
from routes import register_routes

socketio: SocketIO | None = None

def create_app():
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(Config)
    
    # 配置CORS - 允许所有来源的跨域请求
    CORS(app, 
         origins="*",  # 允许所有来源
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 允许的HTTP方法
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],  # 允许的请求头
         supports_credentials=True)  # 支持凭证
    
    # 验证配置
    if not Config.validate():
        raise RuntimeError("配置验证失败")
    
    # 设置日志：控制台 + 按天滚动文件
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    root_logger.handlers.clear()  # 清除默认handler，避免重复

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
    console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件输出（按天轮转，保留N天）
    try:
        log_path = os.path.join(Config.LOG_DIR, Config.LOG_FILE_NAME)
        file_handler = TimedRotatingFileHandler(log_path, when='midnight', backupCount=Config.LOG_BACKUP_COUNT, encoding='utf-8')
        file_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                                           datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        logging.getLogger(__name__).info(f"应用日志写入: {log_path} (保留 {Config.LOG_BACKUP_COUNT} 天)")
    except Exception as e:
        logging.getLogger(__name__).warning(f"文件日志配置失败: {e}")
    
    # 注册中间件
    setup_middleware(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册路由
    register_routes(app)
    
    # 初始化 Socket.IO
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # 延迟导入以避免循环依赖
    from services.terminal_manager import terminal_service

    # Socket 事件：客户端加入特定终端房间
    @socketio.on('join')
    def on_join(data):
        tid = data.get('terminal_id')
        if not tid:
            return
        join_room(tid)
        emit('joined', { 'terminal_id': tid })

    # Socket 事件：发送输入
    @socketio.on('input')
    def on_input(data):
        tid = data.get('terminal_id')
        payload = data.get('data', '')
        if not tid or payload is None:
            return
        try:
            terminal_service.send_command(tid, payload)
        except Exception as e:
            emit('error', { 'terminal_id': tid, 'message': str(e) })

    # 后台线程：将输出推送给订阅房间
    import threading, time
    def push_output_loop():
        while True:
            try:
                # 遍历所有会话，推送增量输出
                sessions = list(terminal_service.sessions.keys())
                for tid in sessions:
                    try:
                        out = terminal_service.get_output(tid)
                        if out:
                            socketio.emit('output', { 'terminal_id': tid, 'data': out }, room=tid)
                    except Exception:
                        # 会话不存在或其他错误，忽略
                        pass
                time.sleep(0.12)
            except Exception:
                time.sleep(0.2)

    threading.Thread(target=push_output_loop, daemon=True).start()

    logging.getLogger(__name__).info("应用初始化完成")

    return app

if __name__ == '__main__':
    app = create_app()
    assert socketio is not None
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, allow_unsafe_werkzeug=True)
