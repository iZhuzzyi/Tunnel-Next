# f32bmp
# f32bmp
# 改变图像分辨率并指定下变换算法 (Resize image resolution and specify downscaling algorithm)
# EEA500

import cv2
import numpy as np

def get_params():
    """S
    定义此节点的参数。
    """
    return {
        'scale_factor': {
            'type': 'slider',
            'label': '缩放比例',
            'min': 0.1,
            'max': 4.0,
            'step': 0.05, # <--- 修改了步长为 0.05
            'value': 1.0,
            'tooltip': '图像缩放比例 (小于1缩小, 大于1放大)'
        },
        'interpolation': {
            'type': 'dropdown',
            'label': '插值算法 (缩小)',
            'options': [
                'INTER_AREA', # 推荐用于缩小
                'INTER_LINEAR',
                'INTER_CUBIC',
                'INTER_NEAREST',
                'INTER_LANCZOS4'
            ],
            'value': 'INTER_AREA',
            'tooltip': '选择图像缩小时使用的插值算法 (INTER_AREA 通常效果最好)'
        }
    }

def process(inputs, params):
    """
    处理图像，根据参数进行缩放。
    """
    # 检查输入图像是否存在
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("缩放节点: 未接收到输入图像 (f32bmp)")
        return {} # 返回空字典表示没有有效输出

    # 获取输入图像和参数
    img_in = inputs['f32bmp']
    # 读取滑块值时确保类型正确
    try:
        scale_factor = float(params.get('scale_factor', 1.0))
    except (ValueError, TypeError):
        scale_factor = 1.0 # 如果转换失败，使用默认值
        print("缩放节点: 无法解析 scale_factor，使用默认值 1.0")

    interpolation_name = params.get('interpolation', 'INTER_AREA')

    # 将插值名称映射到 OpenCV 常量
    interpolation_methods = {
        'INTER_NEAREST': cv2.INTER_NEAREST,
        'INTER_LINEAR': cv2.INTER_LINEAR,
        'INTER_AREA': cv2.INTER_AREA,
        'INTER_CUBIC': cv2.INTER_CUBIC,
        'INTER_LANCZOS4': cv2.INTER_LANCZOS4
    }
    interpolation_cv = interpolation_methods.get(interpolation_name, cv2.INTER_AREA) # 默认 INTER_AREA

    # 获取原始尺寸
    height, width = img_in.shape[:2]

    # 计算新尺寸
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)

    # 确保新尺寸至少为 1x1 像素
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    # 选择插值算法
    # 如果放大，通常 INTER_LINEAR 或 INTER_CUBIC 更好
    if scale_factor > 1.0:
        # 如果用户没有明确选择其他放大算法，可以默认使用线性插值
        if interpolation_name == 'INTER_AREA' or interpolation_name == 'INTER_NEAREST':
             interpolation_cv = cv2.INTER_LINEAR
        # 如果用户选择了CUBIC或LANCZOS4，则使用用户的选择

    # 使用cv2.resize进行缩放
    try:
        # 注意：确保输入图像是连续的，有时resize会出问题
        if not img_in.flags['C_CONTIGUOUS']:
            img_in = np.ascontiguousarray(img_in)

        img_out = cv2.resize(img_in, (new_width, new_height), interpolation=interpolation_cv)

        # 如果原始图像是单通道，确保输出也是单通道 (cv2.resize有时会改变通道数)
        if len(img_in.shape) == 2 and len(img_out.shape) == 3:
            # 检查是否需要转换回 float32
            target_dtype = img_in.dtype
            img_out = cv2.cvtColor(img_out, cv2.COLOR_BGR2GRAY).astype(target_dtype, copy=False)

        elif len(img_in.shape) == 3 and len(img_out.shape) == 2:
             # 如果输入是彩色而输出变灰了（可能发生在尺寸极小时），尝试保持彩色
             # 这不太可能发生，但作为预防措施
             target_dtype = img_in.dtype
             if img_out.dtype == np.float32 or img_out.dtype == np.uint8: # 检查输出类型
                 img_out = cv2.cvtColor(img_out, cv2.COLOR_GRAY2BGR).astype(target_dtype, copy=False)


        print(f"缩放节点: 图像已从 {width}x{height} 缩放到 {new_width}x{new_height} 使用 {interpolation_name}")

        # 返回处理后的图像
        return {'f32bmp': img_out}

    except Exception as e:
        print(f"缩放节点处理时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return {} # 出错时返回空字典