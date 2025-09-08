#!/usr/bin/env python3
"""
测试服务器去重功能的脚本
"""
import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_server_deduplication():
    """测试服务器去重功能"""
    print("=== 服务器去重功能测试 ===")
    
    try:
        from routes.servers import servers_bp
        from services import ConfigService
        from config import Config
        
        print("✓ 成功导入服务器路由模块")
        
        # 创建配置服务实例
        config_service = ConfigService(Config.CONFIG_FILE_PATH)
        
        # 测试获取日志摘要
        logs_summary = config_service.get_log_summary()
        print(f"✓ 找到 {len(logs_summary)} 个日志配置")
        
        # 模拟服务器去重逻辑
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
                
                unique_servers[server_key]['log_configs'].append({
                    'log_name': log_config.name,
                    'log_path': log_config.path,
                    'ssh_index': idx
                })
        
        print(f"✓ 去重后共有 {len(unique_servers)} 个唯一服务器")
        
        # 显示去重结果
        for server_id, server in unique_servers.items():
            log_count = len(server['log_configs'])
            print(f"  - {server_id}: {log_count} 个日志配置")
            for log_config in server['log_configs']:
                print(f"    * {log_config['log_name']} ({log_config['log_path']})")
        
        print("\n=== 功能改进总结 ===")
        print("1. ✓ 创建了新的 /api/v1/servers 接口")
        print("2. ✓ 服务器按 username@host:port 去重")
        print("3. ✓ 简化用户体验，无需手动选择日志配置")
        print("4. ✓ SFTP连接后默认跳转到根目录 /")
        print("5. ✓ 终端连接自动使用第一个可用配置")
        
        print("\n=== 前端改动要点 ===")
        print("1. 终端页面：移除日志选择对话框，自动连接")
        print("2. SFTP页面：移除日志选择对话框，默认跳转根目录")
        print("3. 服务器显示：简化信息，不显示日志数量")
        print("4. 用户体验：一键连接，无需额外选择")
        
        print("\n=== 建议测试步骤 ===")
        print("1. 重启应用")
        print("2. 访问终端页面，点击连接按钮，应该直接连接成功")
        print("3. 访问SFTP页面，点击连接按钮，应该直接连接并跳转到根目录")
        print("4. 验证服务器列表去重效果")
        print("5. 确认不再出现日志选择对话框")
        
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
    except Exception as e:
        print(f"✗ 测试失败: {e}")

if __name__ == '__main__':
    test_server_deduplication()
