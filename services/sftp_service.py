"""
SFTP服务

提供SFTP文件管理功能：
- 连接和管理SFTP会话
- 文件和目录操作
- 批量下载和上传
"""

import os
import posixpath
import stat
import tempfile
import zipfile
import shutil
import time
import uuid
import paramiko
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict


@dataclass
class SFTPConnection:
    """SFTP连接信息"""
    connection_id: str
    connection_name: str
    host: str
    port: int
    username: str
    connected_at: str
    status: str = "active"


class SFTPService:
    """SFTP文件管理服务"""
    
    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.connection_info: Dict[str, SFTPConnection] = {}
    
    def connect(self, host: str, port: int = 22, username: str = "", 
               password: str = "", connection_name: str = "") -> SFTPConnection:
        """连接到SFTP服务器"""
        
        connection_id = f"conn_{uuid.uuid4().hex[:8]}"
        if not connection_name:
            connection_name = f"{host}:{port}"
        
        try:
            # 创建SSH客户端
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接SSH
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=10
            )
            
            # 创建SFTP客户端
            sftp_client = ssh_client.open_sftp()
            
            # 创建连接信息
            connection_info = SFTPConnection(
                connection_id=connection_id,
                connection_name=connection_name,
                host=host,
                port=port,
                username=username,
                connected_at=datetime.now().isoformat() + "Z",
                status="active"
            )
            
            # 存储连接
            self.connections[connection_id] = {
                'ssh': ssh_client,
                'sftp': sftp_client,
                'created_at': datetime.now()
            }
            self.connection_info[connection_id] = connection_info
            
            print(f"[INFO] SFTP连接成功: {connection_id}")
            return connection_info
            
        except Exception as e:
            raise Exception(f"SFTP连接失败: {str(e)}")
    
    def disconnect(self, connection_id: str) -> Dict[str, Any]:
        """断开SFTP连接"""
        connection_data = self.connections.pop(connection_id, None)
        connection_info = self.connection_info.pop(connection_id, None)
        
        if not connection_data or not connection_info:
            raise ValueError("SFTP连接不存在")
        
        try:
            if 'sftp' in connection_data:
                connection_data['sftp'].close()
            if 'ssh' in connection_data:
                connection_data['ssh'].close()
        except:
            pass
        
        return {
            "message": f"已断开连接 {connection_id}",
            "connection_id": connection_id
        }
    
    def get_connections(self) -> Dict[str, Any]:
        """获取所有SFTP连接列表"""
        connections = []
        for connection_id, connection_info in self.connection_info.items():
            connections.append(asdict(connection_info))
        
        return {
            "connections": connections,
            "total": len(connections)
        }
    
    def list_directory(self, connection_id: str, path: str = '.') -> Dict[str, Any]:
        """列出目录内容"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            
            # 获取当前工作目录
            home_dir = sftp.getcwd() or '/'
            
            # 规范化路径
            if not path or path in ('.', './'):
                remote_path = home_dir
            elif path.startswith('~'):
                remote_path = posixpath.normpath(path.replace('~', home_dir, 1))
            elif not path.startswith('/'):
                remote_path = posixpath.normpath(posixpath.join(home_dir, path))
            else:
                remote_path = posixpath.normpath(path)
            
            # 检查路径是否存在
            try:
                sftp.stat(remote_path)
            except FileNotFoundError:
                # 如果路径不存在，回退到home目录
                remote_path = home_dir
            
            # 列出目录内容
            entries = sftp.listdir_attr(remote_path)
            items = []
            
            for item in entries:
                file_info = {
                    'name': item.filename,
                    'type': 'directory' if stat.S_ISDIR(item.st_mode) else 'file',
                    'size': item.st_size if hasattr(item, 'st_size') else 0,
                    'size_human': self._format_size(item.st_size if hasattr(item, 'st_size') else 0),
                    'modified_time': datetime.fromtimestamp(item.st_mtime).isoformat() + "Z" if hasattr(item, 'st_mtime') else "",
                    'permissions': oct(item.st_mode)[-3:] if hasattr(item, 'st_mode') else "",
                    'is_directory': stat.S_ISDIR(item.st_mode) if hasattr(item, 'st_mode') else False
                }
                items.append(file_info)
            
            # 排序：目录在前，然后按名称排序
            items.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            
            return {
                'current_path': remote_path,
                'parent_path': posixpath.dirname(remote_path) if remote_path != '/' else None,
                'items': items,
                'total_items': len(items)
            }
            
        except Exception as e:
            raise Exception(f"列出目录失败: {str(e)}")
    
    def download_file(self, connection_id: str, remote_path: str) -> Tuple[str, str]:
        """下载文件到临时目录"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            
            # 获取文件名
            filename = posixpath.basename(remote_path)
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
            temp_path = temp_file.name
            temp_file.close()
            
            # 下载文件
            sftp.get(remote_path, temp_path)
            
            return temp_path, filename
            
        except Exception as e:
            raise Exception(f"下载文件失败: {str(e)}")
    
    def batch_download(self, connection_id: str, paths: List[str]) -> Tuple[str, str]:
        """批量下载多个文件，打包为ZIP"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        if not paths:
            raise ValueError("没有需要下载的文件")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            
            # 创建临时目录
            staging_dir = tempfile.mkdtemp(prefix='sftp_batch_')
            
            def fetch_directory(remote_dir: str, local_dir: str):
                """递归下载目录"""
                os.makedirs(local_dir, exist_ok=True)
                for item in sftp.listdir_attr(remote_dir):
                    remote_item_path = posixpath.join(remote_dir, item.filename)
                    local_item_path = os.path.join(local_dir, item.filename)
                    
                    if stat.S_ISDIR(item.st_mode):
                        fetch_directory(remote_item_path, local_item_path)
                    else:
                        try:
                            sftp.get(remote_item_path, local_item_path)
                        except Exception as e:
                            print(f"[ERROR] 下载文件失败(跳过): {remote_item_path} - {e}")
            
            # 下载所有文件/目录
            for remote_path in paths:
                remote_path = posixpath.normpath(remote_path)
                base_name = posixpath.basename(remote_path.rstrip('/')) or 'root'
                
                # 处理同名冲突
                counter = 2
                final_name = base_name
                while os.path.exists(os.path.join(staging_dir, final_name)):
                    final_name = f"{base_name}_{counter}"
                    counter += 1
                
                local_target = os.path.join(staging_dir, final_name)
                
                try:
                    attr = sftp.stat(remote_path)
                    if stat.S_ISDIR(attr.st_mode):
                        fetch_directory(remote_path, local_target)
                    else:
                        sftp.get(remote_path, local_target)
                except Exception as e:
                    print(f"[ERROR] 处理路径失败(跳过): {remote_path} - {e}")
            
            # 创建ZIP文件
            zip_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
            zip_filename = f"batch_{int(time.time())}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for root, dirs, files in os.walk(staging_dir):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, staging_dir)
                        zf.write(abs_path, rel_path)
            
            # 清理临时目录
            shutil.rmtree(staging_dir, ignore_errors=True)
            
            return zip_path, zip_filename
            
        except Exception as e:
            raise Exception(f"批量下载失败: {str(e)}")
    
    def upload_file(self, connection_id: str, local_file_path: str, 
                   remote_path: str, filename: str = None) -> Dict[str, Any]:
        """上传文件"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            
            # 确定目标文件名
            if filename is None:
                filename = os.path.basename(local_file_path)
            
            # 构建远程文件路径
            remote_file_path = posixpath.join(remote_path, filename)
            
            # 上传文件
            sftp.put(local_file_path, remote_file_path)
            
            # 获取文件大小
            file_size = os.path.getsize(local_file_path)
            
            return {
                "message": f"文件 {filename} 上传成功",
                "remote_path": remote_file_path,
                "file_size": file_size
            }
            
        except Exception as e:
            raise Exception(f"上传文件失败: {str(e)}")
    
    def create_directory(self, connection_id: str, remote_path: str, dir_name: str) -> Dict[str, Any]:
        """创建目录"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            full_path = posixpath.join(remote_path, dir_name)
            sftp.mkdir(full_path)
            
            return {
                "message": f"目录 {dir_name} 创建成功",
                "full_path": full_path
            }
            
        except Exception as e:
            raise Exception(f"创建目录失败: {str(e)}")
    
    def delete_item(self, connection_id: str, remote_path: str, is_directory: bool = False) -> Dict[str, Any]:
        """删除文件或目录"""
        if connection_id not in self.connections:
            raise ValueError("SFTP连接不存在")
        
        try:
            sftp = self.connections[connection_id]['sftp']
            
            if is_directory:
                sftp.rmdir(remote_path)
                item_type = "directory"
            else:
                sftp.remove(remote_path)
                item_type = "file"
            
            return {
                "message": "文件删除成功" if item_type == "file" else "目录删除成功",
                "remote_path": remote_path,
                "type": item_type
            }
            
        except Exception as e:
            raise Exception(f"删除失败: {str(e)}")
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def cleanup(self):
        """清理所有连接"""
        for connection_id in list(self.connections.keys()):
            try:
                self.disconnect(connection_id)
            except:
                pass
