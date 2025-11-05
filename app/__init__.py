import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler, WatchedFileHandler
from flask import Flask, render_template
from flask_socketio import SocketIO, join_room, leave_room, rooms
from flask_cors import CORS

from .config.system_settings import Settings
from .middleware import register_error_handlers, setup_middleware
from .api.routes import register_routes

socketio: SocketIO | None = None

def create_app() -> Flask:
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    static_folder = os.path.join(base_path, 'static') if os.path.isdir(os.path.join(base_path, 'static')) else os.path.join(os.path.dirname(base_path), 'static')
    template_folder = os.path.join(base_path, 'templates') if os.path.isdir(os.path.join(base_path, 'templates')) else os.path.join(os.path.dirname(base_path), 'templates')

    app = Flask(__name__, static_folder=static_folder, template_folder=template_folder)
    settings = Settings()
    app.config.update(settings.to_flask_config())

    CORS(app, origins="*", methods=["GET","POST","PUT","DELETE","OPTIONS"], allow_headers=["Content-Type","Authorization","X-Requested-With"], supports_credentials=True)

    _configure_logging(settings)

    setup_middleware(app)
    register_error_handlers(app)
    register_routes(app)

    # Frontend root (logs main)
    @app.route('/')
    def index():  # pragma: no cover
        return render_template('index.html', page='')

    @app.route('/sftp')
    def sftp_page():  # pragma: no cover
        return render_template('sftp.html', page='sftp')

    @app.route('/terminals')
    def terminals_page():  # pragma: no cover
        return render_template('terminals.html', page='terminals')

    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # 延迟导入新的终端服务单例
    from app.services.terminal.manager import terminal_service as terminal_service_singleton  # noqa

    import threading, time
    def push_output_loop():
        while True:
            try:
                if hasattr(terminal_service_singleton, 'sessions'):
                    for tid in list(terminal_service_singleton.sessions.keys()):
                        try:
                            out = terminal_service_singleton.get_output(tid)
                            if out:
                                socketio.emit('output', {'terminal_id': tid, 'data': out}, room=tid)
                        except Exception:
                            pass
                time.sleep(0.12)
            except Exception:
                time.sleep(0.2)
    threading.Thread(target=push_output_loop, daemon=True).start()

    # Socket.IO 事件处理（终端交互）
    @socketio.on('join')  # pragma: no cover - realtime
    def handle_join(data):  # noqa
        try:
            tid = data.get('terminal_id') if isinstance(data, dict) else None
            if not tid:
                return
            if tid in terminal_service_singleton.sessions:
                join_room(tid)
        except Exception:
            pass

    @socketio.on('leave')  # pragma: no cover - realtime
    def handle_leave(data):  # noqa
        try:
            tid = data.get('terminal_id') if isinstance(data, dict) else None
            if not tid:
                return
            leave_room(tid)
        except Exception:
            pass

    @socketio.on('input')  # pragma: no cover - realtime
    def handle_input(data):  # noqa
        try:
            if not isinstance(data, dict):
                return
            tid = data.get('terminal_id')
            payload = data.get('data')
            if not tid or payload is None:
                return
            terminal_service_singleton.send_raw(tid, payload)
            terminal_service_singleton.touch(tid)
        except ValueError:
            pass
        except Exception:
            pass


    @socketio.on('resize')  # pragma: no cover - realtime
    def handle_resize(data):  # noqa
        try:
            if not isinstance(data, dict):
                return
            tid = data.get('terminal_id')
            cols = int(data.get('cols', 0) or 0)
            rows = int(data.get('rows', 0) or 0)
            if not tid or cols <= 0 or rows <= 0:
                return
            terminal_service_singleton.resize_terminal(tid, cols=cols, rows=rows)
            terminal_service_singleton.touch(tid)
        except Exception:
            pass

    @socketio.on('disconnect')  # pragma: no cover - realtime
    def handle_disconnect():  # noqa
        """在客户端 Socket 断开时标记相关终端，延迟几秒无重连则关闭。"""
        try:
            current_rooms = list(rooms()) if callable(rooms) else []
            terminal_ids = [r for r in current_rooms if isinstance(r, str) and r.startswith('term_')]
            if not terminal_ids:
                return
            logging.getLogger(__name__).info("[socket] disconnect; candidate terminal rooms=%s", terminal_ids)
            import threading, time as _time

            def _delayed_check(tids):
                _time.sleep(5)
                for tid in tids:
                    try:
                        if tid in terminal_service_singleton.sessions:
                            logging.getLogger(__name__).info("[socket] closing orphan terminal after disconnect: %s", tid)
                            terminal_service_singleton.close_terminal(tid)
                    except Exception:
                        continue

            threading.Thread(target=_delayed_check, args=(terminal_ids,), daemon=True).start()
        except Exception:
            logging.getLogger(__name__).exception("socket disconnect handler failed")

    # 注册关闭回调，通知前端
    def _on_close(payload):  # pragma: no cover - realtime
        try:
            socketio.emit('terminal_closed', payload, room=payload.get('terminal_id'))
        except Exception:
            pass
    try:
        terminal_service_singleton.register_close_listener(_on_close)
    except Exception:
        pass

    logging.getLogger(__name__).info("应用初始化完成 (new structure)")
    return app


def _configure_logging(settings: Settings):
    root_logger = logging.getLogger()
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', '%Y-%m-%d %H:%M:%S')
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    try:
        # Determine log file path: prefer explicit LOG_PATH; else compose from DIR + FILE
        if getattr(settings, 'LOG_PATH', ''):
            log_file = settings.LOG_PATH
            log_dir = os.path.dirname(log_file) or '.'
        else:
            log_dir = settings.LOG_DIR
            log_file = os.path.join(settings.LOG_DIR, settings.LOG_FILE_NAME)
        os.makedirs(log_dir, exist_ok=True)
        # In multi-process environments (debug reloader, multiple workers), TimedRotatingFileHandler
        # can leave some processes writing to the rotated file. Allow opting into WatchedFileHandler
        # which cooperates with external rotation tools (logrotate/newsyslog) and is safe for multi-proc.
        use_watched = bool(getattr(settings, 'USE_WATCHED_LOG', False))
        if use_watched:
            file_handler = WatchedFileHandler(log_file, encoding='utf-8')
        else:
            file_handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=settings.LOG_BACKUP_COUNT, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.getLogger(__name__).warning(f'文件日志配置失败: {e}')

__all__ = ['create_app', 'socketio']
