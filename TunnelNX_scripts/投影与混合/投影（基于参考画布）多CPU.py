# f32bmp,f32bmp
# f32bmp
# 将源图像投影到参考画布上（多核CPU加速版）
# 9370DB
#SupportedFeatures:PerfSensitive=True
import cv2
import numpy as np
import time
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
import os

# 获取CPU核心数以设置并行线程数
CPU_COUNT = os.cpu_count() or 4
MAX_THREADS = max(2, CPU_COUNT - 1)  # 保留一个核心给系统
print(f"检测到{CPU_COUNT}个CPU核心，将使用{MAX_THREADS}个线程进行处理")

# 禁用OpenCL
cv2.ocl.setUseOpenCL(False)


def get_params():
    return {
        'theta_x': {'type': 'slider', 'label': 'X轴旋转 (俯仰)', 'min': -45, 'max': 45, 'value': 0},
        'theta_y': {'type': 'slider', 'label': 'Y轴旋转 (偏航)', 'min': -45, 'max': 45, 'value': 0},
        'theta_z': {'type': 'slider', 'label': 'Z轴旋转 (翻滚)', 'min': -180, 'max': 180, 'value': 0},
        'tx': {'type': 'slider', 'label': 'X轴平移', 'min': -300, 'max': 300, 'value': 0},
        'ty': {'type': 'slider', 'label': 'Y轴平移', 'min': -300, 'max': 300, 'value': 0},
        'distance': {'type': 'slider', 'label': '摄像机距离', 'min': 500, 'max': 3000, 'value': 1000},
        'scale': {'type': 'slider', 'label': '缩放 (%)', 'min': 50, 'max': 150, 'value': 100},
        'cpu_threads': {'type': 'slider', 'label': 'CPU线程数', 'min': 1, 'max': CPU_COUNT, 'value': MAX_THREADS},
        'quality': {'type': 'dropdown', 'label': '质量', 'value': 'balanced', 
                    'options': ['speed', 'balanced', 'quality']}
    }


# 图像分块处理函数，用于并行处理
def process_image_chunk(args):
    chunk, roi, alpha_blend = args
    y_start, y_end, img_chunk = chunk
    result_chunk = np.zeros_like(img_chunk)
    
    if alpha_blend:
        # 有alpha通道的图像混合
        alpha_src = img_chunk[:, :, 3:4]
        mask = alpha_src > 0
        
        if np.any(mask):
            roi_chunk = roi[y_start:y_end]
            if roi_chunk.shape[2] == 4:
                # 目标也有alpha
                result_chunk[:, :, :3] = np.where(
                    mask,
                    img_chunk[:, :, :3] * alpha_src + 
                    roi_chunk[:, :, :3] * roi_chunk[:, :, 3:4] * (1 - alpha_src),
                    roi_chunk[:, :, :3]
                )
                result_chunk[:, :, 3:4] = np.where(
                    mask,
                    alpha_src + roi_chunk[:, :, 3:4] * (1 - alpha_src),
                    roi_chunk[:, :, 3:4]
                )
            else:
                # 目标没有alpha
                result_chunk = np.where(
                    mask,
                    img_chunk[:, :, :3] * alpha_src + roi_chunk * (1 - alpha_src),
                    roi_chunk
                )
    else:
        # 无alpha通道，直接替换非零区域
        non_zero = np.any(img_chunk > 0, axis=2)
        roi_chunk = roi[y_start:y_end]
        result_chunk = np.where(
            non_zero[:, :, np.newaxis],
            img_chunk,
            roi_chunk
        )
    
    return (y_start, y_end, result_chunk)


def process(inputs, params):
    # 记录开始时间
    start_time = time.time()
    
    # 获取输入
    source_img = None
    reference_img = None
    
    # 尝试不同方式获取输入
    if 'f32bmp' in inputs and 'f32bmp_1' in inputs:
        source_img = inputs['f32bmp']
        reference_img = inputs['f32bmp_1']
    elif len(inputs) >= 2:
        keys = list(inputs.keys())
        source_img = inputs[keys[0]]
        reference_img = inputs[keys[1]]
    
    # 检查输入有效性
    if source_img is None or reference_img is None:
        error_img = np.zeros((100, 100, 4), dtype=np.float32)
        error_img[:, :, 0] = 1.0  # 红色
        error_img[:, :, 3] = 1.0  # 不透明
        return {'f32bmp': error_img}
    
    # 获取图像尺寸
    img = source_img
    h, w = img.shape[:2]
    ref_h, ref_w = reference_img.shape[:2]
    
    # 获取参数
    theta_x = np.radians(params.get('theta_x', 0))
    theta_y = np.radians(params.get('theta_y', 0))
    theta_z = np.radians(params.get('theta_z', 0))
    tx = params.get('tx', 0)
    ty = params.get('ty', 0)
    distance = params.get('distance', 1000)
    default_distance = 1000
    scale = params.get('scale', 100) / 100.0
    cpu_threads = min(params.get('cpu_threads', MAX_THREADS), MAX_THREADS)
    quality = params.get('quality', 'balanced')
    
    # 根据质量设置选择插值方法
    if quality == 'speed':
        interpolation = cv2.INTER_NEAREST
    elif quality == 'quality':
        interpolation = cv2.INTER_CUBIC
    else:  # balanced
        interpolation = cv2.INTER_LINEAR
    
    # 检查是否使用默认参数（快速路径）
    use_default = (abs(theta_x) < 1e-6 and abs(theta_y) < 1e-6 and abs(theta_z) < 1e-6 and 
                  abs(tx) < 1e-6 and abs(ty) < 1e-6 and 
                  abs(distance - default_distance) < 1e-6 and 
                  abs(scale - 1.0) < 1e-6)
    
    if use_default:
        # 简单居中叠加
        result = reference_img.copy()
        
        # 计算居中位置
        start_x = max(0, (ref_w - w) // 2)
        start_y = max(0, (ref_h - h) // 2)
        end_x = min(ref_w, start_x + w)
        end_y = min(ref_h, start_y + h)
        
        # 源图像区域
        src_w = end_x - start_x
        src_h = end_y - start_y
        
        if src_w <= 0 or src_h <= 0 or src_w > w or src_h > h:
            return {'f32bmp': result}
        
        # 多线程处理
        if cpu_threads > 1 and src_h > 100:
            try:
                # 并行处理图像
                chunk_size = max(1, src_h // cpu_threads)
                chunks = []
                
                # 准备数据块
                for i in range(0, src_h, chunk_size):
                    y_end = min(i + chunk_size, src_h)
                    chunks.append((i, y_end, img[i:y_end, :src_w]))
                
                # 是否需要alpha混合
                has_alpha = img.shape[2] == 4 and result.shape[2] == 4
                
                # 并行处理
                with ThreadPoolExecutor(max_workers=cpu_threads) as executor:
                    results = list(executor.map(
                        process_image_chunk, 
                        [(chunk, result[start_y:end_y, start_x:end_x], has_alpha) for chunk in chunks]
                    ))
                
                # 将结果组合回原始图像
                for y_start, y_end, chunk_result in results:
                    result[start_y + y_start:start_y + y_end, start_x:end_x] = chunk_result
                
            except Exception as e:
                print(f"多线程处理失败：{e}，回落到单线程模式")
                # 回落到单线程处理
                roi = result[start_y:end_y, start_x:end_x]
                src_roi = img[:src_h, :src_w]
                
                # 根据通道数选择处理方式
                if src_roi.shape[2] == 4 and roi.shape[2] == 4:
                    alpha_src = src_roi[:, :, 3:4]
                    result[start_y:end_y, start_x:end_x, :3] = (
                        src_roi[:, :, :3] * alpha_src + roi[:, :, :3] * roi[:, :, 3:4] * (1 - alpha_src)
                    )
                    result[start_y:end_y, start_x:end_x, 3:4] = alpha_src + roi[:, :, 3:4] * (1 - alpha_src)
                else:
                    result[start_y:end_y, start_x:end_x] = src_roi
        else:
            # 单线程处理
            roi = result[start_y:end_y, start_x:end_x]
            src_roi = img[:src_h, :src_w]
            
            # 根据通道数选择处理方式
            if src_roi.shape[2] == 4 and roi.shape[2] == 4:
                alpha_src = src_roi[:, :, 3:4]
                result[start_y:end_y, start_x:end_x, :3] = (
                    src_roi[:, :, :3] * alpha_src + roi[:, :, :3] * roi[:, :, 3:4] * (1 - alpha_src)
                )
                result[start_y:end_y, start_x:end_x, 3:4] = alpha_src + roi[:, :, 3:4] * (1 - alpha_src)
            else:
                result[start_y:end_y, start_x:end_x] = src_roi
        
        elapsed = time.time() - start_time
        print(f"简单叠加完成，使用{cpu_threads}线程CPU模式，耗时: {elapsed:.3f}秒")
        return {'f32bmp': result}

    # 创建3D变换矩阵
    # 1. 旋转矩阵
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(theta_x), -np.sin(theta_x)],
        [0, np.sin(theta_x), np.cos(theta_x)]
    ])

    Ry = np.array([
        [np.cos(theta_y), 0, np.sin(theta_y)],
        [0, 1, 0],
        [-np.sin(theta_y), 0, np.cos(theta_y)]
    ])

    Rz = np.array([
        [np.cos(theta_z), -np.sin(theta_z), 0],
        [np.sin(theta_z), np.cos(theta_z), 0],
        [0, 0, 1]
    ])

    # 组合旋转矩阵 (矢量化计算)
    R = Rz @ Ry @ Rx
    
    # 透视变换计算
    f_default = default_distance
    focal_length = f_default * (distance / default_distance)
    
    # 图像3D尺寸
    img_width_3d = w * scale
    img_height_3d = h * scale
    half_w = img_width_3d / 2
    half_h = img_height_3d / 2
    
    # 原始3D点
    pts_3d = np.array([
        [-half_w, -half_h, distance],  # 左上
        [half_w, -half_h, distance],   # 右上
        [half_w, half_h, distance],    # 右下
        [-half_w, half_h, distance]    # 左下
    ])
    
    # 应用旋转和平移 (矢量化计算)
    centered_pts = pts_3d - np.array([0, 0, distance])
    pts_3d_rotated = centered_pts @ R.T + np.array([0, 0, distance])
    pts_3d_transformed = pts_3d_rotated + np.array([tx, ty, 0])
    
    # 透视投影到2D (矢量化计算)
    pts_2d = np.zeros((4, 2))
    z_positive = pts_3d_transformed[:, 2] > 0
    pts_2d[z_positive, 0] = focal_length * pts_3d_transformed[z_positive, 0] / pts_3d_transformed[z_positive, 2] + ref_w / 2
    pts_2d[z_positive, 1] = focal_length * pts_3d_transformed[z_positive, 1] / pts_3d_transformed[z_positive, 2] + ref_h / 2
    
    # 处理z <= 0的情况
    z_negative = ~z_positive
    if np.any(z_negative):
        pts_2d[z_negative, 0] = np.where(pts_3d_transformed[z_negative, 0] > 0, ref_w * 2, -ref_w)
        pts_2d[z_negative, 1] = np.where(pts_3d_transformed[z_negative, 1] > 0, ref_h * 2, -ref_h)
    
    # 源图像中的四个角点
    pts_src = np.array([
        [0, 0],         # 左上
        [w - 1, 0],     # 右上
        [w - 1, h - 1], # 右下
        [0, h - 1]      # 左下
    ], dtype=np.float32)
    
    # 检查四边形有效性
    try:
        # 快速检查边长和面积
        edges = np.zeros(4)
        for i in range(4):
            j = (i + 1) % 4
            edges[i] = np.sqrt(
                (pts_2d[i, 0] - pts_2d[j, 0])**2 + 
                (pts_2d[i, 1] - pts_2d[j, 1])**2
            )
        
        valid_edge_length = np.all(edges >= 1)
        
        # 计算面积
        area = 0.5 * abs(
            (pts_2d[0, 0] * (pts_2d[1, 1] - pts_2d[3, 1])) +
            (pts_2d[1, 0] * (pts_2d[2, 1] - pts_2d[0, 1])) +
            (pts_2d[2, 0] * (pts_2d[3, 1] - pts_2d[1, 1])) +
            (pts_2d[3, 0] * (pts_2d[0, 1] - pts_2d[2, 1]))
        )
        
        # 检查点是否在范围内
        in_bounds = np.all(
            (-ref_w/2 <= pts_2d[:, 0]) & (pts_2d[:, 0] <= ref_w*1.5) & 
            (-ref_h/2 <= pts_2d[:, 1]) & (pts_2d[:, 1] <= ref_h*1.5)
        )
        
        valid = valid_edge_length and area >= 100 and in_bounds
        
        if not valid:
            print("投影形状无效，返回原图")
            return {'f32bmp': reference_img}
        
        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(pts_src, pts_2d.astype(np.float32))
        
        # 准备结果
        result = reference_img.copy()
        
        # 透视变换
        warped = cv2.warpPerspective(
            img, M, (ref_w, ref_h),
            flags=interpolation,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )
        
        # 多线程处理alpha混合
        if cpu_threads > 1 and ref_h > 100:
            try:
                # 检查是否需要进行额外的alpha混合处理
                needs_alpha_blending = img.shape[2] == 4
                
                if needs_alpha_blending:
                    # 准备数据分块
                    chunk_size = max(1, ref_h // cpu_threads)
                    chunks = []
                    
                    for i in range(0, ref_h, chunk_size):
                        y_end = min(i + chunk_size, ref_h)
                        chunks.append((i, y_end, warped[i:y_end]))
                    
                    # 并行处理
                    with ThreadPoolExecutor(max_workers=cpu_threads) as executor:
                        results = list(executor.map(
                            process_image_chunk, 
                            [(chunk, result, True) for chunk in chunks]
                        ))
                    
                    # 将结果组合回原始图像
                    for y_start, y_end, chunk_result in results:
                        result[y_start:y_end] = chunk_result
                else:
                    # 无alpha通道处理，使用多线程加速掩码操作
                    chunk_size = max(1, ref_h // cpu_threads)
                    chunks = []
                    
                    for i in range(0, ref_h, chunk_size):
                        y_end = min(i + chunk_size, ref_h)
                        chunks.append((i, y_end, warped[i:y_end]))
                    
                    # 并行处理
                    with ThreadPoolExecutor(max_workers=cpu_threads) as executor:
                        results = list(executor.map(
                            process_image_chunk, 
                            [(chunk, result, False) for chunk in chunks]
                        ))
                    
                    # 将结果组合回原始图像
                    for y_start, y_end, chunk_result in results:
                        result[y_start:y_end] = chunk_result
                
            except Exception as e:
                print(f"多线程处理失败：{e}，回落到单线程模式")
                # 回落到单线程处理
                if img.shape[2] == 4:
                    alpha_src = warped[:, :, 3:4]
                    mask = alpha_src > 0
                    if np.any(mask):
                        if result.shape[2] == 4:
                            result[:, :, :3][mask[:, :, 0]] = (
                                warped[:, :, :3][mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                                result[:, :, :3][mask[:, :, 0]] * result[:, :, 3:4][mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                            result[:, :, 3:4][mask[:, :, 0]] = (
                                alpha_src[mask[:, :, 0]] + result[:, :, 3:4][mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                        else:
                            rgb_src = warped[:, :, :3]
                            result[mask[:, :, 0]] = (
                                rgb_src[mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                                result[mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                else:
                    non_zero = np.any(warped > 0, axis=2)
                    result[non_zero] = warped[non_zero]
        else:
            # 单线程处理
            if img.shape[2] == 4:
                alpha_src = warped[:, :, 3:4]
                mask = alpha_src > 0
                if np.any(mask):
                    if result.shape[2] == 4:
                        result[:, :, :3][mask[:, :, 0]] = (
                            warped[:, :, :3][mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                            result[:, :, :3][mask[:, :, 0]] * result[:, :, 3:4][mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                        )
                        result[:, :, 3:4][mask[:, :, 0]] = (
                            alpha_src[mask[:, :, 0]] + result[:, :, 3:4][mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                        )
                    else:
                        rgb_src = warped[:, :, :3]
                        result[mask[:, :, 0]] = (
                            rgb_src[mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                            result[mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                        )
            else:
                non_zero = np.any(warped > 0, axis=2)
                result[non_zero] = warped[non_zero]
        
        elapsed = time.time() - start_time
        print(f"透视投影完成，使用{cpu_threads}线程CPU模式，质量设置: {quality}，耗时: {elapsed:.3f}秒")
        
        return {'f32bmp': result}
            
    except Exception as e:
        print(f"透视变换计算失败: {e}")
        elapsed = time.time() - start_time
        print(f"处理失败，耗时: {elapsed:.3f}秒")
        return {'f32bmp': reference_img}