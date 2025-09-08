#!/usr/bin/env python3
"""
调试 get_log_files 方法在Linux服务器上的问题
"""

import os
import sys
from services.log_service import LogSearchService

# 模拟SSH连接类
class MockSSHConnection:
    def __init__(self, system_type='linux'):
        self.system_type = system_type
    
    def execute_command(self, command, timeout=10):
        print(f"执行命令: {command}")
        
        if 'find' in command and '-printf' in command:
            # Linux find命令
            if self.system_type == 'linux':
                stdout = """app.log.1	1048576	2025-09-08 10:30:45	2025-09-08 15:45:20	/var/log/app.log.1
app.log.2	2097152	2025-09-07 09:15:30	2025-09-07 18:22:10	/var/log/app.log.2
error.log	524288	2025-09-08 08:20:15	2025-09-08 16:30:25	/var/log/error.log
2025-09-08.8.log	1024	2025-09-08 12:00:00	2025-09-08 12:30:00	/var/log/2025-09-08.8.log"""
                return stdout, "", 0
            else:
                return "", "find: -printf: unknown primary or operator", 1
        elif 'find' in command and 'stat -f' in command:
            # macOS find+stat命令
            if self.system_type == 'macos':
                stdout = """app.log.1	1048576	2025-09-08 10:30:45	2025-09-08 15:45:20	/var/log/app.log.1
app.log.2	2097152	2025-09-07 09:15:30	2025-09-07 18:22:10	/var/log/app.log.2
error.log	524288	2025-09-08 08:20:15	2025-09-08 16:30:25	/var/log/error.log"""
                return stdout, "", 0
            else:
                return "", "stat: illegal option -- f", 1
        elif 'ls -la' in command:
            # ls命令
            stdout = """-rw-r--r--  1 user  group  1048576 Sep  8 15:45 app.log.1
-rw-r--r--  1 user  group  2097152 Sep  7 18:22 app.log.2
-rw-r--r--  1 user  group   524288 Sep  8 16:30 error.log
-rw-r--r--  1 user  group     1024 Sep  8 12:30 2025-09-08.8.log"""
            return stdout, "", 0
        else:
            return "", "", 0

def test_get_log_files():
    """测试get_log_files方法"""
    
    service = LogSearchService()
    
    print("测试修复后的get_log_files方法")
    print("=" * 60)
    
    log_path = '/var/log/app.log'
    ssh_config = {'host': 'test-server'}
    
    # 测试Linux系统
    print("\n场景1：Linux服务器")
    mock_ssh_linux = MockSSHConnection('linux')
    
    # 手动替换get_connection方法
    original_get_connection = service.ssh_manager.get_connection
    service.ssh_manager.get_connection = lambda config: mock_ssh_linux
    
    try:
        files = service.get_log_files(ssh_config, log_path)
        print(f"找到 {len(files)} 个文件:")
        for file_info in files:
            print(f"  - 文件名: {file_info['filename']}")
            print(f"    路径: {file_info['full_path']}")
            print(f"    大小: {file_info['size']} bytes")
            print(f"    创建时间: {file_info['birth_time']}")
            print(f"    修改时间: {file_info['modified_time']}")
            print(f"    主机: {file_info['host']}")
            print()
    except Exception as e:
        print(f"Linux测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试macOS系统
    print("\n场景2：macOS服务器")
    mock_ssh_macos = MockSSHConnection('macos')
    service.ssh_manager.get_connection = lambda config: mock_ssh_macos
    
    try:
        files = service.get_log_files(ssh_config, log_path)
        print(f"找到 {len(files)} 个文件:")
        for file_info in files:
            print(f"  - 文件名: {file_info['filename']}")
            print(f"    大小: {file_info['size']} bytes")
            print(f"    修改时间: {file_info['modified_time']}")
            print()
    except Exception as e:
        print(f"macOS测试失败: {e}")
    
    # 测试fallback到ls命令
    print("\n场景3：fallback到ls命令")
    mock_ssh_fallback = MockSSHConnection('unknown')
    service.ssh_manager.get_connection = lambda config: mock_ssh_fallback
    
    try:
        files = service.get_log_files(ssh_config, log_path)
        print(f"找到 {len(files)} 个文件:")
        for file_info in files:
            print(f"  - 文件名: {file_info['filename']}")
            print(f"    大小: {file_info['size']} bytes")
            print(f"    修改时间: {file_info['modified_time']}")
            print()
    except Exception as e:
        print(f"fallback测试失败: {e}")
    
    # 恢复原始方法
    service.ssh_manager.get_connection = original_get_connection

if __name__ == "__main__":
    test_get_log_files()
