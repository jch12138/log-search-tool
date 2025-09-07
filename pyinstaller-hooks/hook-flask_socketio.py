from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('flask_socketio') + collect_submodules('engineio') + collect_submodules('socketio')
