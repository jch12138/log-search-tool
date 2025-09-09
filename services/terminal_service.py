"""
终端服务

提供SSH终端会话管理功能：
- 创建和管理SSH终端会话
- 处理命令执行和输出
- 会话状态跟踪
"""

import threading
import time
import uuid
import codecs
from .encoding import decode_bytes
from datetime import datetime
from typing import Dict, List, Optional, Any
import paramiko
from dataclasses import dataclass, asdict


@dataclass
class TerminalSession:
    """终端会话信息"""
    terminal_id: str
    session_id: str
    host: str
    port: int
    username: str
    status: str  # "connecting", "connected", "disconnected", "error"
    created_at: str
    last_activity: str
    current_directory: str = "~"
    current_prompt: str = ""
    command_count: int = 0
    session_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.session_history is None:
            self.session_history = []


class TerminalService:
    """终端服务"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_info: Dict[str, TerminalSession] = {}
        self._lock = threading.Lock()
    
    def create_terminal(self, host: str, port: int = 22, username: str = "", 
                       password: str = "", private_key: str = "", 
                       initial_command: str = "") -> TerminalSession:
        """创建新的终端会话"""
        
        terminal_id = f"term_{uuid.uuid4().hex[:8]}"
        session_id = f"session_{uuid.uuid4().hex[:6]}"
        
        try:
            # 创建SSH连接
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接参数
            connect_kwargs = {
                'hostname': host,
                'port': port,
                'username': username,
                'timeout': 10
            }
            
            if password:
                connect_kwargs['password'] = password
            elif private_key:
                # 处理私钥连接
                from io import StringIO
                key_file = StringIO(private_key)
                try:
                    pkey = paramiko.RSAKey.from_private_key(key_file)
                except:
                    try:
                        key_file.seek(0)
                        pkey = paramiko.DSSSKey.from_private_key(key_file)
                    except:
                        key_file.seek(0)
                        pkey = paramiko.ECDSAKey.from_private_key(key_file)
                connect_kwargs['pkey'] = pkey
            else:
                raise ValueError("必须提供密码或私钥")
            
            ssh_client.connect(**connect_kwargs)
            
            # 创建交互式shell
            channel = ssh_client.invoke_shell(term='xterm-256color')
            channel.settimeout(0.0)
            
            # 创建会话信息
            session_info = TerminalSession(
                terminal_id=terminal_id,
                session_id=session_id,
                host=host,
                port=port,
                username=username,
                status="connected",
                created_at=datetime.now().isoformat() + "Z",
                last_activity=datetime.now().isoformat() + "Z"
            )
            
            # 存储会话数据
            with self._lock:
                self.sessions[terminal_id] = {
                    'ssh_client': ssh_client,
                    'channel': channel,
                    'buffer': [],
                    'decoder': codecs.getincrementaldecoder('utf-8')(),
                    'encoding': 'utf-8',
                    'lock': threading.Lock(),
                    'created_at': datetime.now(),
                }
                self.session_info[terminal_id] = session_info
            
            # 启动输出读取线程
            threading.Thread(target=self._output_reader, args=(terminal_id,), daemon=True).start()
            
            # 尝试将远端环境切换为 UTF-8，降低乱码概率（C.UTF-8 通常更通用）
            try:
                channel.send("export LANG=C.UTF-8 LC_ALL=C.UTF-8\n")
            except Exception:
                pass

            # 执行初始命令（如果提供）
            if initial_command:
                time.sleep(1)  # 等待shell准备就绪
                self.send_command(terminal_id, initial_command)
            
            return session_info
            
        except Exception as e:
            raise Exception(f"创建终端会话失败: {str(e)}")
    
    def get_terminals(self) -> Dict[str, Any]:
        """获取所有终端会话列表"""
        with self._lock:
            terminals = []
            active_count = 0
            
            for terminal_id, session_info in self.session_info.items():
                session_dict = asdict(session_info)
                if session_info.status == "connected":
                    active_count += 1
                terminals.append(session_dict)
            
            return {
                "terminals": terminals,
                "total_count": len(terminals),
                "active_count": active_count
            }
    
    def get_terminal(self, terminal_id: str) -> Optional[TerminalSession]:
        """获取特定终端会话信息"""
        with self._lock:
            return self.session_info.get(terminal_id)
    
    def close_terminal(self, terminal_id: str) -> Dict[str, Any]:
        """关闭终端会话"""
        with self._lock:
            session_data = self.sessions.pop(terminal_id, None)
            session_info = self.session_info.pop(terminal_id, None)
            
            if not session_data or not session_info:
                raise ValueError("终端会话不存在")
            
            try:
                session_data['channel'].close()
                session_data['ssh_client'].close()
            except:
                pass
            
            # 计算会话持续时间
            created_at = session_data['created_at']
            closed_at = datetime.now()
            duration = closed_at - created_at
            
            return {
                "message": "终端会话已关闭",
                "terminal_id": terminal_id,
                "closed_at": closed_at.isoformat() + "Z",
                "session_duration": str(duration).split('.')[0],  # 去掉微秒
                "commands_executed": session_info.command_count
            }
    
    def send_command(self, terminal_id: str, command: str):
        """发送命令到终端"""
        with self._lock:
            session_data = self.sessions.get(terminal_id)
            session_info = self.session_info.get(terminal_id)
            
            if not session_data or not session_info:
                raise ValueError("终端会话不存在")
            
            try:
                channel = session_data['channel']
                channel.send(command.encode(session_data['encoding']))
                
                # 更新会话信息
                session_info.last_activity = datetime.now().isoformat() + "Z"
                session_info.command_count += 1
                
                # 记录命令历史
                session_info.session_history.append({
                    "timestamp": session_info.last_activity,
                    "command": command,
                    "output": ""  # 输出会在后续更新
                })
                
            except Exception as e:
                session_info.status = "error"
                raise Exception(f"发送命令失败: {str(e)}")

    def resize_terminal(self, terminal_id: str, cols: int, rows: int):
        """调整终端尺寸"""
        with self._lock:
            session_data = self.sessions.get(terminal_id)
            session_info = self.session_info.get(terminal_id)
            
            if not session_data or not session_info:
                raise ValueError("终端会话不存在")
            
            try:
                channel = session_data['channel']
                # 调整SSH通道的伪终端尺寸
                channel.resize_pty(width=cols, height=rows)
                
                # 更新会话信息
                session_info.last_activity = datetime.now().isoformat() + "Z"
                
            except Exception as e:
                raise Exception(f"调整终端尺寸失败: {str(e)}")
    
    def get_output(self, terminal_id: str) -> str:
        """获取终端输出"""
        session_data = self.sessions.get(terminal_id)
        if not session_data:
            raise ValueError("终端会话不存在")
        
        with session_data['lock']:
            if not session_data['buffer']:
                return ''
            
            output = ''.join(session_data['buffer'])
            session_data['buffer'].clear()
            
            # 更新最后活动时间
            with self._lock:
                session_info = self.session_info.get(terminal_id)
                if session_info:
                    session_info.last_activity = datetime.now().isoformat() + "Z"
            
            return output
    
    def _output_reader(self, terminal_id: str):
        """输出读取线程"""
        session_data = self.sessions.get(terminal_id)
        if not session_data:
            return
        
        channel = session_data['channel']
        decoder = session_data['decoder']
        
        while True:
            if channel.closed:
                break
            
            try:
                if channel.recv_ready():
                    data = channel.recv(8192)
                    if not data:
                        break

                    try:
                        text = decoder.decode(data)
                    except Exception:
                        # 使用统一 decode_bytes 回退策略
                        text = decode_bytes(data)
                    
                    with session_data['lock']:
                        session_data['buffer'].append(text)
                else:
                    time.sleep(0.05)
                    
            except Exception:
                time.sleep(0.1)
        
        # 会话结束处理
        try:
            tail = decoder.decode(b"", final=True)
        except Exception:
            tail = ""
        
        with session_data['lock']:
            if tail:
                session_data['buffer'].append(tail)
            session_data['buffer'].append("\n[会话已结束]\n")
        
        # 更新会话状态
        with self._lock:
            session_info = self.session_info.get(terminal_id)
            if session_info:
                session_info.status = "disconnected"
