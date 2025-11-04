import app as app_pkg  # type: ignore
from app.config.system_settings import Settings  # type: ignore

settings = Settings()
app = app_pkg.create_app()
socketio = app_pkg.socketio

if __name__ == '__main__':
    if socketio is None:
        raise RuntimeError('SocketIO 未初始化')
    print('-'*50)
    print('Log Search Tool (refactored)')
    print(f'http://{settings.HOST}:{settings.PORT}')
    print('-'*50)
    socketio.run(app, host=settings.HOST, port=settings.PORT, debug=settings.DEBUG, allow_unsafe_werkzeug=True, use_reloader=settings.DEBUG)
