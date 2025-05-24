# f32bmp, f32bmp_mask
# f32bmp
# 将遮罩应用到输入图像上
# 8D2E92

import cv2
import numpy as np

def get_params():
    """返回节点参数"""
    return {
        'use_input_alpha': {
            'label': '使用输入的Alpha通道',
            'type': 'checkbox',
            'value': False
        },
        'invert_mask': {
            'label': '反转遮罩',
            'type': 'checkbox',
            'value': False
        },
        'mask_strength': {
            'label': '遮罩强度',
            'type': 'slider',
            'min': 0,
            'max': 1,
            'step': 0.01,
            'value': 1.0
        }
    }

def process(inputs, params):
    """处理函数，将遮罩应用到输入图像上"""
    # 获取输入图像
    input_image = inputs.get('f32bmp')
    
    if input_image is None:
        print("错误：缺少输入图像")
        return {'f32bmp': None}
        
    # 获取参数
    invert_mask = params.get('invert_mask', False)
    mask_strength = params.get('mask_strength', 1.0)
    use_input_alpha = params.get('use_input_alpha', False)
    
    # 确定要使用的遮罩
    mask = None
    
    # 1. 检查是否使用输入图像的Alpha通道作为遮罩
    if use_input_alpha and len(input_image.shape) == 3 and input_image.shape[2] == 4:
        # 使用输入图像的Alpha通道作为遮罩
        mask = input_image[:, :, 3].copy()
    # 2. 否则检查是否有外部遮罩输入
    elif 'f32bmp_mask' in inputs and inputs['f32bmp_mask'] is not None:
        mask_image = inputs['f32bmp_mask']
        
        # 判断mask_image是否是RGBA格式
        if len(mask_image.shape) == 3 and mask_image.shape[2] == 4:
            # 优先使用Alpha通道作为遮罩
            mask = mask_image[:, :, 3].copy()
        # 如果不是RGBA格式，将整个图像作为遮罩（如果是RGB，则转为灰度）
        elif len(mask_image.shape) == 3 and mask_image.shape[2] == 3:
            # 将RGB转换为灰度作为遮罩
            mask = cv2.cvtColor(mask_image, cv2.COLOR_RGB2GRAY)
        else:
            # 单通道图像，直接使用
            mask = mask_image.copy()
    
    # 如果没有找到有效的遮罩，返回原图
    if mask is None:
        print("错误：没有找到有效的遮罩")
        return {'f32bmp': input_image}
    
    # 确保mask是单通道的
    if len(mask.shape) > 2:
        mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
    
    # 确保mask和输入图像尺寸一致
    if mask.shape[:2] != input_image.shape[:2]:
        mask = cv2.resize(mask, (input_image.shape[1], input_image.shape[0]))
    
    # 如果反转遮罩
    if invert_mask:
        mask = 1.0 - mask
    
    # 调整遮罩强度
    if mask_strength < 1.0:
        mask = mask * mask_strength + (1.0 - mask_strength)
    
    # 创建输出图像（保持输入图像的通道数）
    if len(input_image.shape) == 3:
        # 处理RGBA图像
        output_image = np.zeros_like(input_image)
        if input_image.shape[2] == 4:
            # 为RGB通道应用遮罩
            mask_3d = np.expand_dims(mask, axis=2)
            output_image[:, :, :3] = input_image[:, :, :3] * mask_3d
            # 复制原始Alpha通道或将mask作为新的Alpha通道
            output_image[:, :, 3] = input_image[:, :, 3]
        else:
            # 普通RGB图像
            mask_3d = np.expand_dims(mask, axis=2)
            output_image = input_image * mask_3d
    else:
        # 灰度图像
        output_image = input_image * mask
    
    return {'f32bmp': output_image}

def sub_preview(params, inputs, context):
    """预览函数，允许在节点上直接查看效果"""
    outputs = process(inputs, params)
    return {'success': True, 'message': '预览已更新'}
