#
#constant
#提供一个数值常量
#7FFFAA
import numpy as np

def get_params():
    """定义节点参数"""
    return {
        'value': {
            'type': 'text',
            'label': '数值',
            'value': '1.0'
        }
    }

def process(inputs, params):
    """
    处理常量节点，创建一个1x1像素的f32bmp图像，填充用户指定的常量值
    """
    try:
        # 正确获取参数值
        value_str = params.get('value', '1.0')
        # 尝试转换为浮点数
        value = float(value_str)
        
        # 创建1x1像素的RGBA图像
        constant_pixel = np.zeros((1, 1, 4), dtype=np.float32)
        constant_pixel[0, 0, 0] = value  # R
        constant_pixel[0, 0, 1] = value  # G
        constant_pixel[0, 0, 2] = value  # B
        constant_pixel[0, 0, 3] = 1.0    # Alpha (完全不透明)
        
        # 注意这里的键名应该是constant而不是Constant
        return {'constant': constant_pixel}
    except Exception as e:
        print(f"常量节点处理出错: {str(e)}")
        # 错误情况下返回默认值(1.0)
        default_pixel = np.zeros((1, 1, 4), dtype=np.float32)
        default_pixel[0, 0, :3] = 1.0  # RGB
        default_pixel[0, 0, 3] = 1.0   # Alpha
        return {'constant': default_pixel}