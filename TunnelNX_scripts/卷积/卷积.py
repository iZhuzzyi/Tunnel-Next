# f32bmp,kernel
# f32bmp
# 卷积滤波
# FFFF00
import cv2
import numpy as np


def process(inputs, params):
    # 检查图像输入是否存在
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        return {'f32bmp': None}

    # 创建输入图像的副本以避免修改原始数据
    img = inputs['f32bmp'].copy()

    # 获取卷积参数
    border_type = params.get('border_type', 'reflect_101')
    intensity = params.get('intensity', 1.0)
    normalize = params.get('normalize', False)
    bias = params.get('bias', 0)

    try:
        # 确定卷积核 - 优先使用输入的kernel，如果没有则使用内部生成
        kernel = None

        if 'kernel' in inputs and inputs['kernel'] is not None:
            # 使用连接的核节点提供的卷积核
            kernel = inputs['kernel'].copy()
            # 确保kernel是float32类型并且形状正确
            if kernel.dtype != np.float32:
                kernel = kernel.astype(np.float32)
            print(f"使用外部卷积核: 形状={kernel.shape}, 类型={kernel.dtype}")
        else:
            # 没有外部核输入，使用参数定义的核
            kernel_type = params.get('kernel_type', 'custom')
            custom_kernel = params.get('custom_kernel', '0,0,0;0,1,0;0,0,0')

            # 创建卷积核
            if kernel_type == 'custom':
                # 解析自定义卷积核字符串
                try:
                    rows = custom_kernel.strip().split(';')
                    kernel_data = []
                    for row in rows:
                        kernel_data.append([float(x) for x in row.strip().split(',')])
                    kernel = np.array(kernel_data, dtype=np.float32)
                except Exception as e:
                    print(f"解析自定义卷积核出错: {str(e)}")
                    # 解析失败时使用默认单位核
                    kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)

            elif kernel_type == 'sharpen':
                # 锐化卷积核
                kernel = np.array([
                    [0, -1, 0],
                    [-1, 5, -1],
                    [0, -1, 0]
                ], dtype=np.float32)

            elif kernel_type == 'edge_detect':
                # 边缘检测卷积核 (Sobel)
                kernel = np.array([
                    [-1, 0, 1],
                    [-2, 0, 2],
                    [-1, 0, 1]
                ], dtype=np.float32)

            elif kernel_type == 'edge_enhance':
                # 边缘增强卷积核
                kernel = np.array([
                    [0, 0, 0],
                    [-1, 1, 0],
                    [0, 0, 0]
                ], dtype=np.float32)

            elif kernel_type == 'emboss':
                # 浮雕效果卷积核
                kernel = np.array([
                    [-2, -1, 0],
                    [-1, 1, 1],
                    [0, 1, 2]
                ], dtype=np.float32)

            elif kernel_type == 'blur':
                # 均值模糊核
                kernel = np.ones((3, 3), dtype=np.float32) / 9

            elif kernel_type == 'gaussian_blur':
                # 高斯模糊核
                kernel = np.array([
                    [1, 2, 1],
                    [2, 4, 2],
                    [1, 2, 1]
                ], dtype=np.float32) / 16

        # 对内部核应用强度因子
        if kernel is not None and 'kernel' not in inputs and intensity != 1.0:
            # 对于某些滤波器（如模糊），应该保持核的和为1
            if kernel_type in ['blur', 'gaussian_blur']:
                # 重新归一化核以保持和为1
                kernel_sum = np.sum(kernel)
                kernel = kernel * intensity
                new_sum = np.sum(kernel)
                if new_sum != 0:
                    kernel = kernel * (kernel_sum / new_sum)
            else:
                # 对于其他滤波器，直接应用强度
                kernel = kernel * intensity

        # 如果选择了归一化，对卷积核进行归一化处理
        if normalize and kernel is not None:
            kernel_sum = np.sum(kernel)
            if kernel_sum != 0:
                kernel = kernel / kernel_sum

        # 选择边界类型
        border_types = {
            'constant': cv2.BORDER_CONSTANT,
            'replicate': cv2.BORDER_REPLICATE,
            'reflect': cv2.BORDER_REFLECT,
            'reflect_101': cv2.BORDER_REFLECT_101,
            'isolated': cv2.BORDER_ISOLATED
        }
        # 注意：BORDER_WRAP 在filter2D中不支持
        # 注意：BORDER_TRANSPARENT 仅用于特定函数

        cv_border_type = border_types.get(border_type, cv2.BORDER_REFLECT_101)

        # 应用卷积处理
        if kernel is not None:
            # 打印调试信息
            print(f"应用卷积处理: 图像形状={img.shape}, 图像类型={img.dtype}, 卷积核形状={kernel.shape}")
            
            # 针对浮点图像处理，确保输出保持在0-1范围内
            if img.dtype == np.float32:
                # 检查图像维度是否为3D（彩色）
                if len(img.shape) == 3:
                    # 对彩色图像的每个通道分别应用卷积
                    result = np.zeros_like(img)
                    for channel in range(img.shape[2]):
                        channel_img = img[:, :, channel]
                        filtered_channel = cv2.filter2D(
                            channel_img,
                            -1,  # 保持原始深度
                            kernel,
                            borderType=cv_border_type,
                            delta=bias / 255.0  # 偏移值按比例缩放
                        )
                        result[:, :, channel] = filtered_channel
                    filtered_img = result
                else:
                    # 对灰度图像直接应用卷积
                    filtered_img = cv2.filter2D(
                        img,
                        -1,  # 保持原始深度
                        kernel,
                        borderType=cv_border_type,
                        delta=bias / 255.0  # 偏移值按比例缩放
                    )
                # 确保值在合法范围内（0-1对于float32图像）
                img = np.clip(filtered_img, 0, 1).astype(np.float32)
            else:
                filtered_img = cv2.filter2D(
                    img,
                    -1,  # 保持原始深度
                    kernel,
                    borderType=cv_border_type,
                    delta=bias  # 应用偏移值
                )
                # 根据数据类型进行裁剪
                if img.dtype == np.uint8:
                    img = np.clip(filtered_img, 0, 255).astype(np.uint8)
                elif img.dtype == np.uint16:
                    img = np.clip(filtered_img, 0, 65535).astype(np.uint16)
                else:
                    img = filtered_img  # 其他类型，保持不变

        # 返回处理后的图像
        return {'f32bmp': img}

    except Exception as e:
        print(f"卷积处理错误: {str(e)}")
        import traceback
        traceback.print_exc()
        # 出错时返回原始图像
        return {'f32bmp': inputs['f32bmp']}


def get_params():
    # 定义卷积参数配置
    return {
        # 以下参数仅在没有连接kernel输入时使用
        'kernel_type': {
            'type': 'dropdown',
            'label': '内置卷积核类型',
            'value': 'custom',
            'options': [
                'custom', 'sharpen', 'edge_detect',
                'edge_enhance', 'emboss',
                'blur', 'gaussian_blur'
            ]
        },
        'custom_kernel': {
            'type': 'text',
            'label': '自定义卷积核 (行;列)',
            'value': '0,0,0;0,1,0;0,0,0'
        },

        # 以下参数总是可用
        'intensity': {
            'type': 'slider',
            'label': '内置核强度',
            'min': 0.1,
            'max': 5.0,
            'value': 1.0,
            'step': 0.1
        },
        'normalize': {
            'type': 'checkbox',
            'label': '归一化卷积核',
            'value': False
        },
        'bias': {
            'type': 'slider',
            'label': '偏移值',
            'min': -1000,
            'max': 1000,
            'value': 0,
            'step': 1
        },
        'border_type': {
            'type': 'dropdown',
            'label': '边界处理',
            'value': 'reflect_101',
            'options': [
                'constant', 'replicate', 'reflect',
                'reflect_101', 'isolated'
            ]
        }
    }


# 预设卷积核子操作
def sub_preset_sharpen_strong():
    """应用强力锐化预设"""
    print("应用预设：强力锐化")
    # 注意：实际预设应用逻辑需要在主应用程序中实现
    # 这里只是一个触发器
    return True


def sub_preset_emboss():
    """应用浮雕效果预设"""
    print("应用预设：浮雕效果")
    return True


def sub_visualize_applied_kernel():
    """显示当前应用的卷积核"""
    print("显示当前应用的卷积核")
    return True