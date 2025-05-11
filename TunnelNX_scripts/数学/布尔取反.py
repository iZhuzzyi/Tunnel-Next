# f32bmp
# f32bmp
# 布尔取反：先将输入图像转灰度并二值化 (>0→1, ≤0→0)，然后将 1→0、0→1
# AA33CC

import numpy as np

def process(inputs, params):
    """
    Legacy 脚本接口：接收 inputs(dict)、params(dict)，返回 outputs(dict)。
    1) 将多通道图像转为灰度
    2) 对灰度图做二值化 (>0→1, ≤0→0)
    3) 对二值结果取反 (1→0, 0→1)
    最终返回二维浮点数组，Preview 组件会当灰度图展示。
    """
    # 1. 获取并检查输入
    img = inputs.get('f32bmp')
    if img is None:
        print("Error: 未获取到输入 'f32bmp'")
        return {}
    if not isinstance(img, np.ndarray):
        print(f"Error: 输入类型错误，期望 NumPy 数组，实际为 {type(img)}")
        return {}

    # 2. 转灰度（忽略 alpha 通道）
    if img.ndim == 3 and img.shape[2] >= 3:
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        gray = 0.299 * r + 0.587 * g + 0.114 * b
    elif img.ndim == 2:
        gray = img
    else:
        # 少见情况：4 通道但只有 alpha 或其他通道
        gray = img[..., 0]  # 取第一个通道

    # 3. 二值化 (>0→1, ≤0→0)
    try:
        bin_mask = (gray > 0).astype(np.float32)
    except Exception as e:
        print(f"Error during binarization: {e}")
        return {}

    # 4. 取反 (1→0, 0→1)
    inv_mask = 1.0 - bin_mask

    # 5. 返回二维灰度图
    return {'f32bmp': inv_mask}