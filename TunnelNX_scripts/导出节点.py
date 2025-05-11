# f32bmp
#
# 导出图像（支持透明度）
# EEAC00
import cv2
import numpy as np
import os
import tkinter as tk
from tkinter import filedialog, messagebox


def process(inputs, params):
    # 导出节点没有输出
    return {}


def get_params():
    return {
        'format': {'type': 'dropdown', 'label': '格式', 'value': 'PNG',
                   'options': ['JPEG', 'PNG', 'TIFF', 'BMP']},
        'quality': {'type': 'slider', 'label': '质量', 'min': 1, 'max': 100, 'value': 90},
        'use_alpha': {'type': 'checkbox', 'label': '使用透明度', 'value': True},
        'export_path': {'type': 'path', 'label': '导出路径', 'value': 'C:/photos/export.png'}
    }


def sub_export(params, inputs, context):
    """
    导出图像子操作（支持透明度）

    参数:
        params: 节点参数字典
        inputs: 节点输入数据
        context: 应用上下文信息

    返回:
        包含操作结果的字典
    """
    # 获取格式和输出路径
    export_format = params.get('format', 'PNG')  # 默认为PNG，因为它支持透明度
    export_path = params.get('export_path', '')
    quality = params.get('quality', 90)
    use_alpha = params.get('use_alpha', True)  # 是否使用透明度

    # 获取应用上下文
    work_folder = context.get('work_folder', 'C:/photos')

    # 如果未指定路径，请求用户选择路径
    if not export_path:
        # 获取Tk根窗口
        app = context.get('app')
        if app and hasattr(app, 'root'):
            root = app.root
        else:
            # 如果没有应用实例，创建一个临时的根窗口
            root = tk.Tk()
            root.withdraw()

        # 根据所选格式提供适当的文件类型选项
        if export_format == 'JPEG':
            filetypes = (("JPEG 文件", "*.jpg"), ("所有文件", "*.*"))
        elif export_format == 'PNG':
            filetypes = (("PNG 文件", "*.png"), ("所有文件", "*.*"))
        elif export_format == 'TIFF':
            filetypes = (("TIFF 文件", "*.tif"), ("所有文件", "*.*"))
        elif export_format == 'BMP':
            filetypes = (("BMP 文件", "*.bmp"), ("所有文件", "*.*"))
        else:
            filetypes = (("所有文件", "*.*"),)

        export_path = filedialog.asksaveasfilename(
            initialdir=work_folder,
            title="保存图像",
            filetypes=filetypes
        )

        if not export_path:
            # 如果用户取消选择，返回失败
            return {'success': False, 'error': '没有选择保存路径'}

    # 检查文件后缀
    file_ext = os.path.splitext(export_path)[1].lower()
    if not file_ext:
        # 添加默认后缀
        if export_format == 'JPEG':
            export_path += '.jpg'
        elif export_format == 'PNG':
            export_path += '.png'
        elif export_format == 'TIFF':
            export_path += '.tif'
        elif export_format == 'BMP':
            export_path += '.bmp'

    # 检查是否有有效输入
    if not inputs or 'f32bmp' not in inputs:
        return {'success': False, 'error': '没有有效的图像数据可导出'}

    # 获取图像数据
    img = inputs['f32bmp']
    
    # 从RGBA图像中提取RGB和Alpha通道
    has_alpha = False
    if img is not None and len(img.shape) == 3 and img.shape[2] == 4 and use_alpha:
        # 分离RGBA通道
        rgb_channels = img[:, :, :3]
        alpha_channel = img[:, :, 3]
        has_alpha = True
    else:
        # 如果图像没有4通道，或者用户不使用透明度
        rgb_channels = img
        if len(img.shape) == 3 and img.shape[2] == 4:
            rgb_channels = img[:, :, :3]  # 提取RGB部分
        alpha_channel = None

    # 检查是否支持Alpha通道
    supports_alpha = export_format in ['PNG', 'TIFF']

    try:
        # 转换为适合保存的格式
        if rgb_channels.dtype == np.float32:
            # 将浮点范围[0,1]转换为8位[0,255]
            img_display = (rgb_channels * 255).clip(0, 255).astype(np.uint8)
        else:
            img_display = rgb_channels

        # 准备Alpha通道 (如果有)
        if has_alpha and alpha_channel is not None and supports_alpha:
            if alpha_channel.dtype == np.float32:
                alpha_display = (alpha_channel * 255).clip(0, 255).astype(np.uint8)
            else:
                alpha_display = alpha_channel

            # 合并RGB和Alpha通道
            if len(img_display.shape) == 3 and img_display.shape[2] == 3:
                # 创建RGBA图像
                rgba = np.zeros((img_display.shape[0], img_display.shape[1], 4), dtype=np.uint8)
                rgba[:, :, :3] = img_display  # RGB通道
                rgba[:, :, 3] = alpha_display  # Alpha通道
                
                # 转换为BGR+A以供OpenCV使用
                bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
            else:
                # 如果不是3通道RGB图像，则忽略Alpha
                bgra = cv2.cvtColor(img_display, cv2.COLOR_RGB2BGR)
                has_alpha = False
        else:
            # 无Alpha通道，转换为BGR
            bgra = cv2.cvtColor(img_display, cv2.COLOR_RGB2BGR)
            has_alpha = False

        # 保存图像
        if export_format == 'JPEG':
            # JPEG不支持透明度
            cv2.imwrite(export_path, bgra[:, :, :3] if has_alpha else bgra,
                        [cv2.IMWRITE_JPEG_QUALITY, quality])
        elif export_format == 'PNG':
            # PNG支持透明度
            compression_level = min(9, max(0, 10 - quality // 10))
            if has_alpha:
                cv2.imwrite(export_path, bgra, 
                           [cv2.IMWRITE_PNG_COMPRESSION, compression_level])
            else:
                cv2.imwrite(export_path, bgra,
                           [cv2.IMWRITE_PNG_COMPRESSION, compression_level])
        elif export_format == 'TIFF':
            # TIFF支持透明度
            if has_alpha:
                cv2.imwrite(export_path, bgra)
            else:
                cv2.imwrite(export_path, bgra)
        elif export_format == 'BMP':
            # BMP不支持透明度
            cv2.imwrite(export_path, bgra[:, :, :3] if has_alpha else bgra)

        # 用户反馈
        if has_alpha:
            return {'success': True, 'message': f'带透明度的图像已导出到:\n{export_path}'}
        else:
            return {'success': True, 'message': f'图像已导出到:\n{export_path}'}

    except Exception as e:
        return {'success': False, 'error': f'导出图像时出错:\n{str(e)}'}
