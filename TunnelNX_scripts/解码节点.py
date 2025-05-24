# img
# f32bmp
# 解码图像为32位浮点BMP，支持透明度通道
# FFC0CB
#SupportedFeatures:PreviewOnNode=True
import cv2
import numpy as np


def process(inputs, params):
    if 'img' not in inputs:
        return {'f32bmp': None}

    img = inputs['img']
    if img is None:
        return {'f32bmp': None}

    # 处理Alpha通道
    if len(img.shape) == 3 and img.shape[2] == 4:
        # 带Alpha通道的彩色图像 (来自图像节点的是 BGRA)
        has_alpha = True
        # 先转换为 RGBA
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        color_img = img[:, :, :3]
        alpha_channel = img[:, :, 3]
    elif len(img.shape) == 3 and img.shape[2] == 3:
        # 彩色图像 (来自图像节点的是 RGB)
        has_alpha = False
        color_img = img # 已经是RGB了
        alpha_channel = None
    else:
        # 灰度图像（来自图像节点，只有1通道）
        has_alpha = False
        color_img = img # 稍后处理
        alpha_channel = None

    # 处理RAW图像 或 灰度图像
    if params.get('is_raw', False):
        # 确保图像是2D的（RAW图像）
        if len(color_img.shape) == 2:
            # 获取解拜尔方式
            bayer_pattern = params.get('bayer_pattern', 'RGGB')

            # 解拜尔
            if bayer_pattern == 'RGGB':
                color_img = cv2.cvtColor(color_img, cv2.COLOR_BAYER_RG2RGB)
            elif bayer_pattern == 'BGGR':
                color_img = cv2.cvtColor(color_img, cv2.COLOR_BAYER_BG2RGB)
            elif bayer_pattern == 'GRBG':
                color_img = cv2.cvtColor(color_img, cv2.COLOR_BAYER_GR2RGB)
            elif bayer_pattern == 'GBRG':
                color_img = cv2.cvtColor(color_img, cv2.COLOR_BAYER_GB2RGB)
    elif len(color_img.shape) == 2:
        # 普通灰度图像转换为RGB
        color_img = cv2.cvtColor(color_img, cv2.COLOR_GRAY2RGB)

    # 将图像转换为32位浮点格式，范围[0.0, 1.0]
    if color_img.dtype == np.uint8:
        # 8位图像 [0, 255] -> [0.0, 1.0]
        img_float = color_img.astype(np.float32) / 255.0
    elif color_img.dtype == np.uint16:
        # 16位图像 [0, 65535] -> [0.0, 1.0]
        img_float = color_img.astype(np.float32) / 65535.0
    else:
        # 确保值范围正确 [min, max] -> [0.0, 1.0]
        img_min = np.min(color_img)
        img_max = np.max(color_img)

        if img_max > img_min:
            img_float = (color_img.astype(np.float32) - img_min) / (img_max - img_min)
        else:
            img_float = np.zeros_like(color_img, dtype=np.float32)

    # 处理Alpha通道
    if has_alpha:
        # 如果有Alpha通道，进行转换
        if alpha_channel.dtype == np.uint8:
            # 8位Alpha [0, 255] -> [0.0, 1.0]
            alpha_float = alpha_channel.astype(np.float32) / 255.0
        elif alpha_channel.dtype == np.uint16:
            # 16位Alpha [0, 65535] -> [0.0, 1.0]
            alpha_float = alpha_channel.astype(np.float32) / 65535.0
        else:
            # 确保值范围正确 [min, max] -> [0.0, 1.0]
            alpha_min = np.min(alpha_channel)
            alpha_max = np.max(alpha_channel)

            if alpha_max > alpha_min:
                alpha_float = (alpha_channel.astype(np.float32) - alpha_min) / (alpha_max - alpha_min)
            else:
                alpha_float = np.zeros_like(alpha_channel, dtype=np.float32)

        # 创建RGBA格式的f32bmp
        height, width = img_float.shape[:2]
        rgba_image = np.zeros((height, width, 4), dtype=np.float32)
        rgba_image[:, :, :3] = img_float
        rgba_image[:, :, 3] = alpha_float
        return {'f32bmp': rgba_image}
    else:
        # 如果没有Alpha通道，创建RGBA格式的f32bmp，Alpha通道设为1.0（完全不透明）
        height, width = img_float.shape[:2]
        rgba_image = np.zeros((height, width, 4), dtype=np.float32)
        rgba_image[:, :, :3] = img_float
        rgba_image[:, :, 3] = 1.0
        return {'f32bmp': rgba_image}


def get_params():
    return {
        'is_raw': {'type': 'checkbox', 'label': '是RAW图像', 'value': False},
        'bayer_pattern': {'type': 'dropdown', 'label': '拜尔模式', 'value': 'RGGB',
                          'options': ['RGGB', 'BGGR', 'GRBG', 'GBRG']}
    }
