"""
TunnelNX 进程间通信模块
提供GUI进程、节点图解析器进程和节点图运行引擎进程之间的通信机制
"""

import multiprocessing
import queue
import json
import pickle
import socket
import struct
import threading
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """消息类型枚举"""
    # 节点图解析相关
    PARSE_NODEGRAPH = "parse_nodegraph"
    PARSE_RESULT = "parse_result"
    PARSE_ERROR = "parse_error"
    
    # 节点图执行相关
    EXECUTE_NODEGRAPH = "execute_nodegraph"
    EXECUTE_RESULT = "execute_result"
    EXECUTE_ERROR = "execute_error"
    EXECUTE_PROGRESS = "execute_progress"
    
    # 节点处理相关
    PROCESS_NODE = "process_node"
    NODE_RESULT = "node_result"
    NODE_ERROR = "node_error"
    
    # 系统控制
    SHUTDOWN = "shutdown"
    PING = "ping"
    PONG = "pong"
    
    # 缓存管理
    CACHE_GET = "cache_get"
    CACHE_SET = "cache_set"
    CACHE_CLEAR = "cache_clear"
    CACHE_RESULT = "cache_result"

class Message:
    """进程间通信消息"""
    def __init__(self, msg_type: MessageType, data: Any = None, request_id: str = None):
        self.type = msg_type
        self.data = data
        self.request_id = request_id or str(time.time())
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'type': self.type.value,
            'data': self.data,
            'request_id': self.request_id,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """从字典创建消息"""
        return cls(
            MessageType(data['type']),
            data.get('data'),
            data.get('request_id')
        )

class ProcessCommunicator:
    """进程通信器基类"""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.running = False
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.pending_requests: Dict[str, threading.Event] = {}
        self.request_results: Dict[str, Any] = {}
        
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[msg_type] = handler
        
    def send_message(self, target: str, message: Message) -> Optional[Any]:
        """发送消息（子类实现）"""
        raise NotImplementedError
        
    def receive_message(self) -> Optional[Message]:
        """接收消息（子类实现）"""
        raise NotImplementedError
        
    def send_request(self, target: str, msg_type: MessageType, data: Any = None, timeout: float = 30.0) -> Any:
        """发送请求并等待响应"""
        message = Message(msg_type, data)
        request_id = message.request_id
        
        # 创建等待事件
        event = threading.Event()
        self.pending_requests[request_id] = event
        
        try:
            # 发送消息
            self.send_message(target, message)
            
            # 等待响应
            if event.wait(timeout):
                return self.request_results.pop(request_id, None)
            else:
                logger.warning(f"Request {request_id} timed out")
                return None
        finally:
            # 清理
            self.pending_requests.pop(request_id, None)
            self.request_results.pop(request_id, None)
    
    def handle_message(self, message: Message):
        """处理接收到的消息"""
        handler = self.message_handlers.get(message.type)
        if handler:
            try:
                result = handler(message.data)
                
                # 如果是请求消息，发送响应
                if message.request_id and message.request_id in self.pending_requests:
                    self.request_results[message.request_id] = result
                    self.pending_requests[message.request_id].set()
                    
            except Exception as e:
                logger.error(f"Error handling message {message.type}: {e}")
                
                # 发送错误响应
                if message.request_id and message.request_id in self.pending_requests:
                    self.request_results[message.request_id] = {'error': str(e)}
                    self.pending_requests[message.request_id].set()
        else:
            logger.warning(f"No handler for message type {message.type}")
    
    def start(self):
        """启动通信器"""
        self.running = True
        
    def stop(self):
        """停止通信器"""
        self.running = False

class QueueCommunicator(ProcessCommunicator):
    """基于队列的进程通信器"""
    
    def __init__(self, process_name: str, input_queue: multiprocessing.Queue, output_queues: Dict[str, multiprocessing.Queue]):
        super().__init__(process_name)
        self.input_queue = input_queue
        self.output_queues = output_queues
        self.receiver_thread = None
        
    def send_message(self, target: str, message: Message) -> Optional[Any]:
        """发送消息到目标进程"""
        if target in self.output_queues:
            try:
                self.output_queues[target].put(message.to_dict(), timeout=5.0)
                return True
            except queue.Full:
                logger.error(f"Queue to {target} is full")
                return False
        else:
            logger.error(f"Unknown target: {target}")
            return False
    
    def receive_message(self) -> Optional[Message]:
        """从输入队列接收消息"""
        try:
            data = self.input_queue.get(timeout=0.1)
            return Message.from_dict(data)
        except queue.Empty:
            return None
    
    def _receiver_loop(self):
        """消息接收循环"""
        while self.running:
            message = self.receive_message()
            if message:
                self.handle_message(message)
    
    def start(self):
        """启动通信器"""
        super().start()
        self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self.receiver_thread.start()
        logger.info(f"Started {self.process_name} communicator")
    
    def stop(self):
        """停止通信器"""
        super().stop()
        if self.receiver_thread:
            self.receiver_thread.join(timeout=1.0)
        logger.info(f"Stopped {self.process_name} communicator")

class SocketCommunicator(ProcessCommunicator):
    """基于Socket的进程通信器（用于更复杂的通信需求）"""
    
    def __init__(self, process_name: str, port: int, target_ports: Dict[str, int]):
        super().__init__(process_name)
        self.port = port
        self.target_ports = target_ports
        self.server_socket = None
        self.client_sockets: Dict[str, socket.socket] = {}
        
    def _send_data(self, sock: socket.socket, data: bytes):
        """发送数据到socket"""
        # 先发送数据长度
        length = len(data)
        sock.sendall(struct.pack('!I', length))
        # 再发送数据
        sock.sendall(data)
    
    def _receive_data(self, sock: socket.socket) -> bytes:
        """从socket接收数据"""
        # 先接收数据长度
        length_data = sock.recv(4)
        if len(length_data) < 4:
            raise ConnectionError("Connection closed")
        length = struct.unpack('!I', length_data)[0]
        
        # 接收数据
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data
    
    def send_message(self, target: str, message: Message) -> Optional[Any]:
        """发送消息到目标进程"""
        if target not in self.target_ports:
            logger.error(f"Unknown target: {target}")
            return False
            
        try:
            # 建立连接（如果尚未建立）
            if target not in self.client_sockets:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(('localhost', self.target_ports[target]))
                self.client_sockets[target] = sock
            
            # 序列化并发送消息
            data = pickle.dumps(message.to_dict())
            self._send_data(self.client_sockets[target], data)
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to {target}: {e}")
            # 清理失效连接
            if target in self.client_sockets:
                self.client_sockets[target].close()
                del self.client_sockets[target]
            return False
    
    def start(self):
        """启动Socket服务器"""
        super().start()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        
        # 启动接收线程
        threading.Thread(target=self._accept_connections, daemon=True).start()
        logger.info(f"Started {self.process_name} socket server on port {self.port}")
    
    def _accept_connections(self):
        """接受连接的循环"""
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
    
    def _handle_client(self, client_sock: socket.socket):
        """处理客户端连接"""
        try:
            while self.running:
                data = self._receive_data(client_sock)
                message_dict = pickle.loads(data)
                message = Message.from_dict(message_dict)
                self.handle_message(message)
        except Exception as e:
            logger.debug(f"Client connection closed: {e}")
        finally:
            client_sock.close()
    
    def stop(self):
        """停止Socket服务器"""
        super().stop()
        if self.server_socket:
            self.server_socket.close()
        for sock in self.client_sockets.values():
            sock.close()
        self.client_sockets.clear()
        logger.info(f"Stopped {self.process_name} socket server")

def create_process_queues():
    """创建进程间通信队列"""
    # 创建各进程的输入队列
    gui_queue = multiprocessing.Queue()
    parser_queue = multiprocessing.Queue()
    engine_queue = multiprocessing.Queue()
    
    # 返回队列映射
    return {
        'gui': {
            'input': gui_queue,
            'outputs': {
                'parser': parser_queue,
                'engine': engine_queue
            }
        },
        'parser': {
            'input': parser_queue,
            'outputs': {
                'gui': gui_queue,
                'engine': engine_queue
            }
        },
        'engine': {
            'input': engine_queue,
            'outputs': {
                'gui': gui_queue,
                'parser': parser_queue
            }
        }
    }
