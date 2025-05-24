# f32bmp
# f32bmp
# 基本图像处理
# 90EE90
#SupportedFeatures:PerfSensitive=True
import numpy as np


def rgb_to_hsv(r, g, b):
    """
    将RGB颜色空间转换为HSV颜色空间

    参数:
        r, g, b: 输入RGB值，范围[0, 1]

    返回:
        h, s, v: 输出HSV值，范围[0, 1]
    """
    r = np.clip(r, 0, 1)
    g = np.clip(g, 0, 1)
    b = np.clip(b, 0, 1)

    max_val = np.maximum(np.maximum(r, g), b)
    min_val = np.minimum(np.minimum(r, g), b)
    delta = max_val - min_val

    # 明度为最大分量
    v = max_val

    # 饱和度为最大值与最小值的差除以最大值（如果最大值不为0）
    s = np.zeros_like(max_val)
    non_zero = max_val > 0
    s[non_zero] = delta[non_zero] / max_val[non_zero]

    # 计算色调
    h = np.zeros_like(max_val)

    # 如果delta为0，色调为0
    non_zero_delta = delta > 0

    # 当max_val是r时，色调 = (g - b) / delta mod 6
    r_max = (max_val == r) & non_zero_delta
    h[r_max] = ((g[r_max] - b[r_max]) / delta[r_max]) % 6

    # 当max_val是g时，色调 = (b - r) / delta + 2
    g_max = (max_val == g) & non_zero_delta
    h[g_max] = ((b[g_max] - r[g_max]) / delta[g_max]) + 2

    # 当max_val是b时，色调 = (r - g) / delta + 4
    b_max = (max_val == b) & non_zero_delta
    h[b_max] = ((r[b_max] - g[b_max]) / delta[b_max]) + 4

    # 将色调转换为[0, 1]范围
    h = h / 6

    return h, s, v


def hsv_to_rgb(h, s, v):
    """
    将HSV颜色空间转换为RGB颜色空间

    参数:
        h, s, v: 输入HSV值，范围[0, 1]

    返回:
        r, g, b: 输出RGB值，范围[0, 1]
    """
    h = np.clip(h, 0, 1) * 6  # 缩放到[0, 6]
    s = np.clip(s, 0, 1)
    v = np.clip(v, 0, 1)

    i = np.floor(h).astype(np.int32)
    f = h - i  # 小数部分

    p = v * (1 - s)
    q = v * (1 - (s * f))
    t = v * (1 - (s * (1 - f)))

    r = np.zeros_like(h)
    g = np.zeros_like(h)
    b = np.zeros_like(h)

    i = i % 6

    # 情况i = 0: r = v, g = t, b = p
    mask = (i == 0)
    r[mask] = v[mask]
    g[mask] = t[mask]
    b[mask] = p[mask]

    # 情况i = 1: r = q, g = v, b = p
    mask = (i == 1)
    r[mask] = q[mask]
    g[mask] = v[mask]
    b[mask] = p[mask]

    # 情况i = 2: r = p, g = v, b = t
    mask = (i == 2)
    r[mask] = p[mask]
    g[mask] = v[mask]
    b[mask] = t[mask]

    # 情况i = 3: r = p, g = q, b = v
    mask = (i == 3)
    r[mask] = p[mask]
    g[mask] = q[mask]
    b[mask] = v[mask]

    # 情况i = 4: r = t, g = p, b = v
    mask = (i == 4)
    r[mask] = t[mask]
    g[mask] = p[mask]
    b[mask] = v[mask]

    # 情况i = 5: r = v, g = p, b = q
    mask = (i == 5)
    r[mask] = v[mask]
    g[mask] = p[mask]
    b[mask] = q[mask]

    return r, g, b


def process(inputs, params):
    """基本处理节点，优化大图像处理性能"""
    # 首先检查输入是否有效
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        return {'f32bmp': None}
        
    # 获取输入图像
    img_input = inputs['f32bmp']
    
    # 大图像优化: 检查图像大小，如果很大则启用分块处理
    use_tiling = (img_input.shape[0] * img_input.shape[1] > 2048 * 2048)
    
    # 判断是否为 RGBA 图像
    is_rgba = False
    alpha_channel = None
    if len(img_input.shape) == 3 and img_input.shape[2] == 4:
        is_rgba = True
        # 分离 Alpha 通道 (避免复制)
        alpha_channel = img_input[:, :, 3]
        # 处理 RGB 通道 (避免复制)
        img = img_input[:, :, :3]
    else:
        # 非 RGBA 图像 (避免复制)
        img = img_input
    
    # 获取参数
    brightness = params.get('brightness', 0)
    contrast = params.get('contrast', 0)
    saturation = params.get('saturation', 0)
    hue = params.get('hue', 0)
    wb_r = params.get('wb_r', 1.0)
    wb_g = params.get('wb_g', 1.0)
    wb_b = params.get('wb_b', 1.0)
    
    # 检查是否需要处理
    need_processing = (brightness != 0 or contrast != 0 or 
                      saturation != 0 or hue != 0 or 
                      wb_r != 1.0 or wb_g != 1.0 or wb_b != 1.0)
    
    if not need_processing:
        # 无需处理，直接返回原图
        return {'f32bmp': img_input}
    
    # 分块处理大图像
    if use_tiling:
        # 定义分块处理函数
        def process_tile(tile, params):
            # 应用基本参数处理
            result = tile.copy()
            
            # 亮度调整
            if brightness != 0:
                factor = 1 + brightness / 100
                result = result * factor
                
            # 对比度调整
            if contrast != 0:
                factor = (259 * (contrast + 255)) / (255 * (259 - contrast))
                midpoint = 0.5
                result = factor * (result - midpoint) + midpoint
            
            # 剪裁处理值域
            np.clip(result, 0, 1, out=result)
            
            return result
            
        # 对RGB通道分块处理
        tile_size = 1024  # 块大小
        h, w = img.shape[:2]
        result = np.zeros_like(img)
        
        for y in range(0, h, tile_size):
            y_end = min(y + tile_size, h)
            for x in range(0, w, tile_size):
                x_end = min(x + tile_size, w)
                
                # 提取块
                tile = img[y:y_end, x:x_end].copy()
                
                # 处理特定块
                if len(tile.shape) == 3:  # RGB图像
                    # 处理RGB基本参数
                    processed_tile = process_tile(tile, params)
                    
                    # 如果需要HSV处理
                    if saturation != 0 or hue != 0:
                        # RGB转HSV
                        r, g, b = processed_tile[:, :, 0], processed_tile[:, :, 1], processed_tile[:, :, 2]
                        h_val, s, v = rgb_to_hsv(r, g, b)
                        
                        # 应用饱和度调整
                        if saturation != 0:
                            s = s * (1 + saturation / 100)
                            
                        # 应用色调调整
                        if hue != 0:
                            h_val = (h_val + hue / 360) % 1.0
                        
                        # HSV转RGB
                        r, g, b = hsv_to_rgb(h_val, s, v)
                        processed_tile = np.stack([r, g, b], axis=2)
                    
                    # 应用白平衡 (向量化操作)
                    if wb_r != 1.0 or wb_g != 1.0 or wb_b != 1.0:
                        processed_tile[:, :, 0] *= wb_r
                        processed_tile[:, :, 1] *= wb_g
                        processed_tile[:, :, 2] *= wb_b
                        
                else:  # 灰度图像，较少的处理
                    processed_tile = process_tile(tile, params)
                
                # 合并结果
                result[y:y_end, x:x_end] = processed_tile
        
        # 重组最终输出
        if is_rgba:
            # 重新添加Alpha通道
            final_img = np.zeros(img_input.shape, dtype=np.float32)
            final_img[:, :, :3] = result
            final_img[:, :, 3] = alpha_channel
        else:
            final_img = result
            
    else:
        # 小图像直接处理
        result = img.copy()
        
        # 应用亮度调整
        if brightness != 0:
            factor = 1 + brightness / 100
            result = result * factor
        
        # 应用对比度调整
        if contrast != 0:
            factor = (259 * (contrast + 255)) / (255 * (259 - contrast))
            midpoint = 0.5
            result = factor * (result - midpoint) + midpoint
        
        # 如果是彩色图像且需要处理HSV参数
        if len(result.shape) == 3 and (saturation != 0 or hue != 0):
            # 分离RGB通道
            r, g, b = result[:, :, 0], result[:, :, 1], result[:, :, 2]
            
            # 转换RGB到HSV
            h, s, v = rgb_to_hsv(r, g, b)
            
            # 应用饱和度调整
            if saturation != 0:
                s = s * (1 + saturation / 100)
            
            # 应用色调调整
            if hue != 0:
                h = (h + hue / 360) % 1.0
            
            # 转换HSV回RGB
            r, g, b = hsv_to_rgb(h, s, v)
            result = np.stack([r, g, b], axis=2)
        
        # 应用白平衡
        if len(result.shape) == 3 and (wb_r != 1.0 or wb_g != 1.0 or wb_b != 1.0):
            result[:, :, 0] = result[:, :, 0] * wb_r
            result[:, :, 1] = result[:, :, 1] * wb_g
            result[:, :, 2] = result[:, :, 2] * wb_b
        
        # 统一剪裁处理后的数据
        np.clip(result, 0, 1, out=result)
        
        # 重组最终输出
        if is_rgba:
            # 重新添加Alpha通道
            final_img = np.zeros(img_input.shape, dtype=np.float32)
            final_img[:, :, :3] = result
            final_img[:, :, 3] = alpha_channel
        else:
            final_img = result
    
    # 确保最终输出是float32类型
    return {'f32bmp': final_img.astype(np.float32)}


def get_params():
    return {
        'brightness': {'type': 'slider', 'label': '亮度', 'min': -100, 'max': 100, 'value': 0},
        'contrast': {'type': 'slider', 'label': '对比度', 'min': -100, 'max': 100, 'value': 0},
        'saturation': {'type': 'slider', 'label': '饱和度', 'min': -100, 'max': 100, 'value': 0},
        'hue': {'type': 'slider', 'label': '色调', 'min': -180, 'max': 180, 'value': 0},
        'wb_r': {'type': 'slider', 'label': '白平衡 R', 'min': 0.5, 'max': 2.0, 'value': 1.0, 'step': 0.01},
        'wb_g': {'type': 'slider', 'label': '白平衡 G', 'min': 0.5, 'max': 2.0, 'value': 1.0, 'step': 0.01},
        'wb_b': {'type': 'slider', 'label': '白平衡 B', 'min': 0.5, 'max': 2.0, 'value': 1.0, 'step': 0.01}
    }