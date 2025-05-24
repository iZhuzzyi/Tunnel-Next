# 
# f32bmp
# 创建指定大小和颜色的画布
# 2E8B57
import numpy as np

def get_params():
    """定义节点参数"""
    return {
        'width': {
            'type': 'text',
            'label': '宽度',
            'value': '512'
        },
        'height': {
            'type': 'text',
            'label': '高度',
            'value': '512'
        },
        'color_r': {
            'type': 'slider',
            'label': '红色',
            'min': 0,
            'max': 255,
            'value': 0
        },
        'color_g': {
            'type': 'slider',
            'label': '绿色',
            'min': 0,
            'max': 255,
            'value': 0
        },
        'color_b': {
            'type': 'slider',
            'label': '蓝色',
            'min': 0,
            'max': 255,
            'value': 0
        },
        'alpha': {
            'type': 'slider',
            'label': '不透明度',
            'min': 0,
            'max': 255,
            'value': 255
        }
    }

def process(inputs, params):
    # 获取画布大小参数
    width = int(params.get('width', 512))
    height = int(params.get('height', 512))
    
    # 获取颜色参数（0-255）并转换到浮点数范围（0.0-1.0）
    r = float(params.get('color_r', 0)) / 255.0
    g = float(params.get('color_g', 0)) / 255.0
    b = float(params.get('color_b', 0)) / 255.0
    a = float(params.get('alpha', 255)) / 255.0
    
    # 确保宽高至少为1像素
    width = max(1, width)
    height = max(1, height)
    
    # 创建一个指定颜色和透明度的RGBA图像
    # RGBA格式，R,G,B,A四个通道，值范围[0.0, 1.0]
    canvas = np.zeros((height, width, 4), dtype=np.float32)
    
    # 设置颜色
    canvas[:, :, 0] = r  # 红色通道
    canvas[:, :, 1] = g  # 绿色通道
    canvas[:, :, 2] = b  # 蓝色通道
    canvas[:, :, 3] = a  # Alpha通道
    
    # 返回f32bmp格式的图像
    return {'f32bmp': canvas} 