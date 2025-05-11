# f32bmp
# f32bmp
# 3D 投影与透视校正
# 4169E1
import cv2
import numpy as np


def process(inputs, params):
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        return {'f32bmp': None}

    # 获取输入图像
    img = inputs['f32bmp'].copy()
    h, w = img.shape[:2]

    # 获取变换参数
    theta_x = np.radians(params.get('theta_x', 0))  # 俯仰角 (X轴)
    theta_y = np.radians(params.get('theta_y', 0))  # 偏航角 (Y轴)
    theta_z = np.radians(params.get('theta_z', 0))  # 翻滚角 (Z轴)

    tx = params.get('tx', 0)  # X轴平移
    ty = params.get('ty', 0)  # Y轴平移
    distance = params.get('distance', 1000)  # Z轴距离/深度
    default_distance = 1000  # 默认摄像机距离

    scale = params.get('scale', 100) / 100.0  # 缩放因子

    # 在默认参数下直接返回原图像
    if (abs(theta_x) < 1e-6 and abs(theta_y) < 1e-6 and abs(theta_z) < 1e-6 and 
        abs(tx) < 1e-6 and abs(ty) < 1e-6 and 
        abs(distance - default_distance) < 1e-6 and 
        abs(scale - 1.0) < 1e-6):
        return {'f32bmp': img}

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

    # 组合旋转矩阵 (Rx * Ry * Rz)
    # 修正：正确的旋转顺序应该是先X轴，然后Y轴，最后Z轴
    R = Rz @ Ry @ Rx  # 矩阵乘法顺序是正确的

    # 设置摄像机参数和3D空间
    # 我们采用以下3D坐标系:
    # - 摄像机位于原点(0,0,0)
    # - 摄像机沿Z轴正方向观察
    # - 图像默认位于Z=distance处的平面上
    
    # 1. 设置焦距
    f_default = default_distance
    focal_length = f_default * (distance / default_distance)
    
    # 2. 定义图像在3D空间中的尺寸
    img_width_3d = w * scale
    img_height_3d = h * scale
    
    # 3. 定义3D空间中图像平面上的四个角点
    half_w = img_width_3d / 2
    half_h = img_height_3d / 2
    
    # 原始3D点（相对于图像中心）
    pts_3d = np.array([
        [-half_w, -half_h, distance],  # 左上
        [half_w, -half_h, distance],   # 右上
        [half_w, half_h, distance],    # 右下
        [-half_w, half_h, distance]    # 左下
    ])
    
    # 4. 应用旋转 (绕图像中心)
    pts_3d_rotated = np.zeros_like(pts_3d)
    for i, pt in enumerate(pts_3d):
        # 先移动到原点
        centered_pt = pt - np.array([0, 0, distance])
        # 应用旋转
        rotated_pt = R @ centered_pt
        # 移回原位
        pts_3d_rotated[i] = rotated_pt + np.array([0, 0, distance])
    
    # 5. 应用平移
    pts_3d_transformed = pts_3d_rotated + np.array([tx, ty, 0])
    
    # 6. 透视投影到2D
    pts_2d = np.zeros((len(pts_3d_transformed), 2))  # 修正：确保pts_2d与pts_3d_transformed长度一致
    for i, pt in enumerate(pts_3d_transformed):
        # 透视投影公式：x' = f * x / z, y' = f * y / z
        if pt[2] > 0:  # 确保点在摄像机前方
            pts_2d[i, 0] = focal_length * pt[0] / pt[2] + w / 2
            pts_2d[i, 1] = focal_length * pt[1] / pt[2] + h / 2
        else:
            # 处理在摄像机后方的点
            # 修正：更好地处理负z值情况，避免不合理的投影
            pts_2d[i, 0] = w * 2 if pt[0] > 0 else -w  # 根据x坐标符号决定投影方向
            pts_2d[i, 1] = h * 2 if pt[1] > 0 else -h  # 根据y坐标符号决定投影方向
    
    # 7. 原始图像中的四个角点
    pts_src = np.array([
        [0, 0],         # 左上
        [w - 1, 0],     # 右上
        [w - 1, h - 1], # 右下
        [0, h - 1]      # 左下
    ], dtype=np.float32)
    
    # 8. 计算透视变换矩阵
    try:
        # 检查投影点是否构成有效的四边形
        valid = True
        
        # 计算四边形的边长和面积
        edges = []
        for i in range(4):
            j = (i + 1) % 4
            edge = np.sqrt(
                (pts_2d[i, 0] - pts_2d[j, 0]) ** 2 + 
                (pts_2d[i, 1] - pts_2d[j, 1]) ** 2
            )
            edges.append(edge)
            if edge < 1:  # 如果任何边太短，可能导致变换失败
                valid = False
                break
        
        # 检查四边形的面积
        area = 0.5 * abs(
            (pts_2d[0, 0] * (pts_2d[1, 1] - pts_2d[3, 1])) +
            (pts_2d[1, 0] * (pts_2d[2, 1] - pts_2d[0, 1])) +
            (pts_2d[2, 0] * (pts_2d[3, 1] - pts_2d[1, 1])) +
            (pts_2d[3, 0] * (pts_2d[0, 1] - pts_2d[2, 1]))
        )
        
        if area < 100:  # 面积太小也会导致变换失败
            valid = False
            
        # 修正：检查投影点是否在图像范围内
        in_bounds = True
        margin = -w/2  # 允许一定程度的超出边界，但不要太远
        for pt in pts_2d:
            if (pt[0] < margin or pt[0] > w*1.5 or 
                pt[1] < margin or pt[1] > h*1.5):
                in_bounds = False
                break
        
        valid = valid and in_bounds
        
        if valid:
            # 修正：确保pts_2d是float32类型
            M = cv2.getPerspectiveTransform(pts_src, pts_2d.astype(np.float32))
            
            # 9. 应用透视变换
            if img.dtype == np.float32:
                # 对于浮点图像，确保值在0-1范围内
                dst = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
                dst = np.clip(dst, 0, 1).astype(np.float32)
            else:
                dst = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
                
            return {'f32bmp': dst}
        else:
            # 如果投影形状无效，返回原图像
            return {'f32bmp': img}
            
    except Exception as e:
        # 如果透视变换计算失败，返回原图像
        print(f"透视变换计算失败: {e}")
        return {'f32bmp': img}


def get_params():
    return {
        'theta_x': {'type': 'slider', 'label': 'X轴旋转 (俯仰)', 'min': -45, 'max': 45, 'value': 0},
        'theta_y': {'type': 'slider', 'label': 'Y轴旋转 (偏航)', 'min': -45, 'max': 45, 'value': 0},
        'theta_z': {'type': 'slider', 'label': 'Z轴旋转 (翻滚)', 'min': -180, 'max': 180, 'value': 0},
        'tx': {'type': 'slider', 'label': 'X轴平移', 'min': -300, 'max': 300, 'value': 0},
        'ty': {'type': 'slider', 'label': 'Y轴平移', 'min': -300, 'max': 300, 'value': 0},
        'distance': {'type': 'slider', 'label': '摄像机距离', 'min': 500, 'max': 3000, 'value': 1000},
        'scale': {'type': 'slider', 'label': '缩放 (%)', 'min': 50, 'max': 150, 'value': 100}
    }
