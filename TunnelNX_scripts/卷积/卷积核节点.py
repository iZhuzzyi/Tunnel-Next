#
# kernel
# 生成卷积核
# FF9900
import numpy as np


def process(inputs, params):
    # 生成卷积核并输出
    kernel_type = params.get('kernel_type', 'custom')
    intensity = params.get('intensity', 1.0)
    custom_kernel = params.get('custom_kernel', '0,0,0;0,1,0;0,0,0')
    size_str = params.get('size', '3')

    try:
        # 将size转换为整数
        size = int(size_str)

        # 确保size为奇数
        if size % 2 == 0:
            size += 1

        # 打印调试信息
        print(f"生成卷积核: 类型={kernel_type}, 大小={size}, 强度={intensity}")
            
        # 创建卷积核
        kernel = None

        if kernel_type == 'custom':
            # 解析自定义卷积核字符串
            # 格式：以分号分隔行，以逗号分隔列，例如: "1,0,-1;2,0,-2;1,0,-1"
            try:
                rows = custom_kernel.strip().split(';')
                kernel_data = []
                for row in rows:
                    kernel_data.append([float(x) for x in row.strip().split(',')])
                kernel = np.array(kernel_data, dtype=np.float32)
                # 如果自定义核的形状不符合预期，重新调整大小或使用默认核
                if kernel.shape[0] != kernel.shape[1] or kernel.shape[0] % 2 == 0:
                    print(f"警告：自定义卷积核形状不规则 {kernel.shape}，使用默认单位核")
                    kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)
            except Exception as e:
                print(f"解析自定义卷积核出错: {str(e)}")
                # 解析失败时使用默认单位核
                kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)

        elif kernel_type == 'sharpen':
            # 基本锐化核
            if size == 3:
                kernel = np.array([
                    [0, -1, 0],
                    [-1, 5, -1],
                    [0, -1, 0]
                ], dtype=np.float32)
            else:
                # 对于更大尺寸，生成扩展的锐化核
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                for i in range(size):
                    for j in range(size):
                        dist = abs(i - center) + abs(j - center)
                        if i == center and j == center:
                            kernel[i, j] = 1.0 + 4.0 * (size // 2)
                        elif dist <= size // 2:
                            kernel[i, j] = -1.0

        elif kernel_type == 'edge_detect':
            # 边缘检测核 (Sobel X)
            if size == 3:
                kernel = np.array([
                    [-1, 0, 1],
                    [-2, 0, 2],
                    [-1, 0, 1]
                ], dtype=np.float32)
            else:
                # 扩展的Sobel边缘检测
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                for i in range(size):
                    for j in range(size):
                        if j < center:
                            kernel[i, j] = -1.0 - (center - j)
                        elif j > center:
                            kernel[i, j] = 1.0 + (j - center)

        elif kernel_type == 'edge_detect_y':
            # 垂直边缘检测核 (Sobel Y)
            if size == 3:
                kernel = np.array([
                    [-1, -2, -1],
                    [0, 0, 0],
                    [1, 2, 1]
                ], dtype=np.float32)
            else:
                # 扩展的垂直Sobel
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                for i in range(size):
                    for j in range(size):
                        if i < center:
                            kernel[i, j] = -1.0 - (center - i)
                        elif i > center:
                            kernel[i, j] = 1.0 + (i - center)

        elif kernel_type == 'edge_enhance':
            # 边缘增强核
            if size == 3:
                kernel = np.array([
                    [0, 0, 0],
                    [-1, 1, 0],
                    [0, 0, 0]
                ], dtype=np.float32)
            else:
                # 扩展的边缘增强核
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                kernel[center, center] = 1.0
                kernel[center, center - 1] = -0.5
                kernel[center - 1, center] = -0.5

        elif kernel_type == 'emboss':
            # 浮雕效果核
            if size == 3:
                kernel = np.array([
                    [-2, -1, 0],
                    [-1, 1, 1],
                    [0, 1, 2]
                ], dtype=np.float32)
            else:
                # 扩展的浮雕核
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                for i in range(size):
                    for j in range(size):
                        dist_i = i - center
                        dist_j = j - center
                        if dist_i < 0 and dist_j < 0:
                            kernel[i, j] = -1.0 - min(abs(dist_i), abs(dist_j))
                        elif dist_i > 0 and dist_j > 0:
                            kernel[i, j] = 1.0 + min(dist_i, dist_j)
                        elif i == center and j == center:
                            kernel[i, j] = 1.0

        elif kernel_type == 'blur':
            # 均值模糊核 (Box blur)
            kernel = np.ones((size, size), dtype=np.float32) / (size * size)

        elif kernel_type == 'gaussian_blur':
            # 高斯模糊核
            if size == 3:
                kernel = np.array([
                    [1, 2, 1],
                    [2, 4, 2],
                    [1, 2, 1]
                ], dtype=np.float32) / 16
            else:
                # 使用OpenCV生成高斯核
                center = size // 2
                sigma = 0.3 * ((size - 1) * 0.5 - 1) + 0.8  # 动态计算sigma
                kernel = np.zeros((size, size), dtype=np.float32)

                # 手动实现高斯核计算
                sum_val = 0.0
                for i in range(size):
                    for j in range(size):
                        x = i - center
                        y = j - center
                        kernel[i, j] = np.exp(-(x * x + y * y) / (2 * sigma * sigma))
                        sum_val += kernel[i, j]

                # 归一化
                if sum_val != 0:
                    kernel /= sum_val

        elif kernel_type == 'gradient_x':
            # X方向梯度 (Prewitt)
            kernel = np.zeros((size, size), dtype=np.float32)
            center = size // 2
            for i in range(size):
                for j in range(size):
                    if j < center:
                        kernel[i, j] = -1.0
                    elif j > center:
                        kernel[i, j] = 1.0

        elif kernel_type == 'gradient_y':
            # Y方向梯度 (Prewitt)
            kernel = np.zeros((size, size), dtype=np.float32)
            center = size // 2
            for i in range(size):
                for j in range(size):
                    if i < center:
                        kernel[i, j] = -1.0
                    elif i > center:
                        kernel[i, j] = 1.0

        elif kernel_type == 'laplacian':
            # 拉普拉斯算子 (用于边缘检测)
            if size == 3:
                kernel = np.array([
                    [0, 1, 0],
                    [1, -4, 1],
                    [0, 1, 0]
                ], dtype=np.float32)
            else:
                # 扩展的拉普拉斯
                kernel = np.zeros((size, size), dtype=np.float32)
                center = size // 2
                for i in range(size):
                    for j in range(size):
                        if (i == center and abs(j - center) == 1) or (j == center and abs(i - center) == 1):
                            kernel[i, j] = 1.0
                kernel[center, center] = -4.0  # 中心值等于相邻单元格数量的负数

        # 应用强度因子
        if intensity != 1.0 and kernel is not None:
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

        # 返回生成的核
        if kernel is not None:
            # 确保kernel是float32类型，即使经过计算可能已转换为其他类型
            if kernel.dtype != np.float32:
                kernel = kernel.astype(np.float32)
            print(f"成功生成卷积核: 形状={kernel.shape}, 类型={kernel.dtype}")
            return {'kernel': kernel}
        else:
            # 如果没能生成有效的核，返回单位核
            default_kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)
            print(f"警告：生成卷积核失败，返回默认单位核")
            return {'kernel': default_kernel}

    except Exception as e:
        print(f"卷积核生成错误: {str(e)}")
        import traceback
        traceback.print_exc()
        # 出错时返回默认单位核
        default_kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)
        return {'kernel': default_kernel}


def get_params():
    # 定义核生成参数
    return {
        'kernel_type': {
            'type': 'dropdown',
            'label': '核类型',
            'value': 'custom',
            'options': [
                'custom', 'sharpen', 'edge_detect', 'edge_detect_y',
                'edge_enhance', 'emboss', 'blur', 'gaussian_blur',
                'gradient_x', 'gradient_y', 'laplacian'
            ]
        },
        'size': {
            'type': 'dropdown',
            'label': '核大小',
            'value': '3',
            'options': ['3', '5', '7', '9']
        },
        'intensity': {
            'type': 'slider',
            'label': '强度',
            'min': 0.1,
            'max': 5.0,
            'value': 1.0,
            'step': 0.1
        },
        'custom_kernel': {
            'type': 'text',
            'label': '自定义核 (行;列)',
            'value': '0,0,0;0,1,0;0,0,0'
        }
    }


# 常用预设
def sub_preset_sharpen_extreme():
    """极度锐化预设"""
    print("应用预设：极度锐化")
    return True


def sub_preset_edge_enhance_strong():
    """边缘增强预设"""
    print("应用预设：强边缘增强")
    return True


def sub_visualize_kernel():
    """可视化当前卷积核"""
    print("显示卷积核可视化")
    return True