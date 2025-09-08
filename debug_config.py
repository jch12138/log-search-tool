#!/usr/bin/env python3
"""
调试配置重复问题的脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services import ConfigService
from config import Config

def main():
    config_service = ConfigService(Config.CONFIG_FILE_PATH)
    
    print("=== 原始配置数据 ===")
    config = config_service.load_config()
    logs = config.get('logs', [])
    
    for i, log in enumerate(logs):
        print(f"\n日志配置 {i+1}:")
        print(f"  名称: {log.get('name')}")
        print(f"  路径: {log.get('path')}")
        print(f"  分组: {log.get('group', '无')}")
        print(f"  SSH配置数量: {len(log.get('sshs', []))}")
        
        for j, ssh in enumerate(log.get('sshs', [])):
            print(f"    SSH {j+1}: {ssh.get('username')}@{ssh.get('host')}:{ssh.get('port')}")
    
    print("\n=== 日志摘要数据 ===")
    logs_summary = config_service.get_log_summary()
    for log_summary in logs_summary:
        print(f"日志: {log_summary['name']}, 分组: {log_summary.get('group', '无')}, SSH数量: {log_summary['ssh_count']}")
    
    print("\n=== 服务器去重分析 ===")
    unique_servers = {}
    
    for log in logs_summary:
        log_config = config_service.get_log_by_name(log['name'])
        if not log_config or not hasattr(log_config, 'sshs') or not log_config.sshs:
            continue
            
        for idx, ssh_config in enumerate(log_config.sshs):
            host = ssh_config.get('host', '')
            port = ssh_config.get('port', 22)
            username = ssh_config.get('username', '')
            
            # 生成服务器唯一标识
            server_key = f"{username}@{host}:{port}"
            
            if server_key not in unique_servers:
                unique_servers[server_key] = {
                    'server_id': server_key,
                    'host': host,
                    'port': port,
                    'username': username,
                    'log_configs': []
                }
            
            # 添加日志配置到该服务器
            log_info = {
                'log_name': log_config.name,
                'log_path': log_config.path,
                'group': log_config.group,
                'ssh_index': idx
            }
            
            unique_servers[server_key]['log_configs'].append(log_info)
    
    print(f"去重后的服务器数量: {len(unique_servers)}")
    for server_key, server_info in unique_servers.items():
        print(f"\n服务器: {server_key}")
        print(f"  关联的日志配置:")
        for log_info in server_info['log_configs']:
            print(f"    - {log_info['log_name']} (分组: {log_info.get('group', '无')})")
            print(f"      路径: {log_info['log_path']}")

if __name__ == '__main__':
    main()
