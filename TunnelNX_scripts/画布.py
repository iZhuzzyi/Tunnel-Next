# 
# f32bmp
# 创建指定大小的空白透明画布
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
        }
    }

def process(inputs, params):
    # 获取画布大小参数
    width = int(params.get('width', 512))
    height = int(params.get('height', 512))
    
    # 确保宽高至少为1像素
    width = max(1, width)
    height = max(1, height)
    
    # 创建一个空白且透明的RGBA图像
    # RGBA格式，R,G,B,A四个通道，值范围[0.0, 1.0]
    canvas = np.zeros((height, width, 4), dtype=np.float32)
    
    # Alpha通道设置为0（完全透明）
    # RGB已经是0，表示黑色
    # canvas[:, :, 3] = 0.0  # 这行可以省略，因为np.zeros已经初始化为0
    
    # 返回f32bmp格式的图像
    return {'f32bmp': canvas}