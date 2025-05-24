#f32bmp: 
#f32bmp 
#比较加和节点 - 比较多个图像并叠加显示
#48B6FF
#Type:NeoScript

import numpy as np
import cv2
from PySide6.QtWidgets import QComboBox, QSlider, QLabel, QVBoxLayout, QWidget, QHBoxLayout
from PySide6.QtCore import Qt

def get_params():
    """返回节点的参数配置"""
    return {
        'compare_type': {
            'label': '比较类型',
            'type': 'combo',
            'default': 'greater',
            'options': ['greater', 'less', 'equal', 'abs_diff'],
            'value': 'greater'
        },
        'threshold': {
            'label': '阈值',
            'type': 'slider',
            'min': 0,
            'max': 255,
            'default': 128,
            'value': 128
        },
        'alpha_scale': {
            'label': 'Alpha强度',
            'type': 'slider',
            'min': 0,
            'max': 100,
            'default': 100,
            'value': 100
        },
        'blend_mode': {
            'label': '混合模式',
            'type': 'combo',
            'default': 'normal',
            'options': ['normal', 'multiply', 'screen', 'overlay'],
            'value': 'normal'
        }
    }

def create_settings_widget(params, context, update_callback):
    """创建自定义设置界面"""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    
    # 比较类型
    comp_type_layout = QHBoxLayout()
    comp_type_label = QLabel("比较类型:")
    comp_type_combo = QComboBox()
    comp_type_combo.addItems(['大于阈值', '小于阈值', '接近阈值', '差值'])
    
    # 设置当前值
    type_mapping = {'greater': 0, 'less': 1, 'equal': 2, 'abs_diff': 3}
    comp_type_combo.setCurrentIndex(type_mapping.get(params.get('compare_type'), 0))
    
    comp_type_layout.addWidget(comp_type_label)
    comp_type_layout.addWidget(comp_type_combo)
    layout.addLayout(comp_type_layout)
    
    # 设置比较类型变更回调
    def on_comp_type_changed(index):
        type_values = ['greater', 'less', 'equal', 'abs_diff']
        update_callback('compare_type', type_values[index])
    
    comp_type_combo.currentIndexChanged.connect(on_comp_type_changed)
    
    # 阈值滑块
    threshold_layout = QHBoxLayout()
    threshold_label = QLabel("阈值:")
    threshold_slider = QSlider(Qt.Horizontal)
    threshold_slider.setMinimum(0)
    threshold_slider.setMaximum(255)
    threshold_slider.setValue(params.get('threshold', 128))
    threshold_value = QLabel(f"{params.get('threshold', 128)}")
    
    threshold_layout.addWidget(threshold_label)
    threshold_layout.addWidget(threshold_slider)
    threshold_layout.addWidget(threshold_value)
    layout.addLayout(threshold_layout)
    
    # 设置阈值变更回调
    def on_threshold_changed(value):
        threshold_value.setText(f"{value}")
        update_callback('threshold', value)
        
    threshold_slider.valueChanged.connect(on_threshold_changed)
    
    # Alpha强度滑块
    alpha_layout = QHBoxLayout()
    alpha_label = QLabel("Alpha强度:")
    alpha_slider = QSlider(Qt.Horizontal)
    alpha_slider.setMinimum(0)
    alpha_slider.setMaximum(100)
    alpha_slider.setValue(params.get('alpha_scale', 100))
    alpha_value = QLabel(f"{params.get('alpha_scale', 100)}%")
    
    alpha_layout.addWidget(alpha_label)
    alpha_layout.addWidget(alpha_slider)
    alpha_layout.addWidget(alpha_value)
    layout.addLayout(alpha_layout)
    
    # 设置Alpha强度变更回调
    def on_alpha_changed(value):
        alpha_value.setText(f"{value}%")
        update_callback('alpha_scale', value)
        
    alpha_slider.valueChanged.connect(on_alpha_changed)
    
    # 混合模式
    blend_layout = QHBoxLayout()
    blend_label = QLabel("混合模式:")
    blend_combo = QComboBox()
    blend_combo.addItems(['正常', '正片叠底', '滤色', '叠加'])
    
    # 设置当前值
    blend_mapping = {'normal': 0, 'multiply': 1, 'screen': 2, 'overlay': 3}
    blend_combo.setCurrentIndex(blend_mapping.get(params.get('blend_mode'), 0))
    
    blend_layout.addWidget(blend_label)
    blend_layout.addWidget(blend_combo)
    layout.addLayout(blend_layout)
    
    # 设置混合模式变更回调
    def on_blend_mode_changed(index):
        blend_values = ['normal', 'multiply', 'screen', 'overlay']
        update_callback('blend_mode', blend_values[index])
    
    blend_combo.currentIndexChanged.connect(on_blend_mode_changed)
    
    return widget

def process(params, inputs, context):
    """处理所有输入图像并进行比较和叠加"""
    # 获取参数
    compare_type = params.get('compare_type', 'greater')
    threshold = params.get('threshold', 128)
    alpha_scale = params.get('alpha_scale', 100) / 100.0  # 转换成0-1范围
    blend_mode = params.get('blend_mode', 'normal')
    
    # 收集所有输入图像
    image_inputs = []
    
    # 提取所有f32bmp输入（包括带序号的）
    for key, value in inputs.items():
        if key == 'f32bmp' or key.startswith('f32bmp_'):
            image_inputs.append(value)
    
    if not image_inputs:
        print("没有找到输入图像")
        return {'f32bmp': np.zeros((100, 100, 4), dtype=np.float32)}
    
    # 准备输出图像（与第一个输入图像大小相同）
    if len(image_inputs[0].shape) == 2:  # 灰度图
        height, width = image_inputs[0].shape
        base_img = np.zeros((height, width, 4), dtype=np.float32)
    elif len(image_inputs[0].shape) == 3 and image_inputs[0].shape[2] == 3:  # RGB图
        height, width, _ = image_inputs[0].shape
        base_img = np.zeros((height, width, 4), dtype=np.float32)
    else:  # 已有alpha通道的RGBA图
        height, width, _ = image_inputs[0].shape
        base_img = np.zeros((height, width, 4), dtype=np.float32)
    
    # 从底层到顶层处理每个图像（底层图像先处理）
    for img in image_inputs:
        # 确保图像有4个通道（RGBA）
        if len(img.shape) == 2:  # 灰度图
            img_rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.float32)
            img_rgba[:, :, 0] = img_rgba[:, :, 1] = img_rgba[:, :, 2] = img
            img = img_rgba
        elif len(img.shape) == 3 and img.shape[2] == 3:  # RGB图
            img_rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.float32)
            img_rgba[:, :, :3] = img
            img = img_rgba
        
        # 根据比较类型计算alpha通道
        if compare_type == 'greater':
            # 大于阈值部分变透明
            mask = np.mean(img[:, :, :3], axis=2) > (threshold / 255.0)
            img[:, :, 3] = mask * alpha_scale
        elif compare_type == 'less':
            # 小于阈值部分变透明
            mask = np.mean(img[:, :, :3], axis=2) < (threshold / 255.0)
            img[:, :, 3] = mask * alpha_scale
        elif compare_type == 'equal':
            # 接近阈值部分变透明（使用高斯函数形成平滑过渡）
            avg = np.mean(img[:, :, :3], axis=2)
            norm_threshold = threshold / 255.0
            # 计算与阈值的差距，并使用高斯函数转换为0-1之间的值
            diff = np.abs(avg - norm_threshold)
            sigma = 0.1  # 控制"接近"的范围
            mask = np.exp(-(diff**2) / (2 * sigma**2))
            img[:, :, 3] = mask * alpha_scale
        elif compare_type == 'abs_diff':
            # 绝对差值作为透明度
            avg = np.mean(img[:, :, :3], axis=2)
            norm_threshold = threshold / 255.0
            # 计算与阈值的绝对差距，并归一化到0-1范围
            diff = 1.0 - np.minimum(np.abs(avg - norm_threshold) * 2, 1.0)
            img[:, :, 3] = diff * alpha_scale
        
        # 根据混合模式叠加图像
        if blend_mode == 'normal':
            # 正常混合：src_alpha * src + (1 - src_alpha) * dst
            src_alpha = img[:, :, 3:4]
            base_img = img[:, :, :3] * src_alpha + base_img[:, :, :3] * (1 - src_alpha)
            # 更新基础图像的alpha通道（取两个alpha的最大值）
            base_img[:, :, 3] = np.maximum(base_img[:, :, 3], img[:, :, 3])
        elif blend_mode == 'multiply':
            # 正片叠底：src * dst
            src_alpha = img[:, :, 3:4]
            blended = img[:, :, :3] * base_img[:, :, :3]
            base_img[:, :, :3] = blended * src_alpha + base_img[:, :, :3] * (1 - src_alpha)
            base_img[:, :, 3] = np.maximum(base_img[:, :, 3], img[:, :, 3])
        elif blend_mode == 'screen':
            # 滤色：1 - (1 - src) * (1 - dst)
            src_alpha = img[:, :, 3:4]
            blended = 1 - (1 - img[:, :, :3]) * (1 - base_img[:, :, :3])
            base_img[:, :, :3] = blended * src_alpha + base_img[:, :, :3] * (1 - src_alpha)
            base_img[:, :, 3] = np.maximum(base_img[:, :, 3], img[:, :, 3])
        elif blend_mode == 'overlay':
            # 叠加：亮部滤色，暗部正片叠底
            src_alpha = img[:, :, 3:4]
            # 创建掩码区分亮部和暗部
            mask = base_img[:, :, :3] > 0.5
            # 暗部使用正片叠底
            multiply = 2 * img[:, :, :3] * base_img[:, :, :3]
            # 亮部使用滤色
            screen = 1 - 2 * (1 - img[:, :, :3]) * (1 - base_img[:, :, :3])
            # 根据掩码合并结果
            blended = np.where(mask, screen, multiply)
            base_img[:, :, :3] = blended * src_alpha + base_img[:, :, :3] * (1 - src_alpha)
            base_img[:, :, 3] = np.maximum(base_img[:, :, 3], img[:, :, 3])
    
    # 确保值在有效范围内
    base_img = np.clip(base_img, 0, 1)
    
    return {'f32bmp': base_img}