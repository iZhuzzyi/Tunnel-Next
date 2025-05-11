#bin
#f32bmp
#从二进制文件转换为32位浮点图像（支持自动尺寸检测）
#FF00FF
import numpy as np
import math

def process(inputs, params):
    # 从参数获取文件路径
    file_path = params.get('file_path', '')
    if not file_path:
        return {'f32bmp': None}
    
    # 读取二进制数据
    try:
        with open(file_path, 'rb') as f:
            binary_data = f.read()
    except Exception as e:
        print(f"文件读取失败: {str(e)}")
        return {'f32bmp': None}
    
    # 计算总字节数
    total_bytes = len(binary_data)
    if total_bytes % 4 != 0:  # 32位浮点数每个值占4字节
        print("错误：二进制数据长度必须是4的倍数（32位浮点数据）")
        return {'f32bmp': None}
    
    # 自动检测参数（如果未指定）
    auto_detect = params.get('auto_detect', False)
    if auto_detect:
        # 尝试常见通道数（1、3或4）
        possible_channels = [1, 3, 4]
        valid_params = []
        
        for channels in possible_channels:
            total_pixels = total_bytes // 4 // channels  # 32位浮点数每个值占4字节
            if total_pixels == 0:
                continue
            
            # 寻找接近正方形的尺寸
            sqrt_val = int(math.sqrt(total_pixels))
            for width in range(sqrt_val, 0, -1):
                if total_pixels % width == 0:
                    height = total_pixels // width
                    valid_params.append((width, height, channels))
                    break
            if valid_params:
                break
        
        if valid_params:
            # 选择第一个有效组合并更新参数
            width, height, channels = valid_params[0]
            params['width'] = width
            params['height'] = height
            params['channels'] = str(channels)
        else:
            print("错误：无法自动检测合理尺寸")
            return {'f32bmp': None}
    
    # 解析参数
    try:
        width = int(params.get('width', 0))
        height = int(params.get('height', 0))
        channels = int(params.get('channels', 1))
    except:
        print("参数格式错误")
        return {'f32bmp': None}
    
    # 验证数据长度
    expected_size = width * height * channels * 4  # 32位浮点数每个值占4字节
    if expected_size != total_bytes:
        print(f"数据不匹配: 需要{expected_size}字节，实际{total_bytes}字节")
        return {'f32bmp': None}
    
    # 转换为numpy数组
    try:
        img = np.frombuffer(binary_data, dtype=np.float32)
        if channels == 1:
            # 灰度图像转换为RGBA，创建具有完全不透明alpha通道的图像
            img_reshaped = img.reshape((height, width))
            rgba_img = np.zeros((height, width, 4), dtype=np.float32)
            rgba_img[:, :, 0] = img_reshaped  # R
            rgba_img[:, :, 1] = img_reshaped  # G
            rgba_img[:, :, 2] = img_reshaped  # B
            rgba_img[:, :, 3] = 1.0  # Alpha通道设为完全不透明
            return {'f32bmp': rgba_img}
        elif channels == 3:
            # RGB图像转换为RGBA，创建具有完全不透明alpha通道的图像
            rgb_img = img.reshape((height, width, channels))
            rgba_img = np.zeros((height, width, 4), dtype=np.float32)
            rgba_img[:, :, :3] = rgb_img  # RGB通道
            rgba_img[:, :, 3] = 1.0  # Alpha通道设为完全不透明
            return {'f32bmp': rgba_img}
        elif channels == 4:
            # 直接作为RGBA图像重新形状
            rgba_img = img.reshape((height, width, channels))
            return {'f32bmp': rgba_img}
        else:
            print(f"不支持的通道数: {channels}")
            return {'f32bmp': None}
    except Exception as e:
        print(f"数组转换失败: {str(e)}")
        return {'f32bmp': None}

def get_params():
    return {
        'file_path': {'type': 'path', 'label': '二进制文件路径', 'value': ''},
        'auto_detect': {'type': 'checkbox', 'label': '自动检测尺寸', 'value': True},
        'width': {'type': 'text', 'label': '宽度', 'value': '0'},
        'height': {'type': 'text', 'label': '高度', 'value': '0'},
        'channels': {
            'type': 'dropdown',
            'label': '通道数',
            'options': ['1', '3', '4'],
            'value': '1'
        }
    }

def sub_auto_detect(params, inputs, context):
    """自动检测合理尺寸"""
    file_path = params.get('file_path', '')
    if not file_path:
        return {'success': False, 'error': '未选择文件'}
    
    try:
        with open(file_path, 'rb') as f:
            binary_data = f.read()
    except Exception as e:
        return {'success': False, 'error': f'文件读取失败: {str(e)}'}
    
    total_bytes = len(binary_data)
    if total_bytes % 4 != 0:  # 32位浮点数每个值占4字节
        return {'success': False, 'error': '数据长度必须是4的倍数'}
    
    total_pixels = total_bytes // 4  # 32位浮点数每个值占4字节
    possible_combinations = []
    
    # 尝试常见宽高比（4:3, 16:9等）
    common_ratios = [(16,9), (4,3), (1,1)]
    for ratio in common_ratios:
        width = int(math.sqrt(total_pixels * ratio[0] / ratio[1]))
        height = int(width * ratio[1] / ratio[0])
        if width * height == total_pixels:
            possible_combinations.append((width, height, 1))
            break
    
    # 尝试通道数3
    if total_pixels % 3 == 0:
        total_pixels_3 = total_pixels // 3
        for ratio in common_ratios:
            width = int(math.sqrt(total_pixels_3 * ratio[0] / ratio[1]))
            height = int(width * ratio[1] / ratio[0])
            if width * height == total_pixels_3:
                possible_combinations.append((width, height, 3))
                break
    
    # 尝试通道数4
    if total_pixels % 4 == 0:
        total_pixels_4 = total_pixels // 4
        for ratio in common_ratios:
            width = int(math.sqrt(total_pixels_4 * ratio[0] / ratio[1]))
            height = int(width * ratio[1] / ratio[0])
            if width * height == total_pixels_4:
                possible_combinations.append((width, height, 4))
                break
    
    if not possible_combinations:
        return {'success': False, 'error': '无法自动检测尺寸'}
    
    # 选择最接近正方形的组合
    best_comb = min(possible_combinations, key=lambda x: abs(x[0]-x[1]))
    return {
        'success': True,
        'message': f'检测到尺寸: {best_comb[0]}x{best_comb[1]} 通道:{best_comb[2]}',
        'update_params': {
            'width': best_comb[0],
            'height': best_comb[1],
            'channels': str(best_comb[2]),
            'auto_detect': False
        }
    }
