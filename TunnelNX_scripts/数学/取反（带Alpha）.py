# f32bmp
# f32bmp
# 像素取反：对输入图像进行像素取反操作
# FF00FF

import numpy as np

def process(inputs, params):
    """
    Legacy 脚本接口：接收 inputs(dict)、params(dict)，返回 outputs(dict)。
    将输入图像的像素值取反，假设像素值在 [0,1] 范围内。
    """
    im = inputs.get('f32bmp')
    if im is None:
        print("Error: 需要 f32bmp 输入")
        return {}
    if not isinstance(im, np.ndarray):
        print(f"Error: 输入不是 NumPy 数组，而是 {type(im)}.")
        return {}
    # 对像素取反
    out = 1.0 - im
    return {'f32bmp': out}