# f32bmp
# f32bmp
# 像素取反：对输入图像进行像素取反操作，保留原始Alpha通道
# FF00FF

import numpy as np

def process(inputs, params):
    """
    Legacy 脚本接口：接收 inputs(dict)、params(dict)，返回 outputs(dict)。
    将输入图像的RGB通道像素值取反，保留Alpha通道。
    """
    im = inputs.get('f32bmp')
    if im is None:
        print("Error: 需要 f32bmp 输入")
        return {}
    if not isinstance(im, np.ndarray):
        print(f"Error: 输入不是 NumPy 数组，而是 {type(im)}.")
        return {}
    # 如果是 RGBA 四通道
    if im.ndim == 3 and im.shape[2] == 4:
        # 只对 RGB 通道取反，Alpha 通道保持不变
        out = np.empty_like(im)
        out[..., :3] = 1.0 - im[..., :3]
        out[..., 3]  = im[..., 3]
    else:
        # 其他通道数（如 RGB 或灰度），对所有通道取反
        out = 1.0 - im
    return {'f32bmp': out}