#tif16
#bin
#将TIFF 16位图像转换为二进制数据（支持错误反馈）
#FF00FF
import numpy as np

def process(inputs, params):
    if 'tif16' not in inputs or inputs['tif16'] is None:
        print("错误：无输入图像")
        return {'bin': None}
    
    img = inputs['tif16']
    
    # 验证图像类型
    if not isinstance(img, np.ndarray) or img.dtype != np.uint16:
        print("错误：输入必须是uint16 numpy数组")
        return {'bin': None}
    
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
        'auto_save': {'type': 'checkbox', 'label': '自动保存', 'value': True}
    }

def sub_export(params, inputs, context):
    """手动保存到文件"""
    output_path = params.get('output_path', '')
    if not output_path:
        return {'success': False, 'error': '未指定输出路径'}
    
    if 'tif16' not in inputs or inputs['tif16'] is None:
        return {'success': False, 'error': '无输入图像'}
    
    try:
        binary_data = inputs['tif16'].tobytes()
        with open(output_path, 'wb') as f:
            f.write(binary_data)
        return {'success': True, 'message': f'文件已保存至 {output_path}'}
    except Exception as e:
        return {'success': False, 'error': f'保存失败: {str(e)}'}