# channelR,channelG,channelB,channelA
# f32bmp
# RGBA 通道合成：从四路输入图像分别提取 R/G/B/A 通道并合成一张 RGBA 图像
# FF9933

import numpy as np

def process(inputs, params):
    """
    Legacy 脚本接口：接收 inputs(dict)、params(dict)，返回 outputs(dict)。
    将四路输入图像分别映射到 R/G/B/A 通道，输出一张 4 通道浮点图像。
    """
    # 获取输入元数据
    input_metadata = inputs.get('_metadata', {})

    # 1. 获取并检查输入
    im_r = inputs.get('channelR')
    im_g = inputs.get('channelG')
    im_b = inputs.get('channelB')
    im_a = inputs.get('channelA')
    if im_r is None or im_g is None or im_b is None or im_a is None:
        print("Error: 需要四路输入")
        return {}
    # 类型检查
    for name, im in [('channelR', im_r), ('channelG', im_g), ('channelB', im_b), ('channelA', im_a)]:
        if not isinstance(im, np.ndarray):
            print(f"Error: 输入 {name} 不是 NumPy 数组，而是 {type(im)}。")
            return {}
    # 尺寸一致性检查
    h, w = im_r.shape[:2]
    for name, im in [('channelG', im_g), ('channelB', im_b), ('channelA', im_a)]:
        if im.shape[0] != h or im.shape[1] != w:
            print(f"Error: 输入 {name} 的尺寸 {im.shape[:2]} 与 f32bmp 的尺寸 {(h, w)} 不一致。")
            return {}

    # 2. 创建输出图像
    out = np.zeros((h, w, 4), dtype=np.float32)

    # 辅助：提取单通道灰度
    def extract_channel(im):
        if im.ndim == 2:
            return im
        else:
            return im[..., 0]

    out[..., 0] = extract_channel(im_r)  # R
    out[..., 1] = extract_channel(im_g)  # G
    out[..., 2] = extract_channel(im_b)  # B
    out[..., 3] = extract_channel(im_a)  # A

    # 创建输出元数据
    output_metadata = input_metadata.copy() if input_metadata else {}
    output_metadata.update({
        'channels': 4,
        'format': 'RGBA',
        'width': w,
        'height': h,
        'operation': 'channel_composition'
    })

    # 3. 返回输出，键名必须与头部第2行一致
    return {
        'f32bmp': out,
        '_metadata': output_metadata
    }