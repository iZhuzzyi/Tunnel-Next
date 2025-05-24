# f32bmp
# f32bmp
# 使用贝塞尔曲线调整图像亮度映射。
# 87CEEB
# Type:NeoScript
#SupportedFeatures:PerfSensitive=True
目前有些性能问题所以故意在这里写一行字不让它通过脚本加载，实在想用请移除本行！
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QPolygonF
from numba import jit, prange, float32, int32
# --- Constants for Bezier --- 
HANDLE_SIZE = 4
ANCHOR_SIZE = 6
# Default points: (ax, ay, in_dx, in_dy, out_dx, out_dy)
# Handles point horizontally inward initially
BEZIER_DEFAULT_POINTS = [
    (0.0, 0.0, 0.0, 0.0, 0.15, 0.0),
    (1.0, 1.0, -0.15, 0.0, 0.0, 0.0)
]

# --- Curve Editor Widget (Bezier Version) ---
class CurveWidget(QWidget):
    """一个用于显示和编辑贝塞尔曲线的自定义QWidget。"""
    curveChanged = Signal(list) # 当曲线点改变时发出信号

    def __init__(self, initial_points=None, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # --- Convert old format / Initialize points --- 
        processed_points = []
        raw_points = initial_points if initial_points else BEZIER_DEFAULT_POINTS
        for p in raw_points:
            if len(p) == 2: # Old format (x, y)
                # Convert to new format with default horizontal handles
                # Handle default depends on position (start, middle, end)
                # This simple conversion assumes only start/end or needs refinement
                # For now, let's assume it's only the default linear points
                if p[0] == 0.0:
                    processed_points.append(tuple(BEZIER_DEFAULT_POINTS[0]))
                elif p[0] == 1.0:
                     processed_points.append(tuple(BEZIER_DEFAULT_POINTS[1]))
                else: # Intermediate point - needs better default handle logic
                     processed_points.append((p[0], p[1], -0.1, 0.0, 0.1, 0.0))
            elif len(p) == 6: # New format
                processed_points.append(tuple(p))
            else:
                print(f"CurveWidget: Invalid point format encountered: {p}")
        
        # Sort points based on anchor x-coordinate
        self._points = sorted(processed_points, key=lambda p: p[0])
        # --------------------------------------------

        self._dragging_point_index = -1
        self._dragging_handle_type = None # 'in' or 'out' or None for anchor
        self._drag_offset = QPointF(0, 0) # Offset for smooth dragging
        self.setMouseTracking(True) # 需要跟踪鼠标移动

    def setPoints(self, points):
        """设置新的控制点并重绘。"""
        # Similar processing as in __init__ to ensure format
        processed_points = []
        for p in points:
            if len(p) == 6:
                processed_points.append(tuple(p))
            elif len(p) == 2: # Handle conversion if needed (e.g., loading old saves)
                 if p[0] == 0.0: processed_points.append(tuple(BEZIER_DEFAULT_POINTS[0]))
                 elif p[0] == 1.0: processed_points.append(tuple(BEZIER_DEFAULT_POINTS[1]))
                 else: processed_points.append((p[0], p[1], -0.1, 0.0, 0.1, 0.0))
            else:
                 print(f"CurveWidget.setPoints: Invalid point format: {p}")
        self._points = sorted(processed_points, key=lambda p: p[0])
        self.update() # 请求重绘

    def getPoints(self):
        """获取当前的控制点 (包含控制柄信息)。"""
        return self._points

    def paintEvent(self, event):
        """绘制贝塞尔曲线、锚点、控制柄和背景网格。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), QColor("#333333"))

        # 绘制网格 (same as before)
        grid_color = QColor("#555555")
        pen = QPen(grid_color, 0.5, Qt.DotLine)
        painter.setPen(pen)
        steps = 10
        w_step = self.width() / steps
        h_step = self.height() / steps
        for i in range(1, steps):
            painter.drawLine(int(i * w_step), 0, int(i * w_step), self.height())
            painter.drawLine(0, int(i * h_step), self.width(), int(i * h_step))

        # --- Draw Bezier Curve --- 
        if len(self._points) >= 2:
            curve_color = QColor("#FFFFFF")
            pen = QPen(curve_color, 2)
            painter.setPen(pen)
            
            path = QPainterPath()
            start_anchor = self._points[0]
            path.moveTo(self._normToWidget(start_anchor[0], start_anchor[1]))
            
            for i in range(len(self._points) - 1):
                p1_data = self._points[i]
                p2_data = self._points[i+1]
                
                # Control point 1 (absolute coords, normalized)
                cp1_x = p1_data[0] + p1_data[4] # anchor x + out_dx
                cp1_y = p1_data[1] + p1_data[5] # anchor y + out_dy
                
                # Control point 2 (absolute coords, normalized)
                cp2_x = p2_data[0] + p2_data[2] # anchor x + in_dx
                cp2_y = p2_data[1] + p2_data[3] # anchor y + in_dy
                
                # End point (anchor 2)
                end_x = p2_data[0]
                end_y = p2_data[1]
                
                # Convert points to widget coordinates
                widget_cp1 = self._normToWidget(cp1_x, cp1_y)
                widget_cp2 = self._normToWidget(cp2_x, cp2_y)
                widget_end = self._normToWidget(end_x, end_y)
                
                path.cubicTo(widget_cp1, widget_cp2, widget_end)
            
            painter.drawPath(path)
        # -------------------------

        # --- Draw Anchors and Handles --- 
        anchor_color = QColor("#87CEEB") # Sky blue for anchors
        handle_color = QColor("#FFA500") # Orange for handles
        handle_line_color = QColor("#AAAAAA")

        for i, p_data in enumerate(self._points):
            anchor_x, anchor_y, in_dx, in_dy, out_dx, out_dy = p_data
            widget_anchor = self._normToWidget(anchor_x, anchor_y)
            
            # Calculate absolute handle positions (normalized)
            in_handle_x = anchor_x + in_dx
            in_handle_y = anchor_y + in_dy
            out_handle_x = anchor_x + out_dx
            out_handle_y = anchor_y + out_dy
            
            widget_in_handle = self._normToWidget(in_handle_x, in_handle_y)
            widget_out_handle = self._normToWidget(out_handle_x, out_handle_y)
            
            # Draw handle lines (only if handle is not at anchor)
            painter.setPen(QPen(handle_line_color, 1, Qt.SolidLine))
            if in_dx != 0 or in_dy != 0:
                 if i > 0: # No in-handle line for the first point usually
                      painter.drawLine(widget_anchor, widget_in_handle)
            if out_dx != 0 or out_dy != 0:
                  if i < len(self._points) - 1: # No out-handle line for the last point usually
                       painter.drawLine(widget_anchor, widget_out_handle)
                       
            # Draw handles (circles)
            painter.setBrush(QBrush(handle_color))
            painter.setPen(Qt.NoPen)
            if in_dx != 0 or in_dy != 0:
                 if i > 0:
                     painter.drawEllipse(widget_in_handle, HANDLE_SIZE, HANDLE_SIZE)
            if out_dx != 0 or out_dy != 0:
                 if i < len(self._points) - 1:
                     painter.drawEllipse(widget_out_handle, HANDLE_SIZE, HANDLE_SIZE)
            
            # Draw anchor point (rectangle/square)
            painter.setBrush(QBrush(anchor_color))
            anchor_rect = QRectF(0, 0, ANCHOR_SIZE * 1.5, ANCHOR_SIZE * 1.5)
            anchor_rect.moveCenter(widget_anchor)
            painter.drawRect(anchor_rect)
        # ----------------------------

    def mousePressEvent(self, event):
        """处理鼠标按下 - 检测锚点或控制柄点击，或右键删除锚点。"""
        click_pos_widget = event.pos()
        min_dist_sq = (max(ANCHOR_SIZE, HANDLE_SIZE) + 5)**2 # 点击检测半径 (平方距离)

        # --- Handle Left Click (Dragging/Adding) ---
        if event.button() == Qt.LeftButton:
            self._dragging_point_index = -1
            self._dragging_handle_type = None

            # 1. Check handles first
            for i, p_data in enumerate(self._points):
                anchor_x, anchor_y, in_dx, in_dy, out_dx, out_dy = p_data
                # Check IN handle
                if (in_dx != 0 or in_dy != 0) and i > 0:
                    in_handle_x = anchor_x + in_dx
                    in_handle_y = anchor_y + in_dy
                    widget_in_handle = self._normToWidget(in_handle_x, in_handle_y)
                    delta_x = float(click_pos_widget.x()) - widget_in_handle.x()
                    delta_y = float(click_pos_widget.y()) - widget_in_handle.y()
                    if (delta_x**2 + delta_y**2) < min_dist_sq:
                        self._dragging_point_index = i
                        self._dragging_handle_type = 'in'
                        self._drag_offset = widget_in_handle - click_pos_widget
                        self.update()
                        return
                # Check OUT handle
                if (out_dx != 0 or out_dy != 0) and i < len(self._points) - 1:
                    out_handle_x = anchor_x + out_dx
                    out_handle_y = anchor_y + out_dy
                    widget_out_handle = self._normToWidget(out_handle_x, out_handle_y)
                    delta_x = float(click_pos_widget.x()) - widget_out_handle.x()
                    delta_y = float(click_pos_widget.y()) - widget_out_handle.y()
                    if (delta_x**2 + delta_y**2) < min_dist_sq:
                        self._dragging_point_index = i
                        self._dragging_handle_type = 'out'
                        self._drag_offset = widget_out_handle - click_pos_widget
                        self.update()
                        return

            # 2. Check anchors if no handle was clicked
            for i, p_data in enumerate(self._points):
                anchor_x, anchor_y = p_data[0], p_data[1]
                widget_anchor = self._normToWidget(anchor_x, anchor_y)
                delta_x = float(click_pos_widget.x()) - widget_anchor.x()
                delta_y = float(click_pos_widget.y()) - widget_anchor.y()
                if (delta_x**2 + delta_y**2) < min_dist_sq:
                    if 0 < i < len(self._points) - 1: # Can drag non-endpoints
                        self._dragging_point_index = i
                        self._dragging_handle_type = None # Dragging anchor
                        self._drag_offset = widget_anchor - click_pos_widget
                        self.update()
                        return
                    else: # Clicked on endpoint
                        return

            # 3. Add new point if clicked on empty space
            click_x_norm, click_y_norm = self._widgetToNorm(click_pos_widget)
            insert_index = -1
            for i in range(len(self._points) - 1):
                if self._points[i][0] < click_x_norm < self._points[i+1][0]:
                    insert_index = i + 1
                    break
            if insert_index != -1:
                prev_p = self._points[insert_index - 1]
                next_p = self._points[insert_index]
                dist_prev = click_x_norm - prev_p[0]
                dist_next = next_p[0] - click_x_norm
                default_in_dx = -min(dist_prev / 3.0, 0.15)
                default_out_dx = min(dist_next / 3.0, 0.15)
                new_point_data = (click_x_norm, click_y_norm, default_in_dx, 0.0, default_out_dx, 0.0)
                self._points.insert(insert_index, new_point_data)
                self.curveChanged.emit(self._points)
                self.update()
                # Optionally start dragging the new point
                # self._dragging_point_index = insert_index ...
        
        # --- Handle Right Click (Deleting) ---
        elif event.button() == Qt.RightButton:
            for i in reversed(range(len(self._points))): # Iterate backwards for safe deletion
                 # Only allow deleting non-endpoints
                 if 0 < i < len(self._points) - 1:
                     anchor_x, anchor_y = self._points[i][0], self._points[i][1]
                     widget_anchor = self._normToWidget(anchor_x, anchor_y)
                     delta_x = float(click_pos_widget.x()) - widget_anchor.x()
                     delta_y = float(click_pos_widget.y()) - widget_anchor.y()
                     if (delta_x**2 + delta_y**2) < min_dist_sq:
                         del self._points[i]
                         print(f"删除索引为 {i} 的点")
                         self.curveChanged.emit(self._points)
                         self.update()
                         return # Exit after deleting one point

    def mouseMoveEvent(self, event):
        """处理鼠标移动 - 更新拖动的锚点或控制柄位置（带对称控制柄）。"""
        if self._dragging_point_index == -1:
            return

        # Manual calculation for target position to avoid QPoint + QPointF error
        current_pos_widget = event.pos()
        target_x = float(current_pos_widget.x()) + self._drag_offset.x()
        target_y = float(current_pos_widget.y()) + self._drag_offset.y()
        target_widget_pos = QPointF(target_x, target_y)

        # target_widget_pos = event.pos() + self._drag_offset # Original failing line
        target_x_norm, target_y_norm = self._widgetToNorm(target_widget_pos)

        i = self._dragging_point_index
        p_data = list(self._points[i]) # Convert to list for modification
        anchor_x, anchor_y = p_data[0], p_data[1]

        if self._dragging_handle_type == 'in':
            # Ensure handle doesn't go beyond anchor x or widget bounds implicitly
            target_x_norm = min(anchor_x, max(0.0, target_x_norm))
            target_y_norm = max(0.0, min(1.0, target_y_norm))
            # Update IN handle deltas
            new_in_dx = target_x_norm - anchor_x
            new_in_dy = target_y_norm - anchor_y
            p_data[2] = new_in_dx
            p_data[3] = new_in_dy
            # Symmetrically update OUT handle
            p_data[4] = -new_in_dx
            p_data[5] = -new_in_dy
            self._points[i] = tuple(p_data) # Update point data
            self.curveChanged.emit(self._points)
            self.update()

        elif self._dragging_handle_type == 'out':
            # Ensure handle doesn't go beyond anchor x or widget bounds implicitly
            target_x_norm = max(anchor_x, min(1.0, target_x_norm))
            target_y_norm = max(0.0, min(1.0, target_y_norm))
            # Update OUT handle deltas
            new_out_dx = target_x_norm - anchor_x
            new_out_dy = target_y_norm - anchor_y
            p_data[4] = new_out_dx
            p_data[5] = new_out_dy
             # Symmetrically update IN handle
            p_data[2] = -new_out_dx
            p_data[3] = -new_out_dy
            self._points[i] = tuple(p_data) # Update point data
            self.curveChanged.emit(self._points)
            self.update()

        elif self._dragging_handle_type is None: # Dragging anchor
            # Get X bounds from neighbors
            prev_x = self._points[i-1][0]
            next_x = self._points[i+1][0]
            # Clamp anchor position
            target_x_norm = max(prev_x + 1e-6, min(next_x - 1e-6, target_x_norm))
            target_y_norm = max(0.0, min(1.0, target_y_norm))
            # Update anchor position (handles move implicitly)
            p_data[0] = target_x_norm
            p_data[1] = target_y_norm
            self._points[i] = tuple(p_data) # Update point data
            self.curveChanged.emit(self._points)
            self.update()

    def mouseReleaseEvent(self, event):
        """处理鼠标释放 - 停止拖动。"""
        if event.button() == Qt.LeftButton and self._dragging_point_index != -1:
            print(f"停止拖动点/控制柄 {self._dragging_point_index}")
            self._dragging_point_index = -1
            self._dragging_handle_type = None
            self._drag_offset = QPointF(0, 0)
            self.update() # Redraw to remove potential highlighting
        pass # Keep the pass here for potential future right-click logic

    def _normToWidget(self, x_norm, y_norm):
        """将归一化坐标 (0-1) 转换为 QWidget 坐标 (QPointF)。"""
        # Ensure input is float
        x_norm_f = float(x_norm)
        y_norm_f = float(y_norm)
        x = x_norm_f * self.width()
        y = (1.0 - y_norm_f) * self.height() # Y轴反转
        return QPointF(x, y)

    def _widgetToNorm(self, point):
        """将 QWidget 坐标 (QPointF) 转换为归一化坐标 (0-1)。"""
        if self.width() == 0 or self.height() == 0:
            return 0.0, 0.0 # Avoid division by zero
        x_norm = point.x() / self.width()
        y_norm = 1.0 - (point.y() / self.height()) # Y轴反转
        # 再次钳制确保在 [0, 1] 范围内
        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))
        return x_norm, y_norm

# --- 优化的贝塞尔曲线计算函数 ---
@jit(float32[:,:](float32[:,:,:], float32[:]), nopython=True, parallel=True)
def bezier_curve_parallel(control_points, t_values):
    """使用并行计算直接评估贝塞尔曲线。
    
    Args:
        control_points: 控制点数组，形状为(n_segments, 4, 2)，每段曲线4个控制点(P0,P1,P2,P3)
        t_values: 要评估的t值，范围[0,1]
        
    Returns:
        贝塞尔曲线上的点，形状为(len(t_values), 2)
    """
    n_segments = control_points.shape[0]
    result = np.zeros((len(t_values), 2), dtype=np.float32)
    
    for i in prange(len(t_values)):
        t = t_values[i]
        # 确定t值属于哪个段
        segment_idx = min(int(t * n_segments), n_segments - 1)
        # 重新规范化t到该段内的[0,1]
        local_t = t * n_segments - segment_idx
        
        # 获取当前段的控制点
        p0 = control_points[segment_idx, 0]
        p1 = control_points[segment_idx, 1]
        p2 = control_points[segment_idx, 2]
        p3 = control_points[segment_idx, 3]
        
        # 计算贝塞尔点
        omt = 1.0 - local_t
        omt2 = omt * omt
        omt3 = omt2 * omt
        t2 = local_t * local_t
        t3 = t2 * local_t
        
        result[i] = omt3 * p0 + 3.0 * omt2 * local_t * p1 + 3.0 * omt * t2 * p2 + t3 * p3
    
    return result

@jit(float32[:,:,:](float32[:,:]), nopython=True)
def prepare_control_points(points_data):
    """准备贝塞尔曲线计算所需的控制点格式。
    
    Args:
        points_data: 曲线控制点数据，(n_points, 6)格式
        
    Returns:
        形状为(n_segments, 4, 2)的控制点数组
    """
    n_points = points_data.shape[0]
    n_segments = n_points - 1
    result = np.zeros((n_segments, 4, 2), dtype=np.float32)
    
    for i in range(n_segments):
        # 第一个锚点
        p0 = points_data[i, 0:2]  
        # 第二个锚点
        p3 = points_data[i+1, 0:2]
        
        # 第一个控制点 = 锚点 + 出控制柄
        p1 = np.zeros(2, dtype=np.float32)
        p1[0] = p0[0] + points_data[i, 4]  # anchor_x + out_dx
        p1[1] = p0[1] + points_data[i, 5]  # anchor_y + out_dy
        
        # 第二个控制点 = 锚点 + 入控制柄
        p2 = np.zeros(2, dtype=np.float32)
        p2[0] = p3[0] + points_data[i+1, 2]  # anchor_x + in_dx
        p2[1] = p3[1] + points_data[i+1, 3]  # anchor_y + in_dy
        
        # 保存当前段的控制点
        result[i, 0] = p0
        result[i, 1] = p1
        result[i, 2] = p2
        result[i, 3] = p3
    
    return result

@jit(float32(float32, float32[:,:,:]), nopython=True)
def evaluate_bezier_at_x(x_value, control_points):
    """在给定x值处评估贝塞尔曲线的y值。
    
    使用二分查找找到最接近给定x值的t参数，然后计算对应的y值。
    
    Args:
        x_value: 要评估的x值 (0-1)
        control_points: 控制点数组，形状为(n_segments, 4, 2)
        
    Returns:
        对应的y值
    """
    # 如果x_value超出范围，直接返回边界值
    if x_value <= 0.0:
        return control_points[0, 0, 1]  # 返回第一个点的y值
    if x_value >= 1.0:
        return control_points[-1, 3, 1]  # 返回最后一个点的y值
    
    # 确定x_value所在的段
    n_segments = control_points.shape[0]
    segment_idx = 0
    
    # 首先尝试直接找到包含x_value的段
    for i in range(n_segments):
        if control_points[i, 0, 0] <= x_value <= control_points[i, 3, 0]:
            segment_idx = i
            break
    else:
        # 如果没找到精确的段，选择最接近的段
        for i in range(n_segments - 1):
            if control_points[i, 3, 0] < x_value < control_points[i+1, 0, 0]:
                # 选择更接近的端点所在的段
                if (x_value - control_points[i, 3, 0]) < (control_points[i+1, 0, 0] - x_value):
                    segment_idx = i
                else:
                    segment_idx = i + 1
                break
    
    # 获取当前段的控制点
    p0 = control_points[segment_idx, 0]
    p1 = control_points[segment_idx, 1]
    p2 = control_points[segment_idx, 2]
    p3 = control_points[segment_idx, 3]
    
    # 二分查找t值使得B(t).x接近x_value
    t_low, t_high = 0.0, 1.0
    t_mid = 0.5
    max_iterations = 30  # 防止无限循环
    
    for _ in range(max_iterations):
        # 计算中点t对应的贝塞尔点
        t = t_mid
        omt = 1.0 - t
        omt2 = omt * omt
        omt3 = omt2 * omt
        t2 = t * t
        t3 = t2 * t
        
        point_x = omt3 * p0[0] + 3.0 * omt2 * t * p1[0] + 3.0 * omt * t2 * p2[0] + t3 * p3[0]
        
        # 精度足够或者已达最大迭代次数
        if abs(point_x - x_value) < 1e-6:
            break
        
        # 调整搜索范围
        if point_x < x_value:
            t_low = t_mid
        else:
            t_high = t_mid
        
        t_mid = (t_low + t_high) / 2.0
    
    # 使用最终的t计算y值
    t = t_mid
    omt = 1.0 - t
    omt2 = omt * omt
    omt3 = omt2 * omt
    t2 = t * t
    t3 = t2 * t
    
    point_y = omt3 * p0[1] + 3.0 * omt2 * t * p1[1] + 3.0 * omt * t2 * p2[1] + t3 * p3[1]
    return point_y

@jit(float32[:,:](float32[:,:], float32[:,:,:]), nopython=True, parallel=True)
def apply_bezier_transform_parallel(image, control_points):
    """使用并行计算直接应用贝塞尔曲线变换到图像。
    
    Args:
        image: 输入图像，形状为(height, width) 或者最后一维是通道
        control_points: 控制点数组，形状为(n_segments, 4, 2)
        
    Returns:
        变换后的图像
    """
    height, width = image.shape
    result = np.zeros_like(image)
    
    for y in prange(height):
        for x in range(width):
            pixel_value = image[y, x]
            # 应用贝塞尔变换到像素值
            result[y, x] = evaluate_bezier_at_x(pixel_value, control_points)
    
    return result

@jit(float32[:,:,:](float32[:,:,:], float32[:,:,:]), nopython=True, parallel=True)
def apply_bezier_transform_rgb_parallel(image, control_points):
    """使用并行计算直接应用贝塞尔曲线变换到RGB图像。
    
    Args:
        image: 输入RGB图像，形状为(height, width, channels)
        control_points: 控制点数组，形状为(n_segments, 4, 2)
        
    Returns:
        变换后的RGB图像
    """
    height, width, channels = image.shape
    result = np.zeros_like(image)
    
    for c in range(channels):
        for y in prange(height):
            for x in range(width):
                pixel_value = image[y, x, c]
                # 应用贝塞尔变换到像素值
                result[y, x, c] = evaluate_bezier_at_x(pixel_value, control_points)
    
    return result

# --- NeoScript函数 ---
def get_params():
    """返回节点的默认参数，包含贝塞尔曲线的控制点。"""
    return {
        # 使用带控制柄的新默认值
        'curve_points': {'value': BEZIER_DEFAULT_POINTS, 'type': 'curve_data'} 
    }

def process(inputs, params, context):
    """使用优化的并行贝塞尔曲线计算应用变换到输入图像。"""
    input_image = inputs.get('f32bmp')
    if input_image is None:
        print("曲线节点: 未找到输入图像 'f32bmp'")
        return {}

    if input_image.dtype != np.float32:
        print(f"曲线节点: 输入图像类型不是 float32，而是 {input_image.dtype}。尝试转换...")
        if input_image.dtype == np.uint8:
             input_image = input_image.astype(np.float32) / 255.0
        elif input_image.dtype == np.uint16:
              input_image = input_image.astype(np.float32) / 65535.0
        else:
             print("曲线节点: 不支持的输入图像类型转换。")
             return {}

    # 获取曲线控制点数据
    curve_data = params.get('curve_points', BEZIER_DEFAULT_POINTS)
    
    try:
        # 转换点数据为NumPy数组
        points_array = np.array(curve_data, dtype=np.float32)
        
        # 准备贝塞尔计算所需的控制点格式
        control_points = prepare_control_points(points_array)
        
        # 应用贝塞尔变换
        if input_image.ndim == 3:
            output_image = apply_bezier_transform_rgb_parallel(input_image, control_points)
        elif input_image.ndim == 2:
            output_image = apply_bezier_transform_parallel(input_image, control_points)
        else:
            print("曲线节点: 不支持的图像维度。")
            return {'f32bmp': input_image}
        
        # 确保结果在[0,1]范围内
        np.clip(output_image, 0.0, 1.0, out=output_image)
        
    except Exception as e:
        print(f"曲线节点: 应用曲线变换时出错: {e}")
        import traceback
        traceback.print_exc()
        return {'f32bmp': input_image}

    return {'f32bmp': output_image}

def create_settings_widget(current_params, context, update_callback):
    """创建节点设置的自定义UI (使用贝塞尔曲线编辑器)。"""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)

    # 更新标签
    label = QLabel("亮度曲线 (左键添加/拖动, 右键删除)") 
    label.setAlignment(Qt.AlignCenter)
    layout.addWidget(label)

    initial_points = current_params.get('curve_points', BEZIER_DEFAULT_POINTS)
    curve_widget = CurveWidget(initial_points)

    curve_widget.curveChanged.connect(
        lambda points: update_callback('curve_points', points)
    )

    layout.addWidget(curve_widget)

    return container