# f32bmp, value
# f32bmp, text
# NeoScript Demo: 展示自定义UI、上下文访问和预览叠加层交互
# 8080FF
# Type:NeoScript

import sys
import os
import time
import random

# Try to import PySide6 components safely
try:
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
                                   QPushButton, QCheckBox, QLineEdit, QFrame, QColorDialog,
                                   QSizePolicy, QComboBox)
    from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QRectF, QSize
    from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QPolygonF
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    # Define dummy classes if PySide6 is not available to avoid runtime errors on load
    if 'QWidget' not in locals(): QWidget = object
    if 'QVBoxLayout' not in locals(): QVBoxLayout = object
    if 'QLabel' not in locals(): QLabel = object
    print("NeoDemoScript Warning: PySide6 components not found. Custom UI and overlay drawing will be unavailable.")

import numpy as np

# --- Script Parameters ---
def get_params():
    """定义节点的参数"""
    return {
        "intensity": {"label": "效果强度", "type": "slider", "min": 0, "max": 100, "step": 1, "value": 50},
        "enable_overlay": {"label": "启用叠加层", "type": "checkbox", "value": True},
        "shape_type": {"label": "叠加层形状", "type": "dropdown", "options": ["矩形", "圆形", "随机多边形"], "value": "矩形"},
        "shape_color": {"label": "形状颜色", "type": "color", "value": "#FF8C00"}, # DarkOrange
        "info_text": {"label": "信息文本", "type": "text", "value": "Neo Demo"}
    }

# --- Custom Settings UI ---
if PYSIDE_AVAILABLE:
    class NeoSettingsWidget(QWidget):
        """为 NeoScript 创建的自定义设置小部件"""

        def __init__(self, current_params, context, update_callback, parent=None):
            super().__init__(parent)
            self.params = current_params.copy() # 存储本地参数副本
            self.context = context             # 存储应用程序上下文
            self.update_callback = update_callback # 存储更新参数的回调函数

            # 初始化用户界面
            self.init_ui()
            # 使用当前参数值更新UI元素
            self.update_ui_from_params()

        def init_ui(self):
            """构建设置面板的 UI 元素"""
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(8)

            # 1. 显示部分上下文信息
            context_frame = QFrame()
            context_frame.setFrameShape(QFrame.StyledPanel)
            context_layout = QVBoxLayout(context_frame)
            context_layout.addWidget(QLabel("<b>上下文信息 (示例):</b>"))
            context_layout.addWidget(QLabel(f"窗口: {self.context.get('window_size', QSize(0,0)).width()}x{self.context.get('window_size', QSize(0,0)).height()}"))
            context_layout.addWidget(QLabel(f"缩放: {self.context.get('zoom_level', 1.0):.2f}"))
            context_layout.addWidget(QLabel(f"图像尺寸: {self.context.get('original_image_size', QSize(0,0)).width()}x{self.context.get('original_image_size', QSize(0,0)).height()}"))
            context_layout.addWidget(QLabel(f"视口: {self.context.get('preview_viewport_size', QSize(0,0)).width()}x{self.context.get('preview_viewport_size', QSize(0,0)).height()}"))
            context_layout.addWidget(QLabel(f"平移: {self.context.get('preview_pan_offset', QPoint(0,0)).x()},{self.context.get('preview_pan_offset', QPoint(0,0)).y()}"))
            main_layout.addWidget(context_frame)

            # 2. 参数控制
            self.controls = {} # 用于存储对控件的引用

            # 强度滑块
            intensity_layout = QHBoxLayout()
            intensity_layout.addWidget(QLabel("效果强度:"))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.valueChanged.connect(lambda v: self.update_param("intensity", v))
            intensity_layout.addWidget(slider)
            intensity_label = QLabel("50")
            intensity_label.setFixedWidth(30)
            intensity_layout.addWidget(intensity_label)
            main_layout.addLayout(intensity_layout)
            self.controls["intensity"] = (slider, intensity_label)

            # 启用叠加层复选框
            checkbox = QCheckBox("启用叠加层")
            checkbox.toggled.connect(lambda c: self.update_param("enable_overlay", c))
            main_layout.addWidget(checkbox)
            self.controls["enable_overlay"] = checkbox

            # 形状类型下拉框
            shape_layout = QHBoxLayout()
            shape_layout.addWidget(QLabel("叠加层形状:"))
            combo = QComboBox()
            combo.addItems(get_params()["shape_type"]["options"]) # 从参数定义获取选项
            combo.currentTextChanged.connect(lambda t: self.update_param("shape_type", t))
            shape_layout.addWidget(combo)
            main_layout.addLayout(shape_layout)
            self.controls["shape_type"] = combo

            # 形状颜色选择器
            color_layout = QHBoxLayout()
            color_layout.addWidget(QLabel("形状颜色:"))
            color_button = QPushButton("选择颜色")
            color_button.clicked.connect(self.open_color_picker)
            color_label = QLabel() # 显示颜色预览
            color_label.setMinimumWidth(80)
            color_label.setAutoFillBackground(True)
            color_label.setFrameShape(QFrame.StyledPanel)
            color_layout.addWidget(color_button)
            color_layout.addWidget(color_label)
            color_layout.addStretch(1)
            main_layout.addLayout(color_layout)
            self.controls["shape_color"] = (color_button, color_label)

            # 信息文本输入框
            text_layout = QHBoxLayout()
            text_layout.addWidget(QLabel("信息文本:"))
            line_edit = QLineEdit()
            line_edit.textChanged.connect(lambda t: self.update_param("info_text", t))
            text_layout.addWidget(line_edit)
            main_layout.addLayout(text_layout)
            self.controls["info_text"] = line_edit

            # 3. 示例按钮
            test_button = QPushButton("执行 NeoScript 测试动作")
            test_button.clicked.connect(self.on_test_action)
            main_layout.addWidget(test_button)

            main_layout.addStretch(1) # 将所有内容推到顶部

        def update_param(self, name, value):
            """当 UI 控件值改变时，调用此方法更新参数"""
            # 更新本地存储和 UI（如果需要）
            self.params[name] = value
            if name == "intensity":
                slider, label = self.controls["intensity"]
                label.setText(str(value))
            elif name == "shape_color":
                button, label = self.controls["shape_color"]
                label.setText(value)
                try:
                    label.setStyleSheet(f"background-color: {value}; border: 1px solid grey;")
                except Exception as e:
                    print(f"无效的颜色值: {value}, {e}")
            # 调用回调函数，通知主程序参数已更改
            self.update_callback(name, value)

        def update_ui_from_params(self):
            """使用当前参数值初始化或更新 UI 控件的状态"""
            if "intensity" in self.controls:
                slider, label = self.controls["intensity"]
                value = self.params.get("intensity", 50)
                slider.setValue(value)
                label.setText(str(value))
            if "enable_overlay" in self.controls:
                self.controls["enable_overlay"].setChecked(self.params.get("enable_overlay", True))
            if "shape_type" in self.controls:
                self.controls["shape_type"].setCurrentText(self.params.get("shape_type", "矩形"))
            if "shape_color" in self.controls:
                 button, label = self.controls["shape_color"]
                 value = self.params.get("shape_color", "#FF8C00")
                 label.setText(value)
                 try:
                      label.setStyleSheet(f"background-color: {value}; border: 1px solid grey;")
                 except Exception as e:
                      print(f"更新UI时无效的颜色值: {value}, {e}")
            if "info_text" in self.controls:
                self.controls["info_text"].setText(self.params.get("info_text", "Neo Demo"))

        def open_color_picker(self):
            """打开颜色对话框以选择形状颜色"""
            initial_color = QColor(self.params.get("shape_color", "#FF8C00"))
            color = QColorDialog.getColor(initial_color, self, "选择形状颜色")
            if color.isValid():
                # 使用 #RRGGBB 格式更新参数
                self.update_param("shape_color", color.name(QColor.HexRgb))

        def on_test_action(self):
            """示例按钮的点击事件处理"""
            print("NeoScript 测试动作按钮被点击!")
            # 示例: 随机更改强度参数
            new_intensity = random.randint(0, 100)
            print(f"  随机设置强度为: {new_intensity}")
            # 更新参数（会同时更新UI和通知主程序）
            self.update_param("intensity", new_intensity)
            # 手动确保滑块和标签也更新（如果 update_param 没有处理）
            slider, label = self.controls["intensity"]
            slider.setValue(new_intensity)
            label.setText(str(new_intensity))

def create_settings_widget(current_params, context, update_callback):
    """ 由主程序调用以创建自定义设置小部件的工厂函数 """
    if PYSIDE_AVAILABLE:
        return NeoSettingsWidget(current_params, context, update_callback)
    else:
        # Fallback: 返回一个简单的标签表示缺少依赖
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("错误: PySide6 未安装，无法显示自定义 NeoScript 设置。"))
        return widget

# --- Node Processing ---
def process(inputs, params, context):
    """ 节点的主要处理逻辑 """
    start_time = time.time()

    # 1. 获取输入
    input_img = inputs.get('f32bmp') # 主要输入
    input_value = inputs.get('value') # 次要输入 (可能为 None)

    # 2. 获取参数
    intensity = params.get('intensity', 50) / 100.0 # 标准化强度
    info_text = params.get('info_text', '')

    # 3. 获取上下文信息 (示例)
    zoom = context.get('zoom_level', 1.0)
    app_instance = context.get('app') # 获取主应用实例 (谨慎使用!)

    # 4. 处理逻辑 (示例: 根据强度调整图像亮度，添加文本信息)
    output_img = None
    output_text = f"Input Value: {input_value}, Intensity: {intensity*100:.0f}%, Zoom: {zoom:.2f}"

    if input_img is not None:
        output_img = input_img.copy()
        # 示例处理：调整亮度
        output_img = np.clip(output_img + (intensity - 0.5) * 0.8, 0.0, 1.0)

        # 添加一些基于上下文的处理 (示例)
        win_width = context.get('window_size', QSize(0,0)).width()

        output_text += f"\nProcessed: {info_text}"
    else:
        print("  No 'f32bmp' input image found.")
        output_text += "\nNo input image."

    # 5. 准备输出
    outputs = {
        'f32bmp': output_img, # 主要图像输出
        'text': output_text    # 次要文本输出
    }

    end_time = time.time()

    return outputs


# --- Overlay Drawing ---
if PYSIDE_AVAILABLE:
    _polygon_points = None # 用于存储随机多边形的点
    _last_shape_type = None # 跟踪形状类型是否改变

    def draw_overlay(params, context):
        """ 在预览图像上绘制叠加层 """
        global _polygon_points, _last_shape_type

        painter = context.get('painter')
        if not painter: return

        widget_size = context.get('overlay_widget_size')
        if not widget_size or widget_size.width() == 0 or widget_size.height() == 0: return

        # 获取参数 (修正：从参数字典中提取 'value')
        enable_overlay = params.get('enable_overlay', {}).get('value', True)
        if not enable_overlay:
             return # 如果未启用，则不绘制

        intensity_param = params.get('intensity', {'value': 50})
        intensity = intensity_param.get('value', 50)
        shape_type_param = params.get('shape_type', {'value': '矩形'})
        shape_type = shape_type_param.get('value', '矩形')
        shape_color_param = params.get('shape_color', {'value': '#FF8C00'})
        shape_color_hex = shape_color_param.get('value', '#FF8C00')
        info_text_param = params.get('info_text', {'value': 'Neo Demo'})
        info_text = info_text_param.get('value', 'Neo Demo')

        # --- 绘制背景文本信息 ---
        painter.setPen(QPen(QColor(255, 255, 0, 180), 1)) # Yellow, semi-transparent
        font = painter.font()
        font.setPointSize(10 + intensity // 20)
        painter.setFont(font)
        painter.drawText(15, 25, f"Neo: {info_text} | Shape: {shape_type}")
        painter.drawText(15, 45 + font.pointSize(), f"Intensity: {intensity}")
        # 显示鼠标位置 (如果拖动)
        if context.get('_shape_dragging'):
            mouse_pos = context.get('_current_mouse_pos', QPoint(0,0))
            painter.drawText(widget_size.width() - 100, 25, f"Drag: {mouse_pos.x()},{mouse_pos.y()}")


        # --- 绘制交互式形状 ---
        shape_color = QColor(shape_color_hex)
        shape_size = 40 + intensity * 1.5 # 大小基于强度
        shape_half_size = shape_size / 2.0

        # 获取拖动状态和位置 (中心点)
        is_dragging = context.get('_shape_dragging', False)
        # 使用存储的中心点，如果没有则默认为部件中心
        center_x = context.get('_shape_center_x', widget_size.width() / 2.0)
        center_y = context.get('_shape_center_y', widget_size.height() / 2.0)
        shape_center = QPointF(center_x, center_y)

        # --- 存储计算出的中心点回 context，以便缓存 ---
        context['_shape_center_x'] = center_x
        context['_shape_center_y'] = center_y
        # ----------------------------------------------

        # 设置画笔和画刷
        pen_width = 2 + intensity // 25
        pen = QPen(shape_color, pen_width)
        if is_dragging:
            pen.setStyle(Qt.DashLine)
            brush_color = QColor(shape_color)
            brush_color.setAlpha(100) # Semi-transparent fill when dragging
            brush = QBrush(brush_color)
        else:
            pen.setStyle(Qt.SolidLine)
            brush = Qt.NoBrush # No fill when not dragging

        painter.setPen(pen)
        painter.setBrush(brush)

        # 绘制选定的形状
        interactive_shape_bounds = QRectF() # 用于碰撞检测

        if shape_type == "矩形":
            rect = QRectF(shape_center.x() - shape_half_size, shape_center.y() - shape_half_size, shape_size, shape_size)
            painter.drawRect(rect)
            interactive_shape_bounds = rect
        elif shape_type == "圆形":
            painter.drawEllipse(shape_center, shape_half_size, shape_half_size)
            interactive_shape_bounds = QRectF(shape_center.x() - shape_half_size, shape_center.y() - shape_half_size, shape_size, shape_size)
        elif shape_type == "随机多边形":
            # 如果形状类型刚改变或尚未生成点，则生成新的随机点
            if shape_type != _last_shape_type or _polygon_points is None:
                 num_points = 5 + intensity // 10 # 点的数量基于强度
                 _polygon_points = QPolygonF()
                 for i in range(num_points):
                     angle = (i / num_points) * 2 * np.pi
                     radius_variation = 0.7 + random.random() * 0.6 # 半径变化
                     p_x = shape_center.x() + np.cos(angle) * shape_half_size * radius_variation
                     p_y = shape_center.y() + np.sin(angle) * shape_half_size * radius_variation
                     _polygon_points.append(QPointF(p_x, p_y))
                 _last_shape_type = shape_type # 记录当前形状类型
            else:
                 # 如果形状类型未改变，平移现有点
                 dx = shape_center.x() - _polygon_points.boundingRect().center().x()
                 dy = shape_center.y() - _polygon_points.boundingRect().center().y()
                 _polygon_points.translate(dx, dy)

            painter.drawPolygon(_polygon_points)
            interactive_shape_bounds = _polygon_points.boundingRect()


        # 将交互区域边界存储在上下文中，供鼠标事件使用
        context['_interactive_shape_bounds'] = interactive_shape_bounds


# --- Overlay Interaction ---
if PYSIDE_AVAILABLE:
    def handle_overlay_mouse_press(params, context, trigger_update):
        """ 处理叠加层上的鼠标按下事件 """
        event = context.get('event')
        if not event: return False

        # 修正：从参数字典中提取 'value'
        enable_overlay = params.get('enable_overlay', {}).get('value', True)
        if not enable_overlay: return False # 如果叠加层未启用，不处理交互

        pos = event.position() # QPointF
        context['_current_mouse_pos'] = pos.toPoint() # Store for display
        interactive_bounds = context.get('_interactive_shape_bounds')

        if interactive_bounds and interactive_bounds.contains(pos):
            if event.button() == Qt.LeftButton:
                context['_shape_dragging'] = True
                # 记录鼠标按下位置相对于形状中心的偏移
                center_x = context.get('_shape_center_x', context['overlay_widget_size'].width() / 2.0)
                center_y = context.get('_shape_center_y', context['overlay_widget_size'].height() / 2.0)
                context['_drag_offset_x'] = pos.x() - center_x
                context['_drag_offset_y'] = pos.y() - center_y
                trigger_update() # 重绘以显示拖动状态
                return True # 事件已处理

        context['_shape_dragging'] = False # 如果点击在外部，重置拖动状态
        return False # 事件未处理


    def handle_overlay_mouse_move(params, context, trigger_update):
        """ 处理叠加层上的鼠标移动事件 """
        event = context.get('event')
        if not event: return False

        # 修正：从参数字典中提取 'value' (如果需要检查是否启用)
        # 在这个函数里，我们主要关心是否正在拖动，所以可能不需要检查 enable_overlay
        # 但为了保持一致性和健壮性，可以加上
        enable_overlay = params.get('enable_overlay', {}).get('value', True)
        if not enable_overlay and not context.get('_shape_dragging'): # 如果未启用且未在拖动，则不处理
             return False

        pos = event.position() # QPointF
        context['_current_mouse_pos'] = pos.toPoint() # Update display position

        if context.get('_shape_dragging'):
            # 计算新的中心点位置
            new_center_x = pos.x() - context.get('_drag_offset_x', 0)
            new_center_y = pos.y() - context.get('_drag_offset_y', 0)
            # 将新的中心点存储在上下文中
            context['_shape_center_x'] = new_center_x
            context['_shape_center_y'] = new_center_y

            trigger_update() # 重绘以更新形状位置
            return True # 事件已处理，因为正在拖动

        return False # 事件未处理


    def handle_overlay_mouse_release(params, context, trigger_update):
        """ 处理叠加层上的鼠标释放事件 """
        event = context.get('event')
        if not event: return False

        # 修正：从参数字典中提取 'value' (如果需要检查是否启用)
        enable_overlay = params.get('enable_overlay', {}).get('value', True)
        # 即使叠加层被禁用，如果正在拖动，也应该处理释放事件以停止拖动
        # if not enable_overlay: return False

        context['_current_mouse_pos'] = event.position().toPoint() # Update display position

        if context.get('_shape_dragging'):
            if event.button() == Qt.LeftButton:

                context['_shape_dragging'] = False
                # 可选: 在释放时执行操作，例如根据最终位置更新参数
                # final_x = context.get('_shape_center_x')
                # final_y = context.get('_shape_center_y')
                # print(f"  Final shape center: ({final_x:.1f}, {final_y:.1f})")
                # # Example: update intensity based on final Y position relative to height
                # widget_height = context.get('overlay_widget_size').height()
                # if widget_height > 0:
                #     new_intensity = int(np.clip((final_y / widget_height) * 100, 0, 100))
                #     print(f"  Updating intensity based on final position: {new_intensity}")
                #     # Need update_callback here to update the parameter in the app
                #     # update_callback("intensity", new_intensity) # This won't work directly

                trigger_update() # 重绘以显示非拖动状态
                return True # 事件已处理

        return False # 事件未处理

# Optional: Sub-operation example
def sub_randomize_color(params, input_data, context):
    """ 子操作示例：随机化形状颜色 """
    # 子操作目前无法直接修改节点参数并触发UI更新
    # 最好的方法是让子操作返回需要更新的参数字典
    new_color = QColor.fromHsv(random.randint(0, 359), random.randint(150, 255), random.randint(150, 255)).name(QColor.HexRgb)

    # 返回成功状态和消息，主程序可以（但目前不会）使用它来更新参数
    # A future improvement could involve returning {'update_params': {'shape_color': new_color}}
    return {'success': True, 'message': f'建议颜色已生成: {new_color} (需要主应用更新)'}