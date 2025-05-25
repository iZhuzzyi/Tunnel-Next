# img
# f32bmp
# 解码图像为32位浮点BMP，支持透明度通道
# FFC0CB
#SupportedFeatures:PreviewOnNode=True
import cv2
import numpy as np
import os
from PIL import Image
from PIL.ExifTags import TAGS


def extract_image_metadata(image_path):
    """提取图像的色彩空间和伽马信息"""
    if not image_path or not os.path.exists(image_path):
        return "sRGB", 2.2  # 默认值

    try:
        # 尝试使用PIL读取EXIF信息
        with Image.open(image_path) as img:
            # 检查ICC配置文件
            if hasattr(img, 'info') and 'icc_profile' in img.info:
                # 有ICC配置文件，尝试解析
                icc_profile = img.info['icc_profile']
                if b'sRGB' in icc_profile:
                    return "sRGB", 2.2
                elif b'Adobe RGB' in icc_profile or b'AdobeRGB' in icc_profile:
                    return "Adobe RGB", 2.2
                elif b'ProPhoto' in icc_profile:
                    return "ProPhoto RGB", 1.8
                elif b'Display P3' in icc_profile or b'P3' in icc_profile:
                    return "Display P3", 2.2

            # 检查EXIF信息
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'ColorSpace':
                        if value == 1:
                            return "sRGB", 2.2
                        elif value == 2:
                            return "Adobe RGB", 2.2
                    elif tag == 'Gamma':
                        try:
                            gamma_value = float(value)
                            return "sRGB", gamma_value
                        except:
                            pass
    except Exception as e:
        print(f"[解码节点] 元数据提取警告: {e}")

    # 根据文件扩展名推测
    ext = os.path.splitext(image_path)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        return "sRGB", 2.2
    elif ext in ['.tif', '.tiff']:
        return "Adobe RGB", 2.2
    elif ext in ['.png']:
        return "sRGB", 2.2
    else:
        return "sRGB", 2.2  # 默认值


def process(inputs, params):
    print(f"[解码节点] === 开始处理 ===")
    print(f"[解码节点] 输入键: {list(inputs.keys())}")
    print(f"[解码节点] 参数: {params}")

    if 'img' not in inputs:
        print(f"[解码节点] 错误: 没有找到 'img' 输入")
        return {'f32bmp': None}

    img = inputs['img']
    if img is None:
        print(f"[解码节点] 错误: 图像数据为 None")
        return {'f32bmp': None}

    print(f"[解码节点] 图像形状: {img.shape if hasattr(img, 'shape') else 'N/A'}")
    print(f"[解码节点] 图像类型: {type(img)}")

    # 获取输入元数据
    input_metadata = inputs.get('_metadata', {})
    print(f"[解码节点] 输入元数据: {input_metadata}")

    # 获取图像路径（如果有的话）
    image_path = input_metadata.get('image_path', '')
    print(f"[解码节点] 图像路径: '{image_path}'")

    # 提取或使用用户设置的色彩空间和伽马
    detected_colorspace, detected_gamma = extract_image_metadata(image_path)
    print(f"[解码节点] 检测结果 - 色彩空间: {detected_colorspace}, 伽马: {detected_gamma}")

    # 获取用户设置的色彩空间和伽马，如果为空则使用检测到的值
    user_colorspace = params.get('colorspace_override', '').strip()
    user_gamma = params.get('gamma_override', '').strip()
    print(f"[解码节点] 用户重载 - 色彩空间: '{user_colorspace}', 伽马: '{user_gamma}'")

    final_colorspace = user_colorspace if user_colorspace else detected_colorspace
    try:
        final_gamma = float(user_gamma) if user_gamma else detected_gamma
    except ValueError:
        final_gamma = detected_gamma
        print(f"[解码节点] 警告: 伽马值转换失败，使用检测值: {detected_gamma}")

    print(f"[解码节点] 最终使用 - 色彩空间: {final_colorspace}, 伽马: {final_gamma}")

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

        # 创建输出元数据
        output_metadata = input_metadata.copy() if input_metadata else {}
        output_metadata.update({
            'colorspace': final_colorspace,
            'gamma': final_gamma,
            'detected_colorspace': detected_colorspace,
            'detected_gamma': detected_gamma,
            'has_alpha': True,
            'bit_depth': 32,
            'format': 'f32bmp',
            'width': width,
            'height': height
        })

        print(f"[解码节点] 输出元数据: {output_metadata}")
        print(f"[解码节点] 输出图像形状: {rgba_image.shape}")
        print(f"[解码节点] === 处理完成 ===")

        return {'f32bmp': rgba_image, '_metadata': output_metadata}
    else:
        # 如果没有Alpha通道，创建RGBA格式的f32bmp，Alpha通道设为1.0（完全不透明）
        height, width = img_float.shape[:2]
        rgba_image = np.zeros((height, width, 4), dtype=np.float32)
        rgba_image[:, :, :3] = img_float
        rgba_image[:, :, 3] = 1.0

        # 创建输出元数据
        output_metadata = input_metadata.copy() if input_metadata else {}
        output_metadata.update({
            'colorspace': final_colorspace,
            'gamma': final_gamma,
            'detected_colorspace': detected_colorspace,
            'detected_gamma': detected_gamma,
            'has_alpha': False,
            'bit_depth': 32,
            'format': 'f32bmp',
            'width': width,
            'height': height
        })

        print(f"[解码节点] 输出元数据: {output_metadata}")
        print(f"[解码节点] 输出图像形状: {rgba_image.shape}")
        print(f"[解码节点] === 处理完成 ===")

        return {'f32bmp': rgba_image, '_metadata': output_metadata}


def get_params():
    return {
        'is_raw': {'type': 'checkbox', 'label': '是RAW图像', 'value': False},
        'bayer_pattern': {'type': 'dropdown', 'label': '拜尔模式', 'value': 'RGGB',
                          'options': ['RGGB', 'BGGR', 'GRBG', 'GBRG']},
        'colorspace_override': {'type': 'text', 'label': '色彩空间重载', 'value': '',
                               'tooltip': '留空则自动检测。常用值：sRGB, Adobe RGB, ProPhoto RGB, Display P3'},
        'gamma_override': {'type': 'text', 'label': '伽马重载', 'value': '',
                          'tooltip': '留空则自动检测。常用值：2.2, 1.8, 2.4'}
    }
