"""
SSH连接管理器

负责管理SSH连接池和执行远程命令
"""

import os
import sys
import paramiko
import threading
import time
from typing import Dict, Optional, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import HostResult

import paramiko
import threading
import time
import logging
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

class SSHConnection:
    """SSH连接封装"""
    
    def __init__(self, ssh_config: Dict[str, Any]):
        self.config = ssh_config
        self.client = None
        self.connected = False
        self.last_used = time.time()
        self.lock = threading.Lock()
    
    def connect(self) -> bool:
        """建立SSH连接"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接参数
            connect_params = {
                'hostname': self.config['host'],
                'port': self.config.get('port', 22),
                'username': self.config['username'],
                'timeout': 30
            }
            
            # 认证方式
            if 'password' in self.config:
                connect_params['password'] = self.config['password']
            elif 'private_key' in self.config:
                # TODO: 处理私钥认证
                pass
            
            self.client.connect(**connect_params)
            self.connected = True
            self.last_used = time.time()
            
            logger.info(f"SSH连接成功: {self.config['host']}")
            return True
            
        except Exception as e:
            logger.error(f"SSH连接失败 {self.config['host']}: {e}")
            self.connected = False
            if self.client:
                self.client.close()
                self.client = None
            return False
    
    def execute_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """执行SSH命令"""
        if not self.connected or not self.client:
            raise Exception("SSH连接未建立")
        
        with self.lock:
            try:
                stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
                
                # 读取输出
                stdout_data = stdout.read().decode('utf-8', errors='ignore')
                stderr_data = stderr.read().decode('utf-8', errors='ignore')
                exit_code = stdout.channel.recv_exit_status()
                
                self.last_used = time.time()
                
                return stdout_data, stderr_data, exit_code
                
            except Exception as e:
                logger.error(f"执行命令失败 {self.config['host']}: {e}")
                raise
    
    def is_alive(self) -> bool:
        """检查连接是否有效"""
        if not self.connected or not self.client:
            return False
        
        try:
            # 发送简单命令测试连接
            transport = self.client.get_transport()
            return transport and transport.is_active()
        except:
            return False
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            self.client = None
        self.connected = False

class SSHConnectionManager:
    """SSH连接池管理器"""
    
    def __init__(self, max_connections: int = 20):
        self.connections: Dict[str, SSHConnection] = {}
        self.max_connections = max_connections
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # 启动清理线程
        self._start_cleanup_thread()
    
    def _connection_key(self, ssh_config: Dict[str, Any]) -> str:
        """生成连接键"""
        return f"{ssh_config['host']}:{ssh_config.get('port', 22)}:{ssh_config['username']}"
    
    def get_connection(self, ssh_config: Dict[str, Any]) -> Optional[SSHConnection]:
        """获取或创建SSH连接"""
        key = self._connection_key(ssh_config)
        
        with self.lock:
            # 检查现有连接
            if key in self.connections:
                conn = self.connections[key]
                if conn.is_alive():
                    return conn
                else:
                    # 清理失效连接
                    conn.close()
                    del self.connections[key]
            
            # 检查连接数限制
            if len(self.connections) >= self.max_connections:
                self._cleanup_old_connections()
            
            # 创建新连接
            conn = SSHConnection(ssh_config)
            if conn.connect():
                self.connections[key] = conn
                return conn
            else:
                return None
    
    def execute_command_async(self, ssh_config: Dict[str, Any], command: str) -> Future:
        """异步执行命令"""
        def _execute():
            conn = self.get_connection(ssh_config)
            if not conn:
                raise Exception(f"无法连接到 {ssh_config['host']}")
            
            return conn.execute_command(command)
        
        return self.executor.submit(_execute)
    
    def _cleanup_old_connections(self):
        """清理老旧连接"""
        current_time = time.time()
        to_remove = []
        
        for key, conn in self.connections.items():
            # 清理超过5分钟未使用的连接
            if current_time - conn.last_used > 300:
                to_remove.append(key)
        
        for key in to_remove:
            conn = self.connections.pop(key, None)
            if conn:
                conn.close()
                logger.info(f"清理老旧连接: {key}")
    
    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_loop():
            while True:
                time.sleep(60)  # 每分钟清理一次
                with self.lock:
                    self._cleanup_old_connections()
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            for conn in self.connections.values():
                conn.close()
            self.connections.clear()
        
        self.executor.shutdown(wait=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        with self.lock:
            total = len(self.connections)
            active = sum(1 for conn in self.connections.values() if conn.is_alive())
            
            return {
                'total_connections': total,
                'active_connections': active,
                'max_connections': self.max_connections
            }
