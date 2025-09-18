"""App middleware (moved from project root)."""

from __future__ import annotations

import time
import logging
from functools import wraps
from flask import Flask, request, jsonify, g

logger = logging.getLogger(__name__)

def setup_middleware(app: Flask):
    @app.before_request
    def before_request():
        g.start_time = time.time()
        logger.info(f"Request: {request.method} {request.path}")
        g.request_id = f"{int(time.time())}-{id(request)}"

    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
        response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
        response.headers['X-API-Version'] = 'v1'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '86400'
        return response

def api_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                data, status_code = result
                return jsonify({'success': True, 'data': data}), status_code
            return jsonify({'success': True, 'data': result})
        except ValueError as e:
            msg = str(e)
            return jsonify({'success': False,'error': {'code': 'INVALID_ARGUMENT','message': msg,'details': msg}}), 400
        except FileNotFoundError as e:
            return jsonify({'success': False,'error': {'code': 'NOT_FOUND','message': f'文件或资源不存在: {e}','details': str(e)}}), 404
        except PermissionError as e:
            return jsonify({'success': False,'error': {'code': 'PERMISSION_DENIED','message': f'权限不足: {e}','details': str(e)}}), 403
        except TimeoutError as e:
            return jsonify({'success': False,'error': {'code': 'DEADLINE_EXCEEDED','message': f'操作超时: {e}','details': str(e)}}), 408
        except ConnectionError as e:
            return jsonify({'success': False,'error': {'code': 'CONNECTION_ERROR','message': f'连接失败: {e}','details': str(e)}}), 503
        except Exception as e:  # pragma: no cover
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            return jsonify({'success': False,'error': {'code': 'INTERNAL','message': '服务器内部错误，请稍后重试','details': str(e)}}), 500
    return wrapper

def register_error_handlers(app: Flask):
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False,'error': {'code': 'NOT_FOUND','message': '接口不存在'}}), 404
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'success': False,'error': {'code': 'METHOD_NOT_ALLOWED','message': '请求方法不允许'}}), 405
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'success': False,'error': {'code': 'INTERNAL','message': '服务器内部错误'}}), 500

__all__ = ['setup_middleware','api_response','register_error_handlers']
