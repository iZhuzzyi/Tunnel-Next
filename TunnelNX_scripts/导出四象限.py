#f32bmp
#f32bmp
#四象限导出工具
#4287F5

import numpy as np
import os
import cv2
import time

def get_params():
    """定义节点参数"""
    return {
        "export_dir": {
            "type": "path",
            "value": "",
            "label": "导出目录 (留空使用工作文件夹)"
        },
        "filename_prefix": {
            "type": "text",
            "value": "quadrant",
            "label": "文件名前缀"
        },
        "show_grid": {
            "type": "checkbox",
            "value": True,
            "label": "显示网格线"
        },
        "grid_thickness": {
            "type": "slider",
            "min": 1,
            "max": 10,
            "step": 1,
            "value": 2,
            "label": "网格线粗细"
        },
        "grid_color": {
            "type": "dropdown",
            "options": ["白色", "黑色", "红色", "绿色", "蓝色", "黄色"],
            "value": "红色",
            "label": "网格线颜色"
        }
    }

def process(inputs, params):
    """处理输入图像"""
    # 检查输入是否存在
    if 'f32bmp' not in inputs:
        return {}  # 没有输入，返回空字典
    
    # 获取输入图像
    img = inputs['f32bmp']
    
    # 获取参数
    show_grid = params['show_grid']
    grid_thickness = params['grid_thickness']
    grid_color = params['grid_color']
    
    # 复制原始图像
    result = img.copy()
    
    # 如果启用了网格线，绘制中心十字线
    if show_grid:
        # 获取图像尺寸
        height, width = img.shape[:2]
        
        # 计算中心点
        center_x = width // 2
        center_y = height // 2
        
        # 设置网格线颜色
        color_map = {
            "白色": [1.0, 1.0, 1.0],
            "黑色": [0.0, 0.0, 0.0],
            "红色": [1.0, 0.0, 0.0],
            "绿色": [0.0, 1.0, 0.0],
            "蓝色": [0.0, 0.0, 1.0],
            "黄色": [1.0, 1.0, 0.0]
        }
        grid_color_rgb = color_map.get(grid_color, [1.0, 0.0, 0.0])  # 默认红色
        
        # 绘制水平线
        h_slice = result[center_y-grid_thickness//2:center_y+grid_thickness//2+grid_thickness%2, :]
        # 检查切片是否为 3D 且有 4 个通道 (RGBA)
        if len(h_slice.shape) == 3 and h_slice.shape[-1] == 4:
            h_slice[..., :3] = grid_color_rgb  # 只修改 RGB 通道
            h_slice[..., 3] = 1.0             # 设置 Alpha 为不透明
        # 检查切片是否为 3D 且有 3 个通道 (RGB)
        elif len(h_slice.shape) == 3 and h_slice.shape[-1] == 3:
             h_slice[:] = grid_color_rgb        # 直接赋值 RGB
        # 注意: 这里假设图像总是 RGB 或 RGBA，如果可能出现灰度图需要额外处理

        # 绘制垂直线
        v_slice = result[:, center_x-grid_thickness//2:center_x+grid_thickness//2+grid_thickness%2]
        # 检查切片是否为 3D 且有 4 个通道 (RGBA)
        if len(v_slice.shape) == 3 and v_slice.shape[-1] == 4:
            v_slice[..., :3] = grid_color_rgb  # 只修改 RGB 通道
            v_slice[..., 3] = 1.0             # 设置 Alpha 为不透明
        # 检查切片是否为 3D 且有 3 个通道 (RGB)
        elif len(v_slice.shape) == 3 and v_slice.shape[-1] == 3:
             v_slice[:] = grid_color_rgb        # 直接赋值 RGB
        # --- 结束新的统一绘制逻辑 ---
    
    # 返回处理后的图像
    return {
        'f32bmp': result
    }

def sub_导出四象限(params, inputs, context):
    """导出四个象限为单独的图像文件"""
    try:
        # 检查输入是否存在
        if 'f32bmp' not in inputs:
            return {
                'success': False,
                'error': "没有可用的图像数据"
            }
        
        # 获取输入图像
        img = inputs['f32bmp']
        
        # 获取参数
        export_dir = params['export_dir']
        filename_prefix = params['filename_prefix']
        
        # 如果导出目录为空，使用工作文件夹
        if not export_dir:
            export_dir = context['work_folder']
        
        # 确保导出目录存在
        os.makedirs(export_dir, exist_ok=True)
        
        # 获取图像尺寸
        height, width = img.shape[:2]
        
        # 计算中心点
        center_x = width // 2
        center_y = height // 2
        
        # 生成时间戳（防止文件名冲突）
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 分割四个象限 (路径将在循环内确定)
        quadrant1 = img[0:center_y, center_x:width].copy()
        quadrant2 = img[0:center_y, 0:center_x].copy()
        quadrant3 = img[center_y:height, 0:center_x].copy()
        quadrant4 = img[center_y:height, center_x:width].copy()

        # 保存图像
        quadrants_data = [
            (quadrant1, "q1_右上"),
            (quadrant2, "q2_左上"),
            (quadrant3, "q3_左下"),
            (quadrant4, "q4_右下")
        ]

        saved_paths_info = [] # 用于存储基础名称和完整路径
        for quad, name_suffix in quadrants_data:
            # 转换图像数据类型用于保存
            if quad.dtype == np.float32:
                img_save = (quad * 255).clip(0, 255).astype(np.uint8)
            elif quad.dtype == np.uint16:
                # 注意：从 uint16 到 uint8 的转换可能需要更复杂的处理
                # 取决于期望的范围。这里假设是简单的位移。
                img_save = (quad / 256).astype(np.uint8)
            else:
                img_save = quad.astype(np.uint8) # 确保是 uint8

            # 检查当前象限是否有 Alpha 通道
            quad_has_alpha = len(img_save.shape) == 3 and img_save.shape[2] == 4

            # 统一使用 PNG 格式
            ext = ".png"
            path = os.path.join(export_dir, f"{filename_prefix}_{name_suffix}_{timestamp}{ext}")

            # 根据是否有 Alpha 通道进行颜色转换 (准备写入文件)
            if quad_has_alpha:
                # 输入是 RGBA，需要转换为 BGRA
                img_to_write = cv2.cvtColor(img_save, cv2.COLOR_RGBA2BGRA)
            else:
                # 检查是否是灰度图 (2D array)
                if len(img_save.shape) == 2:
                    # 直接写入灰度图，OpenCV imwrite 可以处理
                    img_to_write = img_save
                # 检查是否是3通道图 (RGB)
                elif len(img_save.shape) == 3 and img_save.shape[2] == 3:
                     # 输入是 RGB，需要转换为 BGR
                    img_to_write = cv2.cvtColor(img_save, cv2.COLOR_RGB2BGR)
                else:
                    # 其他无法处理的情况，跳过这个象限
                    print(f"警告: 象限 '{name_suffix}' 具有无法处理的形状 {img_save.shape}，跳过保存。")
                    continue # 跳到下一个循环

            # 保存图像
            try:
                # 使用 PNG 压缩级别（可选，模仿导出节点）
                # compression_level = 6 # 默认压缩级别
                # cv2.imwrite(path, img_to_write, [cv2.IMWRITE_PNG_COMPRESSION, compression_level])
                cv2.imwrite(path, img_to_write)
                saved_paths_info.append({'basename': os.path.basename(path), 'fullpath': path})
            except Exception as write_e:
                 print(f"错误: 无法写入文件 {path}: {write_e}")
                 # 可以选择继续或返回错误
                 return {
                     'success': False,
                     'error': f"写入文件时出错: {path}\\n{str(write_e)}"
                 }

        # 构建成功消息
        message_lines = [f"已成功导出四个象限图像 (PNG格式) 到: {export_dir}"]
        for item in saved_paths_info:
            message_lines.append(f"- {item['basename']}")

        return {
            'success': True,
            'message': "\\n".join(message_lines)
        }

    except Exception as e:
        # 返回错误消息
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"导出四象限时出错: {str(e)}"
        }

def sub_查看导出目录(params, inputs, context):
    """打开导出目录"""
    try:
        # 获取导出目录
        export_dir = params['export_dir']
        
        # 如果导出目录为空，使用工作文件夹
        if not export_dir:
            export_dir = context['work_folder']
        
        # 确保目录存在
        os.makedirs(export_dir, exist_ok=True)
        
        # 打开文件夹
        import subprocess
        import platform
        
        system = platform.system()
        if system == 'Windows':
            os.startfile(export_dir)
        elif system == 'Darwin':  # macOS
            subprocess.call(['open', export_dir])
        else:  # Linux
            subprocess.call(['xdg-open', export_dir])
        
        return {
            'success': True,
            'message': f"已打开导出目录: {export_dir}"
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f"打开导出目录时出错: {str(e)}"
        }