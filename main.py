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
from flask_cors import CORS

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from middleware import register_error_handlers, setup_middleware
from routes import register_routes

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
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置控制台日志输出格式
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # 获取root logger并设置格式
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # 清除默认handler
    root_logger.addHandler(console_handler)
    
    # 注册中间件
    setup_middleware(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册路由
    register_routes(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=5001,  # 使用不同端口避免冲突
        debug=True
    )
