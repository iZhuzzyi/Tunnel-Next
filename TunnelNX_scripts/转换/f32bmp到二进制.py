#f32bmp
#bin
#将32位浮点图像转换为二进制数据（支持错误反馈）
#FF00FF
import numpy as np

def process(inputs, params):
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("错误：无输入图像")
        return {'bin': None}
    
    img = inputs['f32bmp']
    
    # 验证图像类型
    if not isinstance(img, np.ndarray) or img.dtype != np.float32:
        print("错误：输入必须是float32 numpy数组")
        return {'bin': None}
    
    # 处理通道选择
    export_channels = params.get('export_channels', 'all')
    
    if export_channels == 'rgb' and len(img.shape) == 3 and img.shape[2] == 4:
        # 仅导出RGB通道
        img = img[:, :, :3]
    elif export_channels == 'alpha' and len(img.shape) == 3 and img.shape[2] == 4:
        # 仅导出Alpha通道
        img = img[:, :, 3]
    # 'all'选项使用全部通道，不需要额外处理
    
    try:
        binary_data = img.tobytes()
    except Exception as e:
        print(f"二进制转换失败: {str(e)}")
        return {'bin': None}
    
    # 自动保存（如果路径有效）
    output_path = params.get('output_path', '')
    if output_path:
        try:
            with open(output_path, 'wb') as f:
                f.write(binary_data)
        except Exception as e:
            print(f"文件保存失败: {str(e)}")
    
    return {'bin': binary_data}

def get_params():
    return {
        'output_path': {'type': 'path', 'label': '输出文件路径', 'value': ''},
        'auto_save': {'type': 'checkbox', 'label': '自动保存', 'value': True},
        'export_channels': {
            'type': 'dropdown', 
            'label': '导出通道', 
            'value': 'all',
            'options': ['all', 'rgb', 'alpha']
        }
    }

def sub_export(params, inputs, context):
    """手动保存到文件"""
    output_path = params.get('output_path', '')
    if not output_path:
        return {'success': False, 'error': '未指定输出路径'}
    
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        return {'success': False, 'error': '无输入图像'}
    
    try:
        img = inputs['f32bmp']
        
        # 处理通道选择
        export_channels = params.get('export_channels', 'all')
        
        if export_channels == 'rgb' and len(img.shape) == 3 and img.shape[2] == 4:
            # 仅导出RGB通道
            img = img[:, :, :3]
        elif export_channels == 'alpha' and len(img.shape) == 3 and img.shape[2] == 4:
            # 仅导出Alpha通道
            img = img[:, :, 3]
            
        binary_data = img.tobytes()
        with open(output_path, 'wb') as f:
            f.write(binary_data)
            
        # 提供有关导出的详细信息
        if len(img.shape) == 3:
            channels = img.shape[2]
        else:
            channels = 1
            
        height, width = img.shape[:2]
        size_bytes = len(binary_data)
        message = f'文件已保存至 {output_path}\n尺寸：{width}x{height}，通道数：{channels}\n文件大小：{size_bytes} 字节'
        
        return {'success': True, 'message': message}
    except Exception as e:
        return {'success': False, 'error': f'保存失败: {str(e)}'}
