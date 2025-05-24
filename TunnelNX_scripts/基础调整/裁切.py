#f32bmp
#f32bmp
#图像裁切节点 - 提供专业的裁切GUI界面
#48B6FF
#Type:NeoScript
#SupportedFeatures:CustomizedPreviewPopup=True,PreviewPopupFunction="show_crop_dialog"
print("--- Loading/Reloading 裁切.py ---")
import sys # Add this import as well for flushing
import numpy as np
from PIL import Image, ImageQt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QSlider, QSpinBox, QDialogButtonBox,
                              QComboBox, QCheckBox, QFrame, QSizePolicy, QApplication,
                              QMessageBox)
from PySide6.QtCore import Qt, QRect, QSize, QEvent, QPoint, Signal, Slot
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QCursor, QPainterPath
# ... (其他 imports)
from PySide6.QtCore import Qt, QRect, QSize, QEvent, QPoint, Signal, Slot, QTimer # <-- 添加 QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QCursor, QPainterPath

# --- 全局常量 ---
MIN_CROP_SIZE = 10 # 最小裁切尺寸（显示坐标系）
HANDLE_SIZE = 10   # 调整手柄大小

class CropPreviewWidget(QFrame):
    """
    负责显示图像、绘制裁切框、处理用户交互（创建、移动、调整大小）。
    内部坐标系基于显示图像。
    """
    crop_rect_changed = Signal(QRect) # 发送原始坐标系的裁切矩形

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel) # 使用 StyledPanel 以获得更好的主题兼容性
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus) # 允许接收键盘事件（如果需要）

        # 图像数据
        self.original_data = None # 存储原始 numpy 数组
        self.original_size = QSize(0, 0)
        self.display_pixmap = None # 用于显示的 QPixmap
        self.display_size = QSize(0, 0) # 图像在控件中的实际显示尺寸
        self.image_offset = QPoint(0, 0) # 图像在控件中的绘制偏移量（用于居中）

        # 裁切状态
        self.crop_rect = QRect() # 基于显示坐标系 (相对于 display_pixmap 的左上角)
        self.is_initialized = False # 标记是否已根据控件大小初始化

        # 交互状态
        self.drag_start_pos = QPoint() # 鼠标按下时的控件坐标
        self.drag_start_crop_rect = QRect() # 拖拽开始时的裁切框（显示坐标系）
        self.drag_mode = None  # None, 'create', 'move', 'resize'
        self.resize_edge = None  # 'top', 'bottom', 'left', 'right', 'topleft', etc.

        # 显示选项
        self.aspect_ratio = None  # None 表示自由裁切, 否则为 float (width / height)
        self.guides_enabled = True
        self.background_dimming = True

        self._cursor_map = {
            'topleft': Qt.SizeFDiagCursor, 'topright': Qt.SizeBDiagCursor,
            'bottomleft': Qt.SizeBDiagCursor, 'bottomright': Qt.SizeFDiagCursor,
            'top': Qt.SizeVerCursor, 'bottom': Qt.SizeVerCursor,
            'left': Qt.SizeHorCursor, 'right': Qt.SizeHorCursor,
            'inside': Qt.SizeAllCursor, 'outside': Qt.ArrowCursor
        }

    def set_image(self, image_data):
        """设置要裁切的原始图像数据 (numpy array)。"""
        if not isinstance(image_data, np.ndarray):
            self.original_data = None
            self.original_size = QSize(0, 0)
            self.display_pixmap = None
            self.is_initialized = False
            self.update()
            return

        self.original_data = image_data
        self.original_size = QSize(image_data.shape[1], image_data.shape[0])

        # 转换 numpy 数组为 QPixmap 以便显示
        height, width = image_data.shape[:2]
        channels = image_data.shape[2] if image_data.ndim == 3 else 1

        if image_data.dtype == np.float32 or image_data.dtype == np.float64:
            image_for_display = np.clip(image_data * 255, 0, 255).astype(np.uint8)
        elif image_data.dtype == np.uint8:
            image_for_display = image_data
        else:
             # 不支持的类型，显示错误提示
             self.original_data = None
             self.original_size = QSize(0, 0)
             self.display_pixmap = QPixmap(400, 400)
             self.display_pixmap.fill(Qt.gray)
             painter = QPainter(self.display_pixmap)
             painter.setPen(Qt.white)
             painter.drawText(self.display_pixmap.rect(), Qt.AlignCenter, "Unsupported Image Type")
             painter.end()
             self.is_initialized = False
             self.update()
             return

        if channels == 3:
            qimage = QImage(image_for_display.data, width, height, width * 3, QImage.Format_RGB888).rgbSwapped()
        elif channels == 4:
             qimage = QImage(image_for_display.data, width, height, width * 4, QImage.Format_RGBA8888)
        elif channels == 1:
             qimage = QImage(image_for_display.data, width, height, width, QImage.Format_Grayscale8)
        else:
             # 不支持的通道数
             self.original_data = None
             self.original_size = QSize(0,0)
             # ... (显示错误提示) ...
             return

        self.display_pixmap = QPixmap.fromImage(qimage)
        self.is_initialized = False # 需要重新计算尺寸和初始化裁切框
        self.update() # 触发 resizeEvent 和 paintEvent

    def _initialize_crop_rect(self):
        """在控件尺寸确定后，初始化或重置裁切框为覆盖整个显示图像。"""
        if self.display_pixmap and self.width() > 0 and self.height() > 0:
            self.calculate_display_size()
            self.crop_rect = QRect(0, 0, self.display_size.width(), self.display_size.height())
            self.is_initialized = True
            self.notify_crop_change()
            self.update()

    def reset_crop_rect(self):
        """重置裁切框为覆盖整个显示图像。"""
        self._initialize_crop_rect()

    def calculate_display_size(self):
        """计算图像在控件中的最佳显示尺寸和偏移量以保持纵横比并居中。"""
        if not self.display_pixmap or self.width() <= 0 or self.height() <= 0:
            self.display_size = QSize(0, 0)
            self.image_offset = QPoint(0, 0)
            return

        widget_size = self.size()
        pixmap_size = self.display_pixmap.size()

        scaled_size = pixmap_size.scaled(widget_size, Qt.KeepAspectRatio)

        self.display_size = scaled_size
        self.image_offset = QPoint(
            (widget_size.width() - scaled_size.width()) // 2,
            (widget_size.height() - scaled_size.height()) // 2
        )

    def get_original_crop_rect(self):
        """将当前显示坐标系的裁切框转换为原始图像坐标系。"""
        # 修正：使用 'is None' 检查 numpy 数组是否存在
        if self.original_data is None or not self.crop_rect.isValid() or \
           self.display_size.width() <= 0 or self.display_size.height() <= 0:
            # 如果没有有效数据或裁切框，返回原始图像的全尺寸矩形
            if self.original_size.isValid():
                return QRect(0, 0, self.original_size.width(), self.original_size.height())
            return QRect()

        # 避免除零错误
        if self.display_size.width() == 0 or self.display_size.height() == 0:
            return QRect(0, 0, self.original_size.width(), self.original_size.height())


        scale_x = self.original_size.width() / self.display_size.width()
        scale_y = self.original_size.height() / self.display_size.height()

        original_x = int(self.crop_rect.x() * scale_x)
        original_y = int(self.crop_rect.y() * scale_y)
        original_width = int(self.crop_rect.width() * scale_x)
        original_height = int(self.crop_rect.height() * scale_y)

        # 确保在原始图像边界内
        original_x = max(0, min(original_x, self.original_size.width()))
        original_y = max(0, min(original_y, self.original_size.height()))
        # 宽度和高度计算终点，再约束终点，然后反算宽高，避免负值或零值
        x1 = max(original_x + 1, min(original_x + original_width, self.original_size.width()))
        y1 = max(original_y + 1, min(original_y + original_height, self.original_size.height()))
        final_width = x1 - original_x
        final_height = y1 - original_y

        # 确保宽高至少为1
        final_width = max(1, final_width)
        final_height = max(1, final_height)

        return QRect(original_x, original_y, final_width, final_height)

    def set_crop_rect_from_original(self, original_rect):
        """根据原始坐标系的矩形设置显示坐标系的裁切框。"""
        if not self.is_initialized or not self.original_size.isValid() or \
           self.display_size.width() <= 0 or self.display_size.height() <= 0:
            # print("Warning: Cannot set crop rect from original before widget is initialized or image loaded.")
            # 可以在显示后延迟调用此函数
            return

        if not isinstance(original_rect, QRect) or not original_rect.isValid():
             self.reset_crop_rect() # 无效输入则重置
             return

        scale_x = self.display_size.width() / self.original_size.width()
        scale_y = self.display_size.height() / self.original_size.height()

        display_x = int(original_rect.x() * scale_x)
        display_y = int(original_rect.y() * scale_y)
        display_width = int(original_rect.width() * scale_x)
        display_height = int(original_rect.height() * scale_y)

        self.crop_rect = QRect(display_x, display_y, display_width, display_height)
        self.constrain_crop_rect() # 确保在显示范围内
        self.notify_crop_change()
        self.update()

    def set_aspect_ratio(self, ratio):
        """设置裁切区域的纵横比 (width / height)。"""
        self.aspect_ratio = ratio
        if self.aspect_ratio is not None and self.crop_rect.isValid():
            self.apply_aspect_ratio(self.crop_rect.center()) # 以中心调整
            self.constrain_crop_rect()
            self.notify_crop_change()
            self.update()

    def set_guides_enabled(self, enabled):
        self.guides_enabled = enabled
        self.update()

    def set_background_dimming(self, enabled):
        self.background_dimming = enabled
        self.update()

    # --- 事件处理 ---

    def resizeEvent(self, event):
        """控件大小改变时，重新计算显示尺寸并可能需要重新初始化裁切框。"""
        super().resizeEvent(event)
        if self.display_pixmap:
            old_display_size = self.display_size
            self.calculate_display_size()
            if not self.is_initialized:
                self._initialize_crop_rect()
            elif old_display_size != self.display_size:
                # 如果显示尺寸变化，需要按比例调整现有裁切框
                if old_display_size.width() > 0 and old_display_size.height() > 0:
                    scale_x = self.display_size.width() / old_display_size.width()
                    scale_y = self.display_size.height() / old_display_size.height()
                    self.crop_rect = QRect(
                        int(self.crop_rect.x() * scale_x),
                        int(self.crop_rect.y() * scale_y),
                        int(self.crop_rect.width() * scale_x),
                        int(self.crop_rect.height() * scale_y)
                    )
                    self.constrain_crop_rect()
                    self.notify_crop_change()
                else:
                    # 如果旧尺寸无效，则重置
                    self.reset_crop_rect()
        self.update()

    def paintEvent(self, event):
        """绘制背景、图像、遮罩、裁切框和辅助线。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. 绘制背景
        painter.fillRect(self.rect(), self.palette().color(self.backgroundRole())) # 使用主题背景色

        # 2. 绘制图像 (如果存在)
        if not self.display_pixmap:
            painter.setPen(self.palette().color(self.foregroundRole()))
            painter.drawText(self.rect(), Qt.AlignCenter, "No Image")
            return

        # 图像绘制区域
        image_draw_rect = QRect(self.image_offset, self.display_size)
        painter.drawPixmap(image_draw_rect, self.display_pixmap)

        # 3. 绘制裁切相关元素 (如果裁切框有效)
        if self.crop_rect.isValid() and self.is_initialized:
            # 裁切框在控件中的绝对坐标
            absolute_crop_rect = self.crop_rect.translated(self.image_offset)

            # 3.1 绘制暗色遮罩
            if self.background_dimming:
                mask_path = QPainterPath()
                # 使用整个控件区域作为外框，避免图像外区域也被绘制
                mask_path.addRect(self.rect())
                hole_path = QPainterPath()
                hole_path.addRect(absolute_crop_rect)
                mask_path = mask_path.subtracted(hole_path)
                painter.fillPath(mask_path, QColor(0, 0, 0, 150))

            # 3.2 绘制裁切框边框
            pen = QPen(QColor(255, 255, 255), 1, Qt.SolidLine) # 细一点的线
            painter.setPen(pen)
            painter.drawRect(absolute_crop_rect)

            # 3.3 绘制调整手柄 (小方块)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255))
            half_handle = HANDLE_SIZE // 2
            handles = self.get_handle_rects(absolute_crop_rect)
            for rect in handles.values():
                 painter.drawRect(rect)

            # 3.4 绘制参考线 (三分法)
            if self.guides_enabled:
                pen.setStyle(Qt.DashLine)
                pen.setColor(QColor(255, 255, 255, 120)) # 更淡的颜色
                painter.setPen(pen)
                # 水平线
                y1 = absolute_crop_rect.top() + absolute_crop_rect.height() / 3
                y2 = absolute_crop_rect.top() + 2 * absolute_crop_rect.height() / 3
                painter.drawLine(absolute_crop_rect.left(), y1, absolute_crop_rect.right(), y1)
                painter.drawLine(absolute_crop_rect.left(), y2, absolute_crop_rect.right(), y2)
                # 垂直线
                x1 = absolute_crop_rect.left() + absolute_crop_rect.width() / 3
                x2 = absolute_crop_rect.left() + 2 * absolute_crop_rect.width() / 3
                painter.drawLine(x1, absolute_crop_rect.top(), x1, absolute_crop_rect.bottom())
                painter.drawLine(x2, absolute_crop_rect.top(), x2, absolute_crop_rect.bottom())

        painter.end()

    def mousePressEvent(self, event):
        if not self.is_initialized or not self.display_pixmap or event.button() != Qt.LeftButton:
            return

        pos = event.pos()
        # 将控件坐标转换为相对于显示图像左上角的坐标
        image_local_pos = pos - self.image_offset
        absolute_crop_rect = self.crop_rect.translated(self.image_offset)

        # 检查是否点击了调整手柄
        edge = self.get_resize_edge(pos, absolute_crop_rect)
        if edge:
            self.drag_mode = 'resize'
            self.resize_edge = edge
            self.drag_start_pos = pos
            self.drag_start_crop_rect = QRect(self.crop_rect) # 复制当前裁切框
            return

        # 检查是否点击了裁切区域内部
        if self.crop_rect.contains(image_local_pos):
            self.drag_mode = 'move'
            self.drag_start_pos = pos
            self.drag_start_crop_rect = QRect(self.crop_rect)
            return

        # 检查是否点击了图像区域内部（但在裁切框外部）-> 创建新框
        image_rect = QRect(QPoint(0,0), self.display_size)
        if image_rect.contains(image_local_pos):
            self.drag_mode = 'create'
            self.drag_start_pos = image_local_pos # 使用图像局部坐标作为起点
            # 创建一个无效的矩形，将在 mouseMoveEvent 中更新
            self.crop_rect = QRect(self.drag_start_pos, QSize(0, 0))
            self.update()

    def mouseMoveEvent(self, event):
        if not self.drag_mode:
            # 更新悬停光标
            self.update_cursor(event.pos())
            return

        pos = event.pos()
        image_local_pos = pos - self.image_offset

        if self.drag_mode == 'create':
            # 从起点创建矩形
            self.crop_rect = QRect(self.drag_start_pos, image_local_pos).normalized()
            if self.aspect_ratio is not None:
                 self.apply_aspect_ratio(self.drag_start_pos) # 以起点为固定点调整
            self.constrain_crop_rect()
            self.update()

        elif self.drag_mode == 'move':
            delta = pos - self.drag_start_pos
            self.crop_rect = self.drag_start_crop_rect.translated(delta)
            self.constrain_crop_rect()
            self.update()

        elif self.drag_mode == 'resize':
            # 获取固定点（对角）和当前鼠标在图像上的局部坐标
            new_rect_ref = self.drag_start_crop_rect # 参考拖拽开始时的矩形
            current_local_pos = image_local_pos

            fixed_point = QPoint()
            if 'left' in self.resize_edge: fixed_point.setX(new_rect_ref.right())
            else: fixed_point.setX(new_rect_ref.left())
            if 'top' in self.resize_edge: fixed_point.setY(new_rect_ref.bottom())
            else: fixed_point.setY(new_rect_ref.top())

            # 计算调整后的点 (adjusted_point)，先假设等于当前鼠标位置
            adjusted_point = QPoint(current_local_pos)

            # 如果有纵横比约束，调整 adjusted_point
            if self.aspect_ratio is not None:
                dx = adjusted_point.x() - fixed_point.x()
                dy = adjusted_point.y() - fixed_point.y()

                # --- 精确的纵横比调整逻辑 (保持原样) ---
                if dx == 0 or dy == 0: pass
                elif 'left' in self.resize_edge or 'right' in self.resize_edge:
                    new_dy = dx / self.aspect_ratio if self.aspect_ratio != 0 else 0
                    if ('top' in self.resize_edge and new_dy < 0) or \
                       ('bottom' in self.resize_edge and new_dy > 0):
                         adjusted_point.setY(fixed_point.y() + new_dy)
                    elif ('top' in self.resize_edge and new_dy > 0) or \
                       ('bottom' in self.resize_edge and new_dy < 0):
                         new_dx = dy * self.aspect_ratio
                         adjusted_point.setX(fixed_point.x() + new_dx)
                    # --- 新增：处理仅拖拽左右边缘的情况 ---
                    elif self.resize_edge == 'left' or self.resize_edge == 'right':
                         adjusted_point.setY(fixed_point.y() + new_dy)


                elif 'top' in self.resize_edge or 'bottom' in self.resize_edge:
                     new_dx = dy * self.aspect_ratio
                     if ('left' in self.resize_edge and new_dx < 0) or \
                        ('right' in self.resize_edge and new_dx > 0):
                          adjusted_point.setX(fixed_point.x() + new_dx)
                     elif ('left' in self.resize_edge and new_dx > 0) or \
                        ('right' in self.resize_edge and new_dx < 0):
                          new_dy = dx / self.aspect_ratio if self.aspect_ratio != 0 else 0
                          adjusted_point.setY(fixed_point.y() + new_dy)
                     # --- 新增：处理仅拖拽上下边缘的情况 ---
                     elif self.resize_edge == 'top' or self.resize_edge == 'bottom':
                          adjusted_point.setX(fixed_point.x() + new_dx)


            # --- 修正：根据 resize_edge 构建最终矩形 ---
            final_rect = QRect(self.drag_start_crop_rect) # 从拖拽开始时的矩形拷贝

            # 使用可能经过纵横比调整的 adjusted_point 更新相应的边或角
            if self.resize_edge == 'left':
                final_rect.setLeft(adjusted_point.x())
            elif self.resize_edge == 'right':
                final_rect.setRight(adjusted_point.x())
            elif self.resize_edge == 'top':
                final_rect.setTop(adjusted_point.y())
            elif self.resize_edge == 'bottom':
                final_rect.setBottom(adjusted_point.y())
            elif self.resize_edge == 'topleft':
                 final_rect.setTopLeft(adjusted_point)
            elif self.resize_edge == 'topright':
                 final_rect.setTopRight(adjusted_point)
            elif self.resize_edge == 'bottomleft':
                 final_rect.setBottomLeft(adjusted_point)
            elif self.resize_edge == 'bottomright':
                 final_rect.setBottomRight(adjusted_point)

            # 标准化矩形（处理拖拽反向导致宽高为负的情况）
            final_rect = final_rect.normalized()
            # --- 结束修正 ---

            # 应用新矩形，但要检查最小尺寸
            if final_rect.width() >= MIN_CROP_SIZE and final_rect.height() >= MIN_CROP_SIZE:
                 self.crop_rect = final_rect
                 self.constrain_crop_rect() # 确保在界内
                 self.update() # 触发重绘

        # 实时通知变化 (移到 resize 逻辑块外部)
        self.notify_crop_change()



    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag_mode:
            # 检查最终尺寸是否过小
            if self.crop_rect.width() < MIN_CROP_SIZE or self.crop_rect.height() < MIN_CROP_SIZE:
                # 如果是从创建模式释放且尺寸过小，则视为无效，重置
                if self.drag_mode == 'create':
                    self.reset_crop_rect()
                else: # 如果是移动或调整大小导致过小，恢复到拖拽开始时的状态
                    self.crop_rect = self.drag_start_crop_rect
                    self.constrain_crop_rect() # 确保开始状态也在界内
            else:
                 self.constrain_crop_rect() # 确保最终位置在界内

            self.drag_mode = None
            self.resize_edge = None
            self.notify_crop_change() # 最终确认变化
            self.update_cursor(event.pos()) # 更新光标
            self.update()

    # --- 辅助方法 ---

    def update_cursor(self, pos):
        """根据鼠标位置更新光标形状。"""
        if not self.is_initialized or not self.display_pixmap:
            self.setCursor(Qt.ArrowCursor)
            return

        absolute_crop_rect = self.crop_rect.translated(self.image_offset)
        edge = self.get_resize_edge(pos, absolute_crop_rect)

        if edge:
            self.setCursor(self._cursor_map.get(edge, Qt.ArrowCursor))
        elif absolute_crop_rect.contains(pos):
            self.setCursor(self._cursor_map['inside'])
        else:
            self.setCursor(self._cursor_map['outside'])

    def get_resize_edge(self, pos, absolute_crop_rect):
        """确定鼠标位置在裁切框的哪个边缘或角落。"""
        if not self.crop_rect.isValid():
            return None

        handles = self.get_handle_rects(absolute_crop_rect)
        for edge, rect in handles.items():
            if rect.contains(pos):
                return edge # 返回角落或边缘的名称 ('topleft', 'top', etc.)

        return None

    def get_handle_rects(self, absolute_crop_rect):
        """获取所有调整手柄的 QRect。"""
        handles = {}
        cx = absolute_crop_rect.center().x()
        cy = absolute_crop_rect.center().y()
        l, t = absolute_crop_rect.left(), absolute_crop_rect.top()
        r, b = absolute_crop_rect.right(), absolute_crop_rect.bottom()
        w, h = absolute_crop_rect.width(), absolute_crop_rect.height()
        half_handle = HANDLE_SIZE // 2

        # 角落
        handles['topleft'] = QRect(l - half_handle, t - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['topright'] = QRect(r - half_handle, t - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['bottomleft'] = QRect(l - half_handle, b - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['bottomright'] = QRect(r - half_handle, b - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        # 边缘中心
        handles['top'] = QRect(cx - half_handle, t - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['bottom'] = QRect(cx - half_handle, b - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['left'] = QRect(l - half_handle, cy - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        handles['right'] = QRect(r - half_handle, cy - half_handle, HANDLE_SIZE, HANDLE_SIZE)
        return handles


    def constrain_crop_rect(self):
        """确保裁切矩形（显示坐标系）在显示图像的边界内。"""
        if not self.display_size.isValid() or self.display_size.width() <= 0 or self.display_size.height() <= 0:
            return # 无法约束

        display_bounds = QRect(0, 0, self.display_size.width(), self.display_size.height())
        self.crop_rect = self.crop_rect.intersected(display_bounds)

        # 确保最小尺寸 (可选，mouseRelease 已处理，但这里可以再加一层保险)
        # if self.crop_rect.width() < MIN_CROP_SIZE: self.crop_rect.setWidth(MIN_CROP_SIZE)
        # if self.crop_rect.height() < MIN_CROP_SIZE: self.crop_rect.setHeight(MIN_CROP_SIZE)
        # self.crop_rect = self.crop_rect.intersected(display_bounds) # 再次约束，防止放大超出边界


    def apply_aspect_ratio(self, fixed_point):
        """根据当前 aspect_ratio 调整 crop_rect 大小，保持 fixed_point 不动。"""
        if self.aspect_ratio is None or not self.crop_rect.isValid():
            return

        current_width = self.crop_rect.width()
        current_height = self.crop_rect.height()

        if current_width <= 0 or current_height <= 0: return

        # 尝试基于宽度计算高度
        new_height = current_width / self.aspect_ratio
        # 尝试基于高度计算宽度
        new_width = current_height * self.aspect_ratio

        # 通常选择使面积减小的调整，或者根据拖拽方向判断，这里简化处理：优先匹配宽度
        # 一个更复杂的逻辑会考虑哪个维度变化更大来决定基准
        final_width = current_width
        final_height = new_height

        # 从固定点设置新的宽高
        if fixed_point == self.crop_rect.topLeft():
            self.crop_rect.setSize(QSize(final_width, final_height))
        elif fixed_point == self.crop_rect.topRight():
             self.crop_rect.setTopLeft(QPoint(self.crop_rect.left() + current_width - final_width, self.crop_rect.top()))
             self.crop_rect.setSize(QSize(final_width, final_height))
        elif fixed_point == self.crop_rect.bottomLeft():
             self.crop_rect.setTopLeft(QPoint(self.crop_rect.left(), self.crop_rect.top() + current_height - final_height))
             self.crop_rect.setSize(QSize(final_width, final_height))
        elif fixed_point == self.crop_rect.bottomRight():
             self.crop_rect.setTopLeft(QPoint(self.crop_rect.left() + current_width - final_width, self.crop_rect.top() + current_height - final_height))
             self.crop_rect.setSize(QSize(final_width, final_height))
        else: # 中心或其他点，简化为从左上角调整
            self.crop_rect.setSize(QSize(final_width, final_height))


    def notify_crop_change(self):
        """发送原始坐标系的裁切矩形信号。"""
        if self.is_initialized:
            original_rect = self.get_original_crop_rect()
            self.crop_rect_changed.emit(original_rect)


class CropDialog(QDialog):
    """图像裁切对话框，包含 CropPreviewWidget 和控制选项。"""

    def __init__(self, image_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图像裁切")
        self.setMinimumSize(800, 600)
        self.setModal(True) # 模态对话框

        self.original_data = image_data # 保存原始数据以供 get_result 使用

        # 创建UI
        self.setup_ui()

        # 设置图像到预览部件
        self.crop_widget.set_image(image_data)

        # 连接信号
        self.crop_widget.crop_rect_changed.connect(self.update_crop_info)
        self.reset_button.clicked.connect(self.crop_widget.reset_crop_rect)
        self.ratio_combo.currentIndexChanged.connect(self.on_ratio_changed)
        self.guide_check.stateChanged.connect(self.on_guide_changed)
        self.dim_check.stateChanged.connect(self.on_dim_changed)

        # 立即更新一次初始信息
        # 需要延迟一点点，等待 crop_widget 初始化完成并发出第一次信号
        # 或者在 crop_widget 内部初始化完成后主动调用 update_crop_info
        # 这里采用简单方式：在 set_image 后手动获取一次
        if self.crop_widget.is_initialized:
             self.update_crop_info(self.crop_widget.get_original_crop_rect())
        else:
            # 如果还没初始化，第一次 crop_rect_changed 信号会更新它
            pass


    def setup_ui(self):
        """设置UI布局。"""
        main_layout = QVBoxLayout(self)

        # --- 裁切预览部件 ---
        self.crop_widget = CropPreviewWidget(self)
        main_layout.addWidget(self.crop_widget, 1) # 占据大部分空间

        # --- 信息与控制面板 (底部) ---
        control_panel = QFrame(self)
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_layout = QHBoxLayout(control_panel)

        # 尺寸显示
        size_label = QLabel("尺寸 (原始):")
        self.size_label = QLabel("0 × 0")
        control_layout.addWidget(size_label)
        control_layout.addWidget(self.size_label)
        control_layout.addSpacing(20)

        # 位置显示
        pos_label = QLabel("左上角 (原始):")
        self.pos_label = QLabel("0, 0")
        control_layout.addWidget(pos_label)
        control_layout.addWidget(self.pos_label)
        control_layout.addSpacing(20)

        # 纵横比选择
        ratio_label = QLabel("纵横比:")
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItem("自由", None)
        self.ratio_combo.addItem("1:1", 1.0)
        self.ratio_combo.addItem("4:3", 4.0/3.0)
        self.ratio_combo.addItem("3:4", 3.0/4.0)
        self.ratio_combo.addItem("16:9", 16.0/9.0)
        self.ratio_combo.addItem("9:16", 9.0/16.0)
        # 可以添加更多预设或自定义输入
        control_layout.addWidget(ratio_label)
        control_layout.addWidget(self.ratio_combo)
        control_layout.addSpacing(20)

        # 显示选项
        self.guide_check = QCheckBox("辅助线")
        self.guide_check.setChecked(True)
        control_layout.addWidget(self.guide_check)

        self.dim_check = QCheckBox("暗化背景")
        self.dim_check.setChecked(True)
        control_layout.addWidget(self.dim_check)

        control_layout.addStretch(1) # 将按钮推到右边

        # 重置按钮
        self.reset_button = QPushButton("重置")
        control_layout.addWidget(self.reset_button)

        main_layout.addWidget(control_panel)

        # --- 对话框按钮 ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept) # 接受 = 关闭对话框
        button_box.rejected.connect(self.reject) # 拒绝 = 关闭对话框
        main_layout.addWidget(button_box)

    @Slot(QRect)
    def update_crop_info(self, original_rect):
        """更新底部信息面板的显示（使用原始坐标系）。"""
        if original_rect.isValid():
            self.size_label.setText(f"{original_rect.width()} × {original_rect.height()}")
            self.pos_label.setText(f"{original_rect.x()}, {original_rect.y()}")
        else:
            self.size_label.setText("N/A")
            self.pos_label.setText("N/A")

    @Slot(int)
    def on_ratio_changed(self, index):
        """纵横比下拉框选择变化。"""
        ratio = self.ratio_combo.itemData(index)
        self.crop_widget.set_aspect_ratio(ratio)

    @Slot(int)
    def on_guide_changed(self, state):
        """辅助线复选框变化。"""
        self.crop_widget.set_guides_enabled(state == Qt.Checked)

    @Slot(int)
    def on_dim_changed(self, state):
        """背景暗化复选框变化。"""
        self.crop_widget.set_background_dimming(state == Qt.Checked)

    def get_original_crop_params(self):
        """获取原始坐标系的裁切参数 (x, y, w, h)。"""
        rect = self.crop_widget.get_original_crop_rect()
        if rect.isValid():
            return {
                'crop_x': rect.x(),
                'crop_y': rect.y(),
                'crop_width': rect.width(),
                'crop_height': rect.height()
            }
        return None # 无效裁切

    def get_result(self):
        """根据当前裁切框（原始坐标系）裁切原始图像数据。"""
        if self.original_data is None:
            return None

        params = self.get_original_crop_params()
        if params is None:
             # 如果裁切无效，可以考虑返回原图或 None，这里返回 None 表示未裁切
             # 或者返回原图？取决于调用者的期望
             return self.original_data.copy() # 返回原图副本

        x = params['crop_x']
        y = params['crop_y']
        w = params['crop_width']
        h = params['crop_height']

        # 使用 numpy 切片进行裁切
        # 注意 numpy 的切片是 [y:y+h, x:x+w]
        img_h, img_w = self.original_data.shape[:2]

        # 再次进行边界保护（理论上 get_original_crop_rect 已处理，但多一层保险）
        y0 = max(0, min(y, img_h))
        x0 = max(0, min(x, img_w))
        y1 = max(y0, min(y + h, img_h))
        x1 = max(x0, min(x + w, img_w))

        if y1 > y0 and x1 > x0:
             return self.original_data[y0:y1, x0:x1].copy()
        else:
             # 裁切结果为空或无效，返回 None 或原图
             print(f"Warning: Invalid crop slice calculated in get_result: y={y0}:{y1}, x={x0}:{x1}")
             return self.original_data.copy() # 返回原图副本


# --- 节点入口函数 ---

def show_crop_dialog(node, context):
    """
    节点右键菜单调用的函数：
    1. 获取上游原始输入图像。
    2. 创建并显示 CropDialog。
    3. 如果用户确认，获取原始坐标裁切参数（整数），保存到 node['params']。
    4. 同时，获取裁切后的图像用于即时预览，存入 node['processed_outputs']。
    5. 触发应用刷新预览。
    """
    app = context.get('app')
    if not app:
        print("Error: QApplication instance not found in context.")
        return

    # 1. 获取上游原始输入
    image_data = None
    try:
        node_inputs = app.get_node_inputs(node)
        if node_inputs and 'f32bmp' in node_inputs:
            image_data = node_inputs['f32bmp']
    except Exception as e:
        print(f"Info: Could not get precise node inputs via app API: {e}. Falling back.")

    if image_data is None:
        if node and 'inputs' in node and node['inputs'] and 'f32bmp' in node['inputs']:
            image_data = node['inputs']['f32bmp']

    if image_data is None:
        QMessageBox.warning(app, "裁切错误", "找不到可用的输入图像进行裁切。请确保上游节点已连接并运行。")
        return

    # --- 数据类型检查和转换 ---
    if not isinstance(image_data, np.ndarray):
         QMessageBox.warning(app, "裁切错误", f"输入图像数据类型无效: {type(image_data)}，需要 numpy ndarray。")
         return
    if image_data.ndim < 2 or image_data.ndim > 3:
        QMessageBox.warning(app, "裁切错误", f"输入图像维度无效: {image_data.ndim}，需要 2 或 3。")
        return

    # 2. 创建对话框
    dialog = CropDialog(image_data, app) # 将原始 numpy 数组传给对话框

    # 3. 尝试加载已保存的参数来设置初始裁切框
    params = node.get('params', {})
    required_keys = ('crop_x', 'crop_y', 'crop_width', 'crop_height')
    params_valid = True
    if not all(k in params and isinstance(params[k], dict) and 'value' in params[k] for k in required_keys):
        params_valid = False

    if params_valid:
        try:
            original_rect = QRect(
                int(params['crop_x']['value']), int(params['crop_y']['value']),
                int(params['crop_width']['value']), int(params['crop_height']['value'])
            )
            # --- 修改开始：使用 QTimer.singleShot 延迟调用 ---
            # 将 widget 和 rect 作为参数传递给 lambda 函数，避免闭包问题
            widget = dialog.crop_widget
            QTimer.singleShot(0, lambda w=widget, r=original_rect: w.set_crop_rect_from_original(r))
            # --- 修改结束 ---
        except (ValueError, TypeError) as e:
            print(f"Warning: Failed to load saved crop parameters (will use default): {e}")
    # else: # 参数无效或不存在时，widget 会在 resizeEvent 中自动初始化



    # 4. 显示对话框并处理结果
    if dialog.exec_() == QDialog.Accepted:
        # 5. 用户确认，保存参数并更新预览
        new_params = dialog.get_original_crop_params() # 获取原始坐标参数字典 (值为整数)
        if new_params:
            # --- 恢复：手动保存为 {'value': ...} 结构 ---
            if 'params' not in node or not isinstance(node.get('params'), dict):
                node['params'] = {}
            for key, value in new_params.items():
                if key in node['params'] and isinstance(node['params'][key], dict):
                        node['params'][key]['value'] = value
                else:
                        node['params'][key] = {'value': value}
            print(f"--- show_crop_dialog: Updated node['params'] with value structure: {node['params']} ---") # 修改日志
            # --- 结束恢复 ---

            # 6. 生成裁切后的预览图像
            cropped_preview = dialog.get_result()
            if cropped_preview is not None:
                node.setdefault('processed_outputs', {})['f32bmp'] = cropped_preview
            else:
                    node.setdefault('processed_outputs', {})['f32bmp'] = image_data

            # 7. 触发主程序重新处理节点图
            print(f"--- show_crop_dialog: Triggering process_node_graph for node {node.get('id', 'N/A')} ---")
            app.process_node_graph(changed_nodes=[node])

        else:
                print("Info: Crop dialog accepted, but no valid crop parameters obtained.")
def process(inputs, params, context=None):
    """
    节点实际运行时调用的函数：
    1. 获取当前输入图像。
    2. 读取节点保存的裁切参数 ('params')，从 {'value':...} 结构中获取值。
    3. 如果参数有效，执行裁切并返回结果。
    4. 否则，返回原始输入图像。
    """
    # print(f"--- Process function called for Crop node ---"); sys.stdout.flush() # 可以保留或移除 flush
    # print(f"Received inputs keys: {list(inputs.keys()) if inputs else 'None'}"); sys.stdout.flush()
    # print(f"Received params: {params}"); sys.stdout.flush() # 注意这里收到的应该是扁平结构

    img = inputs.get('f32bmp')
    if img is None:
        # print("Process: Input 'f32bmp' is None. Returning {'f32bmp': None}."); sys.stdout.flush()
        return {'f32bmp': None}

    # ---健壮性检查---
    if not isinstance(img, np.ndarray):
        # print(f"Process Error: Input not ndarray ({type(img)}). Returning original."); sys.stdout.flush()
        return {'f32bmp': img}
    if img.ndim < 2 or img.ndim > 3:
        # print(f"Process Error: Input dim not supported ({img.ndim}). Returning original."); sys.stdout.flush()
        return {'f32bmp': img}

    # 2. 读取裁切参数 (注意：主程序 process_node 已经提取了 'value')
    if not isinstance(params, dict) or not params:
        # print("Process: No valid params. Returning original."); sys.stdout.flush()
        return {'f32bmp': img} # No params, return original

    required_keys = ('crop_x', 'crop_y', 'crop_width', 'crop_height')
    if not all(key in params for key in required_keys):
        # print("Process: Missing params. Returning original."); sys.stdout.flush()
        return {'f32bmp': img} # Missing params, return original

    # 3. 执行裁切
    try:
        # --- 恢复：直接使用 params 字典中的值，因为主程序已经提取了 'value' ---
        x = int(params['crop_x'])
        y = int(params['crop_y'])
        w = int(params['crop_width'])
        h = int(params['crop_height'])
        # print(f"Process: Using crop params: x={x}, y={y}, w={w}, h={h}"); sys.stdout.flush()

        img_h, img_w = img.shape[:2]
        # print(f"Process: Input image shape: H={img_h}, W={img_w}"); sys.stdout.flush()

        # 确保边界合法
        y0 = max(0, min(y, img_h))
        x0 = max(0, min(x, img_w))
        y1 = max(y0, min(y + h, img_h))
        x1 = max(x0, min(x + w, img_w))
        # print(f"Process: Calculated slice: y0={y0}, y1={y1}, x0={x0}, x1={x1}"); sys.stdout.flush()

        # 检查计算出的切片是否有效
        if y1 > y0 and x1 > x0:
            cropped = img[y0:y1, x0:x1].copy()
            # print(f"Process: Cropping successful. Output shape: {cropped.shape}. Returning cropped."); sys.stdout.flush()
            return {'f32bmp': cropped}
        else:
            # print(f"Process Warning: Calculated crop slice invalid (y={y0}:{y1}, x={x0}:{x1}). Returning original."); sys.stdout.flush()
            return {'f32bmp': img}

    except (ValueError, TypeError, KeyError, IndexError) as e:
            # print(f"Process Error accessing params or cropping: {e}. Params: {params}. Returning original."); sys.stdout.flush()
            return {'f32bmp': img}
    except Exception as e:
        import traceback
        # print(f"Process Error: Unexpected error during cropping: {e}\n{traceback.format_exc()}. Returning original."); sys.stdout.flush()
        return {'f32bmp': img}