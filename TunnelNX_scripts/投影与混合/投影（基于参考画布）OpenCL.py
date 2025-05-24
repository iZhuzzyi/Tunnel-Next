# f32bmp,f32bmp
# f32bmp
# 将源图像投影到参考画布上（OpenCL加速版）
# 9370DB
#SupportedFeatures:PerfSensitive=True
import cv2
import numpy as np
import time

# 检测并启用OpenCL
OPENCL_AVAILABLE = False
try:
    # 检查OpenCL是否可用
    OPENCL_AVAILABLE = cv2.ocl.haveOpenCL()
    if OPENCL_AVAILABLE:
        # 启用OpenCL
        cv2.ocl.setUseOpenCL(True)
        print(f"OpenCL加速已启用: {cv2.ocl.useOpenCL()}")
        devices = [cv2.ocl.Device.getDefault().name()]
        print(f"使用OpenCL设备: {devices}")
    else:
        print("系统不支持OpenCL，将使用CPU模式")
except Exception as e:
    print(f"OpenCL初始化失败: {e}")


def get_params():
    return {
        'theta_x': {'type': 'slider', 'label': 'X轴旋转 (俯仰)', 'min': -45, 'max': 45, 'value': 0},
        'theta_y': {'type': 'slider', 'label': 'Y轴旋转 (偏航)', 'min': -45, 'max': 45, 'value': 0},
        'theta_z': {'type': 'slider', 'label': 'Z轴旋转 (翻滚)', 'min': -180, 'max': 180, 'value': 0},
        'tx': {'type': 'slider', 'label': 'X轴平移', 'min': -300, 'max': 300, 'value': 0},
        'ty': {'type': 'slider', 'label': 'Y轴平移', 'min': -300, 'max': 300, 'value': 0},
        'distance': {'type': 'slider', 'label': '摄像机距离', 'min': 500, 'max': 3000, 'value': 1000},
        'scale': {'type': 'slider', 'label': '缩放 (%)', 'min': 50, 'max': 150, 'value': 100},
        'use_opencl': {'type': 'checkbox', 'label': '使用OpenCL加速', 'value': True},
        'quality': {'type': 'dropdown', 'label': '质量', 'value': 'balanced', 
                    'options': ['speed', 'balanced', 'quality']}
    }


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
    use_opencl = params.get('use_opencl', True) and OPENCL_AVAILABLE
    quality = params.get('quality', 'balanced')
    
    # 设置OpenCL
    prev_opencl_state = cv2.ocl.useOpenCL()
    if use_opencl:
        cv2.ocl.setUseOpenCL(True)
    else:
        cv2.ocl.setUseOpenCL(False)
    
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
            cv2.ocl.setUseOpenCL(prev_opencl_state)  # 恢复OpenCL状态
            return {'f32bmp': result}
        
        # 转换为UMat进行GPU加速（如果启用）
        if use_opencl:
            try:
                # 只有在小区域上使用OpenCL，对于简单的叠加可能不需要
                src_roi = cv2.UMat(img[:src_h, :src_w])
                roi = cv2.UMat(result[start_y:end_y, start_x:end_x])
                
                # 检查通道数
                if img.shape[2] == 4 and result.shape[2] == 4:
                    # 两者都有Alpha通道
                    # UMat不支持分割后再组合，需要拆分为CPU操作
                    src_roi_cpu = src_roi.get()  # 转回CPU
                    roi_cpu = roi.get()
                    
                    alpha_src = src_roi_cpu[:, :, 3:4]
                    # 使用向量化操作
                    result_cpu = np.zeros_like(roi_cpu)
                    result_cpu[:, :, :3] = (
                        src_roi_cpu[:, :, :3] * alpha_src + 
                        roi_cpu[:, :, :3] * roi_cpu[:, :, 3:4] * (1 - alpha_src)
                    )
                    result_cpu[:, :, 3:4] = (
                        alpha_src + roi_cpu[:, :, 3:4] * (1 - alpha_src)
                    )
                    
                    # 更新结果
                    result[start_y:end_y, start_x:end_x] = result_cpu
                else:
                    # 简单情况，回落到CPU处理
                    result[start_y:end_y, start_x:end_x] = img[:src_h, :src_w]
            except Exception as e:
                print(f"OpenCL处理失败：{e}，回落到CPU模式")
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
            # CPU模式
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
        print(f"简单叠加完成，使用{'OpenCL' if use_opencl else 'CPU'}模式，耗时: {elapsed:.3f}秒")
        cv2.ocl.setUseOpenCL(prev_opencl_state)  # 恢复OpenCL状态
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

    # 组合旋转矩阵
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
    
    # 应用旋转和平移
    centered_pts = pts_3d - np.array([0, 0, distance])
    pts_3d_rotated = np.zeros_like(pts_3d)
    
    for i, pt in enumerate(centered_pts):
        pts_3d_rotated[i] = R @ pt + np.array([0, 0, distance])
    
    pts_3d_transformed = pts_3d_rotated + np.array([tx, ty, 0])
    
    # 透视投影到2D
    pts_2d = np.zeros((4, 2))
    
    for i, pt in enumerate(pts_3d_transformed):
        if pt[2] > 0:
            pts_2d[i, 0] = focal_length * pt[0] / pt[2] + ref_w / 2
            pts_2d[i, 1] = focal_length * pt[1] / pt[2] + ref_h / 2
        else:
            pts_2d[i, 0] = ref_w * 2 if pt[0] > 0 else -ref_w
            pts_2d[i, 1] = ref_h * 2 if pt[1] > 0 else -ref_h
    
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
        edges = []
        valid_edge_length = True
        for i in range(4):
            j = (i + 1) % 4
            edge = np.sqrt(
                (pts_2d[i, 0] - pts_2d[j, 0])**2 + 
                (pts_2d[i, 1] - pts_2d[j, 1])**2
            )
            if edge < 1:
                valid_edge_length = False
                break
        
        # 计算面积
        area = 0.5 * abs(
            (pts_2d[0, 0] * (pts_2d[1, 1] - pts_2d[3, 1])) +
            (pts_2d[1, 0] * (pts_2d[2, 1] - pts_2d[0, 1])) +
            (pts_2d[2, 0] * (pts_2d[3, 1] - pts_2d[1, 1])) +
            (pts_2d[3, 0] * (pts_2d[0, 1] - pts_2d[2, 1]))
        )
        
        # 检查点是否在范围内
        in_bounds = all(
            -ref_w/2 <= pt[0] <= ref_w*1.5 and 
            -ref_h/2 <= pt[1] <= ref_h*1.5 
            for pt in pts_2d
        )
        
        valid = valid_edge_length and area >= 100 and in_bounds
        
        if not valid:
            print("投影形状无效，返回原图")
            cv2.ocl.setUseOpenCL(prev_opencl_state)  # 恢复OpenCL状态
            return {'f32bmp': reference_img}
        
        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(pts_src, pts_2d.astype(np.float32))
        
        # 使用OpenCL进行变换和混合（如果启用）
        if use_opencl:
            try:
                # 转换为UMat启用OpenCL
                src_umat = cv2.UMat(img)
                result_umat = cv2.UMat(reference_img.copy())
                
                # 透视变换（GPU加速）
                warped_umat = cv2.warpPerspective(
                    src_umat, M, (ref_w, ref_h),
                    flags=interpolation,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0
                )
                
                # 获取结果（需要回到CPU进行alpha混合）
                warped = warped_umat.get()
                result = result_umat.get()
                
                # 处理alpha混合
                if img.shape[2] == 4:
                    # 有alpha通道
                    alpha_src = warped[:, :, 3:4]
                    
                    # 使用向量化操作完成混合
                    mask = alpha_src > 0
                    if np.any(mask):
                        if result.shape[2] == 4:
                            # 目标也有alpha
                            rgb_src = warped[:, :, :3]
                            rgb_dst = result[:, :, :3]
                            alpha_dst = result[:, :, 3:4]
                            
                            # 使用mask索引加速计算
                            result[:, :, :3][mask[:, :, 0]] = (
                                rgb_src[mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                                rgb_dst[mask[:, :, 0]] * alpha_dst[mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                            result[:, :, 3:4][mask[:, :, 0]] = (
                                alpha_src[mask[:, :, 0]] + alpha_dst[mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                        else:
                            # 目标没有alpha
                            rgb_src = warped[:, :, :3]
                            result[mask[:, :, 0]] = (
                                rgb_src[mask[:, :, 0]] * alpha_src[mask[:, :, 0]] + 
                                result[mask[:, :, 0]] * (1 - alpha_src[mask[:, :, 0]])
                            )
                else:
                    # 无alpha通道，只替换非零区域
                    non_zero = np.any(warped > 0, axis=2)
                    result[non_zero] = warped[non_zero]
            except Exception as e:
                print(f"OpenCL处理失败：{e}，回落到CPU模式")
                # 回落到CPU模式
                result = reference_img.copy()
                
                # 透视变换
                warped = cv2.warpPerspective(
                    img, M, (ref_w, ref_h),
                    flags=interpolation,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0
                )
                
                # 处理alpha混合
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
            # CPU模式
            result = reference_img.copy()
            
            # 透视变换
            warped = cv2.warpPerspective(
                img, M, (ref_w, ref_h),
                flags=interpolation,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0
            )
            
            # 处理alpha混合（优化向量化）
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
        print(f"透视投影完成，使用{'OpenCL' if use_opencl else 'CPU'}模式，" +
              f"质量设置: {quality}，耗时: {elapsed:.3f}秒")
        
        # 恢复OpenCL状态
        cv2.ocl.setUseOpenCL(prev_opencl_state)
        return {'f32bmp': result}
            
    except Exception as e:
        print(f"透视变换计算失败: {e}")
        elapsed = time.time() - start_time
        print(f"处理失败，耗时: {elapsed:.3f}秒")
        # 恢复OpenCL状态
        cv2.ocl.setUseOpenCL(prev_opencl_state)
        return {'f32bmp': reference_img}