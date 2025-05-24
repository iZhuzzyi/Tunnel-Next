# f32bmp
# f32bmp
# 预览图像
# 87CEEB
import numpy as np


def process(inputs, params):
    if 'f32bmp' not in inputs:
        return {'f32bmp': None}

    # 直接传递图像用于预览
    # 预览逻辑在主程序中
    return {'f32bmp': inputs['f32bmp']}


def get_params():
    # 没有参数
    return {}