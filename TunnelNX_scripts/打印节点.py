# f32bmp
#
# 打印图像节点（支持Windows打印）
# 007BFF
#Type:NeoScript

import numpy as np
import cv2
import os
import tempfile
import json
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
                              QCheckBox, QGroupBox, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt, QSize

# 检查系统类型
IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
    import win32print
    import win32ui
    import win32con
    from PIL import Image, ImageWin
else:
    try:
        import cups
    except ImportError:
        pass

def get_params():
    return {
        'printer_name': {
            'type': 'text',
            'label': '打印机名称',
            'value': ''
        },
        'media': {
            'type': 'dropdown',
            'label': '纸张类型',
            'options': ['A4', 'A3', 'Letter', 'Legal', '4x6', '5x7'],
            'value': 'A4'
        },
        'quality': {
            'type': 'dropdown',
            'label': '打印质量',
            'options': ['Draft', 'Normal', 'High'],
            'value': 'Normal'
        },
        'copies': {
            'type': 'slider',
            'label': '打印份数',
            'min': 1,
            'max': 10,
            'step': 1,
            'value': 1
        },
        'scale_to_fit': {
            'type': 'checkbox',
            'label': '缩放适应页面',
            'value': True
        },
        'color_mode': {
            'type': 'dropdown',
            'label': '颜色模式',
            'options': ['Color', 'Grayscale', 'Monochrome'],
            'value': 'Color'
        },
        'orientation': {
            'type': 'dropdown',
            'label': '页面方向',
            'options': ['Portrait', 'Landscape'],
            'value': 'Portrait'
        }
    }

def create_settings_widget(current_params, context, update_callback):
    """创建自定义打印设置界面"""
    widget = QWidget()
    main_layout = QVBoxLayout(widget)
    
    # 打印机选择部分
    printer_group = QGroupBox("打印机设置")
    printer_layout = QFormLayout(printer_group)
    
    # 获取可用打印机列表
    printers_combo = QComboBox()
    try:
        if IS_WINDOWS:
            printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        else:
            conn = cups.Connection()
            printers = list(conn.getPrinters().keys())
            
        for printer in printers:
            printers_combo.addItem(printer)
        
        # 选择当前设置的打印机
        current_printer = current_params.get('printer_name', '')
        if current_printer and current_printer in printers:
            printers_combo.setCurrentText(current_printer)
        elif printers:
            # 默认选择第一个打印机
            if IS_WINDOWS:
                default_printer = win32print.GetDefaultPrinter()
                if default_printer in printers:
                    printers_combo.setCurrentText(default_printer)
            else:
                conn = cups.Connection()
                default_printer = conn.getDefault()
                if default_printer and default_printer in printers:
                    printers_combo.setCurrentText(default_printer)
    except Exception as e:
        printers_combo.addItem("无法获取打印机列表")
    
    printer_layout.addRow("打印机:", printers_combo)
    
    # 纸张设置
    media_combo = QComboBox()
    for option in current_params.get('media', {}).get('options', ['A4', 'A3', 'Letter', 'Legal', '4x6', '5x7']):
        media_combo.addItem(option)
    media_combo.setCurrentText(current_params.get('media', {}).get('value', 'A4'))
    printer_layout.addRow("纸张类型:", media_combo)
    
    # 页面方向
    orientation_combo = QComboBox()
    for option in current_params.get('orientation', {}).get('options', ['Portrait', 'Landscape']):
        orientation_combo.addItem(option)
    orientation_combo.setCurrentText(current_params.get('orientation', {}).get('value', 'Portrait'))
    printer_layout.addRow("页面方向:", orientation_combo)
    
    # 打印质量
    quality_combo = QComboBox()
    for option in current_params.get('quality', {}).get('options', ['Draft', 'Normal', 'High']):
        quality_combo.addItem(option)
    quality_combo.setCurrentText(current_params.get('quality', {}).get('value', 'Normal'))
    printer_layout.addRow("打印质量:", quality_combo)
    
    # 颜色模式
    color_mode_combo = QComboBox()
    for option in current_params.get('color_mode', {}).get('options', ['Color', 'Grayscale', 'Monochrome']):
        color_mode_combo.addItem(option)
    color_mode_combo.setCurrentText(current_params.get('color_mode', {}).get('value', 'Color'))
    printer_layout.addRow("颜色模式:", color_mode_combo)
    
    # 打印选项组
    options_group = QGroupBox("打印选项")
    options_layout = QFormLayout(options_group)
    
    # 打印份数
    copies_spinbox = QSpinBox()
    copies_spinbox.setMinimum(1)
    copies_spinbox.setMaximum(10)
    copies_spinbox.setValue(current_params.get('copies', {}).get('value', 1))
    options_layout.addRow("打印份数:", copies_spinbox)
    
    # 缩放适应页面
    scale_checkbox = QCheckBox()
    scale_checkbox.setChecked(current_params.get('scale_to_fit', {}).get('value', True))
    options_layout.addRow("缩放适应页面:", scale_checkbox)
    
    # 连接信号
    def update_printer(text):
        update_callback('printer_name', text)
    
    def update_media(text):
        update_callback('media', text)
    
    def update_orientation(text):
        update_callback('orientation', text)
    
    def update_quality(text):
        update_callback('quality', text)
    
    def update_color_mode(text):
        update_callback('color_mode', text)
    
    def update_copies(value):
        update_callback('copies', value)
    
    def update_scale(state):
        update_callback('scale_to_fit', state == Qt.Checked)
    
    printers_combo.currentTextChanged.connect(update_printer)
    media_combo.currentTextChanged.connect(update_media)
    orientation_combo.currentTextChanged.connect(update_orientation)
    quality_combo.currentTextChanged.connect(update_quality)
    color_mode_combo.currentTextChanged.connect(update_color_mode)
    copies_spinbox.valueChanged.connect(update_copies)
    scale_checkbox.stateChanged.connect(update_scale)
    
    # 添加组到主布局
    main_layout.addWidget(printer_group)
    main_layout.addWidget(options_group)
    
    # 添加打印测试页按钮
    test_print_btn = QPushButton("打印测试页")
    test_print_btn.clicked.connect(lambda: sub_print_test_page(current_params, {}, context))
    main_layout.addWidget(test_print_btn)
    
    return widget

def process(inputs, params, context):
    # 打印节点只是传递输入，不修改图像
    if 'f32bmp' in inputs:
        return {'f32bmp': inputs['f32bmp']}
    return {}

def get_paper_size(paper_type):
    """获取纸张尺寸（单位：毫米）"""
    paper_sizes = {
        'A4': (210, 297),
        'A3': (297, 420),
        'Letter': (216, 279),
        'Legal': (216, 356),
        '4x6': (102, 152),
        '5x7': (127, 178)
    }
    return paper_sizes.get(paper_type, (210, 297))  # 默认A4

def print_image_windows(img_path, printer_name, options):
    """使用win32print在Windows上打印图像"""
    # 打开图像
    bmp = Image.open(img_path)
    
    # 设置打印机
    if not printer_name:
        printer_name = win32print.GetDefaultPrinter()
    
    # 创建设备上下文
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    
    # 开始打印作业
    hdc.StartDoc("ImgPlusPlus打印作业")
    hdc.StartPage()
    
    # 获取打印机分辨率
    dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX)
    dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY)
    
    # 获取打印区域大小（英寸）
    page_width = hdc.GetDeviceCaps(win32con.PHYSICALWIDTH) / dpi_x
    page_height = hdc.GetDeviceCaps(win32con.PHYSICALHEIGHT) / dpi_y
    
    # 计算打印图像的尺寸和位置
    img_width, img_height = bmp.size
    ratio = min(page_width / img_width, page_height / img_height) if options.get('scale_to_fit', True) else 1.0
    
    print_width = int(img_width * ratio * dpi_x)
    print_height = int(img_height * ratio * dpi_y)
    
    # 居中打印
    x_pos = int((page_width * dpi_x - print_width) / 2)
    y_pos = int((page_height * dpi_y - print_height) / 2)
    
    # 处理方向
    if options.get('orientation') == 'Landscape':
        hdc.SetMapMode(win32con.MM_ISOTROPIC)
        hdc.SetWindowExt((page_width * dpi_x, page_height * dpi_y))
        hdc.SetViewportExt((page_height * dpi_y, page_width * dpi_x))
        hdc.SetViewportOrg((0, page_width * dpi_x))
        # 交换宽高
        x_pos, y_pos = y_pos, page_width * dpi_x - x_pos - print_width
        print_width, print_height = print_height, print_width
    
    # 打印图像
    dib = ImageWin.Dib(bmp)
    dib.draw(hdc.GetHandleOutput(), (x_pos, y_pos, x_pos + print_width, y_pos + print_height))
    
    # 结束打印作业
    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()
    
    return True

def sub_打印图像(params, inputs, context):
    """打印当前图像"""
    # 检查是否有有效输入
    if not inputs or 'f32bmp' not in inputs:
        return {'success': False, 'error': '没有有效的图像数据可打印'}
    
    # 获取图像数据
    img = inputs['f32bmp']
    
    # 获取打印参数
    printer_name = params.get('printer_name', '')
    media = params.get('media', 'A4')
    quality = params.get('quality', 'Normal')
    copies = params.get('copies', 1)
    scale_to_fit = params.get('scale_to_fit', True)
    color_mode = params.get('color_mode', 'Color')
    orientation = params.get('orientation', 'Portrait')
    
    try:
        # 将图像转换为合适的格式并暂存
        if img.dtype == np.float32:
            img_to_print = (img[:, :, :3] * 255).clip(0, 255).astype(np.uint8)
        else:
            img_to_print = img[:, :, :3] if img.shape[2] > 3 else img
        
        # 根据颜色模式调整
        if color_mode == 'Grayscale':
            img_to_print = cv2.cvtColor(img_to_print, cv2.COLOR_RGB2GRAY)
        
        # 创建临时文件保存图像
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # 保存图像到临时文件
        cv2.imwrite(temp_path, cv2.cvtColor(img_to_print, cv2.COLOR_RGB2BGR))
        
        # 设置打印选项
        options = {
            'media': media,
            'copies': copies,
            'quality': quality,
            'color_mode': color_mode,
            'orientation': orientation,
            'scale_to_fit': scale_to_fit
        }
        
        if IS_WINDOWS:
            # Windows打印
            success = print_image_windows(temp_path, printer_name, options)
            message = f'打印作业已提交到打印机: {printer_name or "默认打印机"}'
        else:
            # CUPS打印（Linux/Mac）
            conn = cups.Connection()
            
            # 如果没有指定打印机，使用默认打印机
            if not printer_name:
                printer_name = conn.getDefault()
                if not printer_name:
                    # 如果没有默认打印机，使用第一个可用打印机
                    printers = conn.getPrinters()
                    if printers:
                        printer_name = list(printers.keys())[0]
                    else:
                        return {'success': False, 'error': '找不到可用的打印机'}
            
            # 设置CUPS打印选项
            cups_options = {
                'media': media,
                'copies': str(copies)
            }
            
            # 设置打印质量
            if quality == 'Draft':
                cups_options['print-quality'] = '3'
            elif quality == 'Normal':
                cups_options['print-quality'] = '4'
            elif quality == 'High':
                cups_options['print-quality'] = '5'
            
            # 设置颜色模式
            if color_mode == 'Grayscale':
                cups_options['print-color-mode'] = 'monochrome'
            elif color_mode == 'Monochrome':
                cups_options['print-color-mode'] = 'bi-level'
            else:
                cups_options['print-color-mode'] = 'color'
            
            # 设置页面方向
            cups_options['orientation-requested'] = '4' if orientation == 'Landscape' else '3'
            
            # 设置缩放选项
            if scale_to_fit:
                cups_options['fit-to-page'] = 'true'
            
            # 执行打印
            job_id = conn.printFile(printer_name, temp_path, "ImgPlusPlus Image", cups_options)
            message = f'打印作业已提交到 {printer_name}，作业ID: {job_id}'
            success = True
        
        # 删除临时文件
        os.unlink(temp_path)
        
        return {
            'success': success,
            'message': message
        }
        
    except Exception as e:
        return {'success': False, 'error': f'打印图像时出错: {str(e)}'}

def sub_打印设置(params, inputs, context):
    """显示打印设置对话框"""
    try:
        # 获取已保存的设置
        app = context['app']
        settings_path = os.path.join(context['work_folder'], 'print_settings.json')
        
        # 如果文件存在，加载设置
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                saved_settings = json.load(f)
                
            # 找到当前节点
            for node in app.nodes:
                if node['id'] == context['node_id']:
                    # 更新参数
                    for param_name, value in saved_settings.items():
                        if param_name in node['params']:
                            node['params'][param_name]['value'] = value
                    break
            
            return {
                'success': True,
                'message': '已加载上次的打印设置'
            }
        else:
            return {
                'success': False,
                'error': '未找到已保存的打印设置'
            }
            
    except Exception as e:
        return {'success': False, 'error': f'加载打印设置时出错: {str(e)}'}

def sub_保存打印设置(params, inputs, context):
    """保存当前打印设置"""
    try:
        # 保存当前设置
        settings_to_save = {
            'printer_name': params.get('printer_name', ''),
            'media': params.get('media', 'A4'),
            'quality': params.get('quality', 'Normal'),
            'copies': params.get('copies', 1),
            'scale_to_fit': params.get('scale_to_fit', True),
            'color_mode': params.get('color_mode', 'Color'),
            'orientation': params.get('orientation', 'Portrait')
        }
        
        # 保存到文件
        settings_path = os.path.join(context['work_folder'], 'print_settings.json')
        with open(settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)
        
        return {
            'success': True,
            'message': f'打印设置已保存到:\n{settings_path}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'保存打印设置时出错: {str(e)}'}

def sub_打印系统信息(params, inputs, context):
    """显示打印系统信息"""
    try:
        info_text = "打印系统信息:\n\n"
        
        if IS_WINDOWS:
            # Windows打印信息
            info_text += "操作系统: Windows\n\n"
            
            # 获取默认打印机
            default_printer = win32print.GetDefaultPrinter()
            info_text += f"默认打印机: {default_printer}\n\n"
            
            # 获取所有打印机列表
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)
            info_text += "可用打印机:\n"
            
            for i, printer in enumerate(printers):
                info_text += f"\n- {printer[2]}"
                if printer[2] == default_printer:
                    info_text += " (默认)"
        else:
            # CUPS打印信息
            conn = cups.Connection()
            
            # 获取打印机信息
            printers = conn.getPrinters()
            default_printer = conn.getDefault() or "未设置"
            
            # 获取服务器信息
            server_info = conn.getServer()
            
            # 拼接信息字符串
            info_text += f"CUPS服务器: {server_info}\n\n"
            info_text += f"默认打印机: {default_printer}\n\n"
            info_text += f"可用打印机:\n"
            
            for name, printer in printers.items():
                info_text += f"\n- {name}:\n"
                info_text += f"  • 信息: {printer.get('printer-info', '无')}\n"
                info_text += f"  • 位置: {printer.get('printer-location', '无')}\n"
                info_text += f"  • 状态: {printer.get('printer-state-message', '无')}\n"
        
        # 在context中获取应用实例
        app = context.get('app')
        if app:
            QMessageBox.information(app, "打印系统信息", info_text)
        
        return {
            'success': True,
            'message': '已显示打印系统信息'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'获取打印系统信息时出错: {str(e)}'}

def sub_print_test_page(params, inputs, context):
    """打印测试页"""
    try:
        # 获取打印机名称
        printer_name = params.get('printer_name', '')
        
        # 创建一个测试页图像
        test_img = np.ones((1000, 800, 3), dtype=np.uint8) * 255
        
        # 添加一些测试图形
        cv2.rectangle(test_img, (50, 50), (750, 950), (0, 0, 0), 2)
        cv2.rectangle(test_img, (100, 100), (700, 900), (0, 0, 255), 3)
        cv2.circle(test_img, (400, 500), 300, (255, 0, 0), 4)
        cv2.putText(test_img, "ImgPlusPlus 打印测试页", (150, 200),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
        cv2.putText(test_img, f"打印机: {printer_name or '默认打印机'}", (150, 250),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # 保存图像
        cv2.imwrite(temp_path, test_img)
        
        # 设置打印选项
        options = {
            'media': params.get('media', 'A4'),
            'quality': params.get('quality', 'Normal'),
            'orientation': params.get('orientation', 'Portrait'),
            'scale_to_fit': True
        }
        
        success = False
        message = ""
        
        if IS_WINDOWS:
            # Windows打印
            success = print_image_windows(temp_path, printer_name, options)
            message = f'测试页已发送到打印机: {printer_name or "默认打印机"}'
        else:
            # CUPS打印
            try:
                conn = cups.Connection()
                if not printer_name:
                    printer_name = conn.getDefault()
                    if not printer_name and conn.getPrinters():
                        printer_name = list(conn.getPrinters().keys())[0]
            except Exception as e:
                return {'success': False, 'error': f'连接到打印系统失败: {str(e)}'}
            
            if not printer_name:
                return {'success': False, 'error': '未选择打印机且找不到默认打印机'}
            
            # 设置CUPS打印选项
            cups_options = {
                'media': params.get('media', 'A4'),
                'copies': '1',
                'print-quality': '4',
                'orientation-requested': '3',
                'fit-to-page': 'true'
            }
            
            # 执行打印
            job_id = conn.printFile(printer_name, temp_path, "ImgPlusPlus Test Page", cups_options)
            message = f'测试页已发送到打印机 {printer_name}，作业ID: {job_id}'
            success = True
        
        # 删除临时文件
        os.unlink(temp_path)
        
        # 在context中获取应用实例
        app = context.get('app')
        if app:
            QMessageBox.information(app, "打印测试页", message)
        
        return {
            'success': success,
            'message': message
        }
        
    except Exception as e:
        return {'success': False, 'error': f'打印测试页时出错: {str(e)}'}