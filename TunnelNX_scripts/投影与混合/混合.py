# f32bmp, f32bmp
# f32bmp
# 混合两幅图像与多种混合模式
# 5DA5DA
import cv2
import numpy as np


def process(inputs, params):
    """处理混合节点的输入 - 改进的输入处理"""
    # 检查我们是否有第一个输入
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("混合节点缺少主输入")
        return {'f32bmp': None}

    # 获取主输入图像
    img1 = inputs['f32bmp'].copy()
    
    # 安全检查 - 确保img1是有效的numpy数组
    if not isinstance(img1, np.ndarray):
        print("主输入不是有效的图像")
        return {'f32bmp': None}
        
    # 检查图像是否为空或损坏
    if img1.size == 0 or (len(img1.shape) < 2):
        print("主输入图像无效或为空")
        return {'f32bmp': None}

    # 寻找第二个输入 - 尝试多种可能的键名
    img2 = None
    for key in inputs:
        # 跳过主输入
        if key == 'f32bmp':
            continue

        # 检查键是否符合f32bmp_N的模式或直接是第二个f32bmp
        if key.startswith('f32bmp_') or key == 'f32bmp_1' or key == 'f32bmp_2':
            img2 = inputs[key].copy()
            print(f"找到第二输入: {key}")
            break

    # 如果没有找到第二个输入，返回第一个输入
    if img2 is None:
        print("混合节点缺少第二输入")
        return {'f32bmp': img1}
        
    # 安全检查 - 确保img2是有效的numpy数组
    if not isinstance(img2, np.ndarray):
        print("第二输入不是有效的图像")
        return {'f32bmp': img1}
        
    # 检查图像是否为空或损坏
    if img2.size == 0 or (len(img2.shape) < 2):
        print("第二输入图像无效或为空")
        return {'f32bmp': img1}

    print(f"混合节点输入形状: img1={img1.shape}, img2={img2.shape}")
    
    # 提取Alpha通道（如果存在）
    has_alpha1 = len(img1.shape) == 3 and img1.shape[2] == 4
    has_alpha2 = len(img2.shape) == 3 and img2.shape[2] == 4
    
    alpha1 = None
    alpha2 = None
    
    if has_alpha1:
        alpha1 = img1[:, :, 3].copy()
    if has_alpha2:
        alpha2 = img2[:, :, 3].copy()

    # 处理图像形状和通道不匹配的情况
    if img1.shape != img2.shape:
        # 处理通道数不同的情况
        if len(img1.shape) != len(img2.shape):
            # 单通道与多通道的转换
            if len(img1.shape) == 2 and len(img2.shape) == 3:
                if img2.shape[2] == 4:  # RGBA
                    img1 = np.stack([img1, img1, img1, np.ones_like(img1)], axis=2)
                else:  # RGB
                    img1 = np.stack([img1] * img2.shape[2], axis=2)
            elif len(img1.shape) == 3 and len(img2.shape) == 2:
                if img1.shape[2] == 4:  # RGBA
                    img2 = np.stack([img2, img2, img2, np.ones_like(img2)], axis=2)
                else:  # RGB
                    img2 = np.stack([img2] * img1.shape[2], axis=2)
        elif len(img1.shape) == 3 and len(img2.shape) == 3:
            # 处理通道数不同 - RGBA与RGB情况
            if img1.shape[2] == 3 and img2.shape[2] == 4:
                # 将img1从RGB转为RGBA
                alpha_channel = np.ones((img1.shape[0], img1.shape[1]), dtype=img1.dtype)
                img1 = np.dstack((img1, alpha_channel))
            elif img1.shape[2] == 4 and img2.shape[2] == 3:
                # 将img2从RGB转为RGBA
                alpha_channel = np.ones((img2.shape[0], img2.shape[1]), dtype=img2.dtype)
                img2 = np.dstack((img2, alpha_channel))

        # 调整尺寸至最大宽高
        max_height = max(img1.shape[0], img2.shape[0])
        max_width = max(img1.shape[1], img2.shape[1])

        # 调整img1尺寸
        h, w = img1.shape[0], img1.shape[1]
        pad_vert = max_height - h
        pad_top = pad_vert // 2
        pad_bottom = pad_vert - pad_top
        pad_horz = max_width - w
        pad_left = pad_horz // 2
        pad_right = pad_horz - pad_left
        if len(img1.shape) == 3:
            padding = ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0))
        else:
            padding = ((pad_top, pad_bottom), (pad_left, pad_right))
        img1 = np.pad(img1, padding, mode='constant', constant_values=0)

        # 调整img2尺寸
        h, w = img2.shape[0], img2.shape[1]
        pad_vert = max_height - h
        pad_top = pad_vert // 2
        pad_bottom = pad_vert - pad_top
        pad_horz = max_width - w
        pad_left = pad_horz // 2
        pad_right = pad_horz - pad_left
        if len(img2.shape) == 3:
            padding = ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0))
        else:
            padding = ((pad_top, pad_bottom), (pad_left, pad_right))
        img2 = np.pad(img2, padding, mode='constant', constant_values=0)

    # 获取参数
    blend_mode = params.get('blend_mode', 'normal')
    opacity1 = params.get('opacity1', 100) / 100.0
    opacity2 = params.get('opacity2', 100) / 100.0
    swap_order = params.get('swap_order', False)
    respect_alpha = params.get('respect_alpha', True)

    # 如果交换顺序，则交换图像
    if swap_order:
        img1, img2 = img2, img1
        opacity1, opacity2 = opacity2, opacity1

    # 确保图像为float32类型进行处理
    img1 = img1.astype(np.float32)
    img2 = img2.astype(np.float32)
    
    # 检查是否需要考虑Alpha通道进行混合
    if respect_alpha:
        # 从RGBA图像中提取Alpha通道（如果存在）
        if len(img1.shape) == 3 and img1.shape[2] == 4:
            alpha1 = img1[:, :, 3]
            opacity1_map = alpha1 * opacity1
        else:
            opacity1_map = np.ones(img1.shape[:2], dtype=np.float32) * opacity1
        
        if len(img2.shape) == 3 and img2.shape[2] == 4:
            alpha2 = img2[:, :, 3]
            opacity2_map = alpha2 * opacity2
        else:
            opacity2_map = np.ones(img2.shape[:2], dtype=np.float32) * opacity2
    else:
        # 不考虑Alpha通道，直接使用透明度参数
        opacity1_map = np.ones(img1.shape[:2], dtype=np.float32) * opacity1
        opacity2_map = np.ones(img2.shape[:2], dtype=np.float32) * opacity2

    # 应用不同的混合模式
    try:
        # 分离RGB和Alpha通道
        if len(img1.shape) == 3 and img1.shape[2] == 4:
            rgb1 = img1[:, :, :3]
            alpha1 = img1[:, :, 3]
        else:
            rgb1 = img1
            alpha1 = np.ones(img1.shape[:2], dtype=np.float32)
            
        if len(img2.shape) == 3 and img2.shape[2] == 4:
            rgb2 = img2[:, :, :3]
            alpha2 = img2[:, :, 3]
        else:
            rgb2 = img2
            alpha2 = np.ones(img2.shape[:2], dtype=np.float32)
        
        # 混合RGB通道
        if blend_mode == 'normal':
            rgb_result = blend_normal(rgb1, rgb2, opacity1_map, opacity2_map)
        elif blend_mode == 'add':
            rgb_result = blend_add(rgb1, rgb2, opacity1_map, opacity2_map)
        elif blend_mode == 'multiply':
            rgb_result = blend_multiply(rgb1, rgb2, opacity1_map, opacity2_map)
        elif blend_mode == 'screen':
            rgb_result = blend_screen(rgb1, rgb2, opacity1_map, opacity2_map)
        elif blend_mode == 'overlay':
            rgb_result = blend_overlay(rgb1, rgb2, opacity1_map, opacity2_map)
        elif blend_mode == 'difference':
            rgb_result = blend_difference(rgb1, rgb2, opacity1_map, opacity2_map)
        else:
            # 默认使用普通混合
            rgb_result = blend_normal(rgb1, rgb2, opacity1_map, opacity2_map)
            
        # 混合Alpha通道（普通模式）
        if len(alpha1.shape) == 2:
            alpha1 = alpha1.reshape(*alpha1.shape, 1)
        if len(alpha2.shape) == 2:
            alpha2 = alpha2.reshape(*alpha2.shape, 1)
            
        # 创建opacity1_alpha和opacity2_alpha以匹配维度
        if isinstance(opacity1, float):
            opacity1_alpha = np.ones_like(alpha1) * opacity1
        else:
            opacity1_alpha = opacity1.reshape(*opacity1.shape, 1) if len(opacity1.shape) == 2 else opacity1
            
        if isinstance(opacity2, float):
            opacity2_alpha = np.ones_like(alpha2) * opacity2
        else:
            opacity2_alpha = opacity2.reshape(*opacity2.shape, 1) if len(opacity2.shape) == 2 else opacity2
            
        # 使用blend_normal混合alpha通道
        alpha_result = blend_normal(alpha1, alpha2, opacity1_alpha, opacity2_alpha)
        
        # 将RGB和Alpha通道合并
        result = np.zeros((*rgb_result.shape[:2], 4), dtype=np.float32)
        result[:, :, :3] = rgb_result
        
        # 确保alpha_result是二维的
        if len(alpha_result.shape) == 3:
            alpha_result = alpha_result.reshape(alpha_result.shape[:2])
        
        result[:, :, 3] = alpha_result

        # 确保结果在float32的有效范围内（0.0-1.0）
        result = np.clip(result, 0.0, 1.0).astype(np.float32)

    except Exception as e:
        print(f"混合过程中出错: {str(e)}")
        # 出错时返回第一张图像
        return {'f32bmp': img1}

    return {'f32bmp': result}


def get_params():
    return {
        'blend_mode': {
            'type': 'dropdown',
            'label': '混合模式',
            'value': 'normal',
            'options': ['normal', 'add', 'multiply', 'screen', 'overlay', 'difference']
        },
        'opacity1': {
            'type': 'slider',
            'label': '图像1透明度',
            'min': 0,
            'max': 100,
            'value': 100
        },
        'opacity2': {
            'type': 'slider',
            'label': '图像2透明度',
            'min': 0,
            'max': 100,
            'value': 100
        },
        'swap_order': {
            'type': 'checkbox',
            'label': '交换图像顺序',
            'value': False
        },
        'respect_alpha': {
            'type': 'checkbox',
            'label': '尊重Alpha通道',
            'value': True
        }
    }


# 各种混合模式的实现 - 针对0.0-1.0范围的浮点图像
def blend_normal(img1, img2, opacity1, opacity2):
    # 扩展opacity维度以匹配图像维度
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
    
    # 修复混合公式：先对两个图像应用各自的透明度，然后正确混合
    return img1 * opacity1 + img2 * opacity2 * (1.0 - opacity1)


def blend_add(img1, img2, opacity1, opacity2):
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
        
    # 修复加法混合，考虑透明度关系
    return img1 * opacity1 + img2 * opacity2 * (1.0 - opacity1) + img1 * opacity1 * img2 * opacity2


def blend_multiply(img1, img2, opacity1, opacity2):
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
        
    # 修复乘法混合，考虑透明度关系
    multiplied = img1 * img2
    return img1 * opacity1 * (1.0 - opacity2) + img2 * opacity2 * (1.0 - opacity1) + multiplied * opacity1 * opacity2


def blend_screen(img1, img2, opacity1, opacity2):
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
        
    return 1.0 - ((1.0 - img1 * opacity1) * (1.0 - img2 * opacity2))


def blend_overlay(img1, img2, opacity1, opacity2):
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
    
    mask = img1 < 0.5
    result = np.zeros_like(img1)

    # 暗部区域使用乘法混合
    result[mask] = (2 * img1[mask] * img2[mask])

    # 亮部区域使用屏幕混合
    inv_mask = ~mask
    result[inv_mask] = 1.0 - (2 * (1.0 - img1[inv_mask]) * (1.0 - img2[inv_mask]))

    # 应用透明度
    return img1 * (1 - opacity2) + result * opacity2


def blend_difference(img1, img2, opacity1, opacity2):
    if len(img1.shape) == 3 and len(opacity1.shape) == 2:
        opacity1 = np.expand_dims(opacity1, axis=2)
    if len(img2.shape) == 3 and len(opacity2.shape) == 2:
        opacity2 = np.expand_dims(opacity2, axis=2)
        
    return np.abs(img1 * opacity1 - img2 * opacity2)


# 添加子操作以预设一些常用混合模式
def sub_set_multiply():
    # 将混合模式预设为乘法模式
    return {'blend_mode': 'multiply', 'opacity1': 100, 'opacity2': 100}
