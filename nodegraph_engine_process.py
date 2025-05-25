"""
TunnelNX 节点图运行引擎进程
负责实际的节点处理计算，管理节点缓存和中间结果，执行图像处理算法
"""

import os
import sys
import time
import importlib.util
import threading
from typing import Dict, List, Any, Optional
import logging
from collections import OrderedDict
import numpy as np
from PIL import Image

from process_communication import (
    ProcessCommunicator, QueueCommunicator, MessageType, Message
)

logger = logging.getLogger(__name__)

class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 200):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Any:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self.lock:
            if key in self.cache:
                # 更新现有值
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # 移除最久未使用的项
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)

class NodeExecutor:
    """节点执行器"""
    
    def __init__(self, scripts_folder: str, cache_size: int = 200):
        self.scripts_folder = scripts_folder
        self.cache = LRUCache(cache_size)
        self.loaded_modules = {}
        self.node_results = {}  # 存储节点执行结果
        
    def load_module(self, script_path: str):
        """加载脚本模块"""
        if script_path in self.loaded_modules:
            return self.loaded_modules[script_path]
        
        try:
            spec = importlib.util.spec_from_file_location("node_module", script_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module from {script_path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            self.loaded_modules[script_path] = module
            return module
            
        except Exception as e:
            logger.error(f"Error loading module {script_path}: {e}")
            raise
    
    def execute_node(self, node: Dict, inputs: Dict, context: Dict) -> Dict:
        """执行单个节点"""
        try:
            node_id = node['id']
            script_path = node['script_path']
            
            # 生成缓存键
            cache_key = self._generate_cache_key(node, inputs)
            
            # 检查缓存
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for node {node_id}")
                return cached_result
            
            # 加载模块
            module = self.load_module(script_path)
            
            # 检查是否有process函数
            if not hasattr(module, 'process'):
                raise AttributeError(f"Module {script_path} does not have a 'process' function")
            
            # 准备参数
            params = {}
            for param_name, param_info in node.get('params', {}).items():
                if isinstance(param_info, dict) and 'value' in param_info:
                    params[param_name] = param_info['value']
                else:
                    params[param_name] = param_info
            
            # 执行节点
            logger.debug(f"Executing node {node_id}: {node['title']}")
            start_time = time.time()
            
            outputs = module.process(inputs, params, context)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 包装结果
            result = {
                'outputs': outputs or {},
                'execution_time': execution_time,
                'node_id': node_id,
                'success': True
            }
            
            # 缓存结果
            self.cache.set(cache_key, result)
            
            logger.debug(f"Node {node_id} executed in {execution_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error executing node {node['id']}: {e}")
            return {
                'outputs': {},
                'execution_time': 0,
                'node_id': node['id'],
                'success': False,
                'error': str(e)
            }
    
    def _generate_cache_key(self, node: Dict, inputs: Dict) -> str:
        """生成缓存键"""
        import hashlib
        
        # 组合节点信息和输入信息
        key_data = {
            'node_id': node['id'],
            'script_path': node['script_path'],
            'params': node.get('params', {}),
            'inputs_hash': self._hash_inputs(inputs)
        }
        
        # 生成哈希
        key_str = str(sorted(key_data.items()))
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _hash_inputs(self, inputs: Dict) -> str:
        """计算输入数据的哈希值"""
        import hashlib
        
        hash_parts = []
        for key, value in sorted(inputs.items()):
            if isinstance(value, np.ndarray):
                # 对numpy数组计算哈希
                hash_parts.append(f"{key}:{hashlib.md5(value.tobytes()).hexdigest()}")
            elif isinstance(value, (str, int, float, bool)):
                hash_parts.append(f"{key}:{value}")
            else:
                # 其他类型转换为字符串
                hash_parts.append(f"{key}:{str(value)}")
        
        combined = "|".join(hash_parts)
        return hashlib.md5(combined.encode()).hexdigest()

class NodeGraphEngine:
    """节点图执行引擎"""
    
    def __init__(self, scripts_folder: str, cache_size: int = 200):
        self.executor = NodeExecutor(scripts_folder, cache_size)
        self.current_execution = None
        self.execution_lock = threading.Lock()
        
    def execute_nodegraph(self, execution_data: Dict, progress_callback=None) -> Dict:
        """执行节点图"""
        try:
            with self.execution_lock:
                nodes = execution_data.get('nodes', [])
                connections = execution_data.get('connections', [])
                execution_order = execution_data.get('execution_order', [])
                context = execution_data.get('context', {})
                
                if not execution_order:
                    return {
                        'success': False,
                        'error': 'No execution order provided',
                        'results': {}
                    }
                
                # 构建节点映射
                node_map = {node['id']: node for node in nodes}
                
                # 构建连接映射
                input_connections = self._build_input_connections(connections)
                
                # 执行节点
                results = {}
                total_nodes = len(execution_order)
                
                for i, node_id in enumerate(execution_order):
                    if node_id not in node_map:
                        logger.error(f"Node {node_id} not found in node map")
                        continue
                    
                    node = node_map[node_id]
                    
                    # 获取节点输入
                    inputs = self._get_node_inputs(node_id, input_connections, results)
                    
                    # 执行节点
                    result = self.executor.execute_node(node, inputs, context)
                    results[node_id] = result
                    
                    # 报告进度
                    if progress_callback:
                        progress = (i + 1) / total_nodes * 100
                        progress_callback({
                            'progress': progress,
                            'current_node': node_id,
                            'completed_nodes': i + 1,
                            'total_nodes': total_nodes
                        })
                    
                    # 检查执行是否成功
                    if not result.get('success', False):
                        logger.error(f"Node {node_id} execution failed: {result.get('error', 'Unknown error')}")
                        return {
                            'success': False,
                            'error': f"Node {node_id} execution failed: {result.get('error', 'Unknown error')}",
                            'results': results
                        }
                
                return {
                    'success': True,
                    'results': results,
                    'total_execution_time': sum(r.get('execution_time', 0) for r in results.values())
                }
                
        except Exception as e:
            logger.error(f"Error executing nodegraph: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': {}
            }
    
    def _build_input_connections(self, connections: List[Dict]) -> Dict:
        """构建输入连接映射"""
        input_connections = {}
        
        for conn in connections:
            input_node_id = conn['input_node_id']
            if input_node_id not in input_connections:
                input_connections[input_node_id] = []
            input_connections[input_node_id].append(conn)
        
        return input_connections
    
    def _get_node_inputs(self, node_id: str, input_connections: Dict, results: Dict) -> Dict:
        """获取节点的输入数据"""
        inputs = {}
        
        if node_id not in input_connections:
            return inputs
        
        for conn in input_connections[node_id]:
            output_node_id = conn['output_node_id']
            output_port_idx = conn['output_port_idx']
            input_port_idx = conn['input_port_idx']
            
            if output_node_id in results:
                output_result = results[output_node_id]
                if output_result.get('success', False):
                    outputs = output_result.get('outputs', {})
                    
                    # 根据端口索引获取输出
                    output_keys = list(outputs.keys())
                    if output_port_idx < len(output_keys):
                        output_key = output_keys[output_port_idx]
                        output_value = outputs[output_key]
                        
                        # 根据输入端口索引设置输入
                        # 这里简化处理，使用输出的键作为输入键
                        inputs[output_key] = output_value
        
        return inputs

class NodeGraphEngineProcess:
    """节点图执行引擎进程"""
    
    def __init__(self, scripts_folder: str, communicator: ProcessCommunicator, cache_size: int = 200):
        self.engine = NodeGraphEngine(scripts_folder, cache_size)
        self.communicator = communicator
        self.running = False
        
        # 注册消息处理器
        self.communicator.register_handler(MessageType.EXECUTE_NODEGRAPH, self.handle_execute_request)
        self.communicator.register_handler(MessageType.CACHE_CLEAR, self.handle_cache_clear)
        self.communicator.register_handler(MessageType.SHUTDOWN, self.handle_shutdown)
        self.communicator.register_handler(MessageType.PING, self.handle_ping)
    
    def handle_execute_request(self, data: Dict) -> Dict:
        """处理节点图执行请求"""
        logger.info("Received nodegraph execution request")
        
        def progress_callback(progress_data):
            # 发送进度更新
            progress_message = Message(MessageType.EXECUTE_PROGRESS, progress_data)
            self.communicator.send_message('gui', progress_message)
        
        try:
            result = self.engine.execute_nodegraph(data, progress_callback)
            
            if result['success']:
                logger.info(f"Execution completed successfully in {result.get('total_execution_time', 0):.3f}s")
            else:
                logger.error(f"Execution failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling execution request: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': {}
            }
    
    def handle_cache_clear(self, data: Any) -> Dict:
        """处理缓存清理请求"""
        logger.info("Clearing node cache")
        self.engine.executor.cache.clear()
        return {'status': 'cache_cleared', 'size': self.engine.executor.cache.size()}
    
    def handle_shutdown(self, data: Any) -> Dict:
        """处理关闭请求"""
        logger.info("Received shutdown request")
        self.running = False
        return {'status': 'shutting_down'}
    
    def handle_ping(self, data: Any) -> Dict:
        """处理ping请求"""
        return {
            'status': 'alive', 
            'process': 'engine',
            'cache_size': self.engine.executor.cache.size()
        }
    
    def run(self):
        """运行引擎进程"""
        logger.info("Starting NodeGraph Engine Process")
        self.running = True
        self.communicator.start()
        
        try:
            while self.running:
                time.sleep(0.1)  # 避免CPU占用过高
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.communicator.stop()
            logger.info("NodeGraph Engine Process stopped")

def main():
    """主函数"""
    import multiprocessing
    from process_communication import create_process_queues, QueueCommunicator
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建通信队列
    queues = create_process_queues()
    engine_queues = queues['engine']
    
    # 创建通信器
    communicator = QueueCommunicator(
        'engine',
        engine_queues['input'],
        engine_queues['outputs']
    )
    
    # 创建并运行引擎进程
    scripts_folder = "TunnelNX_scripts"
    engine_process = NodeGraphEngineProcess(scripts_folder, communicator)
    engine_process.run()

if __name__ == "__main__":
    main()
