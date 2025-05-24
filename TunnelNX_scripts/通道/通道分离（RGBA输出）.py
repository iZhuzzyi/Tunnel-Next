# f32bmp
# channelR,channelG,channelB,channelA
# 通道分离器：将输入图像的每个通道分离到独立输出，拷贝到输出图像的 RGB 通道中，Alpha 恒为 1.0
# 33AAFF

import numpy as np

def process(inputs, params):
    """
    Legacy 脚本接口：接收 inputs(dict)、params(dict)，返回 outputs(dict)。
    本节点对输入图像的前四个通道分别生成灰度化输出，并将其复制到 RGB 三通道。
    """
    # 1. 获取并检查输入
    img = inputs.get('f32bmp')
    if img is None:
        print("Error: 未获取到输入 f32bmp。")
        return {}
    if not isinstance(img, np.ndarray):
        print(f"Error: 输入类型错误，期望 NumPy 数组，实际为 {type(img)}。")
        return {}
    if img.ndim != 3 or img.shape[2] < 4:
        print(f"Error: 输入图像通道数不足，期望至少4通道，实际形状 {img.shape}。")
        return {}

    h, w, _ = img.shape
    outputs = {}

    try:
        # 2. 对前4个通道分别生成输出
        for i in range(4):
            # 每次都新建一个数组，避免复用导致覆盖
            out = np.zeros((h, w, 4), dtype=np.float32)
            channel = img[..., i]
            out[..., 0] = channel  # R
            out[..., 1] = channel  # G
            out[..., 2] = channel  # B
            out[..., 3] = 1.0      # Alpha 恒为 1.0

            # 这里的 key 必须和头部第2行注释一一对应
            key = 'f32bmp' if i == 0 else f'f32bmp_{i}'
            outputs[key] = out

    except Exception as e:
        print(f"Error during channel separation: {e}")
        import traceback; traceback.print_exc()
        return {}

    # 3. 返回所有输出
    return outputs