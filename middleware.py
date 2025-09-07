"""
中间件模块

处理请求/响应的通用逻辑
"""

from flask import Flask, request, jsonify, g
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def setup_middleware(app: Flask):
    """设置应用中间件"""
    
    @app.before_request
    def before_request():
        """请求前处理"""
        g.start_time = time.time()
        
        # 记录请求信息
        logger.info(f"Request: {request.method} {request.path}")
        
        # 设置请求ID
        g.request_id = f"{int(time.time())}-{id(request)}"
    
    @app.after_request 
    def after_request(response):
        """请求后处理"""
        # 计算处理时间
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
        
        # 设置通用响应头
        response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
        response.headers['X-API-Version'] = 'v1'
        
        # 确保CORS头设置正确（作为Flask-CORS的补充）
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '86400'  # 24小时
        
        return response
    
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        return jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': '接口不存在'
            }
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """405错误处理"""
        return jsonify({
            'success': False,
            'error': {
                'code': 'METHOD_NOT_ALLOWED',
                'message': '请求方法不被允许'
            }
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        logger.error(f"Internal error: {error}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': '服务器内部错误'
            }
        }), 500

def api_response(func):
    """API响应装饰器 - 统一响应格式"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                # 如果返回的是 (data, status_code) 格式
                data, status_code = result
                return jsonify({
                    'success': True,
                    'data': data
                }), status_code
            else:
                # 如果返回的是单个data
                return jsonify({
                    'success': True,
                    'data': result
                })
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_ARGUMENT',
                    'message': str(e)
                }
            }), 400
        except FileNotFoundError as e:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NOT_FOUND',
                    'message': str(e)
                }
            }), 404
        except PermissionError as e:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': str(e)
                }
            }), 403
        except TimeoutError as e:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'DEADLINE_EXCEEDED',
                    'message': str(e)
                }
            }), 408
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INTERNAL',
                    'message': '服务器内部错误'
                }
            }), 500
    return wrapper


def register_error_handlers(app: Flask):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        return jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': '接口不存在'
            }
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """405错误处理"""
        return jsonify({
            'success': False,
            'error': {
                'code': 'METHOD_NOT_ALLOWED', 
                'message': '请求方法不允许'
            }
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': '服务器内部错误'
            }
        }), 500
