"""
TunnelNX 节点图解析器进程
负责解析节点图JSON文件，验证连接有效性，构建执行依赖图
"""

import os
import sys
import json
import time
import importlib.util
from typing import Dict, List, Any, Optional, Tuple
import logging
from collections import defaultdict, deque

from process_communication import (
    ProcessCommunicator, QueueCommunicator, MessageType, Message
)

logger = logging.getLogger(__name__)

class NodeGraphParser:
    """节点图解析器"""
    
    def __init__(self, scripts_folder: str):
        self.scripts_folder = scripts_folder
        self.script_registry = {}
        self.pseudo_types = {}
        self._scan_scripts()
    
    def _scan_scripts(self):
        """扫描脚本文件夹，构建脚本注册表"""
        logger.info(f"Scanning scripts in {self.scripts_folder}")
        self.script_registry = {}
        
        if not os.path.exists(self.scripts_folder):
            logger.warning(f"Scripts folder {self.scripts_folder} does not exist")
            return
        
        # 递归遍历脚本文件夹
        for root, dirs, files in os.walk(self.scripts_folder):
            rel_path = os.path.relpath(root, self.scripts_folder)
            
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    script_path = os.path.join(root, file)
                    rel_script_path = os.path.join(rel_path, file) if rel_path != '.' else file
                    
                    try:
                        script_info = self._load_script_info(script_path)
                        if script_info:
                            # 使用相对路径作为键
                            key = rel_script_path.replace('\\', '/').replace('.py', '')
                            self.script_registry[key] = {
                                'path': script_path,
                                'info': script_info
                            }
                            logger.debug(f"Loaded script: {key}")
                    except Exception as e:
                        logger.error(f"Error loading script {script_path}: {e}")
        
        logger.info(f"Loaded {len(self.script_registry)} scripts")
    
    def _load_script_info(self, script_path: str) -> Optional[Dict]:
        """加载脚本信息"""
        try:
            spec = importlib.util.spec_from_file_location("temp_module", script_path)
            if spec is None or spec.loader is None:
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 获取脚本信息
            info = {
                'inputs': getattr(module, 'get_inputs', lambda: {})(),
                'outputs': getattr(module, 'get_outputs', lambda: {})(),
                'params': getattr(module, 'get_params', lambda: {})(),
                'title': getattr(module, 'get_title', lambda: os.path.basename(script_path))(),
                'color': getattr(module, 'get_color', lambda: '#808080')(),
                'description': getattr(module, 'get_description', lambda: '')(),
                'script_type': getattr(module, 'get_script_type', lambda: 'standard')(),
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error loading script info from {script_path}: {e}")
            return None
    
    def parse_nodegraph(self, nodegraph_data: Dict) -> Dict:
        """解析节点图数据"""
        try:
            result = {
                'success': True,
                'nodes': [],
                'connections': [],
                'execution_order': [],
                'errors': [],
                'warnings': []
            }
            
            # 解析节点
            nodes_data = nodegraph_data.get('nodes', [])
            connections_data = nodegraph_data.get('connections', [])
            
            # 验证节点
            for node_data in nodes_data:
                node_result = self._validate_node(node_data)
                if node_result['valid']:
                    result['nodes'].append(node_result['node'])
                else:
                    result['errors'].extend(node_result['errors'])
            
            # 验证连接
            for conn_data in connections_data:
                conn_result = self._validate_connection(conn_data, result['nodes'])
                if conn_result['valid']:
                    result['connections'].append(conn_result['connection'])
                else:
                    result['errors'].extend(conn_result['errors'])
            
            # 构建执行顺序
            if not result['errors']:
                execution_order = self._build_execution_order(result['nodes'], result['connections'])
                if execution_order['success']:
                    result['execution_order'] = execution_order['order']
                else:
                    result['errors'].extend(execution_order['errors'])
            
            # 如果有错误，标记为失败
            if result['errors']:
                result['success'] = False
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing nodegraph: {e}")
            return {
                'success': False,
                'nodes': [],
                'connections': [],
                'execution_order': [],
                'errors': [f"Parse error: {str(e)}"],
                'warnings': []
            }
    
    def _validate_node(self, node_data: Dict) -> Dict:
        """验证单个节点"""
        errors = []
        
        # 检查必要字段
        required_fields = ['id', 'title', 'script_path']
        for field in required_fields:
            if field not in node_data:
                errors.append(f"Node missing required field: {field}")
        
        if errors:
            return {'valid': False, 'errors': errors}
        
        # 检查脚本是否存在
        script_path = node_data['script_path']
        script_key = script_path.replace('\\', '/').replace('.py', '')
        
        if script_key not in self.script_registry:
            errors.append(f"Script not found: {script_path}")
            return {'valid': False, 'errors': errors}
        
        # 获取脚本信息
        script_info = self.script_registry[script_key]['info']
        
        # 验证参数
        node_params = node_data.get('params', {})
        script_params = script_info.get('params', {})
        
        for param_name, param_value in node_params.items():
            if param_name not in script_params:
                errors.append(f"Node {node_data['id']}: Unknown parameter {param_name}")
        
        # 构建验证后的节点
        validated_node = {
            'id': node_data['id'],
            'title': node_data['title'],
            'script_path': script_path,
            'script_info': script_info,
            'params': node_params,
            'x': node_data.get('x', 0),
            'y': node_data.get('y', 0),
            'inputs': script_info.get('inputs', {}),
            'outputs': script_info.get('outputs', {}),
        }
        
        return {'valid': True, 'node': validated_node, 'errors': []}
    
    def _validate_connection(self, conn_data: Dict, nodes: List[Dict]) -> Dict:
        """验证连接"""
        errors = []
        
        # 检查必要字段
        required_fields = ['output_node_id', 'output_port_idx', 'input_node_id', 'input_port_idx']
        for field in required_fields:
            if field not in conn_data:
                errors.append(f"Connection missing required field: {field}")
        
        if errors:
            return {'valid': False, 'errors': errors}
        
        # 查找节点
        output_node = None
        input_node = None
        
        for node in nodes:
            if node['id'] == conn_data['output_node_id']:
                output_node = node
            if node['id'] == conn_data['input_node_id']:
                input_node = node
        
        if not output_node:
            errors.append(f"Output node not found: {conn_data['output_node_id']}")
        if not input_node:
            errors.append(f"Input node not found: {conn_data['input_node_id']}")
        
        if errors:
            return {'valid': False, 'errors': errors}
        
        # 验证端口
        output_ports = list(output_node['outputs'].keys())
        input_ports = list(input_node['inputs'].keys())
        
        output_port_idx = conn_data['output_port_idx']
        input_port_idx = conn_data['input_port_idx']
        
        if output_port_idx >= len(output_ports):
            errors.append(f"Invalid output port index: {output_port_idx}")
        if input_port_idx >= len(input_ports):
            errors.append(f"Invalid input port index: {input_port_idx}")
        
        if errors:
            return {'valid': False, 'errors': errors}
        
        # 验证类型兼容性
        output_type = output_ports[output_port_idx]
        input_type = input_ports[input_port_idx]
        
        if not self._are_types_compatible(output_type, input_type):
            errors.append(f"Type mismatch: {output_type} -> {input_type}")
        
        if errors:
            return {'valid': False, 'errors': errors}
        
        # 构建验证后的连接
        validated_connection = {
            'output_node_id': conn_data['output_node_id'],
            'output_port_idx': output_port_idx,
            'input_node_id': conn_data['input_node_id'],
            'input_port_idx': input_port_idx,
            'output_type': output_type,
            'input_type': input_type
        }
        
        return {'valid': True, 'connection': validated_connection, 'errors': []}
    
    def _are_types_compatible(self, output_type: str, input_type: str) -> bool:
        """检查类型兼容性"""
        # 处理伪类型
        real_output_type = self.pseudo_types.get(output_type, output_type)
        real_input_type = self.pseudo_types.get(input_type, input_type)
        
        # any类型兼容所有类型
        if output_type == 'any' or input_type == 'any':
            return True
        
        # 相同类型兼容
        if real_output_type == real_input_type:
            return True
        
        return False
    
    def _build_execution_order(self, nodes: List[Dict], connections: List[Dict]) -> Dict:
        """构建节点执行顺序（拓扑排序）"""
        try:
            # 构建依赖图
            dependencies = defaultdict(set)  # node_id -> set of dependency node_ids
            dependents = defaultdict(set)    # node_id -> set of dependent node_ids
            
            for conn in connections:
                output_node_id = conn['output_node_id']
                input_node_id = conn['input_node_id']
                dependencies[input_node_id].add(output_node_id)
                dependents[output_node_id].add(input_node_id)
            
            # 拓扑排序
            in_degree = {}
            for node in nodes:
                node_id = node['id']
                in_degree[node_id] = len(dependencies[node_id])
            
            queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
            execution_order = []
            
            while queue:
                current_node_id = queue.popleft()
                execution_order.append(current_node_id)
                
                # 更新依赖此节点的其他节点
                for dependent_id in dependents[current_node_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)
            
            # 检查是否有循环依赖
            if len(execution_order) != len(nodes):
                remaining_nodes = [node['id'] for node in nodes if node['id'] not in execution_order]
                return {
                    'success': False,
                    'order': [],
                    'errors': [f"Circular dependency detected involving nodes: {remaining_nodes}"]
                }
            
            return {
                'success': True,
                'order': execution_order,
                'errors': []
            }
            
        except Exception as e:
            logger.error(f"Error building execution order: {e}")
            return {
                'success': False,
                'order': [],
                'errors': [f"Error building execution order: {str(e)}"]
            }

class NodeGraphParserProcess:
    """节点图解析器进程"""
    
    def __init__(self, scripts_folder: str, communicator: ProcessCommunicator):
        self.parser = NodeGraphParser(scripts_folder)
        self.communicator = communicator
        self.running = False
        
        # 注册消息处理器
        self.communicator.register_handler(MessageType.PARSE_NODEGRAPH, self.handle_parse_request)
        self.communicator.register_handler(MessageType.SHUTDOWN, self.handle_shutdown)
        self.communicator.register_handler(MessageType.PING, self.handle_ping)
    
    def handle_parse_request(self, data: Dict) -> Dict:
        """处理节点图解析请求"""
        logger.info("Received nodegraph parse request")
        
        try:
            nodegraph_data = data.get('nodegraph_data', {})
            result = self.parser.parse_nodegraph(nodegraph_data)
            
            logger.info(f"Parse completed: {len(result['nodes'])} nodes, {len(result['connections'])} connections")
            if result['errors']:
                logger.warning(f"Parse errors: {result['errors']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling parse request: {e}")
            return {
                'success': False,
                'nodes': [],
                'connections': [],
                'execution_order': [],
                'errors': [f"Parse error: {str(e)}"],
                'warnings': []
            }
    
    def handle_shutdown(self, data: Any) -> Dict:
        """处理关闭请求"""
        logger.info("Received shutdown request")
        self.running = False
        return {'status': 'shutting_down'}
    
    def handle_ping(self, data: Any) -> Dict:
        """处理ping请求"""
        return {'status': 'alive', 'process': 'parser'}
    
    def run(self):
        """运行解析器进程"""
        logger.info("Starting NodeGraph Parser Process")
        self.running = True
        self.communicator.start()
        
        try:
            while self.running:
                time.sleep(0.1)  # 避免CPU占用过高
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.communicator.stop()
            logger.info("NodeGraph Parser Process stopped")

def main():
    """主函数"""
    import multiprocessing
    from process_communication import create_process_queues, QueueCommunicator
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建通信队列
    queues = create_process_queues()
    parser_queues = queues['parser']
    
    # 创建通信器
    communicator = QueueCommunicator(
        'parser',
        parser_queues['input'],
        parser_queues['outputs']
    )
    
    # 创建并运行解析器进程
    scripts_folder = "TunnelNX_scripts"
    parser_process = NodeGraphParserProcess(scripts_folder, communicator)
    parser_process.run()

if __name__ == "__main__":
    main()
