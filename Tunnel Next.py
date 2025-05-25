import os
import sys
import time
import importlib.util
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QFrame, QSplitter, QScrollArea,
                              QFileDialog, QMessageBox, QMenu, QToolTip, QSlider,
                              QCheckBox, QComboBox, QLineEdit, QGridLayout, QToolButton,
                              QTabWidget, QToolBar, QListWidget, QListWidgetItem, QListView, QInputDialog)
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QSize, Signal, QTimer, QEvent, QCoreApplication, QObject, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QCursor, QAction, QPainterPath, QImageReader, QIcon, QFont, QLinearGradient, QRadialGradient, QBrush
import cv2
from PySide6.QtWidgets import QMenu, QDialog, QVBoxLayout, QLabel
from PySide6.QtCore import QRect, QEasingCurve
import numpy as np
from PIL import Image
import shutil
import re
import concurrent.futures
import numpy as np
from PIL import Image
from io import BytesIO
import concurrent.futures
import math
import platform
import subprocess
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
import configparser
import importlib.util
import datetime
import copy
import threading
# 动态导入TNXVC模块
try:
    from TunnelNX_scripts.TNXVC import TNXVC
except ImportError:
    print("TNXVC模块未找到，版本控制功能可能不可用")


class MetadataManager:
    """元数据管理器 - 负责处理节点图中的元数据流"""

    def __init__(self):
        self._lock = threading.Lock()

    def create_metadata(self, **kwargs):
        """创建新的元数据字典"""
        with self._lock:
            metadata = {
                'created_at': datetime.datetime.now().isoformat(),
                'node_path': [],  # 记录经过的节点路径
                'processing_history': [],  # 记录处理历史
                **kwargs
            }
            return metadata

    def merge_metadata(self, *metadata_dicts):
        """合并多个元数据字典，后面的会覆盖前面的同名键"""
        with self._lock:
            merged = {}
            for metadata in metadata_dicts:
                if isinstance(metadata, dict):
                    merged.update(metadata)
            return merged

    def copy_metadata(self, metadata):
        """深拷贝元数据"""
        if not isinstance(metadata, dict):
            return {}
        return copy.deepcopy(metadata)

    def add_node_to_path(self, metadata, node_id, node_title):
        """向元数据的节点路径中添加节点"""
        if not isinstance(metadata, dict):
            metadata = {}

        if 'node_path' not in metadata:
            metadata['node_path'] = []

        metadata['node_path'].append({
            'node_id': node_id,
            'node_title': node_title,
            'processed_at': datetime.datetime.now().isoformat()
        })
        return metadata

    def add_processing_record(self, metadata, operation, details=None):
        """向元数据中添加处理记录"""
        if not isinstance(metadata, dict):
            metadata = {}

        if 'processing_history' not in metadata:
            metadata['processing_history'] = []

        record = {
            'operation': operation,
            'timestamp': datetime.datetime.now().isoformat()
        }
        if details:
            record['details'] = details

        metadata['processing_history'].append(record)
        return metadata

    def get_metadata_value(self, metadata, key, default=None):
        """安全地获取元数据值"""
        if not isinstance(metadata, dict):
            return default
        return metadata.get(key, default)

    def set_metadata_value(self, metadata, key, value):
        """设置元数据值"""
        if not isinstance(metadata, dict):
            metadata = {}
        metadata[key] = value
        return metadata

    def delete_metadata_key(self, metadata, key):
        """删除元数据键"""
        if isinstance(metadata, dict) and key in metadata:
            del metadata[key]
        return metadata

    def validate_metadata(self, metadata):
        """验证元数据格式"""
        if not isinstance(metadata, dict):
            return False

        # 检查必要的字段
        required_fields = ['created_at', 'node_path', 'processing_history']
        for field in required_fields:
            if field not in metadata:
                return False

        return True

    def serialize_metadata(self, metadata):
        """序列化元数据为JSON字符串"""
        try:
            import json
            return json.dumps(metadata, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"元数据序列化失败: {e}")
            return "{}"

    def deserialize_metadata(self, metadata_str):
        """从JSON字符串反序列化元数据"""
        try:
            import json
            return json.loads(metadata_str)
        except Exception as e:
            print(f"元数据反序列化失败: {e}")
            return {}

def scale_tile_worker(tile_byte_array, target_width, target_height, transformation_mode_value, aspect_ratio_mode_value):
    """
    工作进程函数：加载图像块字节，缩放，并返回缩放后的字节。
    """
    try:
        # 需要在工作进程中导入Qt模块
        from PySide6.QtGui import QPixmap, QImage
        from PySide6.QtCore import QBuffer, QByteArray, Qt, QIODevice

        # 从字节数组加载 QPixmap
        buffer = QBuffer(tile_byte_array)
        buffer.open(QIODevice.ReadOnly)
        reader = QImageReader(buffer)
        image = reader.read() # 读取为 QImage 以便获取原始格式
        if image.isNull():
                # 如果直接读取失败，尝试用 fromData 加载（可能格式信息丢失）
                pixmap = QPixmap()
                if not pixmap.loadFromData(tile_byte_array.data()):
                    print(f"[Worker] Error: Failed to load pixmap from data.")
                    return None # 返回 None 表示失败
        else:
            pixmap = QPixmap.fromImage(image) # 从有效 QImage 创建 QPixmap

        if pixmap.isNull():
            print("[Worker] Error: Pixmap is null after loading.")
            return None

        # 将整数值转换回枚举类型
        transformation_mode = Qt.TransformationMode(transformation_mode_value)
        aspect_ratio_mode = Qt.AspectRatioMode(aspect_ratio_mode_value)

        # 执行缩放
        scaled_pixmap = pixmap.scaled(target_width, target_height, aspect_ratio_mode, transformation_mode)

        if scaled_pixmap.isNull():
            print("[Worker] Error: Scaled pixmap is null.")
            return None

        # 将缩放后的 QPixmap 保存回字节数组 (使用 PNG 格式保证无损且支持透明度)
        scaled_buffer = QBuffer()
        scaled_buffer.open(QIODevice.WriteOnly)
        # 使用 PNG 格式保存
        if not scaled_pixmap.save(scaled_buffer, "PNG"):
                print("[Worker] Error: Failed to save scaled pixmap to buffer.")
                scaled_buffer.close()
                return None
        scaled_buffer.close()

        # 返回包含字节数据的 QByteArray
        return scaled_buffer.data()

    except Exception as e:
        # 捕获并打印工作进程中的任何异常
        print(f"[Worker] Exception during scaling: {e}")
        import traceback
        traceback.print_exc()
        return None # 返回 None 表示失败
class TunnelNX(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version = "Alpha 2"
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.node_cache = LRUCache(max_size=200)

        # 初始化元数据管理器
        self.metadata_manager = MetadataManager()

        # 首先，确保 self.script_dir 已定义
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # --- 加载主题配置 ---
        # 确保 self.config 总能被初始化，即使文件操作失败
        self.config = configparser.ConfigParser()
        self.config_path = os.path.join(self.script_dir, "config.ini")
        current_theme_file = "default.TNXtheme"  # 默认主题文件名

        if os.path.exists(self.config_path):
            try:
                self.config.read(self.config_path, encoding='utf-8')
                if 'Theme' in self.config and 'current_theme' in self.config['Theme']:
                    current_theme_file = self.config['Theme']['current_theme']
                else:
                    # 配置文件存在但缺少主题部分或键，则创建/设置默认值
                    if 'Theme' not in self.config:
                        self.config.add_section('Theme')
                    self.config['Theme']['current_theme'] = current_theme_file
                    try:
                        with open(self.config_path, 'w', encoding='utf-8') as configfile:
                            self.config.write(configfile)
                    except Exception as e_write:
                        print(f"写入默认主题到配置文件 {self.config_path} 失败: {e_write}")
            except Exception as e_read:
                print(f"读取配置文件 {self.config_path} 失败: {e_read}")
                # 即使读取失败，也确保Theme部分和current_theme键存在于self.config中
                if 'Theme' not in self.config:
                    self.config.add_section('Theme')
                self.config['Theme']['current_theme'] = current_theme_file
        else:
            # 配置文件不存在，创建它并写入默认主题
            try:
                if 'Theme' not in self.config: # 确保Theme节区存在
                    self.config.add_section('Theme')
                self.config['Theme']['current_theme'] = current_theme_file
                with open(self.config_path, 'w', encoding='utf-8') as configfile:
                    self.config.write(configfile)
            except Exception as e_create:
                print(f"创建配置文件 {self.config_path} 失败: {e_create}")
                # 即使创建失败，也确保Theme部分和current_theme键存在于self.config中
                if 'Theme' not in self.config:
                    self.config.add_section('Theme')
                self.config['Theme']['current_theme'] = current_theme_file

        self.performance_mode_enabled = False

        # 加载伪类型定义
        self.pseudo_types = {}
        if 'Pseudo Type' in self.config:
            for real_type, aliases in self.config['Pseudo Type'].items():
                alias_list = [alias.strip() for alias in aliases.split(',')]
                for alias in alias_list:
                    self.pseudo_types[alias] = real_type
            print(f"已加载伪类型定义: {self.pseudo_types}")

        # 设置窗口标题和图标
        self.setWindowTitle("TunnelNX Preview")
        self.resize(1280, 720)  # 16:9 初始尺寸
        self.setMinimumSize(1024, 576)

        # 初始化节点管理
        self.nodes = []  # 节点列表
        self.connections = []  # 节点连接列表
        self.next_node_id = 0  # 下一个节点ID
        self.selected_node = None  # 当前选择的节点
        self.dragging = False  # 是否正在拖拽
        self.connecting_from = None  # 拖拽连接的起始点
        self.connecting_to_input = None  # 储存拖拽到输入端口的临时信息
        self.selected_port = None  # 当前选择的端口
        self._scroll_update_timer = None # 定时器用于延迟滚动条设置

        # 初始化图像数据
        self.current_image = None  # 当前处理的图像
        self.current_image_path = None  # 当前图像路径

        # 初始化节点图状态
        self.current_nodegraph_path = None  # 当前节点图路径
        self.is_new_nodegraph = True  # 是否为新创建的节点图
        self.nodegraph_modified = False  # 节点图是否被修改
        WORKFOLDER_FILE = "WORKFOLDER"
        if os.path.exists(WORKFOLDER_FILE):
            # 如果存在，读取文件内容并赋值给self.work_folder
            with open(WORKFOLDER_FILE, 'r') as f:
                self.work_folder = f.read().strip()  # 使用strip()去除可能的空白字符
        else:
            # 如果不存在，设置默认值并创建文件
            self.work_folder = os.getcwd()+"\TunnelNXWorkFolder"
            with open(WORKFOLDER_FILE, 'w') as f:
                f.write(self.work_folder)  # 默认工作文件夹
        self.zoom_level = 1.0  # 添加缩放级别追踪

        # 确保工作文件夹存在
        os.makedirs(self.work_folder, exist_ok=True)

        # 确保nodegraphs文件夹存在
        self.nodegraphs_folder = os.path.join(self.work_folder, "nodegraphs")
        os.makedirs(self.nodegraphs_folder, exist_ok=True)

        # 创建缩略图文件夹
        self.thumbnails_folder = os.path.join(self.nodegraphs_folder, "thumbnails")
        os.makedirs(self.thumbnails_folder, exist_ok=True)

        # 确保temp文件夹存在
        self.temp_folder = os.path.join(self.nodegraphs_folder, "temp")
        os.makedirs(self.temp_folder, exist_ok=True)

        # 初始化版本控制系统
        try:
            self.tnxvc = TNXVC(self.work_folder)
            print("版本控制系统已初始化")
        except Exception as e:
            self.tnxvc = None
            print(f"初始化版本控制系统失败: {e}")

        # 设置默认缩略图
        self.default_thumbnail = None
        default_thumbnail_path = os.path.join(self.script_dir, "resources", "default_thumbnail.png")
        if os.path.exists(default_thumbnail_path):
            self.default_thumbnail = QPixmap(default_thumbnail_path)
        else:
            # 如果没有默认缩略图文件，创建一个简单的默认缩略图
            self.default_thumbnail = QPixmap(128, 128)
            self.default_thumbnail.fill(QColor(200, 200, 200))

        # 当前节点图路径和状态
        self.current_nodegraph_path = None
        self.is_new_nodegraph = True  # 默认为新创建的节点图
        self.nodegraph_modified = False  # 节点图是否被修改过

        # 确保脚本文件夹存在
        self.scripts_folder = "TunnelNX_scripts"
        os.makedirs(self.scripts_folder, exist_ok=True)

        self.setup_main_layout() # 这会间接调用 create_paned_areas

        self.setup_aero_style(theme_name=current_theme_file)

        self.script_registry = {}
        self.scan_scripts()

        self.create_context_menus()

        self.init_zoom_functionality()

        # 注: 原自动保存定时器和参数调整延迟保存计时器已移除

        self.node_preview_windows = {} # 存储 node_id: QDialog 实例
        self.last_context_menu_time = 0



    def get_application_context(self, node=None):
        """Gathers relevant application state information for scripts."""
        # --- 直接使用 preview_display_widget ---
        preview_widget_size = QSize(0, 0)
        if hasattr(self, 'preview_display_widget') and self.preview_display_widget:
             preview_widget_size = self.preview_display_widget.size()

        context = {
            'app': self,
            'work_folder': self.work_folder,
            'temp_folder': self.temp_folder,
            'scripts_folder': self.scripts_folder,
            'current_image_path': self.current_image_path if hasattr(self, 'current_image_path') else None,
            'zoom_level': self.zoom_level,
            # 添加预览视口尺寸
            'preview_viewport_size': self.preview_scroll.viewport().size() if hasattr(self, 'preview_scroll') else QSize(0, 0),
            # 添加原始图像尺寸 (如果可用)
            'original_image_size': QSize(self.current_image.shape[1], self.current_image.shape[0]) if hasattr(self, 'current_image') and self.current_image is not None and hasattr(self.current_image, 'shape') and len(self.current_image.shape) >= 2 else QSize(0, 0),
             # 添加预览部件尺寸 (缩放后尺寸)
            'preview_widget_size': preview_widget_size,
            # 添加滚动条位置用于平移信息 (相对于左上角)
            'preview_pan_offset': QPoint(self.preview_scroll.horizontalScrollBar().value(), self.preview_scroll.verticalScrollBar().value()) if hasattr(self, 'preview_scroll') else QPoint(0,0),
            # 添加主窗口尺寸
            'window_size': self.size(),
        }
        if node:
            context.update({
                'node_id': node['id'],
                'node_title': node['title']
            })
        return context
    def setup_aero_style(self, theme_name="default.TNXtheme"):
        """设置Aero风格样式，移除多余边框，统一界面风格"""
        theme_path = os.path.join(self.script_dir, "resources", theme_name)
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
            self.setStyleSheet(stylesheet)
        except FileNotFoundError:
            print(f"主题文件 {theme_path} 未找到，加载默认样式。")
            # 在这里可以放一个非常基础的后备样式，或者让Qt使用默认样式
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1F1F1F;
                    color: #E8E8E8;
                }
            """)
        except Exception as e:
            print(f"加载主题 {theme_path} 失败: {e}")
            # 同上，加载基础后备样式
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1F1F1F;
                    color: #E8E8E8;
                }
            """)


    def update_performance_button_style(self):
        """根据性能模式状态更新按钮样式"""
        if not hasattr(self, 'performance_toolbar'):
            return

        # 确保性能模式启用标志存在
        if not hasattr(self, 'performance_mode_enabled'):
            self.performance_mode_enabled = False

        # 通过设置属性来实现高亮效果
        if self.performance_mode_enabled:
            # 启用时设置属性
            self.performance_toolbar.setProperty("styleClass", "performance_enabled")
            # 设置为选中状态
            self.performance_mode_action.setChecked(True)
        else:
            # 禁用时移除属性
            self.performance_toolbar.setProperty("styleClass", "")
            # 取消选中状态
            self.performance_mode_action.setChecked(False)

        # 更新样式
        self.performance_toolbar.style().unpolish(self.performance_toolbar)
        self.performance_toolbar.style().polish(self.performance_toolbar)
    def create_ribbon_ui(self):
        """创建 Ribbon UI 界面"""
        self.ribbon_widget = QTabWidget()
        self.ribbon_widget.setObjectName("ribbonWidget")  # 设置 objectName 以便样式化
        self.ribbon_widget.setFixedHeight(120) # 设置 Ribbon 的固定高度

        # --- 创建 Ribbon 标签页 ---
        self.create_file_tab()
        self.create_view_tab()
        self.create_node_tab()
        self.create_version_control_tab()
        # --- 主题切换按钮 ---
        self.theme_button = QPushButton(self)
        theme_icon_path = os.path.join(self.script_dir, "resources", "theme.png")
        if os.path.exists(theme_icon_path):
            self.theme_button.setIcon(QIcon(theme_icon_path))
            self.theme_button.setIconSize(QSize(24, 24))
        else:
            self.theme_button.setText("T")
        self.theme_button.setToolTip("切换主题")
        self.theme_button.setFlat(True)
        self.theme_button.setStyleSheet("QPushButton { border: none; background-color: transparent; padding: 0px; }")
        self.theme_button.setFixedSize(QSize(32, 32))
        self.theme_menu = QMenu(self)
        self.theme_button.setMenu(self.theme_menu)
        self.populate_theme_menu()

        # --- 添加 Ribbon 右上角的 Logo 和标题 ---
        corner_widget = QWidget()
        corner_widget.setObjectName("corner_widget")  # 设置对象名称以便样式化
        corner_widget.setProperty("corner", "true")  # 设置属性以便样式化
        corner_widget.setStyleSheet("background: transparent;")  # 直接设置透明背景
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(5, 0, 5, 5)
        corner_layout.setSpacing(5)

        logo_label = QLabel()
        logo_path = os.path.join("resources", "imgpp.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            logo_label.setPixmap(logo_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # 为 logo_label 添加双击事件，打开关于窗口
        logo_label.mouseDoubleClickEvent = lambda event: self.show_about_dialog()

        corner_layout.addWidget(self.theme_button) # <--- 在这里添加主题按钮
        corner_layout.addWidget(logo_label)

        title_label = QLabel("Tunnel Next Preview")
        corner_layout.addWidget(title_label)

        self.ribbon_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)

        # 将 Ribbon 添加到主布局顶部
        self.main_layout.insertWidget(0, self.ribbon_widget)

        # 视图切换逻辑: 默认显示文件标签页
        self.ribbon_widget.setCurrentIndex(0)
    def show_about_dialog(self):
        """显示关于窗口"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 Tunnel Next")
        dialog.setModal(True)
        # 主布局
        layout = QVBoxLayout(dialog)
        # 关于文字
        about_text = QLabel(f"TunnelNX Preview\n版本: {self.version}\n以GPLv3许可证开源发布\n早期开发预览版本\n不建议投入生产环境使用", dialog)
        about_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(about_text)
        # 确定按钮
        ok_button = QPushButton("确定", dialog)
        ok_button.clicked.connect(dialog.accept)
        ok_button.setFixedWidth(100)
        # 按钮居中
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_button)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        # 显示对话框
        dialog.exec_()
    def populate_theme_menu(self):
        self.theme_menu.clear()
        resources_path = os.path.join(self.script_dir, "resources")

        current_theme_file = "default.TNXtheme"
        if 'Theme' in self.config and 'current_theme' in self.config['Theme']:
            current_theme_file = self.config['Theme']['current_theme']

        if os.path.isdir(resources_path):
            for filename in os.listdir(resources_path):
                if filename.endswith(".TNXtheme"):
                    action = QAction(filename.replace(".TNXtheme", ""), self)
                    action.setData(filename)
                    action.setCheckable(True)
                    if filename == current_theme_file:
                        action.setChecked(True)

                    action.triggered.connect(self.on_theme_selected)
                    self.theme_menu.addAction(action)

        self.theme_menu.addSeparator()
        open_folder_action = QAction("打开主题文件夹...", self)
        open_folder_action.triggered.connect(self.open_themes_folder)
        self.theme_menu.addAction(open_folder_action)


    def on_theme_selected(self):
        action = self.sender()
        if action:
            new_theme_file = action.data()

            # 更新配置文件
            if 'Theme' not in self.config:
                self.config.add_section('Theme')
            self.config['Theme']['current_theme'] = new_theme_file
            try:
                with open(self.config_path, 'w', encoding='utf-8') as configfile:
                    self.config.write(configfile)

                # 更新菜单中的勾选状态
                for act in self.theme_menu.actions():
                    if act.isCheckable(): # 确保是主题action而不是分隔符等
                        act.setChecked(act.data() == new_theme_file)

                QMessageBox.information(self, "主题已更改", f"已选择主题: {new_theme_file}\n请重新启动应用程序以应用更改。")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法保存主题配置: {e}")
                print(f"保存主题配置失败: {e}")

    def open_themes_folder(self):
        resources_path = os.path.join(self.script_dir, "resources")
        try:
            # 使用适合各操作系统的打开文件夹方式
            if platform.system() == "Windows":
                os.startfile(resources_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.Popen(["open", resources_path])
            else: # Linux and other UNIX-like
                subprocess.Popen(["xdg-open", resources_path])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开主题文件夹: {e}")
            print(f"无法打开主题文件夹: {e}")

    def setup_main_layout(self):
        """设置主布局"""
        # 创建中央部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(3)

        # --- 修改：先创建工作区，再创建 Ribbon ---
        # 创建工作区域 (包含 node_canvas_widget)
        print("SETUP_MAIN_LAYOUT: About to call create_work_area.")
        self.create_work_area()
        print(f"SETUP_MAIN_LAYOUT (After create_work_area): self.film_preview_list ID={id(self.film_preview_list)}, Parent={self.film_preview_list.parentWidget()}")


        # 创建 Ribbon UI
        self.create_ribbon_ui()
        # ---------------------------------------

        # --- 在主布局完成后设置 central_widget 的 objectName ---
        self.central_widget.setObjectName("central_widget")
        # ------------------------------------------------------

    def create_file_tab(self):
        """创建 '文件' Ribbon 标签页"""
        file_tab = QWidget()
        file_tab.setObjectName("file_tab")
        file_layout = QHBoxLayout(file_tab)
        file_layout.setContentsMargins(5, 0, 5, 0) # 调整边距
        file_layout.setSpacing(10) # 组间距

        # --- 文件操作组 ---
        file_ops_toolbar = QToolBar("文件操作")
        file_ops_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon) # 图标在上，文字在下
        file_ops_toolbar.setIconSize(QSize(48, 48))  # 设置图标大小为48x48
        # -- 将旧的文件操作按钮移到这里 --
        resources_dir = "resources"
        os.makedirs(resources_dir, exist_ok=True) # 确保目录存在

        # 添加新建按钮
        new_action = QAction(QIcon(os.path.join(resources_dir, "newnodegraph.png")), "新建", self)
        new_action.triggered.connect(self.create_new_node_graph)
        new_action.setToolTip("新建节点图")
        file_ops_toolbar.addAction(new_action)

        open_action = QAction(QIcon(os.path.join(resources_dir, "open.png")), "打开", self)
        open_action.triggered.connect(self.open_image)
        open_action.setToolTip("打开图像文件")
        file_ops_toolbar.addAction(open_action)

        save_action = QAction(QIcon(os.path.join(resources_dir, "save.png")), "保存", self)
        save_action.triggered.connect(self.save_node_graph)
        save_action.setToolTip("保存当前节点图")
        file_ops_toolbar.addAction(save_action)

        load_action = QAction(QIcon(os.path.join(resources_dir, "load.png")), "加载", self)
        load_action.triggered.connect(self.load_node_graph)
        load_action.setToolTip("加载节点图文件")
        file_ops_toolbar.addAction(load_action)

        export_action = QAction(QIcon(os.path.join(resources_dir, "export.png")), "导出", self)
        export_action.triggered.connect(self.export_image)
        export_action.setToolTip("导出处理后的图像")
        file_ops_toolbar.addAction(export_action)
        # --------------------------

        file_layout.addWidget(file_ops_toolbar)
        file_layout.addStretch(1) # 添加伸缩，使组靠左

        self.ribbon_widget.addTab(file_tab, "文件")

    def create_view_tab(self):
        """创建 '视图' Ribbon 标签页"""
        view_tab = QWidget()
        view_tab.setObjectName("view_tab")
        view_layout = QHBoxLayout(view_tab)
        view_layout.setContentsMargins(5, 0, 5, 0)
        view_layout.setSpacing(10)

        # --- 缩放组 ---
        zoom_toolbar = QToolBar("缩放")
        zoom_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        zoom_toolbar.setIconSize(QSize(48, 48))  # 设置图标大小为48x48

        # -- 将旧的缩放按钮移到这里 --
        resources_dir = "resources"
        os.makedirs(resources_dir, exist_ok=True) # 确保目录存在

        zoom_in_action = QAction(QIcon(os.path.join(resources_dir, "zoom_in.png")), "放大", self)
        zoom_in_action.triggered.connect(self.zoom_in)
        zoom_in_action.setToolTip("放大图像 (Ctrl+ +)")
        zoom_toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction(QIcon(os.path.join(resources_dir, "zoom_out.png")), "缩小", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        zoom_out_action.setToolTip("缩小图像 (Ctrl+ -)")
        zoom_toolbar.addAction(zoom_out_action)

        zoom_fit_action = QAction(QIcon(os.path.join(resources_dir, "zoom_fit.png")), "适应窗口", self)
        zoom_fit_action.triggered.connect(self.zoom_fit)
        zoom_fit_action.setToolTip("适应窗口大小 (Ctrl+ 0)")
        zoom_toolbar.addAction(zoom_fit_action)

        # --- 添加性能模式按钮 ---
        self.performance_toolbar = QToolBar("性能")
        self.performance_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.performance_toolbar.setIconSize(QSize(48, 48))

        self.performance_mode_action = QAction(QIcon(os.path.join(resources_dir, "performance.png")), "性能模式", self)
        self.performance_mode_action.setCheckable(True)  # 使按钮可切换
        self.performance_mode_action.setToolTip("启用性能模式，对PerfSensitive节点优化处理")
        self.performance_mode_action.triggered.connect(self.toggle_performance_mode)
        self.performance_toolbar.addAction(self.performance_mode_action)

        # 更新后调用样式设置
        self.update_performance_button_style()

        view_layout.addWidget(zoom_toolbar)
        view_layout.addWidget(self.performance_toolbar)
        view_layout.addStretch(1)

        self.ribbon_widget.addTab(view_tab, "视图")

    def toggle_performance_mode(self):
        """切换性能模式开关状态"""
        self.performance_mode_enabled = not self.performance_mode_enabled
        self.update_performance_button_style()

        # 更新提示消息
        status_msg = "性能模式已启用" if self.performance_mode_enabled else "性能模式已禁用"
        if hasattr(self, 'task_label'):
            self.task_label.setText(status_msg)

        # 重新处理节点图以应用更改
        self.process_node_graph()

        print(f"性能模式: {'开启' if self.performance_mode_enabled else '关闭'}")

    def create_node_tab(self):
        """创建 '节点' Ribbon 标签页"""
        node_tab = QWidget()
        node_tab.setObjectName("node_tab")
        node_layout = QHBoxLayout(node_tab)
        node_layout.setContentsMargins(5, 0, 5, 0)
        node_layout.setSpacing(10)

        # --- 节点操作组 ---
        node_ops_toolbar = QToolBar("节点操作")
        node_ops_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        node_ops_toolbar.setIconSize(QSize(48, 48))  # 设置图标大小为48x48

        resources_dir = "resources"
        os.makedirs(resources_dir, exist_ok=True)

        # --- 修改：假设图标文件在 resources 目录下 ---
        add_node_icon_path = os.path.join(resources_dir, "add_node.png")
        delete_node_icon_path = os.path.join(resources_dir, "delete_node.png")
        arrange_nodes_icon_path = os.path.join(resources_dir, "arrange_nodes.png")
        arrange_nodes_dense_icon_path = os.path.join(resources_dir, "arrange_nodes_dense.png")

        add_node_action = QAction(QIcon(add_node_icon_path), "添加节点", self) # 需要图标
        add_node_action.triggered.connect(self.show_node_menu)
        add_node_action.setToolTip("打开添加节点菜单")
        node_ops_toolbar.addAction(add_node_action)

        delete_node_action = QAction(QIcon(delete_node_icon_path), "删除节点", self) # 需要图标
        delete_node_action.triggered.connect(self.delete_selected_node)
        delete_node_action.setToolTip("删除选中的节点")
        node_ops_toolbar.addAction(delete_node_action)

        # --- 节点图整理组 ---
        arrange_toolbar = QToolBar("节点图整理")
        arrange_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        arrange_toolbar.setIconSize(QSize(48, 48))  # 设置图标大小为48x48

        # --- 修改：将原有的 "整理节点" 按钮连接到非密集整理方法 ---
        arrange_action = QAction(QIcon(arrange_nodes_icon_path), "整理节点", self) # 需要图标
        arrange_action.triggered.connect(self.arrange_nodes) # 使用非密集排列
        arrange_action.setToolTip("自动整理节点图布局（非密集）")
        arrange_toolbar.addAction(arrange_action)

        # --- 新增：添加 "密集整理节点" 按钮 ---
        arrange_dense_action = QAction(QIcon(arrange_nodes_dense_icon_path), "密集整理", self) # 需要图标
        arrange_dense_action.triggered.connect(self.arrange_nodes_dense) # 使用密集排列
        arrange_dense_action.setToolTip("自动整理节点图布局（密集）")
        arrange_toolbar.addAction(arrange_dense_action)


        node_layout.addWidget(node_ops_toolbar)
        node_layout.addWidget(arrange_toolbar)
        node_layout.addStretch(1)

        self.ribbon_widget.addTab(node_tab, "节点")

        # 记录节点Tab的索引
        self.node_tab_index = self.ribbon_widget.indexOf(node_tab)

        # --- 连接信号以在与节点图交互时切换到节点Tab ---
        self.node_canvas_widget.installEventFilter(self) # 在画布上安装事件过滤器
        # 也可以连接其他交互信号，例如节点选中、移动等
        # self.nodeSelected.connect(lambda: self.switch_to_node_tab()) # 假设有这个信号

    def create_version_control_tab(self):
        """创建 '版本控制' Ribbon 标签页"""
        version_tab = QWidget()
        version_tab.setObjectName("version_control_tab")
        version_layout = QHBoxLayout(version_tab)
        version_layout.setContentsMargins(5, 0, 5, 0)
        version_layout.setSpacing(10)

        # --- 版本控制基本操作组 ---
        vc_toolbar = QToolBar("版本控制")
        vc_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        vc_toolbar.setIconSize(QSize(48, 48))

        # 创建树按钮
        create_tree_action = QAction("创建版本树", self)
        create_tree_action.triggered.connect(self.create_vc_tree)
        create_tree_action.setToolTip("创建新的版本控制树")
        vc_toolbar.addAction(create_tree_action)

        # --- 版本导航组 ---
        nav_toolbar = QToolBar("版本导航")
        nav_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        nav_toolbar.setIconSize(QSize(48, 48))

        # 前进按钮
        forward_action = QAction("前进", self)
        forward_action.triggered.connect(self.vc_forward)
        forward_action.setToolTip("前进到下一步，如果没有则创建新步骤")
        nav_toolbar.addAction(forward_action)

        # 后退按钮
        backward_action = QAction("后退", self)
        backward_action.triggered.connect(self.vc_backward)
        backward_action.setToolTip("后退到上一步")
        nav_toolbar.addAction(backward_action)

        # 分叉按钮
        branch_action = QAction("分叉", self)
        branch_action.triggered.connect(self.vc_branch)
        branch_action.setToolTip("在当前位置创建新分支")
        nav_toolbar.addAction(branch_action)

        # --- 添加工具栏到布局 ---
        version_layout.addWidget(vc_toolbar)
        version_layout.addWidget(nav_toolbar)

        # --- 添加版本树视图区域 ---
        self.version_tree_view = QWidget()
        self.version_tree_view.setMinimumHeight(80)
        self.version_tree_view.setStyleSheet("""
            background-color: rgba(20, 20, 20, 120);
            border: 1px solid #555555;
            border-radius: 3px;
        """)

        # 版本树视图的绘制将在paintEvent中处理
        self.version_tree_view.paintEvent = lambda event: self.paint_version_tree(event, self.version_tree_view)

        # 如果已存在当前树，需要初始状态下显示
        if hasattr(self, 'tnxvc') and self.tnxvc:
            trees = self.tnxvc.get_tree_list()
            if trees and len(trees) > 0:
                # 加载第一个树进行显示
                self.tnxvc.load_tree(trees[0])

        version_layout.addWidget(self.version_tree_view, 1)  # 1代表伸缩系数，使其占据剩余空间

        # 添加标签页
        self.ribbon_widget.addTab(version_tab, "版本控制")
        return version_tab

    def create_vc_tree(self):
        """创建新的版本控制树（简化版本 - 自动基于节点图名称）"""
        if not hasattr(self, 'tnxvc') or not self.tnxvc:
            QMessageBox.warning(self, "错误", "版本控制系统未初始化")
            return

        # 检查是否有当前打开的节点图
        if len(self.nodes) == 0:
            QMessageBox.warning(self, "错误", "请先创建或打开一个节点图")
            return

        # 检查当前节点图是否已保存
        if not hasattr(self, 'current_nodegraph_path') or not self.current_nodegraph_path:
            QMessageBox.warning(self, "错误", "请先保存当前节点图")
            return

        try:
            # 保存节点图到文件
            if self.save_node_graph_to_file(self.current_nodegraph_path):
                # 自动创建或加载版本树（基于节点图文件名）
                success = self.tnxvc.auto_create_or_load_tree(self.current_nodegraph_path)
                if success:
                    QMessageBox.information(self, "成功", f"成功创建/加载版本树")
                    self.version_tree_view.update()  # 更新树视图
                else:
                    QMessageBox.warning(self, "创建失败", f"无法创建/加载版本树")
            else:
                QMessageBox.warning(self, "保存失败", "无法保存节点图文件")
        except Exception as e:
            print(f"创建版本树失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"创建版本树时发生错误: {e}")

    def vc_forward(self):
        """版本控制前进一步"""
        if not hasattr(self, 'tnxvc') or not self.tnxvc or not self.tnxvc.current_tree:
            QMessageBox.warning(self, "错误", "没有活动的版本树")
            return

        try:
            print("[版本控制] === 前进操作开始 ===")

            # 1. 首先自动保存当前节点图文件
            if self.current_nodegraph_path and hasattr(self, 'nodegraph_modified') and self.nodegraph_modified:
                print("[版本控制] 自动保存当前修改的节点图文件")
                if not self.save_node_graph_to_file(self.current_nodegraph_path):
                    QMessageBox.warning(self, "保存失败", "无法保存当前节点图，前进操作已取消")
                    return

            # 2. 获取清理后的节点图数据
            nodegraph_data = self._get_clean_nodegraph_data()
            nodegraph_data['metadata']['forward_operation'] = True

            print(f"[版本控制] 获取节点图数据，节点数量: {len(nodegraph_data['nodes'])}")

            # 3. 更新版本树的当前版本记录
            if self.tnxvc.current_version > 0:
                print(f"[版本控制] 更新当前版本 v{self.tnxvc.current_version} 的记录")
                self.tnxvc._update_version_record(self.tnxvc.current_version, nodegraph_data)

            # 4. 调用前进操作
            result = self.tnxvc.forward(nodegraph_data)

            if result["success"]:
                self.version_tree_view.update()  # 更新树视图

                # 如果需要重新加载节点图
                if result.get("needs_reload") and result.get("nodegraph_data"):
                    # 保存当前节点图状态
                    self.save_node_graph()

                    # 加载版本数据
                    self._load_nodegraph_from_data(result["nodegraph_data"])

                self.task_label.setText("已前进到新版本")
            else:
                QMessageBox.warning(self, "操作失败", "无法前进")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"前进操作失败: {e}")

    def vc_backward(self):
        """版本控制后退一步"""
        if not hasattr(self, 'tnxvc') or not self.tnxvc or not self.tnxvc.current_tree:
            QMessageBox.warning(self, "错误", "没有活动的版本树")
            return

        try:
            print("[版本控制] === 后退操作开始 ===")

            # 1. 首先自动保存当前节点图文件
            if self.current_nodegraph_path and hasattr(self, 'nodegraph_modified') and self.nodegraph_modified:
                print("[版本控制] 自动保存当前修改的节点图文件")
                if not self.save_node_graph_to_file(self.current_nodegraph_path):
                    QMessageBox.warning(self, "保存失败", "无法保存当前节点图，后退操作已取消")
                    return

            # 2. 更新当前版本记录
            if self.tnxvc.current_version > 0:
                print(f"[版本控制] 更新当前版本 v{self.tnxvc.current_version} 的记录")
                nodegraph_data = self._get_clean_nodegraph_data()
                self.tnxvc._update_version_record(self.tnxvc.current_version, nodegraph_data)

            # 3. 调用后退操作
            result = self.tnxvc.backward()

            if result["success"]:
                self.version_tree_view.update()  # 更新树视图

                # 如果需要重新加载节点图
                if result.get("needs_reload") and result.get("nodegraph_data"):
                    # 清除当前节点图
                    self.clear_node_graph()

                    # 加载版本数据
                    self._load_nodegraph_from_data(result["nodegraph_data"])

                self.task_label.setText("已后退到上一版本")
            else:
                QMessageBox.warning(self, "操作失败", "无法后退，已经是第一步")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"后退操作失败: {e}")

    def _get_clean_nodegraph_data(self):
        """获取清理后的节点图数据，用于版本控制"""
        # 准备并清理节点图数据
        clean_nodes = []
        for node in self.nodes:
            # 记录当前选中节点
            is_selected = (node == self.selected_node)

            # 使用改进的清理函数
            clean_node = self._clean_node_data_for_serialization(node)

            # 记录选中状态
            clean_node['selected'] = is_selected

            clean_nodes.append(clean_node)

        # 清理连接数据
        clean_connections = []
        for conn in self.connections:
            clean_conn = {}
            for key, value in conn.items():
                if key in ['output_node', 'input_node']:  # 这些是节点引用，需要特殊处理
                    if isinstance(value, dict) and 'id' in value:
                        clean_conn[key] = {'id': value['id']}
                else:
                    clean_conn[key] = value
            clean_connections.append(clean_conn)

        # 组装清理后的数据
        return {
            'nodes': clean_nodes,
            'connections': clean_connections,
            'metadata': {
                'saved_at': datetime.datetime.now().isoformat()
            }
        }

    def vc_branch(self):
        """创建版本控制分支"""
        if not hasattr(self, 'tnxvc') or not self.tnxvc or not self.tnxvc.current_tree:
            QMessageBox.warning(self, "错误", "没有活动的版本树")
            return

        try:
            # 准备并清理节点图数据
            clean_nodes = []
            for node in self.nodes:
                # 记录当前选中节点
                is_selected = (node == self.selected_node)

                # 使用改进的清理函数
                clean_node = self._clean_node_data_for_serialization(node)

                # 记录选中状态
                clean_node['selected'] = is_selected

                clean_nodes.append(clean_node)

            # 清理连接数据
            clean_connections = []
            for conn in self.connections:
                clean_conn = {}
                for key, value in conn.items():
                    if key in ['output_node', 'input_node']:  # 这些是节点引用，需要特殊处理
                        if isinstance(value, dict) and 'id' in value:
                            clean_conn[key] = {'id': value['id']}
                    else:
                        clean_conn[key] = value
                clean_connections.append(clean_conn)

            # 组装清理后的数据
            nodegraph_data = {
                'nodes': clean_nodes,
                'connections': clean_connections,
                'metadata': {
                    'branched_at': datetime.datetime.now().isoformat()
                }
            }

            # 保存当前节点图到文件以确保数据一致性
            self.save_node_graph_to_file(self.current_nodegraph_path)

            # 创建新分支
            result = self.tnxvc.branch(nodegraph_data)

            if result["success"]:
                self.version_tree_view.update()  # 更新树视图
                self.task_label.setText("已创建新分支")
            else:
                QMessageBox.warning(self, "操作失败", "无法创建分支")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建分支失败: {e}")

    def switch_version_tree_for_nodegraph(self, nodegraph_path):
        """根据节点图路径自动切换到对应的版本树

        参数:
            nodegraph_path: 当前节点图路径
        """
        if not hasattr(self, 'tnxvc') or not self.tnxvc:
            return

        try:
            # 使用TNXVC查找对应节点图的版本树
            tree_name = self.tnxvc.get_tree_for_nodegraph(nodegraph_path)

            if tree_name:
                # 如果找到对应版本树，切换到该树
                if self.tnxvc.current_tree != tree_name:
                    print(f"自动切换到节点图对应的版本树: {tree_name}")
                    self.tnxvc.load_tree(tree_name)
                    # 更新版本树视图
                    if hasattr(self, 'version_tree_view'):
                        self.version_tree_view.update()
            else:
                # 没有找到对应版本树，如果当前有已加载的版本树，则删除当前版本树的引用
                if self.tnxvc.current_tree:
                    print(f"没有找到节点图对应的版本树，清除当前版本树状态")
                    self.tnxvc.current_tree = None
                    self.tnxvc.current_nodegraph_path = None
                    self.tnxvc.tree_metadata = None
                    self.tnxvc.current_version = 0
                    self.tnxvc.nodegraph_data = None
                    # 更新版本树视图
                    if hasattr(self, 'version_tree_view'):
                        self.version_tree_view.update()
        except Exception as e:
            print(f"切换版本树时出错: {e}")

    def paint_version_tree(self, event, widget):
        """绘制版本树视图"""
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.Antialiasing)

        # 如果没有活动的版本树，显示提示信息
        if not hasattr(self, 'tnxvc') or not self.tnxvc or not self.tnxvc.current_tree:
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawText(widget.rect(), Qt.AlignCenter, "没有活动的版本树\n使用“创建版本树”按钮开始")
            return

        # 获取版本树结构
        tree_info = self.tnxvc.get_tree_structure()
        if not tree_info:
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.drawText(widget.rect(), Qt.AlignCenter, "版本树数据获取失败")
            return

        # 绘制标题
        painter.setPen(QPen(QColor(220, 220, 220)))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QRect(10, 5, widget.width() - 20, 30),
                        Qt.AlignLeft | Qt.AlignTop,
                        f"版本树: {tree_info['name']}")

        # 恢复字体
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)

        # 计算绘图区域
        tree_area = QRect(10, 40, widget.width() - 20, widget.height() - 50)

        # 获取当前版本（简化版本）
        current_version = tree_info['current_version']

        # 绘制版本树（简化版本，横向绘制）
        versions = tree_info['versions']

        # 计算版本间距
        version_width = min(80, tree_area.width() / max(len(versions), 1))
        version_y = tree_area.top() + tree_area.height() / 2

        # 绘制每个版本（简化版本）
        for version_idx, version in enumerate(versions):
            version_x = tree_area.left() + version_idx * version_width + 20

            # 根据是否为当前版本选择颜色
            is_current = (version['version'] == current_version)

            if is_current:
                # 当前版本高亮
                node_color = QColor(160, 80, 200)  # 紫色高亮
                port_color = QColor(200, 120, 255)
            else:
                # 普通版本
                node_color = QColor(80, 80, 80)
                port_color = QColor(120, 120, 120)

            # 绘制版本节点（类似于主程序的端口样式）
            node_rect = QRect(version_x - 10, version_y - 10, 20, 20)

            # 绘制节点底色
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(node_color))
            painter.drawEllipse(node_rect)

            # 绘制端口高光
            grad = QRadialGradient(version_x, version_y, 12)
            grad.setColorAt(0, port_color)
            grad.setColorAt(1, QColor(node_color))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(node_rect)

            # 绘制边框
            painter.setPen(QPen(QColor(40, 40, 40), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(node_rect)

            # 如果不是第一个版本，绘制连接线
            if version_idx > 0:
                prev_x = tree_area.left() + (version_idx - 1) * version_width + 20
                painter.setPen(QPen(QColor(100, 100, 100), 2))
                painter.drawLine(prev_x + 10, version_y, version_x - 10, version_y)

            # 绘制版本号
            painter.setPen(QPen(QColor(220, 220, 220)))
            painter.drawText(QRect(version_x - 10, version_y + 15, 20, 20),
                           Qt.AlignCenter,
                           f"v{version['version']}")

            # 绘制版本名称（如果有空间）
            if version_width > 60:
                painter.setPen(QPen(QColor(180, 180, 180)))
                painter.drawText(QRect(version_x - 30, version_y - 35, 60, 20),
                               Qt.AlignCenter,
                               version.get('name', f"版本{version['version']}"))

            # 如果鼠标悬停在这个节点上，显示详细信息
            # 暂未实现鼠标事件处理

        # 添加说明文字（简化版本）
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(QRect(tree_area.left(), tree_area.bottom() - 20, tree_area.width(), 20),
                       Qt.AlignLeft,
                       f"当前版本: v{current_version}, 总版本数: {len(versions)}")

        # 完成绘制
        painter.end()
    def _load_nodegraph_from_data(self, nodegraph_data):
        """从版本控制数据加载节点图，重建完整的节点图结构

        Args:
            nodegraph_data: 版本控制中保存的节点图数据
        """
        if not nodegraph_data:
            print("无法加载节点图：数据为空")
            return False

        try:
            print("开始从版本控制数据重建节点图...")

            # 完全清除当前节点图
            self.clear_node_graph(suppress_auto_save=True)

            # 重建节点图 - 使用类似load_node_graph_from_file的逻辑
            if 'nodes' in nodegraph_data and nodegraph_data['nodes']:
                # 创建节点映射表
                nodes_map = {}

                # 重建每个节点
                for node_data in nodegraph_data['nodes']:
                    # 查找脚本信息
                    script_path = node_data.get('script_path')
                    if not script_path:
                        print(f"节点缺少script_path，跳过: {node_data}")
                        continue

                    script_info = None

                    # 遍历注册表找到脚本信息
                    def find_script_info(registry, path):
                        for key, value in registry.items():
                            if isinstance(value, dict):
                                if 'path' in value and value['path'] == path:
                                    return value['info']
                                else:
                                    result = find_script_info(value, path)
                                    if result:
                                        return result
                        return None

                    script_info = find_script_info(self.script_registry, script_path)

                    if not script_info:
                        print(f"找不到脚本: {script_path}，跳过该节点")
                        continue

                    # 创建节点（这会创建所有必要的可视化组件）
                    node = self.add_node(script_path, script_info)

                    # 恢复节点属性
                    if 'x' in node_data:
                        node['x'] = node_data['x']
                    if 'y' in node_data:
                        node['y'] = node_data['y']
                    if 'widget' in node and node['widget']:
                        node['widget'].move(node['x'], node['y'])

                    # 恢复节点参数
                    if 'params' in node_data:
                        for param_name, param_value in node_data['params'].items():
                            if param_name in node['params']:
                                if isinstance(param_value, dict) and 'value' in param_value:
                                    node['params'][param_name]['value'] = param_value['value']
                                else:
                                    node['params'][param_name]['value'] = param_value

                    # 恢复灵活端口信息
                    if 'flexible_ports' in node_data:
                        node['flexible_ports'] = node_data['flexible_ports']

                    # 恢复端口计数
                    if 'port_counts' in node_data:
                        node['port_counts'] = node_data['port_counts']

                    # 记录节点映射（使用原始ID）
                    original_id = node_data.get('id')
                    if original_id is not None:
                        nodes_map[original_id] = node

                print(f"重建了 {len(nodes_map)} 个节点")

                # 重建连接
                if 'connections' in nodegraph_data and nodegraph_data['connections']:
                    for conn_data in nodegraph_data['connections']:
                        try:
                            # 获取连接信息
                            if isinstance(conn_data, dict):
                                # 新格式：包含节点引用
                                if 'output_node' in conn_data and 'input_node' in conn_data:
                                    output_node_id = conn_data['output_node'].get('id')
                                    input_node_id = conn_data['input_node'].get('id')
                                    output_port = conn_data.get('output_port', 0)
                                    input_port = conn_data.get('input_port', 0)
                                # 旧格式：直接包含节点ID
                                elif 'output_node_id' in conn_data and 'input_node_id' in conn_data:
                                    output_node_id = conn_data['output_node_id']
                                    input_node_id = conn_data['input_node_id']
                                    output_port = conn_data.get('output_port', 0)
                                    input_port = conn_data.get('input_port', 0)
                                else:
                                    print(f"连接数据格式不正确，跳过: {conn_data}")
                                    continue

                                # 查找对应的节点
                                if output_node_id in nodes_map and input_node_id in nodes_map:
                                    output_node = nodes_map[output_node_id]
                                    input_node = nodes_map[input_node_id]

                                    # 创建连接
                                    self.create_connection(output_node, output_port, input_node, input_port)
                                else:
                                    print(f"找不到连接的节点: {output_node_id} -> {input_node_id}")
                        except Exception as e:
                            print(f"重建连接失败: {e}")
                            continue

                print(f"重建了 {len(self.connections)} 个连接")

            # 更新界面
            self.update_preview(force_refresh=True)  # 强制刷新预览
            self.update_node_settings(None)  # 清除设置面板
            self.node_canvas_widget.update()  # 更新节点画布

            self.task_label.setText("已从版本控制加载节点图")
            print("版本控制节点图重建完成")

            return True
        except Exception as e:
            print(f"从版本控制数据加载节点图失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_work_area(self):
        """创建工作区域"""
        # 创建可分割的工作区域
        self.work_area = QFrame()
        self.work_area.setFrameShape(QFrame.StyledPanel)
        self.main_layout.addWidget(self.work_area, 1)  # 工作区占主要空间

        # 创建可调整的面板
        print("CREATE_WORK_AREA: About to call create_paned_areas.")
        self.create_paned_areas()
        print(f"CREATE_WORK_AREA (After create_paned_areas): self.film_preview_list ID={id(self.film_preview_list)}, Parent={self.film_preview_list.parentWidget()}")


    def on_film_item_double_clicked(self, item):
        """当胶片预览中的项目被双击时调用"""
        if item:
            image_path = item.data(Qt.UserRole) # 从 UserRole 获取完整路径
            if image_path and os.path.exists(image_path):
                self.open_image_path(image_path)
            else:
                print(f"无法打开图像，路径无效或文件不存在: {image_path}")
        """创建底部胶片预览区"""
        self.bottom_preview = QFrame()
        self.bottom_preview.setFrameShape(QFrame.StyledPanel)
        self.bottom_preview.setMaximumHeight(120)
        self.main_layout.addWidget(self.bottom_preview)

        # 胶片预览布局
        film_layout = QHBoxLayout(self.bottom_preview)
        self.film_preview = QFrame()
        # 为film_preview设置布局，避免layout()返回None
        QHBoxLayout(self.film_preview)
        film_layout.addWidget(self.film_preview)

        # 清理孤立的缩略图文件
        self.cleanup_orphaned_thumbnails()

        # 更新胶片预览
        self.update_film_preview()

        # --- 设置 bottom_preview 的 objectName ---
        self.bottom_preview.setObjectName("bottom_preview")
        # ----------------------------------------

    def create_toolbar_buttons(self):
        """创建改进的工具栏按钮"""
        # 创建工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)
        self.toolbar = QFrame()
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        self.top_tools_frame.layout().addWidget(self.toolbar)

        # 定义工具按钮分组
        tool_groups = [
            # 缩放工具组
            [
                {"emoji": "🔍", "text": "放大", "command": self.zoom_in, "tooltip": "放大图像"},
                {"emoji": "🔎", "text": "缩小", "command": self.zoom_out, "tooltip": "缩小图像"},
                {"emoji": "↔️", "text": "适应", "command": self.zoom_fit, "tooltip": "适应窗口"}
            ],
            # 文件操作组
            [
                {"emoji": "📂", "text": "打开", "command": self.open_image, "tooltip": "打开图像"},
                {"emoji": "💾", "text": "保存", "command": self.save_node_graph, "tooltip": "保存节点图"},
                {"emoji": "📥", "text": "导入", "command": self.load_node_graph, "tooltip": "导入节点图"},
                {"emoji": "📤", "text": "导出", "command": self.export_image, "tooltip": "导出处理后图像"}
            ]
        ]

        # 跟踪所有按钮
        self.toolbar_buttons = []

        # 创建分组工具按钮
        for group_index, group in enumerate(tool_groups):
            # 创建工具组框架
            group_frame = QFrame()
            group_layout = QHBoxLayout(group_frame)
            group_layout.setSpacing(3)
            toolbar_layout.addWidget(group_frame)

            # 添加工具组中的按钮
            for tool in group:
                # 创建按钮
                btn = QPushButton(f"{tool['emoji']}\n{tool['text']}")
                btn.setMinimumWidth(60)
                btn.clicked.connect(tool['command'])
                group_layout.addWidget(btn)

                # 存储按钮引用
                self.toolbar_buttons.append(btn)

                # 设置工具提示
                btn.setToolTip(tool['tooltip'])


        # 将布局添加到工具栏
        self.toolbar.setLayout(toolbar_layout)

    def zoom_in(self):
        """放大预览图像，以预览中心为锚点"""
        if hasattr(self, 'preview_display_widget') and self.preview_display_widget:
            # 获取滚动区域的视口中心点
            viewport_width = self.preview_scroll.viewport().width()
            viewport_height = self.preview_scroll.viewport().height()

            # 使用视口中心作为缩放中心点
            center_point = QPoint(viewport_width // 2, viewport_height // 2)

            # 直接调用 PreviewDisplayWidget 的缩放方法
            success = self.preview_display_widget.zoom_in(center_point)

            # 如果缩放成功，不需再次更新预览
            if success:
                return

        # 旧方法兼容代码（应该不会执行到这里）
        self.zoom_level *= 1.15
        if self.zoom_level > 10.0:
            self.zoom_level = 10.0

        if hasattr(self, 'zoom_info'):
            self.zoom_info.setText(f"缩放: {int(self.zoom_level * 100)}%")

        self.update_preview_with_zoom()

    def zoom_out(self):
        """缩小预览图像，以预览中心为锚点"""
        if hasattr(self, 'preview_display_widget') and self.preview_display_widget:
            # 获取滚动区域的视口中心点
            viewport_width = self.preview_scroll.viewport().width()
            viewport_height = self.preview_scroll.viewport().height()

            # 使用视口中心作为缩放中心点
            center_point = QPoint(viewport_width // 2, viewport_height // 2)

            # 直接调用 PreviewDisplayWidget 的缩放方法
            success = self.preview_display_widget.zoom_out(center_point)

            # 如果缩放成功，不需再次更新预览
            if success:
                return

        # 旧方法兼容代码（应该不会执行到这里）
        self.zoom_level /= 1.15
        if self.zoom_level < 0.1:
            self.zoom_level = 0.1

        if hasattr(self, 'zoom_info'):
            self.zoom_info.setText(f"缩放: {int(self.zoom_level * 100)}%")

        self.update_preview_with_zoom()

    def zoom_fit(self):
        """适应窗口大小"""
        if hasattr(self, 'preview_display_widget') and self.preview_display_widget:
            # 直接调用 PreviewDisplayWidget 的缩放适应方法
            success = self.preview_display_widget.zoom_fit()

            # 如果缩放成功，同步缩放级别到主应用
            if success:
                self.zoom_level = self.preview_display_widget.zoom_level
                if hasattr(self, 'zoom_info'):
                    self.zoom_info.setText(f"缩放: {int(self.zoom_level * 100)}%")
                return

        # 旧方法兼容代码（应该不会执行到这里）
        self.zoom_level = 1.0
        if hasattr(self, 'zoom_info'):
            self.zoom_info.setText("缩放: 100%")

        self.update_preview()
    def open_image(self):
        """打开图像文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开图像文件",
            self.work_folder,
            "图像文件 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp);;所有文件 (*.*)"
        )

        if file_path:
            self.open_image_path(file_path)

    def import_multiple_images(self):
        """导入多张图片，每张图片创建图像节点+解码节点"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "导入多张图片",
            self.work_folder,
            "图像文件 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp);;所有文件 (*.*)"
        )

        if not file_paths:
            return

        # 查找图像节点和解码节点的脚本
        image_script = None
        decode_script = None
        image_info = None
        decode_info = None

        # 递归查找图像节点和解码节点脚本
        def find_image_script(registry):
            for key, value in registry.items():
                if isinstance(value, dict):
                    if 'path' in value:
                        script_path = value['path']
                        if '图像节点' in os.path.basename(script_path):
                            return value['path'], value['info']
                    else:
                        result = find_image_script(value)
                        if result:
                            return result
            return None

        def find_decode_script(registry):
            for key, value in registry.items():
                if isinstance(value, dict):
                    if 'path' in value:
                        script_path = value['path']
                        if '解码节点' in os.path.basename(script_path):
                            return value['path'], value['info']
                    else:
                        result = find_decode_script(value)
                        if result:
                            return result
            return None

        # 查找图像节点和解码节点
        image_script_info = find_image_script(self.script_registry)
        decode_script_info = find_decode_script(self.script_registry)

        if image_script_info:
            image_script, image_info = image_script_info

        if decode_script_info:
            decode_script, decode_info = decode_script_info

        # 如果找不到，尝试直接从文件夹加载
        if not image_script or not image_info:
            image_script = os.path.join(self.scripts_folder, "图像节点.py")
            if os.path.exists(image_script):
                image_info = self.parse_script_header(image_script)

        if not decode_script or not decode_info:
            decode_script = os.path.join(self.scripts_folder, "解码节点.py")
            if os.path.exists(decode_script):
                decode_info = self.parse_script_header(decode_script)

        if not image_script or not decode_script or not image_info or not decode_info:
            QMessageBox.warning(self, "导入图片", "找不到图像节点或解码节点脚本")
            return

        # 记录当前节点数，用于计算新节点的位置
        start_x = 100
        start_y = 100
        spacing_y = 150
        spacing_x = 450  # 水平间距
        nodes_per_column = 6  # 每列节点数

        # 保存所有创建的节点，用于后续处理
        created_nodes = []

        # 处理每个图片文件
        for i, file_path in enumerate(file_paths):
            try:
                # 计算当前节点的列和行
                column = i // nodes_per_column
                row = i % nodes_per_column

                # 为每个图片创建图像节点
                image_node = self.add_node(image_script, image_info)

                # 设置图像节点的位置 - 使用网格布局
                image_node['x'] = start_x + column * spacing_x
                image_node['y'] = start_y + row * spacing_y
                if 'widget' in image_node:
                    image_node['widget'].move(image_node['x'], image_node['y'])

                # 设置图像路径参数
                if 'params' in image_node and 'image_path' in image_node['params']:
                    self.update_node_param(image_node, 'image_path', file_path)

                # 创建解码节点
                decode_node = self.add_node(decode_script, decode_info)

                # 设置解码节点的位置
                decode_node['x'] = start_x + column * spacing_x + 200
                decode_node['y'] = start_y + row * spacing_y
                if 'widget' in decode_node:
                    decode_node['widget'].move(decode_node['x'], decode_node['y'])

                # 创建连接：图像节点 -> 解码节点
                self.create_connection(image_node, 0, decode_node, 0)

                created_nodes.extend([image_node, decode_node])

            except Exception as e:
                print(f"导入图片 {file_path} 时出错: {str(e)}")

        # 更新连接线
        self.update_connections()

        # 处理节点图
        self.process_node_graph()

        # 注: 此处原自动保存代码已移除

    def open_image_path(self, file_path):
        """打开指定路径的图像，创建新的节点图"""
        try:
            # 显示加载指示器
            self.task_label.setText("正在加载图像...")
            QApplication.processEvents()  # 强制更新UI

            # 0. 检查文件是否存在
            if not os.path.exists(file_path):
                QMessageBox.critical(self, "错误", f"图像文件不存在: {file_path}")
                self.task_label.setText("图像加载失败")
                return False

            # 1. 保存当前节点图 (如果当前有节点)
            if hasattr(self, 'current_nodegraph_path') and self.current_nodegraph_path and self.nodes:
                try:
                    print(f"切换图片: 正在保存当前节点图到: {self.current_nodegraph_path}")
                    # 保存主文件，但不抑制自动保存（允许记录撤销状态）
                    if not self.save_node_graph_to_file(self.current_nodegraph_path):
                        print(f"警告: 保存当前节点图失败: {self.current_nodegraph_path}")
                # 注: 此处原自动保存代码已移除
                except Exception as e:
                    print(f"切换图片时保存节点图出错: {str(e)}")
                    # 不阻止切换

            # 2. 复制（如果需要）并设置新图像路径
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.work_folder, filename)
            # 检查文件是否已在工作文件夹中
            if os.path.normpath(file_path) != os.path.normpath(dest_path):
                try:
                    # 如果目标文件已存在，先检查是否相同
                    if os.path.exists(dest_path):
                        # 检查文件是否相同（比较修改时间和大小）
                        src_stat = os.stat(file_path)
                        dst_stat = os.stat(dest_path)
                        if src_stat.st_size == dst_stat.st_size and abs(src_stat.st_mtime - dst_stat.st_mtime) < 2:
                            print(f"文件已存在且内容相同，直接使用: {dest_path}")
                        else:
                            # 复制并覆盖
                            shutil.copy2(file_path, dest_path)
                            print(f"已复制并覆盖图像至工作文件夹: {dest_path}")
                    else:
                        # 文件不存在，直接复制
                        shutil.copy2(file_path, dest_path)
                        print(f"已复制图像至工作文件夹: {dest_path}")
                    self.current_image_path = dest_path # 使用工作文件夹中的路径
                except Exception as copy_e:
                     QMessageBox.warning(self, "复制警告", f"无法将图像复制到工作文件夹，将直接使用原始路径。\n错误: {copy_e}")
                     self.current_image_path = file_path # 出错则使用原始路径
            else:
                 self.current_image_path = file_path # 本来就在工作目录

            # 3. 清空当前节点图 (抑制自动保存, 因为这是加载过程的一部分)
            print("清空当前节点图...")
            self.clear_node_graph(suppress_auto_save=True)

            # 4. 创建新的节点图文件名 (图片名+时间戳)
            import time
            image_filename_no_ext = os.path.splitext(filename)[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            new_graph_name = f"{image_filename_no_ext}_{timestamp}"
            new_graph_path = os.path.join(self.nodegraphs_folder, f"{new_graph_name}.json")

            # 使用统一的状态管理设置当前节点图路径和状态
            self.set_nodegraph_state(
                path=new_graph_path,
                is_new=True,
                modified=False
            )

            print(f"创建的新节点图路径: {new_graph_path}")

            # 5. 创建默认节点图
            print(f"创建新节点图: {new_graph_path}")
            self.task_label.setText("创建新节点图...")
            QApplication.processEvents()

            # 创建默认图时不抑制自动保存，让其成为可撤销的第一步
            self.create_default_node_graph() # 内部应调用 process_node_graph

            # 确保默认图创建后，图像节点正确指向当前图像
            image_node = next((n for n in self.nodes if n.get('type') == 'ImageSource'), None)
            if image_node and 'params' in image_node and 'image_path' in image_node['params']:
                self.update_node_param(image_node, 'image_path', self.current_image_path)
                # 可能需要重新处理一下，确保图像正确加载
                self.process_node_graph()
            else:
                print("警告：创建默认图后未找到图像节点或参数，预览可能不正确。")

            # 标记节点图为已修改，以便在退出时会询问保存
            self.set_nodegraph_state(modified=True)


            # 6. 更新UI
            self.setWindowTitle(f"TunnelNX - {filename}")
            print(self.work_folder)
            print(f"OPEN_IMAGE_PATH (Before update_film_preview): self.film_preview_list ID={id(self.film_preview_list)}, Parent={self.film_preview_list.parentWidget()}, Visible={self.film_preview_list.isVisible()}")
            if self.film_preview_list.parentWidget():
                print(f"  Parent is: {self.film_preview_list.parentWidget().objectName()} of type {type(self.film_preview_list.parentWidget())}")
            self.update_film_preview() # 更新胶片预览缩略图
            self.zoom_fit() # 加载新图后适应窗口

            # 切换到视图标签页
            view_tab_index = -1
            for i in range(self.ribbon_widget.count()):
                if self.ribbon_widget.tabText(i) == "视图":
                    view_tab_index = i
                    break
            if view_tab_index != -1:
                self.ribbon_widget.setCurrentIndex(view_tab_index)

            # 更新最终状态
            self.task_label.setText(f"已加载: {filename} (新节点图)")

            # 注: 此处原自动保存定时器代码已移除

            return True
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"打开图像或节点图时发生严重错误: {str(e)}")
            import traceback
            traceback.print_exc()
            self.task_label.setText("图像加载失败")
            # 尝试恢复到一个安全状态，例如清空
            try:
                self.clear_node_graph()
                self.current_image_path = None
                self.setWindowTitle("TunnelNX")
                self.update_preview()
            except Exception as recovery_e:
                 print(f"恢复状态时出错: {recovery_e}")
            return False


    def set_nodegraph_state(self, path=None, is_new=None, modified=None):
        """统一管理节点图状态的核心函数

        参数:
            path: 设置当前节点图路径
            is_new: 设置是否为新创建的节点图
            modified: 设置节点图是否被修改过
        """
        print("\n========== 节点图状态更新 ==========")
        # 记录调用位置，帮助调试
        import traceback
        stack = traceback.extract_stack()
        caller = stack[-2]
        print(f"调用位置: {os.path.basename(caller.filename)}:{caller.lineno}, 函数: {caller.name}")

        # 更新路径（如果提供）
        if path is not None:
            old_path = self.current_nodegraph_path
            self.current_nodegraph_path = path
            print(f"节点图路径从 '{old_path}' 更新为 '{path}'")

            # 文件切换时自动切换版本树
            self.switch_version_tree_for_nodegraph(path)

        # 更新新建状态（如果提供）
        if is_new is not None:
            old_state = self.is_new_nodegraph if hasattr(self, 'is_new_nodegraph') else None
            self.is_new_nodegraph = is_new
            print(f"节点图新建状态从 {old_state} 更新为 {is_new}")

        # 更新修改状态（如果提供）
        if modified is not None:
            old_modified = self.nodegraph_modified if hasattr(self, 'nodegraph_modified') else None
            self.nodegraph_modified = modified
            print(f"节点图修改状态从 {old_modified} 更新为 {modified}")

        # 打印状态更新后的完整状态
        print(f"当前完整状态: 路径={self.current_nodegraph_path}, 新建={self.is_new_nodegraph}, 修改={self.nodegraph_modified}")
        print("===================================\n")

        # 更新窗口标题，显示当前状态
        title = "TunnelNX"
        if self.current_nodegraph_path:
            basename = os.path.basename(self.current_nodegraph_path)
            title = f"{title} - {basename}"
            if self.is_new_nodegraph:
                title += " [新建]"
            if self.nodegraph_modified:
                title += " *"
        self.setWindowTitle(title)

    def save_node_graph(self):
        """保存节点图配置"""
        # 【DEBUG】: 打印当前节点图详细状态
        print("\n========== 节点图保存状态详情 ==========")
        print(f"当前节点图路径: {self.current_nodegraph_path}")
        print(f"节点图是否为新创建: {self.is_new_nodegraph}")
        print(f"节点图是否被修改: {self.nodegraph_modified}")
        print(f"节点数量: {len(self.nodes)}")
        print(f"连接数量: {len(self.connections)}")
        print(f"窗口标题: {self.windowTitle()}")

        # 打印调用栈信息，帮助诊断是从哪里触发的保存
        import traceback
        print("调用栈信息:")
        traceback.print_stack(limit=8)

        # 打印每个节点的简要信息
        for i, node in enumerate(self.nodes):
            print(f"节点[{i}]: ID={node['id']}, 标题={node['title']}, 位置=({node['x']}, {node['y']})")
        print("======================================\n")

        # 如果没有节点，不保存
        if not self.nodes:
            QMessageBox.information(self, "提示", "没有节点图可保存")
            return

        try:
            # 判断当前节点图是否是已打开的存在的节点图
            is_opened_nodegraph = (self.current_nodegraph_path and
                                 os.path.exists(self.current_nodegraph_path))

            print(f"保存检查 - 当前节点图路径: {self.current_nodegraph_path}")
            print(f"是已打开的节点图? {is_opened_nodegraph}")
            print(f"是新创建的节点图? {self.is_new_nodegraph}")
            print(f"节点图修改状态: {self.nodegraph_modified}")

            # 如果是打开的节点图，直接保存 (不考虑是否为新建状态)
            if is_opened_nodegraph:
                print(f"直接保存到当前节点图: {self.current_nodegraph_path}")
                if self.save_node_graph_to_file(self.current_nodegraph_path):
                    # 更新状态：保存后不再是新创建的节点图
                    self.set_nodegraph_state(is_new=False, modified=False)
                    # 更新胶片预览（可选）
                    self.update_film_preview()
                else:
                    QMessageBox.critical(self, "保存错误", "保存节点图时出错")
                return

            # 否则，创建新文件并询问用户命名
            # 准备默认文件名（基于当前图像或时间戳）
            if self.current_image_path:
                image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]
                # 创建默认文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"{image_filename}_{timestamp}.json"
            else:
                # 如果没有加载图片，使用时间戳作为默认文件名
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"nodegraph_{timestamp}.json"

            default_file_path = os.path.join(self.nodegraphs_folder, filename)

            # 创建一个对话框询问用户是否使用默认命名
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit

            dialog = QDialog(self)
            dialog.setWindowTitle("保存节点图")
            layout = QVBoxLayout(dialog)

            # 添加提示标签
            prompt_label = QLabel("请输入节点图名称，或选择使用默认命名")
            layout.addWidget(prompt_label)

            # 添加输入框
            input_layout = QHBoxLayout()
            input_label = QLabel("文件名:")
            input_field = QLineEdit(os.path.splitext(filename)[0])  # 默认文件名（不含扩展名）
            input_layout.addWidget(input_label)
            input_layout.addWidget(input_field)
            layout.addLayout(input_layout)

            # 添加按钮布局
            button_layout = QHBoxLayout()
            cancel_button = QPushButton("取消")
            default_button = QPushButton("使用默认命名")
            save_button = QPushButton("保存")
            save_button.setDefault(True)

            button_layout.addWidget(cancel_button)
            button_layout.addWidget(default_button)
            button_layout.addWidget(save_button)
            layout.addLayout(button_layout)

            # 连接按钮信号
            save_path = [None]  # 使用列表存储最终路径，以便在lambda函数中修改

            cancel_button.clicked.connect(dialog.reject)

            def use_default_name():
                save_path[0] = default_file_path
                dialog.accept()

            default_button.clicked.connect(use_default_name)

            def save_with_custom_name():
                custom_name = input_field.text().strip()
                if not custom_name:
                    QMessageBox.warning(dialog, "错误", "文件名不能为空")
                    return

                # 确保有.json扩展名
                if not custom_name.lower().endswith('.json'):
                    custom_name += '.json'

                custom_path = os.path.join(self.nodegraphs_folder, custom_name)

                # 检查文件是否已存在
                if os.path.exists(custom_path):
                    reply = QMessageBox.question(
                        dialog,
                        "文件已存在",
                        f"文件 {custom_name} 已存在，是否覆盖?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return

                save_path[0] = custom_path
                dialog.accept()

            save_button.clicked.connect(save_with_custom_name)

            # 显示对话框
            result = dialog.exec_()

            # 处理结果
            if result == QDialog.Accepted and save_path[0]:
                file_path = save_path[0]

                # 保存节点图
                if self.save_node_graph_to_file(file_path):
                    # 使用统一的节点图状态管理
                    self.set_nodegraph_state(
                        path=file_path,
                        is_new=False,
                        modified=False
                    )
                    # 更新胶片预览显示
                    self.update_film_preview()
                    QMessageBox.information(self, "保存成功", f"节点图已保存到:\n{file_path}")
                else:
                    QMessageBox.critical(self, "保存错误", "保存节点图时出错")

        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存节点图时出错:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def load_node_graph(self):
        """加载节点图配置"""
        # 自动保存当前节点图（如果有）
        if hasattr(self, 'current_nodegraph_path') and self.current_nodegraph_path and self.nodes:
            try:
                # 自动保存当前节点图
                success = self.save_node_graph_to_file(self.current_nodegraph_path)
                if success:
                    print(f"自动保存当前节点图成功: {self.current_nodegraph_path}")
                else:
                    print(f"自动保存当前节点图失败")
            except Exception as e:
                print(f"保存当前节点图时出错: {e}")

        # 选择加载文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载节点图",
            self.nodegraphs_folder,
            "JSON文件 (*.json);;所有文件 (*.*)"
        )

        if not file_path:
            return

        # 检查文件是否在工作文件夹内
        is_in_workfolder = os.path.abspath(file_path).startswith(os.path.abspath(self.nodegraphs_folder))

        # 如果不在工作文件夹内，创建副本
        target_path = file_path  # 默认使用原始路径

        if not is_in_workfolder:
            # 创建副本到工作文件夹
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            new_filename = f"{base_name}_{timestamp}.json"
            target_path = os.path.join(self.nodegraphs_folder, new_filename)

            try:
                shutil.copy2(file_path, target_path)
                print(f"为工作文件夹外的节点图创建副本: {file_path} -> {target_path}")
            except Exception as e:
                print(f"创建节点图副本时出错: {str(e)}")
                # 如果创建副本失败，提示用户并使用原路径
                reply = QMessageBox.question(
                    self,
                    "创建副本失败",
                    f"无法在工作文件夹创建节点图副本: {str(e)}\n是否直接打开原文件?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                target_path = file_path  # 使用原始路径

        try:
            # 加载节点图
            if self.load_node_graph_from_file(target_path):
                # 注意：不需要再次设置状态，load_node_graph_from_file 已经正确设置

                # 处理节点图并更新预览，禁用自动保存
                self.process_node_graph(suppress_auto_save=True)
                # 更新缩放以适应显示
                self.zoom_fit()
                # 更新状态栏
                if is_in_workfolder:
                    self.task_label.setText(f"已打开节点图: {os.path.basename(target_path)}")
                    QMessageBox.information(self, "加载成功", f"节点图已加载: {os.path.basename(target_path)}")
                else:
                    self.task_label.setText(f"已打开节点图副本: {os.path.basename(target_path)}")
                    QMessageBox.information(self, "加载成功", f"已创建并加载节点图副本: {os.path.basename(target_path)}")
            else:
                QMessageBox.critical(self, "加载错误", "加载节点图时出错")
        except Exception as e:
            print(f"加载节点图时出错: {str(e)}")
            QMessageBox.critical(self, "加载错误", f"加载节点图时出错: {str(e)}")

    def export_image(self):
        """导出处理后的图像"""
        # 检查是否有预览节点
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        if not preview_node:
            QMessageBox.information(self, "提示", "没有预览节点可导出")
            return

        # 确保预览节点和其所有上游节点都已处理
        self._ensure_preview_dependencies_processed(preview_node)

        # 获取输出图像
        img = None
        if 'processed_outputs' in preview_node:
            if 'f32bmp' in preview_node['processed_outputs']:
                img = preview_node['processed_outputs']['f32bmp']
            elif 'tif16' in preview_node['processed_outputs']:
                img = preview_node['processed_outputs']['tif16']

        if img is None:
            QMessageBox.information(self, "提示", "没有可导出的图像")
            return

        # 获取保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图像",
            self.work_folder,
            "JPEG文件 (*.jpg);;PNG文件 (*.png);;TIFF文件 (*.tif);;所有文件 (*.*)"
        )

        if file_path:
            # 确保文件有正确的扩展名
            if not any(file_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']):
                file_path += '.jpg'  # 默认添加jpg扩展名

            try:
                # 转换图像
                if img.dtype == np.float32:
                    # 将32位浮点图像转换为8位用于保存
                    img_save = (img * 255).clip(0, 255).astype(np.uint8)
                elif img.dtype == np.uint16:
                    # 将16位图像转换为8位用于保存
                    img_save = (img / 256).astype(np.uint8)
                else:
                    img_save = img

                # 保存图像
                cv2.imwrite(file_path, cv2.cvtColor(img_save, cv2.COLOR_RGB2BGR))

                QMessageBox.information(self, "导出成功", f"图像已保存到:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "导出错误", f"保存图像时出错: {str(e)}")

    def init_zoom_functionality(self):
        """初始化和配置缩放功能"""
        # 确保缩放级别已初始化
        self.zoom_level = 1.0

        # 更新缩放信息显示
        if hasattr(self, 'zoom_info'):
            self.zoom_info.setText("缩放: 100%")

        # --- 移除旧的鼠标滚轮事件处理 ---
        # 添加鼠标滚轮事件处理
        # self.preview_canvas.wheelEvent = self.on_preview_mousewheel
        # 滚轮事件现在通过 preview_scroll.viewport() 的事件过滤器处理

        # 添加键盘快捷键
        self.add_zoom_keyboard_shortcuts()

    def add_zoom_keyboard_shortcuts(self):
        """添加缩放相关的键盘快捷键"""
        # 放大快捷键 - Ctrl+加号
        zoom_in_shortcut = QAction("放大", self)
        zoom_in_shortcut.setShortcut("Ctrl++")
        zoom_in_shortcut.triggered.connect(self.zoom_in)
        self.addAction(zoom_in_shortcut)

        # 放大快捷键 - Ctrl+等号(兼容不需要Shift的键盘)
        zoom_in_shortcut2 = QAction("放大2", self)
        zoom_in_shortcut2.setShortcut("Ctrl+=")
        zoom_in_shortcut2.triggered.connect(self.zoom_in)
        self.addAction(zoom_in_shortcut2)

        # 缩小快捷键 - Ctrl+减号
        zoom_out_shortcut = QAction("缩小", self)
        zoom_out_shortcut.setShortcut("Ctrl+-")
        zoom_out_shortcut.triggered.connect(self.zoom_out)
        self.addAction(zoom_out_shortcut)

        # 适应窗口快捷键 - Ctrl+0
        zoom_fit_shortcut = QAction("适应窗口", self)
        zoom_fit_shortcut.setShortcut("Ctrl+0")
        zoom_fit_shortcut.triggered.connect(self.zoom_fit)
        self.addAction(zoom_fit_shortcut)

        # 删除节点快捷键 - Delete
        delete_node_shortcut = QAction("删除节点", self)
        delete_node_shortcut.setShortcut("Delete")
        delete_node_shortcut.triggered.connect(self.delete_selected_node)
        self.addAction(delete_node_shortcut)

        # 复制节点快捷键 - Ctrl+C
        copy_node_shortcut = QAction("复制节点", self)
        copy_node_shortcut.setShortcut("Ctrl+C")
        copy_node_shortcut.triggered.connect(self.copy_node)
        self.addAction(copy_node_shortcut)

        # 粘贴节点快捷键 - Ctrl+V
        paste_node_shortcut = QAction("粘贴节点", self)
        paste_node_shortcut.setShortcut("Ctrl+V")
        paste_node_shortcut.triggered.connect(self.paste_node)
        self.addAction(paste_node_shortcut)

        # 撤销快捷键 - Ctrl+Z
        undo_shortcut = QAction("撤销", self)
        undo_shortcut.setShortcut("Ctrl+Z")
        undo_shortcut.triggered.connect(self.undo_node_graph)
        self.addAction(undo_shortcut)

        # 排列节点快捷键 - Ctrl+A
        arrange_shortcut = QAction("排列节点", self)
        arrange_shortcut.setShortcut("Ctrl+A")
        arrange_shortcut.triggered.connect(self.arrange_nodes)
        self.addAction(arrange_shortcut)

        # 保存快捷键 - Ctrl+S
        save_shortcut = QAction("保存", self)
        save_shortcut.setShortcut("Ctrl+S")
        save_shortcut.triggered.connect(self.save_node_graph)
        self.addAction(save_shortcut)

    def create_context_menus(self):
        """创建右键菜单"""
        # 创建预览区右键菜单
        self.preview_context_menu = QMenu(self)

        # 添加预览区菜单项
        zoom_in_action = self.preview_context_menu.addAction("放大 (+)")
        zoom_in_action.triggered.connect(self.zoom_in)

        zoom_out_action = self.preview_context_menu.addAction("缩小 (-)")
        zoom_out_action.triggered.connect(self.zoom_out)

        zoom_fit_action = self.preview_context_menu.addAction("适应窗口 (□)")
        zoom_fit_action.triggered.connect(self.zoom_fit)

        self.preview_context_menu.addSeparator()

        copy_action = self.preview_context_menu.addAction("复制到剪贴板")
        copy_action.triggered.connect(self.copy_image_to_clipboard)

        export_action = self.preview_context_menu.addAction("导出当前视图")
        export_action.triggered.connect(self.export_current_view)

        # 创建节点画布右键菜单将在on_canvas_right_click中动态生成

    def show_node_menu(self):
        """显示节点导入菜单 (通常由按钮或画布右键菜单触发)"""
        # 需要导入: from PySide6.QtWidgets import QMenu
        # 需要导入: from PySide6.QtGui import QCursor
        # (假设这些已在主文件中导入)
        try:
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
        except ImportError:
            print("警告: 无法导入 QMenu 或 QCursor，show_node_menu 可能无法正常工作。")
            return # 或者根据需要处理

        # 创建节点菜单
        menu = QMenu(self)

        # 递归添加菜单项的辅助函数
        def add_menu_items(submenu, registry_dict, path=""):
            # 注意：内部函数的缩进基于外部函数的缩进
            for key, value in registry_dict.items():
                if isinstance(value, dict) and 'path' not in value:
                    # 创建子菜单
                    nested_submenu = QMenu(key, submenu)
                    submenu.addMenu(nested_submenu)
                    # 递归添加子菜单项
                    add_menu_items(nested_submenu, value, path + "/" + key if path else key)
                else:
                    # 添加节点项
                    action = submenu.addAction(key)
                    # 使用唯一的变量名确保 lambda 捕获正确的值
                    current_p = value['path']
                    current_i = value['info']
                    action.triggered.connect(lambda checked=False, p=current_p, i=current_i: self.add_node(p, i))

        # 添加所有菜单项到主菜单
        if hasattr(self, 'script_registry') and self.script_registry:
            add_menu_items(menu, self.script_registry)
        else:
            print("警告: script_registry 未找到或为空，无法添加节点菜单项。")
            action = menu.addAction("(无可用脚本)")
            action.setEnabled(False)


        # 显示菜单 (在鼠标光标位置)
        menu.exec(QCursor.pos())

    def create_preview_area(self):
        """创建预览区UI"""
        # 预览区布局
        preview_layout = QVBoxLayout(self.preview_area)
        preview_layout.setContentsMargins(5, 5, 5, 5)

        # 创建预览区画布框架
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(0, 0, 0, 0)

        # 创建预览画布的滚动区域
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True) # Important for layout alignment
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建一个容器widget以允许内容居中
        # 滚动区域需要一个子widget，我们将把 PreviewDisplayWidget 放在这个widget的布局中
        preview_container = QWidget()
        preview_container_layout = QVBoxLayout(preview_container)
        preview_container_layout.setAlignment(Qt.AlignCenter) # 居中布局
        preview_container_layout.setContentsMargins(0, 0, 0, 0)

        # 创建新的 PreviewDisplayWidget
        self.preview_display_widget = PreviewDisplayWidget(parent_app=self)
        # 将新的显示部件添加到容器布局中
        preview_container_layout.addWidget(self.preview_display_widget)

        # 不再需要旧的 preview_canvas 和 preview_tool_button
        # self.preview_canvas = QLabel() ...
        # self.preview_tool_button = QToolButton(...) ...

        # 将容器添加到滚动区域
        self.preview_scroll.setWidget(preview_container)
        preview_frame_layout.addWidget(self.preview_scroll)

        # 添加预览框架到预览区
        preview_layout.addWidget(preview_frame)

        # 关联滚轮事件到主应用的处理器
        # 注意：滚轮事件发生在滚动区域上更可靠，但也可以在子部件上处理
        # 我们将滚轮事件保留在主应用处理（on_preview_mousewheel）
        # 但需要确保它能正确获取 preview_display_widget 的尺寸
        # 通常，将事件过滤器安装在 viewport() 上处理滚轮事件更佳
        self.preview_scroll.viewport().installEventFilter(self) # 安装事件过滤器处理滚轮

        # 右键菜单通过 PreviewDisplayWidget 的 contextMenuEvent 处理
        # self.preview_display_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.preview_display_widget.customContextMenuRequested.connect(self.show_preview_context_menu)
        # 像素信息更新由 PreviewDisplayWidget 的 mouseMoveEvent 调用

        # 添加状态栏
        self.preview_status_bar = QFrame()
        self.preview_status_bar.setObjectName("previewStatusBar") # 添加 objectName
        self.preview_status_bar.setMaximumHeight(25)
        # ----------------------
        status_layout = QHBoxLayout(self.preview_status_bar)
        status_layout.setContentsMargins(5, 0, 5, 0)
        status_layout.setSpacing(0)  # 移除控件之间的间距

        # 添加色彩空间和伽马指示器（最左侧，无间隙）
        self.colorspace_label = QLabel("色彩空间: --")
        self.colorspace_label.setObjectName("colorspace_label")
        status_layout.addWidget(self.colorspace_label)

        self.gamma_label = QLabel("伽马: --")
        self.gamma_label.setObjectName("gamma_label")
        status_layout.addWidget(self.gamma_label)

        # 创建状态栏标签
        self.pixel_info_label = QLabel("坐标: -- , --  RGB: --, --, --")
        self.pixel_info_label.setObjectName("pixel_info_label")
        self.pixel_info_label.setMinimumWidth(235) # 为像素信息标签设置最小宽度，防止抖动
        status_layout.addWidget(self.pixel_info_label)

        # 添加任务状态标签（放在弹性空间之后，避免影响左侧布局）
        # 暂时移除，稍后在弹性空间后添加

        # 添加弹性伸缩项，将右侧标签推到右边
        status_layout.addStretch(1)

        # 添加任务状态标签（在弹性空间之后，不影响左侧布局）
        self.task_label = QLabel("") # 初始化为空
        status_layout.addWidget(self.task_label)

        # 图像尺寸标签（右侧）
        self.image_size_label = QLabel("尺寸: -- x --")
        self.image_size_label.setObjectName("image_size_label")
        status_layout.addWidget(self.image_size_label)

        preview_layout.addWidget(self.preview_status_bar)

    def update_colorspace_gamma_indicators(self):
        """更新色彩空间和伽马指示器"""
        # 查找解码节点获取色彩空间和伽马信息
        colorspace = "--"
        gamma = "--"

        for node in self.nodes:
            if node.get('title') == '解码节点':
                if 'processed_outputs' in node:
                    # 检查节点的元数据
                    if '_metadata' in node['processed_outputs']:
                        metadata = node['processed_outputs']['_metadata']
                        colorspace = metadata.get('colorspace', '--')
                        gamma = metadata.get('gamma', '--')
                        break

        # 更新指示器标签
        if hasattr(self, 'colorspace_label'):
            self.colorspace_label.setText(f"色彩空间: {colorspace}")

        if hasattr(self, 'gamma_label'):
            self.gamma_label.setText(f"伽马: {gamma}")

    def create_node_graph_area(self):
        """创建节点图区域UI"""
        # 节点图布局
        node_layout = QVBoxLayout(self.node_graph_area)
        node_layout.setContentsMargins(5, 5, 5, 5)

        # 节点图标题栏
        node_header = QFrame()
        node_header.setMaximumHeight(40)
        node_header_layout = QHBoxLayout(node_header)
        # --- 修改：设置内容边距和对齐方式 ---
        node_header_layout.setContentsMargins(5, 0, 5, 0) # 减少垂直边距
        # node_header_layout.setAlignment(Qt.AlignVCenter) # 尝试对整个布局垂直居中 (可能不适用于所有 widget)

        # 节点图标题
        node_graph_title = QLabel("节点图")
        node_graph_title.setProperty("styleClass", "subtitle")
        # --- 修改：垂直居中标题 ---
        node_header_layout.addWidget(node_graph_title, 0, Qt.AlignVCenter)

        # --- 添加按钮 ---
        node_header_layout.addStretch(1) # 添加弹性伸缩项，将按钮推到右边

        self.add_node_button = QPushButton("添加节点")
        self.add_node_button.setToolTip("打开添加节点菜单")
        self.add_node_button.clicked.connect(self.show_node_menu)
        # --- 修改：垂直居中按钮 ---
        node_header_layout.addWidget(self.add_node_button, 0, Qt.AlignVCenter)

        self.delete_node_button = QPushButton("删除节点")
        self.delete_node_button.setToolTip("删除选中的节点")
        self.delete_node_button.clicked.connect(lambda: self.delete_selected_node(self.selected_node))
        # --- 修改：垂直居中按钮 ---
        node_header_layout.addWidget(self.delete_node_button, 0, Qt.AlignVCenter)
        # ----------------

        # 添加标题栏到节点图区域
        node_layout.addWidget(node_header)

        # 创建节点图框架
        node_frame = QFrame()
        node_frame.setFrameShape(QFrame.StyledPanel)
        node_frame_layout = QVBoxLayout(node_frame)
        node_frame_layout.setContentsMargins(0, 0, 0, 0)

        # 创建节点图画布的滚动区域
        self.node_scroll = QScrollArea()
        self.node_scroll.setWidgetResizable(True)
        self.node_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.node_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建节点图画布
        self.node_canvas_widget = NodeCanvasWidget()
        self.node_canvas_widget.parent_app = self  # 关键：设置对主应用的引用
        self.node_canvas_widget.setObjectName("node_canvas_widget") # 确保 objectName 被设置，以便 Aero 样式生效

        # 为节点画布添加布局以便添加子部件
        self.node_canvas_layout = QGridLayout(self.node_canvas_widget)

        # 设置上下文菜单策略
        self.node_canvas_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.node_canvas_widget.customContextMenuRequested.connect(self.on_canvas_right_click)

        # 将画布添加到滚动区域
        self.node_scroll.setWidget(self.node_canvas_widget)
        node_frame_layout.addWidget(self.node_scroll)
        # 绘制网格背景
        # 添加节点框架到节点图区域
        node_layout.addWidget(node_frame)

        # 初始化绘图状态
        self.temp_line = None



    def create_node_settings_area(self):
        """创建节点设置区域UI"""
        # 节点设置布局
        settings_layout = QVBoxLayout(self.node_settings_area)
        settings_layout.setContentsMargins(5, 5, 5, 5)

        # 节点设置标题栏
        settings_header = QFrame()
        settings_header.setMaximumHeight(40)
        settings_header_layout = QHBoxLayout(settings_header)

        # 节点设置标题
        self.settings_title = QLabel("节点设置")
        self.settings_title.setProperty("styleClass", "subtitle")
        settings_header_layout.addWidget(self.settings_title)

        # 添加标题栏到设置区域
        settings_layout.addWidget(settings_header)

        # 创建设置框架
        self.settings_frame = QScrollArea()
        self.settings_frame.setObjectName("settings_frame") # 添加 objectName
        self.settings_frame.setWidgetResizable(True)

        # 创建内容部件
        self.settings_content = QWidget()
        self.settings_frame.setWidget(self.settings_content)

        # 设置默认内容
        self.settings_content_layout = QVBoxLayout(self.settings_content)
        self.no_node_label = QLabel("")  # 改为空标签，不再显示提示信息
        self.no_node_label.setAlignment(Qt.AlignCenter)
        self.settings_content_layout.addWidget(self.no_node_label)

        settings_layout.addWidget(self.settings_frame)
    def create_info_panel(self):
        """创建信息面板"""
        # 设置objectName
        self.info_panel.setObjectName("info_panel")

        # 信息面板布局
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(5, 5, 5, 5)

        # 信息面板标题栏
        info_header = QFrame()
        info_header.setObjectName("info_header")
        info_header.setMaximumHeight(40)
        info_header_layout = QHBoxLayout(info_header)

        # 信息面板标题
        info_title = QLabel("图像信息")
        info_title.setProperty("styleClass", "subtitle")
        info_header_layout.addWidget(info_title)

        # 添加标题栏到信息面板
        info_layout.addWidget(info_header)

        # 创建信息内容区域
        info_content = QWidget()
        info_content.setObjectName("info_content")
        info_content_layout = QGridLayout(info_content)

        # 图像信息标签
        self.image_info = {
            "文件名": QLabel("文件名: 未加载"),
            "尺寸": QLabel("尺寸: 0 x 0"),
            "类型": QLabel("类型: 未知"),
            "节点数": QLabel("节点数: 0")
        }

        # 放置信息标签
        row = 0
        for label in self.image_info.values():
            label.setObjectName(f"info_label_{row}")
            info_content_layout.addWidget(label, row, 0, Qt.AlignLeft)
            row += 1

        info_layout.addWidget(info_content)
    def update_pixel_info(self, event):
        """更新像素信息显示"""
        # 检查是否有图像
        if not hasattr(self, 'preview_image') or self.preview_image is None:
            return

        # 获取鼠标相对于图像的位置
        pos = event.pos()
        rel_x = pos.x()
        rel_y = pos.y()

        # 检查图像大小
        if not hasattr(self, 'current_image') or self.current_image is None:
            # 查找预览节点获取图像
            preview_node = None
            for node in self.nodes:
                if node['title'] == '预览节点':
                    preview_node = node
                    break

            if preview_node and 'processed_outputs' in preview_node:
                if 'f32bmp' in preview_node['processed_outputs']:
                    self.current_image = preview_node['processed_outputs']['f32bmp']
                elif 'tif16' in preview_node['processed_outputs']:
                    self.current_image = preview_node['processed_outputs']['tif16']
                else:
                    return
            else:
                return

        # 获取图像尺寸
        if self.current_image is not None:
            img_height, img_width = self.current_image.shape[:2]

            # 更新图像尺寸标签
            self.image_size_label.setText(f"尺寸: {img_width} x {img_height}")

            # 计算相对于图像的坐标（考虑缩放）
            if hasattr(self, 'zoom_level'):
                rel_x = int(rel_x / self.zoom_level)
                rel_y = int(rel_y / self.zoom_level)

            # 检查坐标是否在图像范围内
            if 0 <= rel_x < img_width and 0 <= rel_y < img_height:
                # 获取像素颜色
                try:
                    if len(self.current_image.shape) == 3:  # 彩色图像
                        # 根据图像类型获取像素值
                        if self.current_image.dtype == np.float32:
                            # 支持RGBA格式
                            pixel_values = self.current_image[rel_y, rel_x]
                            # 判断是3通道还是4通道
                            if len(pixel_values) == 3:  # RGB
                                r, g, b = pixel_values
                                a = 255  # 默认完全不透明
                            elif len(pixel_values) == 4:  # RGBA
                                r, g, b, a = pixel_values
                                a = int(a * 255) if a <= 1.0 else a
                            else:
                                r, g, b, a = 0, 0, 0, 255  # 默认值

                            # 将浮点值缩放到0-255范围
                            r = int(r * 255) if r <= 1.0 else int(r)
                            g = int(g * 255) if g <= 1.0 else int(g)
                            b = int(b * 255) if b <= 1.0 else int(b)
                        elif self.current_image.dtype == np.uint16:
                            # 支持RGBA格式
                            pixel_values = self.current_image[rel_y, rel_x]
                            # 判断是3通道还是4通道
                            if len(pixel_values) == 3:  # RGB
                                r, g, b = pixel_values
                                a = 65535  # 默认完全不透明
                            elif len(pixel_values) == 4:  # RGBA
                                r, g, b, a = pixel_values
                            else:
                                r, g, b, a = 0, 0, 0, 65535  # 默认值

                            r = int(r / 256)
                            g = int(g / 256)
                            b = int(b / 256)
                            a = int(a / 256)
                        else:
                            # 支持RGBA格式
                            pixel_values = self.current_image[rel_y, rel_x]
                            # 判断是3通道还是4通道
                            if len(pixel_values) == 3:  # RGB
                                r, g, b = pixel_values
                                a = 255  # 默认完全不透明
                            elif len(pixel_values) == 4:  # RGBA
                                r, g, b, a = pixel_values
                            else:
                                r, g, b, a = 0, 0, 0, 255  # 默认值

                        # 更新像素信息，包含Alpha通道信息
                        self.pixel_info_label.setText(f"坐标: {rel_x}, {rel_y}  RGBA: {r}, {g}, {b}, {a}")
                    else:  # 灰度图像
                        if self.current_image.dtype == np.float32:
                            value = self.current_image[rel_y, rel_x]
                            # 将浮点值缩放到0-255范围
                            value = int(value * 255) if value <= 1.0 else int(value)
                        elif self.current_image.dtype == np.uint16:
                            value = int(self.current_image[rel_y, rel_x] / 256)
                        else:
                            value = self.current_image[rel_y, rel_x]

                        # 更新像素信息
                        self.pixel_info_label.setText(f"坐标: {rel_x}, {rel_y}  值: {value}")
                        self.pixel_info_label.setObjectName("pixel_info_label")
                        self.image_size_label.setObjectName("image_size_label")

                except IndexError:
                    # 索引错误时更新为默认值
                    self.pixel_info_label.setText(f"坐标: {rel_x}, {rel_y}  RGBA: --, --, --, --")
                except ValueError as e:
                    # 打印错误用于调试
                    print(f"处理像素值时出错: {e}")
                    print(f"像素数据类型: {type(self.current_image[rel_y, rel_x])}")
                    print(f"像素值: {self.current_image[rel_y, rel_x]}")
                    # 值错误时更新为默认值
                    self.pixel_info_label.setText(f"坐标: {rel_x}, {rel_y}  RGBA: --, --, --, --")
            else:
                # 超出图像范围时更新为默认值
                self.pixel_info_label.setText("坐标: -- , --  RGBA: --, --, --, --")

    def show_preview_context_menu(self, position):
        """显示预览区右键菜单"""
        # 确保预览区有图像才显示菜单
        if hasattr(self, 'preview_image') and self.preview_image is not None:
            # 创建菜单
            menu = QMenu(self)

            # 添加菜单项
            zoom_in_action = menu.addAction("放大 (+)")
            zoom_in_action.triggered.connect(self.zoom_in)

            zoom_out_action = menu.addAction("缩小 (-)")
            zoom_out_action.triggered.connect(self.zoom_out)

            zoom_fit_action = menu.addAction("适应窗口 (□)")
            zoom_fit_action.triggered.connect(self.zoom_fit)

            menu.addSeparator()

            copy_action = menu.addAction("复制到剪贴板")
            copy_action.triggered.connect(self.copy_image_to_clipboard)

            export_action = menu.addAction("导出当前视图")
            export_action.triggered.connect(self.export_current_view)

            # 显示菜单
            menu.exec(self.preview_canvas.mapToGlobal(position))

    def draw_node_grid(self):
        """绘制节点图网格背景"""
        # 在PySide6中，我们需要使用QPainter来绘制网格
        # 创建网格背景图像
        grid_size = 20
        width = max(self.node_canvas_widget.width(), 1000)
        height = max(self.node_canvas_widget.height(), 1000)

        # 设置最小尺寸
        self.node_canvas_widget.setMinimumSize(width, height)

        # 将绘制逻辑放入paintEvent中
        # 或者创建QLabel做背景
        grid_image = QImage(width, height, QImage.Format_RGB32)
        # 使用与样式表中相同的浅蓝色背景
        grid_image.fill(QColor("#D8E4EB"))

        painter = QPainter(grid_image)
        # 使用稍深一点的蓝灰色，增加对比度使网格可见
        painter.setPen(QPen(QColor("#CCDFED"), 1))

        # 绘制网格线
        for x in range(0, width, grid_size):
            painter.drawLine(x, 0, x, height)

        for y in range(0, height, grid_size):
            painter.drawLine(0, y, width, y)

        painter.end()

        # 创建QLabel作为背景
        if hasattr(self, 'grid_label'):
            self.grid_label.setParent(None)

        self.grid_label = QLabel(self.node_canvas_widget)
        self.grid_label.setPixmap(QPixmap.fromImage(grid_image))
        self.grid_label.move(0, 0)
        self.grid_label.lower()  # 确保网格在最底层

    def on_canvas_right_click(self, position):
        """处理节点画布的右键点击"""
        # 需要导入: from PySide6.QtWidgets import QMenu
        # 需要导入: from PySide6.QtGui import QCursor
        # (假设这些已在主文件中导入)
        try:
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
        except ImportError:
            print("警告: 无法导入 QMenu 或 QCursor，on_canvas_right_click 可能无法正常工作。")
            return # 或者根据需要处理

        # 创建右键菜单
        menu = QMenu(self)
        # --- 设置白色菜单样式 ---
        # -------------------------

        # --- 添加正确的画布右键菜单项 ---
        # 添加节点菜单项 (调用 show_node_menu 显示详细列表)
        add_node_action = menu.addAction("添加节点")
        add_node_action.triggered.connect(self.show_node_menu) # 连接到节点选择菜单

        # 添加导入多张图片菜单项
        import_images_action = menu.addAction("导入多张图片")
        import_images_action.triggered.connect(self.import_multiple_images)

        # 添加节点操作菜单项 (复制、粘贴、删除)
        # 假设 self.get_node_at_position 存在
        node_at_click = None
        if hasattr(self, 'get_node_at_position'):
            node_at_click = self.get_node_at_position(position) # 使用传入的画布相对位置
        else:
            print("警告: 未找到 get_node_at_position 方法，无法添加节点特定菜单项。")

        node_actions_added = False
        if node_at_click:
            menu.addSeparator()
            # 假设 self.copy_node 存在且接受节点参数
            if hasattr(self, 'copy_node'):
                copy_node_action = menu.addAction("复制节点")
                copy_node_action.triggered.connect(lambda: self.copy_node(node_at_click))
            else:
                print("警告: 未找到 copy_node 方法。")

            # 假设 self.delete_selected_node 存在且接受节点参数
            if hasattr(self, 'delete_selected_node'):
                delete_node_action = menu.addAction("删除节点")
                delete_node_action.triggered.connect(lambda: self.delete_selected_node(node_at_click))
            else:
                 print("警告: 未找到 delete_selected_node 方法。")
            node_actions_added = True

        paste_action_added = False
        # 假设 self.copied_node_data 和 self.paste_node 存在
        if hasattr(self, 'copied_node_data') and self.copied_node_data and hasattr(self, 'paste_node'):
            if not node_actions_added: # 如果没添加复制/删除，则加分隔符
                 menu.addSeparator()
            paste_node_action = menu.addAction("粘贴节点")
            paste_node_action.triggered.connect(self.paste_node)
            paste_action_added = True
        elif hasattr(self, 'copied_node_data') and self.copied_node_data:
            print("警告: copied_node_data 存在但未找到 paste_node 方法。")


        arrange_actions_added = False
        # 假设 self.nodes, self.arrange_nodes, self.arrange_nodes_dense, self.clear_node_graph 存在
        if hasattr(self, 'nodes') and self.nodes:
            needs_separator = not node_actions_added and not paste_action_added
            if needs_separator:
                 menu.addSeparator()

            if hasattr(self, 'arrange_nodes'):
                arrange_action = menu.addAction("自动排列节点")
                arrange_action.triggered.connect(self.arrange_nodes)
            else:
                print("警告: 未找到 arrange_nodes 方法。")

            if hasattr(self, 'arrange_nodes_dense'):
                arrange_dense_action = menu.addAction("密集排列节点")
                arrange_dense_action.triggered.connect(self.arrange_nodes_dense)
            else:
                print("警告: 未找到 arrange_nodes_dense 方法。")

            if hasattr(self, 'clear_node_graph'):
                clear_action = menu.addAction("清除所有节点")
                clear_action.triggered.connect(self.clear_node_graph)
            else:
                print("警告: 未找到 clear_node_graph 方法。")

            arrange_actions_added = True

        # 假设 self.can_undo 和 self.undo_node_graph 存在
        if hasattr(self, 'can_undo') and self.can_undo():
             needs_separator = arrange_actions_added or (not node_actions_added and not paste_action_added)
             if needs_separator:
                 menu.addSeparator()

             if hasattr(self, 'undo_node_graph'):
                 undo_action = menu.addAction("撤销 (Ctrl+Z)")
                 undo_action.triggered.connect(self.undo_node_graph)
             else:
                 print("警告: 未找到 undo_node_graph 方法。")
        elif hasattr(self, 'can_undo') and not self.can_undo():
            pass # 没有可撤销的操作
        else:
            print("警告: 未找到 can_undo 方法。")

        # -----------------------------------

        # 显示菜单 (在画布的点击位置的全局坐标)
        # 假设 self.node_canvas_widget 存在
        if hasattr(self, 'node_canvas_widget'):
            global_pos = self.node_canvas_widget.mapToGlobal(position)
            menu.exec(global_pos)
        else:
            print("错误: 未找到 self.node_canvas_widget，无法显示菜单。")

    def add_node(self, script_path, script_info):
        """添加节点到节点图"""
        # 计算默认位置
        x, y = 100 + (self.next_node_id * 20) % 300, 100 + (self.next_node_id * 20) % 200

        # 创建节点数据
        node = {
            'id': self.next_node_id,
            'x': x,
            'y': y,
            'width': 120,
            'height': 80,
            'script_path': script_path,
            'script_info': script_info,
            'script_type': script_info.get('script_type', 'legacy'),  # 从 script_info 获取类型
            'title': os.path.splitext(os.path.basename(script_path))[0],
            'params': {},  # 将在加载模块时填充
            'inputs': {},
            'outputs': {},
            'widget': None,
            'port_widgets': {},
            'module': None,
            # 为 NeoScript 准备自定义设置UI和叠加层状态
            'custom_settings_widget': None,
            'overlay_elements': [],
            # 新增：灵活端口支持
            'flexible_ports': {
                'inputs': script_info.get('flexible_inputs', []),
                'outputs': script_info.get('flexible_outputs', [])
            },
            'port_counts': {
                'inputs': len(script_info.get('inputs', [])),
                'outputs': len(script_info.get('outputs', []))
            },
            # 新增：元数据支持
            'metadata': self.metadata_manager.create_metadata(
                node_id=self.next_node_id,
                node_title=os.path.splitext(os.path.basename(script_path))[0],
                script_path=script_path
            )
        }

        # 加载模块并获取默认参数
        try:
            spec = importlib.util.spec_from_file_location("module.name", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 存放到 node 中
            node['module'] = module
            node['script_module'] = module  # 【新增】兼容旧版自定义预览调用
            node['_base_height'] = node['height']

            # 如果脚本定义了 get_params，读取默认参数
            if hasattr(module, 'get_params'):
                node['params'] = module.get_params()

            # 如果是 NeoScript，尝试加载各种自定义回调
            if node['script_type'] == 'neo':
                node['draw_overlay_func'] = getattr(module, 'draw_overlay', None)
                node['handle_mouse_press_func'] = getattr(module, 'handle_overlay_mouse_press', None)
                node['handle_mouse_move_func'] = getattr(module, 'handle_overlay_mouse_move', None)
                node['handle_mouse_release_func'] = getattr(module, 'handle_overlay_mouse_release', None)
                node['create_settings_widget_func'] = getattr(module, 'create_settings_widget', None)
                node['create_popup_window_func'] = getattr(module, 'create_popup_window', None)

            # 检查子操作
            node['sub_operations'] = []
            for attr_name in dir(module):
                if attr_name.startswith('sub_') and callable(getattr(module, attr_name)):
                    op_name = attr_name[4:]  # 去掉 'sub_' 前缀
                    node['sub_operations'].append(op_name)

        except Exception as e:
            print(f"加载模块出错: {str(e)}")

        # 添加到节点列表
        self.nodes.append(node)
        self.next_node_id += 1

        # 设置节点图为已修改状态
        self.set_nodegraph_state(modified=True)

        # 绘制节点并更新预览
        self.draw_node(node)
        self.node_canvas_widget.update()

        # 第一个节点时自动选中
        if len(self.nodes) == 1:
            self.select_node(node)

        # 处理节点图
        # 只处理新添加的节点，而不是所有节点
        self.process_node_graph(changed_nodes=[node])
        # 注: 此处原自动保存代码已移除

        return node

    def draw_node(self, node):
        """绘制节点到画布上"""
        # 获取节点颜色
        input_count = len(node['script_info']['inputs'])
        output_count = len(node['script_info']['outputs'])
        max_ports = max(input_count, output_count)
        base_height = node.get('_base_height', node['height'])
        if max_ports > 2:
            node['height'] = base_height + (max_ports - 2) * 20
        else:
            node['height'] = base_height
        raw_color = node['script_info']['color'] # 获取原始值
        print(f"节点 '{node['title']}' (ID: {node['id']}) - 原始颜色: {raw_color}") # 打印原始颜色

        # --- 预先计算颜色值，确保 QColor 处理正确 ---
        stylesheet_string = "" # Initialize stylesheet_string
        try:
            base_color = QColor(raw_color) # 使用原始值
            if not base_color.isValid(): # 检查 QColor 是否有效
                raise ValueError(f"无效的颜色值: {raw_color}")

            # --- 计算新的淡化渐变颜色 (基于 HSL 调整) ---
            highlight_color = QColor("#FFFFFF")

            # 获取基色的 HSL 值
            hue = base_color.hue()
            saturation = base_color.saturation()
            lightness = base_color.lightness()

            # --- 计算中间色: 固定高亮度、低饱和度，保留色相 ---
            # mid_lightness = min(255, lightness + 75) # 旧：基于原始亮度增加
            # mid_color = QColor.fromHsl(hue, saturation, mid_lightness)
            mid_fixed_saturation = 80  # 固定低饱和度 (0-255)
            mid_fixed_lightness = 235 # 固定高亮度 (0-255)
            mid_color = QColor.fromHsl(hue, mid_fixed_saturation, mid_fixed_lightness)

            # --- 计算底部颜色: 使用原始基色 ---
            bottom_color = QColor.fromHsl(hue, saturation, lightness)

            # --- 计算最底部颜色: 明显降低亮度，保持饱和度 ---
            darker_bottom_lightness = max(0, lightness - 25)
            darker_bottom_color = QColor.fromHsl(hue, saturation, darker_bottom_lightness)

            # 边框颜色：使用基色稍微变暗
            node_border_color = base_color.darker(110).name()

            # --- 选中状态颜色 (同样基于 HSL, 固定中间点) ---
            # sel_mid_lightness = min(255, lightness + 70) # 旧
            # sel_mid_color = QColor.fromHsl(hue, saturation, sel_mid_lightness)
            sel_mid_fixed_saturation = 60  # 选中时饱和度更低
            sel_mid_fixed_lightness = 240 # 选中时亮度更高
            sel_mid_color = QColor.fromHsl(hue, sel_mid_fixed_saturation, sel_mid_fixed_lightness)

            # sel_bottom_lightness = min(255, lightness + 10) # 旧
            # sel_bottom_color = QColor.fromHsl(hue, saturation, sel_bottom_lightness)
            # sel_darker_bottom_lightness = lightness # 旧
            # sel_darker_bottom_color = QColor.fromHsl(hue, saturation, sel_darker_bottom_lightness)
            # --- 选中状态的底部颜色逻辑保持不变 (比基色稍亮 -> 基色) ---
            sel_bottom_lightness = min(255, lightness + 10)
            sel_bottom_color = QColor.fromHsl(hue, saturation, sel_bottom_lightness)
            sel_darker_bottom_lightness = lightness
            sel_darker_bottom_color = QColor.fromHsl(hue, saturation, sel_darker_bottom_lightness)

            # 选中阴影颜色：使用基色提亮
            sel_shadow_color = base_color.lighter(140).name()

            color = base_color.name() # 原始基色

            print(f"  -> 解析后颜色 (HSL): base={color}, border={node_border_color}, mid={mid_color.name()}, bottom={bottom_color.name()}, darker_bottom={darker_bottom_color.name()}")

            # --- 定义固定文本颜色 ---
            main_text_color = "#202020"
            filename_text_color = "#555555"
            # --- 结束定义 ---

            # --- 创建新的样式表字符串 (淡化风格渐变) ---
            stylesheet_string = f"""
                QFrame {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {highlight_color.name()}, /* Top White */
                                        stop:0.4 {mid_color.name()},    /* Mid Light (Stop 0.4) */
                                        stop:0.8 {bottom_color.name()}, /* Bottom Base (Stop 0.8) */
                                        stop:1 {darker_bottom_color.name()} /* Darker Bottom */
                                        );
                    border: 1px solid {node_border_color};
                    border-radius: 6px;
                    color: #1E395B;
                }}
                QFrame[selected="true"] {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {highlight_color.name()},        /* Top White */
                                        stop:0.4 {sel_mid_color.name()},       /* Selected Mid Lighter (Stop 0.4) */
                                        stop:0.8 {sel_bottom_color.name()},      /* Selected Bottom (Lighter Base) (Stop 0.8) */
                                        stop:1 {sel_darker_bottom_color.name()} /* Selected Bottom (Base) */
                                        );
                    border: 2px solid #FFFFFF; /* White selection border */

                }}
                QLabel {{
                    background-color: transparent;
                    color: {main_text_color};
                    font-weight: bold;
                    padding-top: 2px;
                    border: none;
                }}
                QLabel#filenameLabel {{
                    color: {filename_text_color};
                    font-size: 8pt;
                    font-weight: normal;
                    border: none;
                }}
            """
            # --- 结束样式表 ---

        except Exception as e:
            print(f"警告：无法解析节点颜色 '{raw_color}'。将使用默认颜色。错误：{e}")
            # --- 设置备用情况下的颜色和样式 (灰色，增强对比度) ---
            fallback_highlight = "#FFFFFF"
            fallback_mid = "#F0F0F0"       # 亮灰
            fallback_bottom = "#D8D8D8"   # 中灰
            fallback_darker_bottom = "#BDBDBD" # 暗灰
            fallback_border_color = "#A0A0A0" # 更深的灰色边框

            # 备用选中状态
            fallback_sel_mid = "#F8F8F8"
            fallback_sel_bottom = "#E0E0E0"
            fallback_sel_darker_bottom = "#C8C8C8"
            fallback_shadow_color = "#D0D0D0"

            main_text_color = "#202020"
            filename_text_color = "#555555"
            print(f"  -> 使用备用淡化灰色: border={fallback_border_color}")

            # --- 创建备用的样式表字符串 ---
            stylesheet_string = f"""
                QFrame {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {fallback_highlight},
                                        stop:0.4 {fallback_mid},
                                        stop:0.8 {fallback_bottom},
                                        stop:1 {fallback_darker_bottom});
                    border: 1px solid {fallback_border_color};
                    border-radius: 6px;
                    color: #1E395B;

                }}
                QFrame[selected="true"] {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 {fallback_highlight},
                                        stop:0.4 {fallback_sel_mid},
                                        stop:0.8 {fallback_sel_bottom},
                                        stop:1 {fallback_sel_darker_bottom});
                    border: 2px solid #FFFFFF;

                }}
                QLabel {{
                    background-color: transparent;
                    color: {main_text_color};
                    font-weight: bold;
                    padding-top: 2px;
                    border: none;
                }}
                QLabel#filenameLabel {{
                    color: {filename_text_color};
                    font-size: 8pt;
                    font-weight: normal;
                    border: none;
                }}
            """
            # --- 结束备用样式表 ---
        # --- 结束颜色计算和样式表定义 ---


        # 创建节点框架
        node_widget = QFrame(self.node_canvas_widget)
        # --- 应用新的节点样式 (使用格式化好的字符串) ---
        node_widget.setStyleSheet(stylesheet_string)
        # --- 结束修改 ---
        node_widget.setGeometry(node['x'], node['y'], node['width'], node['height'])

        # --- 新增：设置初始选择状态为 False ---
        node_widget.setProperty("selected", False)
        # --- 结束新增 ---

        # 强制重新计算和应用样式 (这一步在这里可能不是必须的，但保留无害)
        # node_widget.style().unpolish(node_widget)
        # node_widget.style().polish(node_widget)

        # 创建节点布局
        node_layout = QVBoxLayout(node_widget)
        node_layout.setContentsMargins(5, 5, 5, 5)

        # 创建标题标签
        title_label = QLabel(node['title'])
        title_label.setObjectName("filenameLabel") # 添加 objectName 以便应用特定样式
        # title_label.setStyleSheet("color: #555555; font-size: 8px;") # 样式移到上面
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)  # 添加自动换行属性
        node_layout.addWidget(title_label)

        # 如果是图像节点，显示图像文件名
        if node['title'] == '图像节点' or 'image' in node['title'].lower():
            if 'params' in node and 'image_path' in node['params'] and node['params']['image_path']['value']:
                image_path = node['params']['image_path']['value']
                filename = os.path.basename(image_path)
                if len(filename) > 12:  # 如果文件名太长，截断显示
                    filename = filename[:10] + "..."

                # 创建文件名标签
                filename_label = QLabel(filename)
                filename_label.setObjectName("filenameLabel") # 添加 objectName 以便应用特定样式
                # filename_label.setStyleSheet("color: #555555; font-size: 8px;") # 样式移到上面
                filename_label.setAlignment(Qt.AlignCenter)
                node_layout.addWidget(filename_label)

        # 检查节点是否支持在节点上显示预览
        has_preview_on_node = False
        if 'script_info' in node and 'supported_features' in node['script_info']:
            # 从新的支持特性系统中检查PreviewOnNode
            has_preview_on_node = node['script_info']['supported_features'].get('PreviewOnNode', False)

        # 如果节点支持在节点上显示预览且已经处理过，显示预览图像
        if has_preview_on_node and 'processed_outputs' in node and node['processed_outputs']:
            try:
                outputs = node['processed_outputs']

                # 查找输出中的图像类型（img或f32bmp是常见的图像类型）
                image_data = None
                for output_type in ['img', 'f32bmp']:
                    if output_type in outputs and outputs[output_type] is not None:
                        image_data = outputs[output_type]
                        break

                if image_data is not None:
                    import numpy as np
                    from PIL import Image
                    import cv2  # 添加OpenCV导入，用于pil_to_qimage中的颜色通道转换

                    # 创建预览标签
                    preview_label = QLabel()
                    preview_label.setFixedSize(80, 60)  # 预览图像固定大小
                    preview_label.setAlignment(Qt.AlignCenter)
                    preview_label.setObjectName("previewLabel")

                    # 将numpy数组转换为QPixmap
                    if isinstance(image_data, np.ndarray):
                        try:
                            # 处理特殊形状的数据(如1x1x4的浮点数据)
                            if image_data.ndim == 3 and image_data.shape[0] == 1 and image_data.shape[1] == 1:
                                # 创建一个更大的图像以便显示（扩展为20x20像素）
                                if image_data.shape[2] == 4:  # RGBA数据
                                    pixel_value = image_data[0, 0, :]
                                    # 创建20x20的相同颜色图像
                                    expanded_data = np.zeros((20, 20, 4), dtype=np.float32)
                                    for i in range(20):
                                        for j in range(20):
                                            expanded_data[i, j, :] = pixel_value
                                    # 转换为0-255范围的uint8
                                    image_data = (expanded_data * 255).astype(np.uint8)
                                elif image_data.shape[2] == 3:  # RGB数据
                                    pixel_value = image_data[0, 0, :]
                                    expanded_data = np.zeros((20, 20, 3), dtype=np.float32)
                                    for i in range(20):
                                        for j in range(20):
                                            expanded_data[i, j, :] = pixel_value
                                    image_data = (expanded_data * 255).astype(np.uint8)

                            # 确保浮点数据在0-1范围内并转换为uint8
                            if image_data.dtype == np.float32 or image_data.dtype == np.float64:
                                image_data = (np.clip(image_data, 0, 1) * 255).astype(np.uint8)

                            # 将numpy数组转换为PIL图像
                            if image_data.ndim == 2:  # 灰度图
                                pil_image = Image.fromarray(image_data)
                            elif image_data.ndim == 3 and image_data.shape[2] == 3:  # RGB
                                pil_image = Image.fromarray(image_data)
                            elif image_data.ndim == 3 and image_data.shape[2] == 4:  # RGBA
                                pil_image = Image.fromarray(image_data)
                            else:
                                print(f"无法显示形状为 {image_data.shape} 的图像数据")
                                pil_image = None
                        except Exception as e:
                            print(f"在节点上显示预览时出错: {e}")
                            pil_image = None

                        if pil_image:
                            try:
                                # 缩放图像以适应预览标签
                                pil_image.thumbnail((80, 60), Image.LANCZOS)

                                # 确保图像是RGB或RGBA模式
                                if pil_image.mode not in ['RGB', 'RGBA', 'L']:
                                    print(f"转换图像模式从 {pil_image.mode} 到 RGB")
                                    pil_image = pil_image.convert('RGB')

                                # 转换为QPixmap
                                qimage = self.pil_to_qimage(pil_image)
                                if qimage is not None:
                                    pixmap = QPixmap.fromImage(qimage)

                                    # 设置预览图像
                                    preview_label.setPixmap(pixmap)
                                    node_layout.addWidget(preview_label)

                                    print(f"节点 '{node['title']}' 添加了预览图像")
                                else:
                                    print(f"错误: pil_to_qimage返回None")
                            except Exception as img_e:
                                print(f"处理预览图像时出错: {str(img_e)}")
            except Exception as e:
                print(f"在节点上显示预览时出错: {str(e)}")

        # 保存节点部件
        node['widget'] = node_widget

        # 初始化端口存储
        node['port_widgets'] = {'inputs': {}, 'outputs': {}}

        # 绘制输入端口
        input_types = node['script_info']['inputs']
        for i, input_type in enumerate(input_types):
            # 确定端口颜色
            port_color = self.get_port_color(input_type)

            # 创建端口部件
            port_widget = QFrame(node_widget)
            # --- 应用新的端口样式 ---
            port_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #FFFFFF, stop:1 {port_color}); /* 白色到端口颜色的渐变 */
                    border: 1px solid {QColor(port_color).darker(130).name()}; /* 端口边框颜色加深 */
                    border-radius: 5px; /* 纵向椭圆端口 */
                }}
            """)
            # ------------------------
            port_widget.setFixedSize(10, 16) # 修改端口大小为纵向椭圆，与输出保持一致

            # 放置端口在节点左侧边缘并稍微突出
            port_x = -3 # 修改 x 坐标使其突出
            port_y = 20 + i * 20
            port_widget.move(port_x, port_y)

            # 设置工具提示
            port_widget.setToolTip(f"输入端口: {input_type}")

            # 保存端口信息
            node['port_widgets']['inputs'][i] = {
                'widget': port_widget,
                'type': input_type,
                'pos': QPoint(port_x + 5, port_y + 8)  # 调整中心点 Y 坐标 (新高度 16 / 2 = 8)
            }

            # 设置鼠标事件 - 使用函数来避免lambda闭包问题
            def create_input_handler(node, idx):
                return lambda event: self.on_port_click(event, node, idx, 'input')

            def create_input_context_handler(node, idx):
                return lambda pos: self.show_port_context_menu(pos, node, idx, 'input')

            port_widget.mousePressEvent = create_input_handler(node, i)
            port_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            port_widget.customContextMenuRequested.connect(
                create_input_context_handler(node, i)
            )

        # 绘制输出端口
        output_types = node['script_info']['outputs']
        for i, output_type in enumerate(output_types):
            # 确定端口颜色
            port_color = self.get_port_color(output_type)

            # 创建端口部件
            port_widget = QFrame(node_widget)
            # --- 应用新的端口样式 ---
            port_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #FFFFFF, stop:1 {port_color}); /* 白色到端口颜色的渐变 */
                    border: 1px solid {QColor(port_color).darker(130).name()}; /* 端口边框颜色加深 */
                    border-radius: 5px; /* 纵向椭圆端口 */
                }}
            """)
            # ------------------------
            port_widget.setFixedSize(10, 16) # 修改端口大小为纵向椭圆，与输出保持一致

            # 放置端口在节点右侧边缘并稍微突出
            port_x = node['width'] - 7 # 修改 x 坐标使其突出 (10 - 3 = 7)
            port_y = 20 + i * 20
            port_widget.move(port_x, port_y)

            # 设置工具提示
            port_widget.setToolTip(f"输出端口: {output_type}")

            # 保存端口信息
            node['port_widgets']['outputs'][i] = {
                'widget': port_widget,
                'type': output_type,
                'pos': QPoint(port_x + 5, port_y + 8)  # 调整中心点 Y 坐标 (新高度 16 / 2 = 8)
            }

            # 设置鼠标事件 - 使用函数来避免lambda闭包问题
            def create_output_handler(node, idx):
                return lambda event: self.on_port_click(event, node, idx, 'output')

            def create_output_context_handler(node, idx):
                return lambda pos: self.show_port_context_menu(pos, node, idx, 'output')

            port_widget.mousePressEvent = create_output_handler(node, i)
            port_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            port_widget.customContextMenuRequested.connect(
                create_output_context_handler(node, i)
            )

        # 设置节点的鼠标事件
        node_widget.mousePressEvent = lambda event, n=node: self.on_node_press(event, n)
        node_widget.mouseMoveEvent = lambda event, n=node: self.on_node_move(event, n)
        node_widget.mouseReleaseEvent = lambda event, n=node: self.on_node_release(event, n)
        node_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        node_widget.customContextMenuRequested.connect(
            lambda pos, n=node: self.show_node_context_menu(pos, n)
        )

        # 确保样式在显示前被应用
        node_widget.ensurePolished()

        # 显示节点
        node_widget.show()

    def auto_connect_nodes(self, source_node, target_node):
        """自动连接两个节点的端口（不需要端口完全是空闲状态）"""
        # 优先检查节点是否有port_widgets属性
        if 'port_widgets' not in source_node or 'port_widgets' not in target_node:
            print(f"无法连接：节点缺少port_widgets属性")
            return

        # 获取所有输出端口（无论是否已连接）
        outputs = list(source_node['port_widgets'].get('outputs', {}).keys())

        # 获取所有输入端口（无论是否已连接）
        inputs = list(target_node['port_widgets'].get('inputs', {}).keys())

        print(f"所有输出端口: {outputs}")
        print(f"所有输入端口: {inputs}")

        # 获取数量一致的端口数（取较小值）
        connection_count = min(len(outputs), len(inputs))

        # 只有当有端口可用时才连接
        if connection_count > 0:
            # 按端口索引顺序连接，无论端口是否已经连接
            # create_connection函数会自动处理断开现有连接
            for i in range(connection_count):
                self.create_connection(source_node, outputs[i], target_node, inputs[i])

            # 更新连接线
            self.update_connections()

            # 通知用户
            self.task_label.setText(f"已自动连接 {connection_count} 个端口")
            print(f"已连接 {connection_count} 对端口")
        else:
            print(f"未能自动连接：至少一个节点没有端口 (输出:{len(outputs)}, 输入:{len(inputs)})")

    def get_port_color(self, port_type):
        """获取端口颜色"""
        # 定义端口类型颜色映射
        port_colors = {
            'tif16': "#0000FF",  # 蓝色（已废弃请勿使用）
            'tif8': "#87CEFA",  # 浅蓝色（预留，可能没啥用）
            'img': "#8A2BE2",  # 蓝紫色
            'kernel': "#FFFF00",  # 黄色
            'spectrumf': "#FF6A6A", # 浅甜红（本软件的频域图像处理之野心所在）
            'f32bmp': "#F08080",  # 珊瑚粉
            'constant': "#228B22",  # 森林绿
            'mask': "#F0E68C",  # 卡其色
            'channelR': "#FF0000",  # 正红
            'channelG': "#00FF00",  # 正绿
            'channelB': "#0000FF",  # 正蓝
            'channelA': "#778899",  # 浅石板灰
        }

        return port_colors.get(port_type, "#CCCCCC")  # 默认灰色

    def on_node_press(self, event, node):
        """处理节点鼠标按下事件"""
        # 记录拖动起始位置
        if event.button() == Qt.LeftButton:
            # 检测Ctrl键是否按下，确保转换为布尔值
            self.ctrl_dragging = bool(event.modifiers() & Qt.ControlModifier)

            # 如果按下Ctrl键，则执行连接操作而不是拖动
            if self.ctrl_dragging:
                # 不设置dragging标志，这样节点不会被拖动
                self.drag_source_node = node
                # 初始化目标节点为空，确保其存在于对象属性中
                self.drag_target_node = None
                # 设置彩虹线的起点为节点中心
                self.rainbow_line_start = QPoint(node['x'] + node['width'] // 2, node['y'] + node['height'] // 2)
                # 保存当前鼠标位置用于绘制彩虹线
                self.rainbow_line_end = self.rainbow_line_start
                print(f"已选择源节点: {node['title']}")
            else:
                # 正常拖动操作
                self.dragging = True
                self.drag_start_pos = event.globalPosition().toPoint()
                self.drag_node_start_pos = QPoint(node['x'], node['y'])

            # 选择节点
            self.select_node(node)

    def on_node_move(self, event, node):
        """处理节点拖动事件"""
        # 处理Ctrl键按下的情况 - 只更新彩虹线，不移动节点
        if hasattr(self, 'ctrl_dragging') and self.ctrl_dragging:
            # 获取鼠标当前位置 - 转换为节点画布坐标
            mouse_pos = event.globalPosition().toPoint()
            # 将鼠标位置转换为节点画布坐标 - 确保转换正确
            canvas_pos = self.node_canvas_widget.mapFromGlobal(mouse_pos)
            self.rainbow_line_end = canvas_pos

            # 查找目标节点 - 添加调试日志
            target_node = self.get_node_at_position(canvas_pos)

            # 确保drag_target_node属性存在，再进行比较
            if not hasattr(self, 'drag_target_node'):
                self.drag_target_node = None

            # 只有当目标节点变化时才打印
            if target_node != self.drag_target_node:
                if target_node:
                    print(f"鼠标悬停在节点: {target_node['title']} 上 (位置: {canvas_pos.x()}, {canvas_pos.y()})")
                else:
                    print(f"鼠标不在任何节点上 (位置: {canvas_pos.x()}, {canvas_pos.y()})")

            # 更新目标节点
            self.drag_target_node = target_node
            # 强制重绘以显示彩虹线
            self.node_canvas_widget.update()
            return  # 提前返回，不执行节点移动逻辑

        # 正常的节点拖动逻辑
        if self.dragging and hasattr(self, 'drag_start_pos'):
            # 计算移动距离
            delta = event.globalPosition().toPoint() - self.drag_start_pos
            new_x = self.drag_node_start_pos.x() + delta.x()
            new_y = self.drag_node_start_pos.y() + delta.y()

            # 更新节点位置
            node['x'] = new_x
            node['y'] = new_y
            node['widget'].move(new_x, new_y)

            # 更新连接线
            self.update_connections()

    def on_node_release(self, event, node):
        """处理节点鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            # 处理Ctrl拖拽自动连接
            if hasattr(self, 'ctrl_dragging') and self.ctrl_dragging:
                # 获取当前鼠标全局位置和画布位置
                mouse_pos = event.globalPosition().toPoint()
                canvas_pos = self.node_canvas_widget.mapFromGlobal(mouse_pos)

                # 获取鼠标当前下方的节点
                target_node = self.get_node_at_position(canvas_pos)

                # 如果找到了目标节点，设置为拖拽目标节点
                if target_node:
                    self.drag_target_node = target_node
                    print(f"释放时检测到目标节点: {target_node['title']}")

                # 检查是否有源节点和目标节点，且不是同一个节点
                if (hasattr(self, 'drag_source_node') and
                    hasattr(self, 'drag_target_node') and
                    self.drag_target_node and
                    self.drag_source_node and
                    self.drag_target_node != self.drag_source_node):

                    print(f"尝试连接: {self.drag_source_node['title']} -> {self.drag_target_node['title']}")
                    # 执行自动连接
                    self.auto_connect_nodes(self.drag_source_node, self.drag_target_node)
                else:
                    print("未能连接: 缺少源节点或目标节点，或源/目标是同一节点")

                # 清理Ctrl拖拽相关属性
                self.ctrl_dragging = False
                if hasattr(self, 'drag_source_node'):
                    delattr(self, 'drag_source_node')
                if hasattr(self, 'drag_target_node'):
                    delattr(self, 'drag_target_node')
                if hasattr(self, 'rainbow_line_start'):
                    delattr(self, 'rainbow_line_start')
                if hasattr(self, 'rainbow_line_end'):
                    delattr(self, 'rainbow_line_end')

                # 强制重绘以清除彩虹线
                self.node_canvas_widget.update()
            else:
                # 正常拖动结束
                self.dragging = False
                if hasattr(self, 'drag_start_pos'):
                    del self.drag_start_pos
                    del self.drag_node_start_pos

    def on_port_click(self, event, node, port_idx, port_type):
        """处理端口点击事件"""
        if event.button() == Qt.LeftButton:
            # 只允许从输出端口开始创建连接
            if port_type == 'output':
                self.start_connection(node, port_idx, port_type)
            # 点击输入端口时不执行任何操作或可以考虑其他交互，例如断开连接
            # else:
            #     print(f"点击了输入端口: 节点={node['title']}, 端口={port_idx}")


    def show_port_context_menu(self, pos, node, port_idx, port_type):
        """显示端口右键菜单"""
        # 保存当前选中的端口信息
        self.selected_port = {
            'node': node,
            'port_idx': port_idx,
            'port_type': port_type
        }

        # 检查端口是否有连接
        has_connection = False
        for conn in self.connections:
            if (port_type == 'input' and conn['input_node'] == node and conn['input_port'] == port_idx) or \
               (port_type == 'output' and conn['output_node'] == node and conn['output_port'] == port_idx):
                has_connection = True
                break

        # 创建菜单
        menu = QMenu(self)

        # 添加菜单项
        if has_connection:
            disconnect_action = menu.addAction("断开此连接")
            disconnect_action.triggered.connect(self.disconnect_port)
        else:
            connect_action = menu.addAction("创建连接")
            connect_action.triggered.connect(lambda: self.start_connection(node, port_idx, port_type))

        # 显示菜单
        menu.exec_(node['port_widgets'][port_type + 's'][port_idx]['widget'].mapToGlobal(pos))
# imgpp_REIMAGINED.py
    def show_node_context_menu(self, pos, node):
        """显示节点右键菜单，并添加独立预览窗口功能"""
        # 取消旧节点的选中样式
        if self.selected_node and 'widget' in self.selected_node and self.selected_node['widget']:
            try:
                self.selected_node['widget'].setProperty("selected", False)
                self.selected_node['widget'].style().unpolish(self.selected_node['widget'])
                self.selected_node['widget'].style().polish(self.selected_node['widget'])
                deselect_anim = QPropertyAnimation(self.selected_node['widget'], b"geometry")
                deselect_anim.setDuration(150)
                current_geometry = self.selected_node['widget'].geometry()
                deselect_anim.setStartValue(current_geometry)
                deselect_anim.setEndValue(current_geometry)
                deselect_anim.start(QPropertyAnimation.DeleteWhenStopped)
            except Exception as e:
                print(f"Error updating style for deselected node {self.selected_node.get('id')}: {e}")

        # 设置新的选中状态
        self.selected_node = node
        if node and 'widget' in node and node['widget']:
            try:
                node['widget'].setProperty("selected", True)
                node['widget'].style().unpolish(node['widget'])
                node['widget'].style().polish(node['widget'])
                select_anim = QPropertyAnimation(node['widget'], b"geometry")
                select_anim.setDuration(200)
                current_geometry = node['widget'].geometry()
                expanded = QRect(
                    current_geometry.x() - 2,
                    current_geometry.y() - 2,
                    current_geometry.width() + 4,
                    current_geometry.height() + 4
                )
                select_anim.setStartValue(current_geometry)
                select_anim.setKeyValueAt(0.5, expanded)
                select_anim.setEndValue(current_geometry)
                select_anim.setEasingCurve(QEasingCurve.OutElastic)
                select_anim.start(QPropertyAnimation.DeleteWhenStopped)
            except Exception as e:
                print(f"Error updating style for selected node {node.get('id')}: {e}")

        # --- 右键仅弹出菜单，不自动更新设置面板 ---
        menu = QMenu(self)

        # 删除节点
        delete_action = menu.addAction("删除节点")
        delete_action.triggered.connect(lambda: self.delete_selected_node(node))

        # 编辑节点（点击时再刷新设置面板）
        edit_action = menu.addAction("编辑节点")
        edit_action.triggered.connect(lambda: self.update_node_settings(node))

        # 子操作列表
        if 'sub_operations' in node and node['sub_operations']:
            menu.addSeparator()
            for op in node['sub_operations']:
                op_action = menu.addAction(op)
                op_action.triggered.connect(lambda checked=False, n=node, o=op: self.execute_sub_operation(n, o))

                # --- 修改：独立预览窗口选项 (支持自定义) ---
        menu.addSeparator()
        open_win_action = menu.addAction("打开独立预览窗口")

        # --- 检查是否使用自定义预览 ---
        script_info = node.get('script_info', {})
        supported_features = script_info.get('supported_features', {})
        use_custom_preview = supported_features.get('CustomizedPreviewPopup', False)
        custom_preview_func_name = supported_features.get('PreviewPopupFunction', None) # 新增：获取自定义函数名

        if use_custom_preview and custom_preview_func_name:
            # 如果启用自定义预览且指定了函数名
            print(f"Node {node['id']} uses custom preview function: {custom_preview_func_name}") # DEBUG
            def trigger_custom_preview():
                module = node.get('script_module') # 获取加载的模块
                if module and hasattr(module, custom_preview_func_name):
                    try:
                        custom_func = getattr(module, custom_preview_func_name)
                        context = self.get_application_context(node) # 获取上下文
                        custom_func(node, context) # 调用脚本定义的函数
                    except Exception as e:
                        print(f"Error calling custom preview function '{custom_preview_func_name}' for node {node['id']}: {e}")
                        # 可选：显示错误消息给用户
                        QMessageBox.warning(self, "自定义预览错误", f"调用节点 '{node['title']}' 的自定义预览函数时出错:\n{e}")
                else:
                    print(f"Error: Custom preview function '{custom_preview_func_name}' not found in module for node {node['id']}.")
                    QMessageBox.warning(self, "自定义预览错误", f"未能在节点 '{node['title']}' 的脚本中找到指定的预览函数 '{custom_preview_func_name}'。")

            open_win_action.triggered.connect(trigger_custom_preview)
        else:
            # 否则，使用默认的标准预览窗口逻辑
            open_win_action.triggered.connect(lambda: self.show_node_preview_window(node))

        # --- 元数据查看选项 ---
        metadata_action = menu.addAction("元数据查看")
        metadata_action.triggered.connect(lambda: self.show_node_metadata_dialog(node))

        # --- （菜单显示逻辑不变） ---
        # 在节点 widget 全局坐标处显示菜单
        menu.exec_(node['widget'].mapToGlobal(pos))

    def start_connection(self, node, port_idx, port_type):
        """开始创建连接线 (使用 Event Filter + Grab Mouse)"""
        if port_type != 'output':
            print(f"警告: start_connection 意外地由非输出端口触发: {port_type}")
            return

        # 记录连接起点等信息
        self.connecting_from = (node, port_idx, port_type)
        print(f"DEBUG: start_connection - Starting connection from Node {node['id']} Port {port_idx}")

        try:
            port_info = node['port_widgets']['outputs'][port_idx]
            global_pos = node['widget'].mapToGlobal(port_info['pos'])
            canvas_pos = self.node_canvas_widget.mapFromGlobal(global_pos)

            self.connection_start_pos = canvas_pos
            self.connection_current_pos = canvas_pos
        except Exception as e:
             print(f"DEBUG: Error getting start position: {e}")
             self.connecting_from = None # Abort if error
             return

        # *** 安装事件过滤器 ***
        print("DEBUG: start_connection - Installing event filter")
        self.node_canvas_widget.installEventFilter(self)
        self._is_connecting_filter_active = True # 标记过滤器状态

        # *** 显式抓取鼠标 ***
        print("DEBUG: start_connection - Grabbing mouse")
        self.node_canvas_widget.grabMouse() # 确保画布接收事件

        # 设置鼠标指针
        self.setCursor(Qt.CrossCursor)
    def show_node_preview_window(self, node):
        """
        弹出一个独立窗口显示节点输出预览，或更新已存在的窗口。
        窗口非模态，不阻塞主程序。
        兼容 numpy.ndarray 和 PIL.Image 两种输入类型。
        """
        # 局部导入，避免全局污染
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QApplication
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt, Signal
        import numpy as np
        from PIL import Image

        node_id = node['id']

        # --- 内部辅助函数：更新图像 ---
        def update_image_content(dialog, img_data):
            try:
                if img_data is None:
                    dialog.image_label.setText("无图像输出")
                    dialog.image_label.setPixmap(QPixmap()) # 清除旧图像
                    dialog.adjustSize() # 调整大小
                    return

                # 支持 numpy.ndarray 类型
                if isinstance(img_data, np.ndarray):
                    if img_data.dtype == np.float32 or img_data.dtype == np.float64:
                        arr = np.clip(img_data * 255, 0, 255).astype(np.uint8)
                    else:
                        arr = img_data.astype(np.uint8)
                    pil_img = Image.fromarray(arr)
                    qimg = self.pil_to_qimage(pil_img)
                elif isinstance(img_data, Image.Image):
                     # 直接当作 PIL Image 处理
                    qimg = self.pil_to_qimage(img_data)
                else:
                    # 尝试直接创建 QPixmap (例如，如果已经是 QImage 或 QPixmap)
                    # 或其他支持的类型
                    qimg = img_data # 假设可以直接使用

                if qimg is None or not hasattr(qimg, 'isNull') or qimg.isNull():
                     # 检查转换后的 qimg 是否有效
                    raise RuntimeError("QImage 转换或原始数据无效")

                pixmap = QPixmap.fromImage(qimg) if isinstance(qimg, QImage) else QPixmap(qimg)

                if pixmap.isNull():
                     raise RuntimeError("QPixmap 转换失败")

                dialog.image_label.setPixmap(pixmap)
                dialog.image_label.setText("") # 清除提示文字
                dialog.adjustSize() # 根据新图像调整对话框大小

            except Exception as e:
                error_message = f"预览更新失败: {e}"
                print(f"Error updating preview for node {node_id}: {e}") # 打印错误便于调试
                dialog.image_label.setText(error_message)
                dialog.image_label.setPixmap(QPixmap()) # 清除旧图像
                dialog.adjustSize() # 调整大小

        # --- 先确保节点已处理过 ---
        if 'processed_outputs' not in node:
            print(f"节点 {node['title']} (ID: {node_id}) 尚未处理，先进行处理...")
            try:
                # 确保该节点和所有上游节点都被处理
                self.process_node(node)
            except Exception as e:
                print(f"处理节点 {node['title']} 时出错: {e}")
                import traceback
                traceback.print_exc()

        # --- 检查窗口是否已存在 ---
        if node_id in self.node_preview_windows:
            dialog = self.node_preview_windows[node_id]
            if dialog and dialog.isVisible():
                print(f"更新现有预览窗口，节点ID: {node_id}")
                # 获取最新的图像数据
                latest_img = None
                if 'processed_outputs' in node and node['processed_outputs']:
                    # 简单获取第一个输出，可根据需要调整
                    latest_img = next(iter(node['processed_outputs'].values()), None)

                update_image_content(dialog, latest_img)
                dialog.raise_() # 提升到顶层
                dialog.activateWindow() # 激活窗口
                return # 不再创建新窗口
            else:
                # 窗口存在但不可见或已删除，清理引用
                self.node_preview_windows.pop(node_id, None)

        # --- 创建新窗口 ---
        print(f"Creating new preview window for node {node_id}")
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{node['title']} 独立预览 (ID: {node_id})")
        dialog.setModal(False) # 强制非模态

        layout = QVBoxLayout(dialog)
        pic_label = QLabel("正在加载...")
        pic_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(pic_label)

        # 将 QLabel 保存为对话框的属性，方便 update_image_content 访问
        dialog.image_label = pic_label
        # 将更新函数附加到对话框实例上
        dialog.update_image = lambda img_data: update_image_content(dialog, img_data)

        # 获取初始图像
        initial_img = None
        if 'processed_outputs' in node and node['processed_outputs']:
            initial_img = next(iter(node['processed_outputs'].values()), None)

        # 设置初始图像
        update_image_content(dialog, initial_img) # 使用通用更新函数

        # 连接关闭信号，以便从字典中移除
        # 使用 lambda 确保传递正确的 node_id
        dialog.finished.connect(lambda result, nid=node_id: self._on_preview_window_closed(nid))

        # 存储并显示窗口
        self.node_preview_windows[node_id] = dialog
        dialog.show()

    def _on_preview_window_closed(self, node_id):
        """当独立预览窗口关闭时，从跟踪字典中移除它。"""
        print(f"Preview window closed for node {node_id}. Cleaning up.")
        if node_id in self.node_preview_windows:
            # dialog = self.node_preview_windows.pop(node_id)
            # dialog.deleteLater() # 可能需要，确保资源释放
            # 使用 pop 即可，finished 信号意味着对象生命周期即将结束
             self.node_preview_windows.pop(node_id, None)
        else:
            print(f"Warning: Node ID {node_id} not found in preview window dictionary during cleanup.")

    def show_node_metadata_dialog(self, node):
        """显示节点元数据查看对话框"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                                       QPushButton, QLabel, QDialogButtonBox, QApplication)
        from PySide6.QtCore import Qt
        import json
        import datetime

        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"元数据查看 - {node.get('title', '未知节点')} (ID: {node.get('id', 'N/A')})")
        dialog.setModal(True)
        dialog.resize(600, 500)

        # 主布局
        layout = QVBoxLayout(dialog)

        # 标题标签
        title_label = QLabel(f"节点: {node.get('title', '未知节点')}")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # 获取节点元数据
        node_metadata = node.get('metadata', {})

        # 如果节点有处理输出，也获取输出中的元数据
        output_metadata = {}
        if 'processed_outputs' in node and '_metadata' in node['processed_outputs']:
            output_metadata = node['processed_outputs']['_metadata']

        # 合并元数据（输出元数据优先）
        combined_metadata = self.metadata_manager.merge_metadata(node_metadata, output_metadata)

        # 格式化元数据文本
        metadata_text = self._format_metadata_for_display(combined_metadata)

        # 文本显示区域
        text_edit = QTextEdit()
        text_edit.setPlainText(metadata_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QApplication.font())  # 使用系统默认字体
        layout.addWidget(text_edit)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 复制到剪贴板按钮
        copy_button = QPushButton("复制到剪贴板")
        copy_button.clicked.connect(lambda: self._copy_metadata_to_clipboard(metadata_text))
        button_layout.addWidget(copy_button)

        # 导出到文件按钮
        export_button = QPushButton("导出到文件")
        export_button.clicked.connect(lambda: self._export_metadata_to_file(combined_metadata, node))
        button_layout.addWidget(export_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 对话框按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # 显示对话框
        dialog.exec_()

    def stop_connection_drag(self):
        """辅助函数：清理连接拖拽状态、过滤器和鼠标抓取"""
        # *** 释放鼠标抓取 ***
        print("DEBUG: stop_connection_drag - Releasing mouse")
        self.node_canvas_widget.releaseMouse() # 必须释放

        if hasattr(self, '_is_connecting_filter_active') and self._is_connecting_filter_active:
            print("DEBUG: stop_connection_drag - Removing event filter")
            self.node_canvas_widget.removeEventFilter(self)
            self._is_connecting_filter_active = False

        print("DEBUG: stop_connection_drag - Resetting connection state")
        self.connecting_from = None
        self.connection_start_pos = None
        self.connection_current_pos = None
        self.unsetCursor()
        # 拖拽结束后，更新一次画布以清除可能残留的临时线
        self.node_canvas_widget.update() # 这里用 update() 即可


    def eventFilter(self, watched, event):
        # --- 处理预览区滚轮缩放 ---
        if watched == self.preview_scroll.viewport() and event.type() == QEvent.Wheel:
            # 检查是否已经处理过该事件
            if hasattr(event, '_zoom_handled') and event._zoom_handled:
                return True

            # 标记该事件已被处理
            event._zoom_handled = True

            # 检查是否有活动的预览显示
            if not hasattr(self, 'preview_display') or not self.preview_display:
                return True

            # 检查是否有有效的图像
            if self.preview_display._display_pixmap.isNull():
                return True

            # 获取鼠标在视口中的位置
            mouse_pos_viewport = event.position().toPoint()

            # 获取预览区域的当前大小和滚动位置
            h_scrollbar = self.preview_scroll.horizontalScrollBar()
            v_scrollbar = self.preview_scroll.verticalScrollBar()
            scroll_x = h_scrollbar.value()
            scroll_y = v_scrollbar.value()

            # 计算鼠标在图像坐标系中的位置
            image_mouse_x = scroll_x + mouse_pos_viewport.x()
            image_mouse_y = scroll_y + mouse_pos_viewport.y()

            # 检查鼠标是否在图像边界内
            image_width = self.preview_display._display_pixmap.width()
            image_height = self.preview_display._display_pixmap.height()

            if (image_mouse_x < 0 or image_mouse_x >= image_width or
                image_mouse_y < 0 or image_mouse_y >= image_height):
                # 如果鼠标不在图像区域内，不处理缩放
                return True

            # 获取当前滚动条和视口
            old_scroll_x = h_scrollbar.value()
            old_scroll_y = v_scrollbar.value()
            old_zoom = self.zoom_level

            # 我们已经获取了鼠标在 viewport 中的位置
            # print(f"DEBUG: Zoom - Wheel Event - Mouse Viewport Pos: {mouse_pos_viewport}, OldScroll: ({old_scroll_x}, {old_scroll_y}), OldZoom: {old_zoom:.4f}") # DEBUG

            # 计算鼠标指向点在当前已缩放图像中的绝对坐标
            mouse_scaled_image_x = old_scroll_x + mouse_pos_viewport.x()
            mouse_scaled_image_y = old_scroll_y + mouse_pos_viewport.y()

            # 计算鼠标指向点在原始未缩放图像上的坐标 (使用浮点数)
            orig_image_x = 0.0
            orig_image_y = 0.0
            if abs(old_zoom) > 1e-9:
                    orig_image_x = mouse_scaled_image_x / old_zoom
                    orig_image_y = mouse_scaled_image_y / old_zoom
            else:
                    print("DEBUG: Zoom - Old zoom level too small.") # DEBUG
                    return True # 缩放级别过小，无法计算
            # print(f"DEBUG: Zoom - Scaled Image Pos: ({mouse_scaled_image_x:.2f}, {mouse_scaled_image_y:.2f}), Orig Image Pos: ({orig_image_x:.2f}, {orig_image_y:.2f})") # DEBUG

            # 获取滚轮增量和计算新的缩放级别
            delta = event.angleDelta().y()
            step = abs(delta) / 120.0
            factor = 1.15 ** step

            if delta > 0:
                new_zoom = old_zoom * factor
                if new_zoom > 8.0: new_zoom = 8.0
            else:
                new_zoom = old_zoom / factor
                if new_zoom < 0.1: new_zoom = 0.1

            if abs(new_zoom - old_zoom) < 1e-6:
                # print("DEBUG: Zoom - Zoom level change too small, skipping.") # DEBUG
                return True
            # print(f"DEBUG: Zoom - Delta: {delta}, NewZoom: {new_zoom:.4f}") # DEBUG

            # --- 更新状态 (应用新缩放级别) ---
            self.zoom_level = new_zoom
            if hasattr(self, 'zoom_info'):
                self.zoom_info.setText(f"缩放: {int(self.zoom_level * 100)}%")

            #--- 更新图像并调整 Widget 尺寸 ---
            print(f"DEBUG: Zoom - Before update_preview_with_zoom...") # DEBUG
            self.update_preview_with_zoom()
            print(f"DEBUG: Zoom - After update_preview_with_zoom...") # DEBUG

            # --- 重新计算目标滚动位置 (基于新尺寸和原始锚点) ---
            # 将原始图像上的锚点 (orig_image_x/y) 映射到新的缩放级别下的坐标
            new_anchor_scaled_x = orig_image_x * self.zoom_level
            new_anchor_scaled_y = orig_image_y * self.zoom_level
            # 计算滚动条需要设置到的值，以使得 new_anchor_scaled_x/y 出现在 mouse_pos_viewport 的位置
            target_scroll_x = round(new_anchor_scaled_x - mouse_pos_viewport.x())
            target_scroll_y = round(new_anchor_scaled_y - mouse_pos_viewport.y())
            # print(f"DEBUG: Zoom - Recalculated Target Scroll: H={target_scroll_x}, V={target_scroll_y}") # DEBUG

            # --- 立即设置滚动条值 (移除 QTimer) ---
            h_scrollbar_updated = self.preview_scroll.horizontalScrollBar()
            v_scrollbar_updated = self.preview_scroll.verticalScrollBar()
            # print(f"DEBUG: Zoom - Setting Scroll Directly: H={target_scroll_x}, V={target_scroll_y}. Current Range: H(0-{h_scrollbar_updated.maximum()}), V(0-{v_scrollbar_updated.maximum()})") # DEBUG
            h_scrollbar_updated.setValue(target_scroll_x)
            v_scrollbar_updated.setValue(target_scroll_y)
            # 再次读取确认
            # final_h = h_scrollbar_updated.value()
            # final_v = v_scrollbar_updated.value()
            # print(f"DEBUG: Zoom - Scroll Read After Set: H={final_h}, V={final_v}") # DEBUG

            # --- 确保 QTimer 相关代码已被移除 ---
            # if self._scroll_update_timer and self._scroll_update_timer.isActive(): ...
            # self._scroll_update_timer = QTimer() ...
            # self._scroll_update_timer.start(0) ...

            event.accept() # 接受事件
            return True # 事件已处理
        # --- 处理节点连接拖拽 (保持原有逻辑) ---
        if (hasattr(self, '_is_connecting_filter_active') and self._is_connecting_filter_active and
                watched == self.node_canvas_widget and self.connecting_from):

            if event.type() == QEvent.MouseMove:
                # ---- 处理鼠标移动 ----
                # print("DEBUG: eventFilter - MouseMove") # 频繁输出，可以注释掉
                current_pos = event.pos()
                self.connection_current_pos = current_pos
                # *** 使用 repaint() 强制立即重绘 ***
                self.node_canvas_widget.repaint() # 请求立即重绘临时线
                return True # 事件已处理

            elif event.type() == QEvent.MouseButtonRelease:
                # ---- 处理鼠标释放 ----
                print("DEBUG: eventFilter - MouseButtonRelease")
                if event.button() == Qt.LeftButton: # 仅处理左键释放
                    release_pos = event.pos()
                    print(f"DEBUG: eventFilter - Release position (canvas coords): {release_pos.x()}, {release_pos.y()}")

                    # 查找目标端口
                    target_node, target_port_idx, target_port_type = self.find_port_at_position(release_pos)

                    if target_node:
                        print(f"DEBUG: eventFilter - Found potential target: Node {target_node['id']} '{target_node['title']}', Port {target_port_idx}, Type {target_port_type}")
                    else:
                        print("DEBUG: eventFilter - No target port found at release position.")

                    # 获取起点信息
                    source_node, source_port_idx, source_port_type = self.connecting_from

                    # --- 关键：先清理状态，移除过滤器，释放鼠标 ---
                    self.stop_connection_drag() # 调用清理函数

                    # --- 再进行验证和连接创建（如果找到有效目标） ---
                    if target_node and target_port_type == 'input':
                         if source_node == target_node:
                             print("DEBUG: eventFilter - Validation failed: self connection.")
                             QMessageBox.warning(self, "无效连接", "节点不能连接到自身")
                         else:
                             # 检查类型兼容性
                             try:
                                 # 首先尝试从port_widgets获取类型信息
                                 if ('port_widgets' in source_node and 'outputs' in source_node['port_widgets'] and
                                     source_port_idx in source_node['port_widgets']['outputs']):
                                     output_type = source_node['port_widgets']['outputs'][source_port_idx]['type']
                                 else:
                                     # 回退到script_info
                                     output_type = source_node['script_info']['outputs'][source_port_idx]

                                 if ('port_widgets' in target_node and 'inputs' in target_node['port_widgets'] and
                                     target_port_idx in target_node['port_widgets']['inputs']):
                                     input_type = target_node['port_widgets']['inputs'][target_port_idx]['type']
                                 else:
                                     # 回退到script_info
                                     input_type = target_node['script_info']['inputs'][target_port_idx]

                                 # 检查是否为伪类型
                                 real_output_type = output_type
                                 if output_type in self.pseudo_types:
                                     real_output_type = self.pseudo_types[output_type]
                                     print(f"DEBUG: eventFilter - Output port is pseudo-type: {output_type} -> {real_output_type}")

                                 real_input_type = input_type
                                 if input_type in self.pseudo_types:
                                     real_input_type = self.pseudo_types[input_type]
                                     print(f"DEBUG: eventFilter - Input port is pseudo-type: {input_type} -> {real_input_type}")

                                 print(f"DEBUG: eventFilter - Checking type compatibility: Output '{output_type}' -> Input '{input_type}'")

                                 # 比较时考虑伪类型的真实类型
                                 is_compatible = (output_type == input_type or  # 类型名称完全匹配
                                                 real_output_type == real_input_type or  # 伪类型的真实类型匹配
                                                 output_type == 'any' or input_type == 'any' or  # 通配符类型
                                                 real_output_type == input_type or  # 输出伪类型和输入匹配
                                                 output_type == real_input_type or  # 输出和输入伪类型匹配
                                                 True)  # 最后总是允许（为了兼容性，可以考虑在未来移除）

                                 if is_compatible:
                                     # 尝试连接
                                     print(f"DEBUG: eventFilter - Attempting connection: {source_node['id']}:{source_port_idx} -> {target_node['id']}:{target_port_idx}")
                                     success = self.create_connection(source_node, source_port_idx, target_node, target_port_idx)
                                 if output_type != input_type and real_output_type != real_input_type:
                                     self.task_label.setText(f"类型不匹配，输出端口类型 '{output_type}' 与输入端口类型 '{input_type}' 不同")
                             except Exception as e:
                                 print(f"DEBUG: eventFilter - Validation failed: error getting port types: {str(e)}")
                                 QMessageBox.warning(self, "连接错误", f"检查端口类型时出错: {str(e)}")
                    else:
                        if target_node:
                            print(f"DEBUG: eventFilter - Validation failed: target port type is not 'input' ({target_port_type}).")
                        # else: (no target found message already printed)

                    return True # 事件已处理

        # 如果事件不是我们在此过滤器中处理的，则调用基类实现，允许默认处理
        return super().eventFilter(watched, event)

    # ---- 再次确认以下方法已被移除或注释掉 ----
    # def on_canvas_drag(self, event): ...
    # def on_canvas_release(self, event): ...
    # ---------------------------------------
    def find_port_at_position(self, pos):
        """查找指定位置的端口"""
        # 保存最近的端口和距离
        closest_node = None
        closest_port_idx = None
        closest_port_type = None
        min_distance = 30  # 增加检测范围到30像素

        # 遍历所有节点和端口
        for node in self.nodes:
            # 检查输入端口
            for port_idx, port_info in node['port_widgets']['inputs'].items():
                # 计算端口的全局位置
                global_port_pos = node['widget'].mapToGlobal(port_info['pos'])
                # 转换为画布坐标
                canvas_port_pos = self.node_canvas_widget.mapFromGlobal(global_port_pos)

                # 检查距离
                distance = ((canvas_port_pos.x() - pos.x()) ** 2 + (canvas_port_pos.y() - pos.y()) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    closest_node = node
                    closest_port_idx = port_idx
                    closest_port_type = 'input'

            # 检查输出端口
            for port_idx, port_info in node['port_widgets']['outputs'].items():
                # 计算端口的全局位置
                global_port_pos = node['widget'].mapToGlobal(port_info['pos'])
                # 转换为画布坐标
                canvas_port_pos = self.node_canvas_widget.mapFromGlobal(global_port_pos)

                # 检查距离
                distance = ((canvas_port_pos.x() - pos.x()) ** 2 + (canvas_port_pos.y() - pos.y()) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    closest_node = node
                    closest_port_idx = port_idx
                    closest_port_type = 'output'

        return closest_node, closest_port_idx, closest_port_type

    def create_connection(self, output_node, output_port, input_node, input_port):
        """创建节点之间的连接 (实现替换逻辑)"""
        # 检查连接是否已存在 (完全相同的连接)
        for conn in self.connections:
            if (conn['output_node'] == output_node and conn['output_port'] == output_port and
                conn['input_node'] == input_node and conn['input_port'] == input_port):
                return False # 完全相同的连接，无需操作

        # 检查是否会形成环路 (必须在替换之前检查，否则可能错误地允许环路)
        if self.would_form_cycle(output_node, input_node):
            QMessageBox.warning(self, "连接错误", "不能形成环路连接！")
            return False

        # --- 新增：查找并移除指向目标输入端口的旧连接 ---
        connection_to_remove = None
        for existing_conn in self.connections:
            if existing_conn['input_node'] == input_node and existing_conn['input_port'] == input_port:
                connection_to_remove = existing_conn
                break # 一个输入端口只有一个连接

        if connection_to_remove:
            print(f"自动断开旧连接: {connection_to_remove['output_node']['title']}:{connection_to_remove['output_port']} -> {connection_to_remove['input_node']['title']}:{connection_to_remove['input_port']}")
            self.connections.remove(connection_to_remove)
        # --- 结束移除旧连接逻辑 ---

        # 创建新连接
        connection = {
            'output_node': output_node,
            'output_port': output_port,
            'input_node': input_node,
            'input_port': input_port
        }

        self.connections.append(connection)

        # 设置节点图为已修改状态
        self.set_nodegraph_state(modified=True)

        # --- 新增：处理灵活端口 ---
        # 检查并处理输出节点的灵活端口
        self._handle_flexible_port(output_node, output_port, 'outputs')

        # 检查并处理输入节点的灵活端口
        self._handle_flexible_port(input_node, input_port, 'inputs')
        # --- 结束灵活端口处理 ---

        # 连接创建只会影响输入节点和其下游节点
        # 输出节点的逻辑和结果不会受到影响，所以无需重新处理
        # 在这里精确控制重新计算的范围，避免不必要的处理
        print(f"创建连接：只处理输入节点 {input_node['title']} 及其下游节点")
        self.process_node_graph(changed_nodes=[input_node])

        # 不直接调用 self.process_node_graph() 以避免处理全部节点

        return True

    def _handle_flexible_port(self, node, port_idx, port_type):
        """处理灵活端口逻辑，如果是灵活端口且所有端口都已连接，则添加新端口"""
        # 检查是否是灵活端口类型
        port_type_singular = port_type[:-1]  # 'inputs' -> 'input', 'outputs' -> 'output'
        flexible_ports = node.get('flexible_ports', {}).get(port_type, [])

        if not flexible_ports:
            return  # 节点没有灵活端口，直接返回

        # 获取当前端口的类型
        port_widget_info = node['port_widgets'][port_type].get(port_idx)
        if not port_widget_info:
            return  # 端口不存在

        current_port_type = port_widget_info['type']

        # 检查是否是灵活端口类型
        if current_port_type not in flexible_ports:
            return  # 不是灵活端口类型

        # 检查是否所有此类型的端口都已连接
        all_connected = True
        for conn_idx, port_info in node['port_widgets'][port_type].items():
            if port_info['type'] == current_port_type:
                # 检查该端口是否有连接
                has_connection = False
                for conn in self.connections:
                    if (port_type == 'inputs' and
                        conn['input_node'] == node and
                        conn['input_port'] == conn_idx):
                        has_connection = True
                        break
                    elif (port_type == 'outputs' and
                          conn['output_node'] == node and
                          conn['output_port'] == conn_idx):
                        has_connection = True
                        break

                if not has_connection:
                    all_connected = False
                    break

        # 如果所有相同类型的灵活端口都已连接，添加一个新端口
        if all_connected:
            # 添加新端口
            new_port_idx = node['port_counts'][port_type]

            # 更新端口数量
            node['port_counts'][port_type] += 1

            # 创建新端口部件
            port_color = self.get_port_color(current_port_type)
            port_widget = QFrame(node['widget'])
            port_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                     stop:0 #FFFFFF, stop:1 {port_color}); /* 白色到端口颜色的渐变 */
                    border: 1px solid {QColor(port_color).darker(130).name()}; /* 端口边框颜色加深 */
                    border-radius: 5px; /* 纵向椭圆端口 */
                }}
            """)
            port_widget.setFixedSize(10, 16)

            # 计算端口位置
            if port_type == 'inputs':
                port_x = -3
            else:  # outputs
                port_x = node['width'] - 7

            port_y = 20 + new_port_idx * 20
            port_widget.move(port_x, port_y)

            # 设置工具提示
            port_widget.setToolTip(f"{port_type_singular}端口: {current_port_type}")

            # 保存端口信息
            node['port_widgets'][port_type][new_port_idx] = {
                'widget': port_widget,
                'type': current_port_type,
                'pos': QPoint(port_x + 5, port_y + 8)
            }

            # 设置鼠标事件 - 使用函数来避免lambda闭包问题
            def create_press_handler(n, idx, t):
                return lambda event: self.on_port_click(event, n, idx, t)

            def create_context_menu_handler(n, idx, t):
                return lambda pos: self.show_port_context_menu(pos, n, idx, t)

            port_widget.mousePressEvent = create_press_handler(node, new_port_idx, port_type_singular)
            port_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            port_widget.customContextMenuRequested.connect(
                create_context_menu_handler(node, new_port_idx, port_type_singular)
            )

            # 显示新端口
            port_widget.show()

            # 调整节点高度以适应新端口
            max_ports = max(node['port_counts']['inputs'], node['port_counts']['outputs'])
            node['height'] = max(80, 40 + max_ports * 20)
            node['widget'].setFixedHeight(node['height'])

            print(f"已为节点 {node['title']} 添加新的灵活{port_type_singular}端口: {current_port_type}")

    def update_connections(self):
        """更新所有连接线"""
        # 触发重绘以更新连接线
        self.node_canvas_widget.update()

    def would_form_cycle(self, output_node, input_node):
        """检查添加连接是否会形成循环"""
        # 实现简单的循环检测
        visited = set()

        def dfs(node):
            if node['id'] in visited:
                return False

            if node == output_node:
                return True

            visited.add(node['id'])

            # 检查当前节点的所有输出连接
            for conn in self.connections:
                if conn['output_node'] == node:
                    if dfs(conn['input_node']):
                        return True

            return False

        return dfs(input_node)

    def paintEvent(self, event):
        """重写绘制事件处理连接线的绘制"""
        super().paintEvent(event)

        # 我们需要在node_canvas_widget上绘制连接线
        # 但是这个方法是主窗口的paintEvent
        # 所以我们需要重写QWidget的paintEvent方法

        # 这里我们使用一个变通方法：创建一个自定义的NodeCanvasWidget类
        # 并重写它的paintEvent方法

    def select_node(self, node):
        """选择节点并显示其设置 (使用 setProperty)"""
        # 清除旧的选择状态
        if self.selected_node and self.selected_node != node and 'widget' in self.selected_node and self.selected_node['widget']:
            try:
                # --- 修改：设置 selected 属性为 False 并刷新样式 ---
                self.selected_node['widget'].setProperty("selected", False)
                self.selected_node['widget'].style().unpolish(self.selected_node['widget'])
                self.selected_node['widget'].style().polish(self.selected_node['widget'])
                # --- 结束修改 ---
            except Exception as e:
                print(f"Error updating style for deselected node {self.selected_node.get('id')}: {e}")

        # 设置新的选择状态
        self.selected_node = node
        if node and 'widget' in node and node['widget']:
            try:
                # --- 修改：设置 selected 属性为 True 并刷新样式 ---
                node['widget'].setProperty("selected", True)
                node['widget'].style().unpolish(node['widget'])
                node['widget'].style().polish(node['widget'])
                # --- 结束修改 ---
            except Exception as e:
                 print(f"Error updating style for selected node {node.get('id')}: {e}")

        # 静默更新设置面板，不创建新窗口或显示消息框
        if node:
            self.update_node_settings(node)

    def update_node_settings(self, node):
        """更新节点设置面板，不创建新窗口"""
        # 清除旧的设置UI
        for i in reversed(range(self.settings_content_layout.count())):
            widget = self.settings_content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 创建设置标题
        title_label = QLabel(f"{node['title']} 设置")
        title_label.setProperty("styleClass", "title")
        title_label.setAlignment(Qt.AlignCenter)
        self.settings_content_layout.addWidget(title_label)

        # --- 新增：处理 NeoScript 自定义设置 UI ---
        if node.get('script_type') == 'neo' and node.get('create_settings_widget_func'):
            print(f"Creating custom settings UI for NeoScript: {node['title']}") # DEBUG
            try:
                factory_func = node['create_settings_widget_func']
                # 准备回调函数 (使用 lambda 确保传递正确的节点引用)
                update_callback = lambda p_name, p_value: self.update_node_param(node, p_name, p_value)
                # 获取当前参数值字典
                current_params = {name: info['value'] for name, info in node.get('params', {}).items()}
                # 获取上下文
                context = self.get_application_context(node)
                # 创建自定义部件
                custom_widget = factory_func(current_params, context, update_callback)
                if custom_widget:
                    self.settings_content_layout.addWidget(custom_widget)
                    self.settings_content_layout.addStretch(1) # 添加伸缩项到底部
                    return # 自定义 UI 已创建，不再生成标准控件
                else:
                    print(f"Warning: create_settings_widget for {node['title']} returned None.")
            except Exception as e:
                print(f"Error creating custom settings UI for {node['title']}: {e}")
                import traceback
                traceback.print_exc()
                # 如果自定义UI创建失败，可以考虑回退到标准控件
                error_label = QLabel("创建自定义设置UI时出错！")
                error_label.setAlignment(Qt.AlignCenter)
                self.settings_content_layout.addWidget(error_label)
                return
        # --- 结束 NeoScript 处理 ---

        # --- 标准参数处理 (仅在非 NeoScript 或自定义 UI 创建失败时执行) ---
        if not node['params']:
            no_params_label = QLabel("此节点没有可配置参数")
            no_params_label.setAlignment(Qt.AlignCenter)
            self.settings_content_layout.addWidget(no_params_label)
            return

        # 创建参数设置区域
        params_widget = QWidget()
        params_layout = QGridLayout(params_widget)

        # 计算合适的列数
        params_count = len(node['params'])
        settings_width = self.settings_frame.width()


        # 基于宽度和参数数确定列数
        if settings_width > 600:
            max_columns = min(3, params_count)
        elif settings_width > 400:
            max_columns = min(2, params_count)
        else:
            max_columns = 1

        # 确保至少1列
        num_columns = max(1, max_columns)

        # 放置参数控件
        row, col = 0, 0
        for param_name, param_info in node['params'].items():
            # 创建参数框架
            param_frame = QFrame()
            param_frame.setFrameShape(QFrame.StyledPanel)
            param_layout = QVBoxLayout(param_frame)

            # 参数标签
            label = QLabel(param_info.get('label', param_name))
            label.setProperty("styleClass", "subtitle")
            param_layout.addWidget(label)

            # 创建参数控件
            self.create_param_control(param_frame, param_layout, node, param_name, param_info)

            # 添加到网格
            params_layout.addWidget(param_frame, row, col)

            # 更新行列
            col += 1
            if col >= num_columns:
                col = 0
                row += 1

        # 添加参数设置区域
        self.settings_content_layout.addWidget(params_widget)

    def create_param_control(self, parent, layout, node, param_name, param_info):
        """创建参数控件"""
        param_type = param_info.get('type', 'text')

        if param_type == 'slider':
            # 滑块控件
            min_val = param_info.get('min', 0)
            max_val = param_info.get('max', 100)
            step = param_info.get('step', 1)
            value = param_info.get('value', min_val)
            is_float_slider = isinstance(step, float) and step < 1.0

            # --- 新增：浮点滑块处理 ---
            scale_factor = 1
            if is_float_slider:
                # 避免除零错误
                if step > 0:
                    scale_factor = int(1 / step)
                else:
                    print(f"警告: 节点 {node['title']} 参数 {param_name} 的 step 为零或负数，将使用整数滑块。")
                    is_float_slider = False # 回退到整数滑块

                # 将浮点值转换为整数用于 QSlider
                slider_min = int(min_val * scale_factor)
                slider_max = int(max_val * scale_factor)
                slider_value = int(value * scale_factor)
            else:
                # 整数滑块保持原样
                slider_min = int(min_val)
                slider_max = int(max_val)
                slider_value = int(value)
            # --- 结束浮点滑块处理 ---

            # 创建水平布局
            slider_widget = QWidget()
            slider_layout = QHBoxLayout(slider_widget)
            slider_layout.setContentsMargins(0, 0, 0, 0)

            # 滑块
            slider = QSlider(Qt.Horizontal)
            # --- 修改：使用转换后的整数值 ---
            slider.setMinimum(slider_min)
            slider.setMaximum(slider_max)
            # 设置步长（QSlider本身步长为1，我们通过值转换实现逻辑步长）
            slider.setSingleStep(1)
            slider.setValue(slider_value)
            # --- 结束修改 ---
            slider_layout.addWidget(slider, 1)

            # 值显示 - 初始显示格式化后的值
            if is_float_slider:
                value_label = QLabel(f"{value:.{len(str(step).split('.')[-1])}f}") # 根据step小数位数格式化
            else:
                value_label = QLabel(str(int(value)))
            value_label.setFixedWidth(50) # 增加宽度以容纳小数
            slider_layout.addWidget(value_label)

            # 更新函数
            def update_value(slider_int_val):
                actual_val = 0
                if is_float_slider:
                    actual_val = float(slider_int_val) / scale_factor
                    # 根据 step 的小数位数格式化显示
                    try:
                         num_decimals = len(str(step).split('.')[-1])
                         value_label.setText(f"{actual_val:.{num_decimals}f}")
                    except: #  fallback
                         value_label.setText(f"{actual_val:.2f}") # 默认保留两位小数
                else:
                    actual_val = int(slider_int_val)
                    value_label.setText(str(actual_val))
                # --- 结束修改 ---

                # 更新节点参数
                self.update_node_param(node, param_name, actual_val)

            # 连接信号
            slider.valueChanged.connect(update_value)

            # 添加到布局
            layout.addWidget(slider_widget)

        elif param_type == 'checkbox':
            # 复选框
            value = param_info.get('value', False)

            checkbox = QCheckBox()
            checkbox.setChecked(value)

            # 更新函数
            def update_value(state):
                self.update_node_param(node, param_name, state == Qt.Checked)

            # 连接信号
            checkbox.stateChanged.connect(update_value)

            # 添加到布局
            layout.addWidget(checkbox)

        elif param_type == 'dropdown':
            # 下拉框
            options = param_info.get('options', [])
            value = param_info.get('value', options[0] if options else '')

            dropdown = QComboBox()
            dropdown.addItems(options)

            # 设置当前值
            index = dropdown.findText(value)
            if index >= 0:
                dropdown.setCurrentIndex(index)

            # 更新函数
            def update_value(idx):
                self.update_node_param(node, param_name, dropdown.itemText(idx))

            # 连接信号
            dropdown.currentIndexChanged.connect(update_value)

            # 添加到布局
            layout.addWidget(dropdown)

        elif param_type == 'path':
            # 路径选择
            value = param_info.get('value', '')

            # 创建水平布局
            path_widget = QWidget()
            path_layout = QHBoxLayout(path_widget)
            path_layout.setContentsMargins(0, 0, 0, 0)

            # 路径输入框
            path_edit = QLineEdit(value)
            path_layout.addWidget(path_edit, 1)

            # 浏览按钮
            browse_btn = QPushButton("...")
            browse_btn.setFixedWidth(30)
            path_layout.addWidget(browse_btn)

            # 浏览函数
            def browse_path():
                current_path = path_edit.text()
                start_dir = os.path.dirname(current_path) if current_path else self.work_folder

                if param_name.lower().find('export') >= 0:
                    # 导出路径使用保存对话框
                    file_path, _ = QFileDialog.getSaveFileName(
                        self,
                        "选择保存位置",
                        start_dir,
                        "JPEG文件 (*.jpg);;PNG文件 (*.png);;TIFF文件 (*.tif);;所有文件 (*.*)"
                    )
                else:
                    # 否则使用打开对话框
                    file_path, _ = QFileDialog.getOpenFileName(
                        self,
                        "选择文件",
                        start_dir,
                        "图像文件 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp);;所有文件 (*.*)"
                    )

                if file_path:
                    path_edit.setText(file_path)
                    self.update_node_param(node, param_name, file_path)

            # 连接信号
            browse_btn.clicked.connect(browse_path)
            path_edit.textChanged.connect(lambda text: self.update_node_param(node, param_name, text))

            # 添加到布局
            layout.addWidget(path_widget)

        else:
            # 默认文本输入
            value = param_info.get('value', '')

            text_edit = QLineEdit(str(value))

            # 更新函数
            def update_value(text):
                self.update_node_param(node, param_name, text)

            # 连接信号
            text_edit.textChanged.connect(update_value)

            # 添加到布局
            layout.addWidget(text_edit)

    def update_node_param(self, node, param_name, param_value):
        """更新节点参数并触发处理，但延迟保存操作"""
        if 'params' in node and param_name in node['params']:
            # 保存旧值用于比较
            old_value = node['params'][param_name]['value']

            # 如果值没有变化，不触发更新
            if old_value == param_value:
                return

            # 更新参数值
            node['params'][param_name]['value'] = param_value
            print(f"update_node_param: Node '{node['title']}', Param '{param_name}' updated to: {param_value}") # DEBUG

            # 设置节点图为已修改状态
            self.set_nodegraph_state(modified=True)

            # 清除节点的已处理输出缓存以强制重新计算
            if 'processed_outputs' in node:
                del node['processed_outputs']

            # 检查此节点是否是预览节点的上游节点
            is_preview_relevant = False
            preview_node = None
            for n in self.nodes:
                if n['title'] == '预览节点':
                    preview_node = n
                    break

            if preview_node and (node == preview_node or self.is_upstream_of_preview(node)):
                is_preview_relevant = True

            # 选择性处理节点图 - 只处理当前节点和下游节点
            # 将suppress_auto_save设为True，抑制即时自动保存
            self.process_node_graph(suppress_auto_save=True, changed_nodes=[node])

            # 更新预览（确保在参数更新后更新预览）
            # 如果是预览节点的上游，确保所有依赖都被处理
            if is_preview_relevant:
                self.update_preview(force_refresh=True)
            else:
                self.update_preview()

            # 注: 原来的延迟保存计时器代码已移除

    def delete_selected_node(self, node=None):
        """删除选中的节点或指定节点"""
        # 确定要删除的节点
        target_node = node if node is not None else self.selected_node

        if not target_node:
            return

        # 删除相关的连接
        conn_to_remove = []
        for conn in self.connections:
            if conn['input_node'] == target_node or conn['output_node'] == target_node:
                conn_to_remove.append(conn)

        for conn in conn_to_remove:
            self.connections.remove(conn)

        # 删除节点部件
        if 'widget' in target_node and target_node['widget']:
            target_node['widget'].setParent(None)

        # 从节点列表中移除
        self.nodes.remove(target_node)

        # 设置节点图为已修改状态
        self.set_nodegraph_state(modified=True)

        # 清除选择
        if self.selected_node == target_node:
            self.selected_node = None

            # 清除设置区域
            for i in reversed(range(self.settings_content_layout.count())):
                widget = self.settings_content_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            # 不显示任何提示，保持空白
            # self.no_node_label = QLabel("")
            # self.no_node_label.setAlignment(Qt.AlignCenter)
            # self.settings_content_layout.addWidget(self.no_node_label)

        # 只处理受删除节点影响的下游节点
        # 1. 找出哪些节点是受影响的（有连接被删除的节点）
        affected_nodes = []
        affected_node_ids = set()

        # 收集所有删除连接影响的输入节点
        for conn in conn_to_remove:
            # 如果节点是输入节点，则它受到影响
            if conn['input_node'] != target_node:  # 不是被删除的节点
                if conn['input_node']['id'] not in affected_node_ids:
                    affected_nodes.append(conn['input_node'])
                    affected_node_ids.add(conn['input_node']['id'])

        if affected_nodes:
            print(f"删除节点 '{target_node['title']}' 影响了 {len(affected_nodes)} 个节点，只处理这些节点")
            self.process_node_graph(changed_nodes=affected_nodes)
        else:
            print(f"删除节点 '{target_node['title']}' 没有影响其他节点，无需重新处理")
            # 只需要更新预览即可
            self.update_preview()

        # 更新画布
        self.node_canvas_widget.update()

        # 注: 此处原来的自动保存代码已移除
    def get_node_at_position(self, pos):
        """获取指定位置处的节点"""
        # 安全检查 - 确保pos是QPoint或QPointF类型
        if not isinstance(pos, (QPoint, QPointF)):
            print(f"警告: get_node_at_position接收到非有效位置: {type(pos)}")
            return None

        # 优先返回排序靠后的节点（通常是最近添加/选择的节点，在UI上层）
        for node in reversed(self.nodes):
            # 确保节点有所有必要的属性
            if 'x' not in node or 'y' not in node or 'width' not in node or 'height' not in node:
                continue

            # 创建节点矩形 - 确保值有效
            try:
                # 节点以其左上角为原点
                node_rect = QRectF(
                    float(node['x']),
                    float(node['y']),
                    float(node['width']),
                    float(node['height'])
                )

                # 检查是否点击在节点内
                if node_rect.contains(pos):
                    return node
            except (ValueError, TypeError) as e:
                print(f"警告: 节点位置计算错误: {e}")

        return None
    def process_node_graph(self, suppress_auto_save=False, changed_nodes=None):
        """
        使用更健壮的拓扑排序逻辑处理节点图，并记录处理过的节点ID

        参数:
            suppress_auto_save (bool): 是否抑制自动保存
            changed_nodes (list): 需要重新处理的节点列表
                - 如果为None，则重新处理所有节点
                - 如果不为None，则只处理指定节点及其下游节点

        注意:
            当添加新节点时，应该只处理新添加的节点，即使用changed_nodes=[node]
            仅在完全清空节点图或者加载新节点图时才清空缓存
        """
        processed_node_ids = set() # 记录在此次运行中处理的节点

        if not self.nodes:
            # 如果没有节点，确保清除上次处理记录并返回
            if hasattr(self, 'preview_display_widget'):
                self.preview_display_widget.processed_in_last_run = set()
                self.preview_display_widget.update() # 更新一次以清除可能残留的叠加层
            return

        # --- 1. 初始化处理状态 ---
        # processing_state: node_id -> {'node': node_obj, 'inputs_needed': set(indices), 'inputs_received': set(indices), 'status': 'pending/ready/processing/done/error'}
        processing_state = {}
        # input_connections: input_node_id -> list of {output_node_id, output_port_idx, input_port_idx}
        input_connections = {node['id']: [] for node in self.nodes}
        # output_connections: output_node_id -> list of {input_node_id, input_port_idx, output_port_idx}
        output_connections = {node['id']: [] for node in self.nodes}

        for conn in self.connections:
            in_node_id = conn['input_node']['id']
            out_node_id = conn['output_node']['id']
            input_connections[in_node_id].append({
                'output_node_id': out_node_id,
                'output_port_idx': conn['output_port'],
                'input_port_idx': conn['input_port']
            })
            output_connections[out_node_id].append({
                'input_node_id': in_node_id,
                'input_port_idx': conn['input_port'],
                'output_port_idx': conn['output_port']
            })

        for node in self.nodes:
            node_id = node['id']
            num_expected_inputs = len(node['script_info'].get('inputs', []))
            inputs_needed = set(idx for idx in range(num_expected_inputs)
                                if any(conn_info['input_port_idx'] == idx for conn_info in input_connections[node_id]))
            processing_state[node_id] = {
                'node': node,
                'inputs_needed': inputs_needed,
                'inputs_received': set(),
                'status': 'pending'
            }
            # 只有当节点需要重新处理时才清除旧输出
            if changed_nodes is None or node['id'] in set(n['id'] for n in changed_nodes if isinstance(n, dict) and 'id' in n):
                if 'processed_outputs' in node:
                    del node['processed_outputs']

        # --- 2. 确定处理范围和起始节点 ---
        nodes_to_process_ids = set()
        if changed_nodes is None:
            # 完全重新计算
            nodes_to_process_ids = set(processing_state.keys())
        else:
            # 选择性重新计算
            nodes_to_process_ids = set(n['id'] for n in changed_nodes)
            queue = list(nodes_to_process_ids)
            while queue:
                current_id = queue.pop(0)
                for conn_info in output_connections.get(current_id, []):
                    downstream_id = conn_info['input_node_id']
                    if downstream_id not in nodes_to_process_ids:
                        nodes_to_process_ids.add(downstream_id)
                        queue.append(downstream_id)
            # 对于受影响的节点，重置其状态
            for node_id in nodes_to_process_ids:
                processing_state[node_id]['status'] = 'pending'
                processing_state[node_id]['inputs_received'] = set()
            # 对于未受影响的节点，标记为完成 (假设它们有缓存的结果)
            for node_id in processing_state:
                 if node_id not in nodes_to_process_ids:
                      processing_state[node_id]['status'] = 'done' # 标记为完成
                      # 不需要添加到 processed_node_ids，因为我们只关心本次运行处理的

        # 查找处理范围内的起始节点 (没有需要的输入，或者所有需要的输入都来自已完成/范围外的节点)
        processing_queue = []
        for node_id in nodes_to_process_ids:
            state = processing_state[node_id]
            if not state['inputs_needed']: # 没有输入端口
                state['status'] = 'ready'
                processing_queue.append(node_id)
            else:
                # 检查输入是否来自已完成的节点
                received_from_done = set()
                all_inputs_accounted_for = True
                for conn_info in input_connections[node_id]:
                    upstream_id = conn_info['output_node_id']
                    input_port_idx = conn_info['input_port_idx']
                    if input_port_idx in state['inputs_needed']:
                         if upstream_id not in processing_state or processing_state[upstream_id]['status'] == 'done':
                              received_from_done.add(input_port_idx)
                         elif upstream_id not in nodes_to_process_ids: # 输入来自范围外
                              received_from_done.add(input_port_idx)
                         # else: 输入来自处理范围内的未完成节点，等待

                state['inputs_received'] = received_from_done
                if state['inputs_received'] == state['inputs_needed']:
                     state['status'] = 'ready'
                     processing_queue.append(node_id)

        # --- 3. 执行处理 ---
        start_time = time.time()
        processed_count = 0
        error_occurred = False

        # 记录每个节点的处理时间
        node_times = {}

        while processing_queue:
            current_id = processing_queue.pop(0)
            state = processing_state[current_id]

            if state['status'] != 'ready': # 可能已被其他路径处理
                continue

            current_node = state['node']
            state['status'] = 'processing'
            # 记录节点处理开始时间
            node_start_time = time.time()
            try:
                # 调用 process_node 来实际执行节点逻辑
                # process_node 内部会调用 get_node_inputs，后者依赖上游节点的 processed_outputs
                self.process_node(current_node)
                state['status'] = 'done'
                processed_node_ids.add(current_id)
                processed_count += 1
                # 记录节点处理结束时间并计算用时
                node_end_time = time.time()
                node_processing_time = node_end_time - node_start_time
                node_times[current_node['title']] = node_processing_time
                # 通知下游节点输入已就绪
                for conn_info in output_connections.get(current_id, []):
                    downstream_id = conn_info['input_node_id']
                    input_port_idx = conn_info['input_port_idx']
                    if downstream_id in processing_state and processing_state[downstream_id]['status'] == 'pending':
                        ds_state = processing_state[downstream_id]
                        ds_state['inputs_received'].add(input_port_idx)
                        if ds_state['inputs_received'] == ds_state['inputs_needed']:
                            ds_state['status'] = 'ready'
                            if downstream_id not in processing_queue: # 避免重复添加
                                processing_queue.append(downstream_id)

            except Exception as e:
                print(f"Error processing node {current_node['title']}: {e}")
                import traceback
                traceback.print_exc()
                state['status'] = 'error'
                error_occurred = True
                # 错误传播？当前不处理，下游节点将无法获得输入

        end_time = time.time()
        processing_time = end_time - start_time
        # --- 4. 更新UI和状态 ---
        # 将本次运行处理的节点ID集合传递给预览部件
        if hasattr(self, 'preview_display_widget'):
            self.preview_display_widget.processed_in_last_run = processed_node_ids
            # 触发一次重绘，让 paintEvent 使用新的集合
            self.preview_display_widget.update()

        # 更新预览图像 (记录预览更新时间)
        preview_start_time = time.time()
        self.update_preview()

        # 强制刷新预览显示 - 确保即使在初次加载时也能显示
        if processed_count > 0:
            QTimer.singleShot(50, lambda: self.refresh_preview_display())

        # 优化的PreviewOnNode重绘逻辑 - 减少不必要的重建
        preview_nodes_count = 0
        nodes_to_update = []

        for node in self.nodes:
            # 只处理已处理过的节点
            if node['id'] not in processed_node_ids:
                continue

            # 检查节点是否支持预览（针对新的SupportedFeatures格式）
            has_preview_support = False
            if 'script_info' in node and 'supported_features' in node['script_info']:
                has_preview_support = node['script_info']['supported_features'].get('PreviewOnNode', False)

            if has_preview_support:
                preview_nodes_count += 1

                # 检查节点是否还没有widget或widget已被删除
                needs_widget_rebuild = not node.get('widget') or not node['widget'].isVisible()

                if needs_widget_rebuild:
                    # 需要完全重建widget
                    nodes_to_update.append(('rebuild', node))
                else:
                    # 只需要更新预览图像
                    nodes_to_update.append(('update_preview', node))

        # 批量处理需要更新的节点
        if nodes_to_update:
            rebuild_count = 0
            update_count = 0

            for update_type, node in nodes_to_update:
                if update_type == 'rebuild':
                    # 完全重建节点widget
                    self._rebuild_preview_node_widget(node)
                    rebuild_count += 1
                elif update_type == 'update_preview':
                    # 只更新预览图像部分
                    self._update_node_preview_image(node)
                    update_count += 1

            # 减少UI更新频率 - 只在最后统一更新
            if rebuild_count > 0:
                self.node_canvas_widget.update()

        preview_end_time = time.time()
        preview_time = preview_end_time - preview_start_time

        # 更新色彩空间和伽马指示器
        self.update_colorspace_gamma_indicators()

        # 注: 此处原来的自动保存代码已移除



    def _rebuild_preview_node_widget(self, node):
        """
        完全重建支持PreviewOnNode的节点widget

        参数:
            node: 需要重建的节点
        """
        # 保存位置和大小信息
        old_x, old_y = node['x'], node['y']
        old_width, old_height = node['width'], node['height']

        # 如果有旧widget，先移除
        old_widget = node.get('widget')
        if old_widget:
            old_widget.setParent(None)
            old_widget.deleteLater()

        # 重新绘制节点
        self.draw_node(node)

        # 恢复位置和大小
        node['x'], node['y'] = old_x, old_y
        node['width'], node['height'] = old_width, old_height
        if 'widget' in node and node['widget']:
            node['widget'].move(old_x, old_y)

    def _update_node_preview_image(self, node):
        """
        只更新节点的预览图像部分，不重建整个widget

        参数:
            node: 需要更新预览的节点
        """
        if not node.get('widget') or not node.get('processed_outputs'):
            return

        # 查找现有的预览标签
        preview_label = None
        widget = node['widget']

        # 遍历子控件寻找预览标签
        for child in widget.findChildren(QLabel):
            if child.objectName() == "previewLabel":
                preview_label = child
                break

        if not preview_label:
            # 如果没有找到预览标签，可能需要重建整个widget
            self._rebuild_preview_node_widget(node)
            return

        # 更新预览图像
        outputs = node['processed_outputs']
        image_data = None

        # 查找输出中的图像类型
        for output_type in ['img', 'f32bmp']:
            if output_type in outputs and outputs[output_type] is not None:
                image_data = outputs[output_type]
                break

        if image_data is not None:
            try:
                # 使用与draw_node中相同的逻辑生成预览图像
                pixmap = self._generate_preview_pixmap(image_data)
                if pixmap:
                    preview_label.setPixmap(pixmap)
            except Exception as e:
                print(f"更新节点 '{node['title']}' 预览图像时出错: {e}")

    def _generate_preview_pixmap(self, image_data):
        """
        生成预览用的QPixmap

        参数:
            image_data: 图像数据（numpy数组）

        返回:
            QPixmap: 生成的预览图像，如果失败返回None
        """
        import numpy as np
        from PIL import Image

        try:
            if not isinstance(image_data, np.ndarray):
                return None

            # 处理特殊形状的数据(如1x1x4的浮点数据)
            if image_data.ndim == 3 and image_data.shape[0] == 1 and image_data.shape[1] == 1:
                # 创建一个更大的图像以便显示（扩展为20x20像素）
                if image_data.shape[2] == 4:  # RGBA数据
                    pixel_value = image_data[0, 0, :]
                    # 创建20x20的相同颜色图像
                    expanded_data = np.zeros((20, 20, 4), dtype=np.float32)
                    for i in range(20):
                        for j in range(20):
                            expanded_data[i, j, :] = pixel_value
                    # 转换为0-255范围的uint8
                    image_data = (expanded_data * 255).astype(np.uint8)
                elif image_data.shape[2] == 3:  # RGB数据
                    pixel_value = image_data[0, 0, :]
                    expanded_data = np.zeros((20, 20, 3), dtype=np.float32)
                    for i in range(20):
                        for j in range(20):
                            expanded_data[i, j, :] = pixel_value
                    image_data = (expanded_data * 255).astype(np.uint8)

            # 确保浮点数据在0-1范围内并转换为uint8
            if image_data.dtype == np.float32 or image_data.dtype == np.float64:
                image_data = (np.clip(image_data, 0, 1) * 255).astype(np.uint8)

            # 将numpy数组转换为PIL图像
            if image_data.ndim == 2:  # 灰度图
                pil_image = Image.fromarray(image_data)
            elif image_data.ndim == 3 and image_data.shape[2] == 3:  # RGB
                pil_image = Image.fromarray(image_data)
            elif image_data.ndim == 3 and image_data.shape[2] == 4:  # RGBA
                pil_image = Image.fromarray(image_data)
            else:
                return None

            # 缩放图像以适应预览标签
            pil_image.thumbnail((80, 60), Image.LANCZOS)

            # 确保图像是RGB或RGBA模式
            if pil_image.mode not in ['RGB', 'RGBA', 'L']:
                pil_image = pil_image.convert('RGB')

            # 转换为QPixmap
            qimage = self.pil_to_qimage(pil_image)
            if qimage is not None:
                return QPixmap.fromImage(qimage)

        except Exception as e:
            print(f"生成预览图像时出错: {e}")

        return None

    def _get_node_cache_key(self, node):
        """
        为节点生成唯一的缓存键，考虑节点ID、输入节点、参数值

        参数:
            node: 要处理的节点

        返回:
            唯一标识节点及其处理状态的缓存键
        """
        # 基本键：节点ID和脚本路径
        key_parts = [
            f"id:{node.get('id', 'unknown')}",
            f"script:{node.get('script_path', 'unknown')}"
        ]

        # 添加参数信息 - 仅包含可能影响输出的参数
        if 'params' in node and isinstance(node['params'], dict):
            params_str = "|".join(f"{param}={info.get('value')}"
                                for param, info in sorted(node['params'].items())
                                if isinstance(info, dict))
            key_parts.append(f"params:{params_str}")

        # 添加输入节点信息 - 仅包含输入节点ID和输出端口索引，不再包含输入端口索引
        # 因为重要的是输入数据来源，而不是如何连接到当前节点
        input_connections = []
        for conn in self.connections:
            if conn['input_node'] == node:
                # 查找上游节点的输出结果的哈希值 - 更稳定的缓存键方式
                output_node = conn['output_node']
                output_port = conn['output_port']
                input_port = conn['input_port']

                # 更稳定的连接表示方式，仅关注输入数据的来源
                conn_repr = f"{output_node.get('id', 'unknown')}:{output_port}->{input_port}"
                input_connections.append(conn_repr)

        if input_connections:
            key_parts.append(f"inputs:{','.join(sorted(input_connections))}")

        # 合并所有部分生成最终缓存键
        cache_key = "|".join(key_parts)
        return cache_key
    def process_node(self, node):
        """处理单个节点并返回输出，正确处理Neo和Legacy脚本，支持性能模式自动缩放"""
        # 检查node是否有效
        if not isinstance(node, dict):
            print(f"警告: process_node接收到的'node'不是字典: {type(node)}")
            return {}

        # 如果节点已处理，直接返回结果
        if 'processed_outputs' in node:
            # 确保返回的是一个字典，即使之前存储的是None或其他类型
            outputs = node['processed_outputs']
            return outputs if isinstance(outputs, dict) else {}

        # 计算缓存键
        cache_key = self._get_node_cache_key(node)

        # 尝试从缓存中获取结果
        cached_result = self.node_cache.get(cache_key)
        if cached_result is not None:
            # 有缓存结果，记录缓存命中并直接使用
            node_title = node.get('title', '未知')
            node_id = node.get('id', '未知ID')
            node_type = node.get('script_info', {}).get('node_type', '未知类型')

            # 为了调试目的，只打印某些类型节点的缓存命中日志
            is_debug_node = node_type in ['decode', 'input', 'filter', 'transform']
            if is_debug_node:
                print(f"缓存命中：节点 '{node_title}' ({node_id}) - 类型: {node_type}")

            # 保存到节点缓存，避免再次计算
            node['processed_outputs'] = cached_result
            return cached_result

        # 初始化输出
        outputs = {}
        try:
            # 获取节点输入（包含元数据）
            inputs = self.get_node_inputs(node)

            # 提取元数据
            input_metadata = inputs.pop('_metadata', {})

            # 获取节点参数
            params = {}
            if 'params' in node and isinstance(node['params'], dict):
                params = {name: param_info.get('value') for name, param_info in node['params'].items() if isinstance(param_info, dict)}

            # 获取应用上下文(对NeoScript有用)
            context = self.get_application_context(node)

            # --- 性能模式预处理 ---
            # 检查是否启用了性能模式且节点支持性能模式
            is_perf_sensitive = False
            original_sizes = {}  # 存储原始尺寸信息

            # --- 性能模式预处理 ---
            # 检查是否启用了性能模式且节点支持性能模式
            is_perf_sensitive = False
            original_sizes = {}  # 存储原始尺寸信息

            if hasattr(self, 'performance_mode_enabled') and self.performance_mode_enabled and 'script_info' in node:
                print(f"节点 '{node.get('title', '未知')}' 支持性能模式: {node['script_info'].get('supported_features', {})}")
                supported_features = node['script_info'].get('supported_features', {})
                # 使用新的SupportedFeatures格式
                is_perf_sensitive = supported_features.get('PerfSensitive', False)

                if is_perf_sensitive:
                    print(f"性能模式: 对节点 '{node.get('title', '未知')}' 应用自动缩放优化")
                    # 获取预览区域尺寸作为目标缩放尺寸
                    target_size = None
                    if hasattr(self, 'preview_display_widget'):
                        preview_widget = self.preview_display_widget
                        preview_size = preview_widget.size()
                        target_size = (preview_size.width(), preview_size.height())

                    # 如果有合适的目标尺寸，对输入图像进行缩放
                    if target_size and all(size > 50 for size in target_size):  # 确保目标尺寸合理
                        import cv2
                        import numpy as np

                        # 第一步：查找所有图像输入和最大的图像尺寸
                        valid_inputs = {}  # 存储所有有效的图像输入
                        max_width = 0
                        max_height = 0

                        for input_key, input_data in inputs.items():
                            # 只处理numpy数组类型的图像输入
                            if isinstance(input_data, np.ndarray) and len(input_data.shape) >= 2:
                                # 保存原始尺寸和数据类型
                                original_sizes[input_key] = {
                                    'shape': input_data.shape,
                                    'dtype': input_data.dtype
                                }

                                # 记录有效的图像输入
                                valid_inputs[input_key] = input_data

                                # 更新最大尺寸
                                max_width = max(max_width, input_data.shape[1])
                                max_height = max(max_height, input_data.shape[0])

                                                    # 第二步：只有当开启性能模式且最大图像尺寸明显大于预览窗口时才应用缩放
                            # 添加检查避免低分辨率问题
                            is_preview_node = node['title'] == '预览节点'
                            is_independent_preview = node_id in getattr(self, 'node_preview_windows', {})
                            should_scale = False

                            # 是否应该进行缩放的条件
                            if not is_preview_node and not is_independent_preview:
                                # 普通节点在性能模式下可以缩放
                                should_scale = (max_width > target_size[0] * 1.2 or max_height > target_size[1] * 1.2)
                            else:
                                # 预览节点或独立预览窗口节点使用高分辨率
                                should_scale = False
                                print(f"跳过缩放以保持高分辨率: {'预览节点' if is_preview_node else '独立预览窗口节点'}")

                            if should_scale:
                                # 计算全局缩放比例（基于最大的那个图像）
                                global_scale_factor = min(
                                    target_size[0] / max_width,
                                    target_size[1] / max_height
                                )

                                # 设置最小缩放因子，确保不会过度缩小图像
                                min_scale_factor = 0.5  # 最小不低于原始分辨率的一半
                                global_scale_factor = max(global_scale_factor, min_scale_factor)

                                print(f"性能模式全局缩放比例: {global_scale_factor:.3f}，基于最大图像尺寸 {max_width}x{max_height}")

                                # 第三步：对所有图像应用相同的缩放比例以保持相对尺寸
                                for input_key, input_data in valid_inputs.items():
                                    # 计算新尺寸(应用全局缩放比例)
                                    new_width = max(int(input_data.shape[1] * global_scale_factor), 1)
                                    new_height = max(int(input_data.shape[0] * global_scale_factor), 1)

                                    # 根据图像类型选择合适的插值方法
                                    interp = cv2.INTER_LINEAR

                                    # 缩放图像
                                    if len(input_data.shape) == 2:  # 灰度图
                                        resized = cv2.resize(input_data, (new_width, new_height), interpolation=interp)
                                    elif len(input_data.shape) == 3 or len(input_data.shape) == 4:  # 彩色图或带通道
                                        resized = cv2.resize(input_data, (new_width, new_height), interpolation=interp)
                                    else:
                                        # 对于其他维度的数据，跳过处理
                                        continue

                                    # 确保缩放后的图像与原图像具有相同的数据类型
                                    resized = resized.astype(input_data.dtype)

                                    # 替换原输入
                                    inputs[input_key] = resized
                                    print(f"  - 输入'{input_key}'从{input_data.shape[:2]}缩放至{resized.shape[:2]}")
            # 调用节点的处理函数
            if node.get('module') and hasattr(node['module'], 'process'):
                script_type = node.get('script_type', 'legacy')
                node_title = node.get('title', '未知')
                process_func = node['module'].process

                # 根据脚本类型调用处理函数
                if script_type == 'neo':
                    # NeoScript: 可接收context参数
                    try:
                        import inspect
                        sig = inspect.signature(process_func)
                        if len(sig.parameters) == 3:
                            outputs = process_func(inputs, params, context)
                        elif len(sig.parameters) == 2:
                            print(f"警告: NeoScript '{node_title}'的process函数只有两个参数，未传递context")
                            outputs = process_func(inputs, params)
                        else:
                            print(f"错误: NeoScript '{node_title}'的process函数签名不正确")
                            outputs = {}
                    except Exception as call_e:
                        print(f"调用NeoScript '{node_title}'.process时出错: {call_e}")
                        import traceback
                        traceback.print_exc()
                        outputs = {}
                else:
                    # Legacy script: 只接收inputs和params
                    try:
                        outputs = process_func(inputs, params)
                    except Exception as call_e:
                        print(f"调用Legacy Script '{node_title}'.process时出错: {call_e}")
                        import traceback
                        traceback.print_exc()
                        outputs = {}

                # --- 处理伪类型输出 ---
                # 如果输出中包含伪类型对应的真实类型数据，添加伪类型标签副本
                for pseudo_type, real_type in self.pseudo_types.items():
                    if real_type in outputs and pseudo_type not in outputs:
                        # 创建对原始数据的引用，不复制数据
                        outputs[pseudo_type] = outputs[real_type]
                        print(f"为节点 '{node_title}' 添加伪类型输出: {pseudo_type} -> {real_type}")

                # --- 性能模式后处理：缩放输出图像回原始尺寸 ---
                if is_perf_sensitive and original_sizes and outputs:
                    import cv2
                    import numpy as np

                    # 处理所有图像类型的输出
                    for output_key, output_data in list(outputs.items()):  # 使用list复制字典项，避免在迭代中修改
                        # 对应的输入键名(通常输入输出的键名相同，如'f32bmp')
                        input_key = output_key

                        # 如果找不到对应的原始尺寸信息，尝试查找任意一个原始尺寸信息
                        if input_key not in original_sizes and original_sizes:
                            input_key = next(iter(original_sizes.keys()))

                        # 如果有原始尺寸信息且输出是numpy数组
                        if input_key in original_sizes and isinstance(output_data, np.ndarray) and len(output_data.shape) >= 2:
                            orig_info = original_sizes[input_key]
                            orig_shape = orig_info['shape']

                            # 检查是否需要恢复尺寸(高度或宽度不同)
                            if len(output_data.shape) >= 2 and len(orig_shape) >= 2:
                                if output_data.shape[0] != orig_shape[0] or output_data.shape[1] != orig_shape[1]:
                                    # 计算新尺寸(保持原始宽高比)
                                    new_size = (orig_shape[1], orig_shape[0])  # 注意cv2.resize需要(宽,高)

                                    # 选择合适的插值方法
                                    interp = cv2.INTER_LINEAR

                                    # 缩放图像
                                    if len(output_data.shape) == 2:  # 灰度图
                                        resized = cv2.resize(output_data, new_size, interpolation=interp)
                                    elif len(output_data.shape) == 3:  # 彩色图或带通道
                                        if len(orig_shape) == 3 and output_data.shape[2] != orig_shape[2]:
                                            # 通道数不匹配，需要特殊处理
                                            if output_data.shape[2] < orig_shape[2]:
                                                # 输出通道少于原始通道，需要添加额外通道
                                                resized = cv2.resize(output_data, new_size, interpolation=interp)
                                                if output_data.shape[2] == 1 and orig_shape[2] == 3:
                                                    # 灰度转RGB
                                                    resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
                                                # 其他情况可能需要特殊处理...
                                            else:
                                                # 输出通道多于原始通道，截取需要的通道
                                                resized = cv2.resize(output_data[:,:,:orig_shape[2]], new_size, interpolation=interp)
                                        else:
                                            # 通道数匹配或原始图像不是多通道的
                                            resized = cv2.resize(output_data, new_size, interpolation=interp)
                                    else:
                                        # 对于不支持的维度，跳过处理
                                        continue

                                    # 确保数据类型匹配
                                    if 'dtype' in orig_info:
                                        resized = resized.astype(orig_info['dtype'])

                                    # 替换输出
                                    outputs[output_key] = resized
                                    print(f"  - 输出'{output_key}'已恢复至原始尺寸{new_size[1]}x{new_size[0]}")

                                    # 如果有对应的伪类型，也更新伪类型输出
                                    for pseudo_type, real_type in self.pseudo_types.items():
                                        if real_type == output_key and pseudo_type in outputs:
                                            outputs[pseudo_type] = resized
                                            print(f"  - 伪类型输出'{pseudo_type}'也已更新")
            else:
                # 模块或process函数不存在
                print(f"节点{node.get('title', '未知')}没有有效的process处理函数或模块")
                outputs = {}

        except Exception as e:
            # 处理其他错误
            print(f"处理节点{node.get('title', '未知')}时发生意外错误: {str(e)}")
            import traceback
            traceback.print_exc()
            outputs = {}

        # 确保outputs是一个字典
        if not isinstance(outputs, dict):
            outputs = {}

        # 更新节点元数据
        if 'metadata' not in node:
            node['metadata'] = self.metadata_manager.create_metadata(
                node_id=node.get('id'),
                node_title=node.get('title', '未知'),
                script_path=node.get('script_path', '')
            )

        # 合并输入元数据到当前节点元数据
        if input_metadata:
            node['metadata'] = self.metadata_manager.merge_metadata(node['metadata'], input_metadata)

        # 添加当前节点到处理路径
        node['metadata'] = self.metadata_manager.add_node_to_path(
            node['metadata'],
            node.get('id'),
            node.get('title', '未知')
        )

        # 记录处理操作
        node['metadata'] = self.metadata_manager.add_processing_record(
            node['metadata'],
            'process_node',
            {
                'script_type': node.get('script_type', 'legacy'),
                'script_path': node.get('script_path', ''),
                'output_types': list(outputs.keys()) if outputs else []
            }
        )

        # 为每个输出添加元数据（如果脚本没有返回_metadata）
        enhanced_outputs = {}
        for output_key, output_value in outputs.items():
            if output_key == '_metadata':
                # 如果脚本返回了_metadata，跳过处理
                continue
            enhanced_outputs[output_key] = output_value

        # 如果脚本没有返回_metadata，为所有输出添加当前节点的元数据
        if '_metadata' not in outputs and enhanced_outputs:
            enhanced_outputs['_metadata'] = self.metadata_manager.copy_metadata(node['metadata'])
        elif '_metadata' in outputs:
            # 如果脚本返回了_metadata，合并到节点元数据中
            script_metadata = outputs['_metadata']
            if isinstance(script_metadata, dict):
                node['metadata'] = self.metadata_manager.merge_metadata(node['metadata'], script_metadata)
            enhanced_outputs['_metadata'] = self.metadata_manager.copy_metadata(node['metadata'])

        # 保存处理结果到节点
        node['processed_outputs'] = enhanced_outputs

        # 如果有支持自定义预览更新的函数，则触发它
        # 例如让节点自己处理预览窗口的更新，而不是由主程序统一更新
        node_id = node.get('id')
        if node_id is not None:
            # --- 检查是否有自定义预览更新函数 ---
            supported_features = node.get('script_info', {}).get('supported_features', {})
            custom_update_func_name = supported_features.get('PreviewUpdateFunction')

            if custom_update_func_name and node.get('module') and hasattr(node['module'], custom_update_func_name):
                # 调用节点的自定义预览更新函数
                try:
                    custom_update_func = getattr(node['module'], custom_update_func_name)
                    # 注意：传递 node 本身，脚本函数可以从中获取 outputs
                    # 使用 QTimer 以安全地从处理逻辑调用可能更新UI的脚本代码
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda n=node, ctx=context: custom_update_func(n, ctx))
                except Exception as e:
                    print(
                        f"Error calling custom preview update function '{custom_update_func_name}' for node {node_id}: {e}")
            elif node_id in self.node_preview_windows:
                # --- 更新标准预览窗口 ---
                dialog = self.node_preview_windows[node_id]
                if dialog and dialog.isVisible():
                    updated_img = None
                    if 'processed_outputs' in node and node['processed_outputs']:
                        updated_img = next(iter(node['processed_outputs'].values()), None)

                    # 使用 QTimer.singleShot 确保安全更新
                    from PySide6.QtCore import QTimer
                    # 需要捕获 dialog 和 updated_img 的当前值
                    QTimer.singleShot(0, lambda d=dialog, img=updated_img: d.update_image(img))

        return outputs

    def get_node_inputs(self, node):
        """获取节点的输入数据，支持灵活端口"""
        inputs = {}
        input_type_counts = {}  # 记录每种类型输入的数量

        # 初始化输入类型计数
        # 注意：这里要考虑灵活端口可能会有多个同类型端口
        # 使用port_widgets而不是script_info['inputs']，因为灵活端口可能增加了端口数量
        if 'port_widgets' in node and 'inputs' in node['port_widgets']:
            for port_idx, port_info in node['port_widgets']['inputs'].items():
                input_type = port_info['type']
                if input_type not in input_type_counts:
                    input_type_counts[input_type] = 0
        else:
            # 回退到原来的逻辑
            for input_type in node['script_info']['inputs']:
                input_type_counts[input_type] = 0

        # 首先按照输入端口索引排序连接，确保输入顺序一致
        input_connections = [conn for conn in self.connections if conn['input_node'] == node]
        input_connections.sort(key=lambda conn: conn['input_port'])

                        # 处理每个连接
        for conn in input_connections:
            # 获取输出节点数据
            output_node = conn['output_node']
            output_port = conn['output_port']
            input_port = conn['input_port']

            # 获取输入类型 - 使用端口部件信息
            try:
                if 'port_widgets' in node and 'inputs' in node['port_widgets'] and input_port in node['port_widgets']['inputs']:
                    input_type = node['port_widgets']['inputs'][input_port]['type']
                else:
                    # 如果找不到端口信息，回退到script_info
                    # 对于灵活端口节点，可能会有额外的端口
                    if 'flexible_ports' in node and 'inputs' in node['flexible_ports'] and node['flexible_ports']['inputs']:
                        # 如果是灵活端口节点，且输入端口超出了基本输入数量
                        if isinstance(input_port, int) and input_port >= len(node['script_info']['inputs']):
                            # 使用灵活端口类型
                            input_type = node['flexible_ports']['inputs'][0]  # 使用第一个灵活类型
                        elif isinstance(input_port, int) and input_port < len(node['script_info']['inputs']):
                            input_type = node['script_info']['inputs'][input_port]
                        else:
                            # 无法确定端口类型，跳过此连接
                            continue
                    elif isinstance(input_port, int) and input_port < len(node['script_info']['inputs']):
                        input_type = node['script_info']['inputs'][input_port]
                    else:
                        # 安静地跳过，不打印警告以避免刷屏
                        continue
            except Exception as e:
                print(f"获取节点 {node['title']} 的输入端口 {input_port} 类型时出错: {str(e)}")
                continue

            # 处理输出节点
            output_data = self.process_node(output_node)

            # 获取相应端口的输出数据
            if output_data:
                # 获取输出类型 - 同样使用端口部件信息
                try:
                    if 'port_widgets' in output_node and 'outputs' in output_node['port_widgets'] and output_port in output_node['port_widgets']['outputs']:
                        output_type = output_node['port_widgets']['outputs'][output_port]['type']
                    else:
                        # 回退到script_info
                        # 对于灵活端口节点，可能会有额外的端口
                        if 'flexible_ports' in output_node and 'outputs' in output_node['flexible_ports'] and output_node['flexible_ports']['outputs']:
                            # 如果是灵活端口节点，且输出端口超出了基本输出数量
                            if isinstance(output_port, int) and output_port >= len(output_node['script_info']['outputs']):
                                # 使用灵活端口类型
                                output_type = output_node['flexible_ports']['outputs'][0]  # 使用第一个灵活类型
                            elif isinstance(output_port, int) and output_port < len(output_node['script_info']['outputs']):
                                output_type = output_node['script_info']['outputs'][output_port]
                            else:
                                # 无法确定端口类型，跳过此连接
                                continue
                        elif isinstance(output_port, int) and output_port < len(output_node['script_info']['outputs']):
                            output_type = output_node['script_info']['outputs'][output_port]
                        else:
                            # 安静地跳过，不打印警告以避免刷屏
                            continue
                except Exception as e:
                    print(f"获取节点 {output_node['title']} 的输出端口 {output_port} 类型时出错: {str(e)}")
                    continue

                # 检查输出是否是伪类型
                real_output_type = output_type
                if output_type in self.pseudo_types:
                    real_output_type = self.pseudo_types[output_type]
                    print(f"伪类型转换: {output_type} -> {real_output_type}")

                # 如果是伪类型但数据中仍使用原始类型，则获取原始类型的数据
                if output_type in self.pseudo_types and real_output_type in output_data:
                    # 增加此类型输入的计数
                    input_type_counts[input_type] += 1
                    count = input_type_counts[input_type]

                    # 对于第一个该类型的输入，使用原始类型名
                    if count == 1:
                        # 确保节点得到正确类型的数据，但保持输入标签为伪类型
                        inputs[input_type] = output_data[real_output_type]
                    else:
                        # 对于额外的同类型输入，添加序号
                        inputs[f"{input_type}_{count - 1}"] = output_data[real_output_type]
                elif output_type in output_data:
                    # 正常类型处理
                    input_type_counts[input_type] += 1
                    count = input_type_counts[input_type]

                    # 对于第一个该类型的输入，使用原始类型名
                    if count == 1:
                        inputs[input_type] = output_data[output_type]
                    else:
                        # 对于额外的同类型输入，添加序号
                        inputs[f"{input_type}_{count - 1}"] = output_data[output_type]

        # 收集所有上游节点的元数据
        accumulated_metadata = {}
        for conn in input_connections:
            output_node = conn['output_node']
            if 'metadata' in output_node:
                upstream_metadata = self.metadata_manager.copy_metadata(output_node['metadata'])
                accumulated_metadata = self.metadata_manager.merge_metadata(
                    accumulated_metadata, upstream_metadata
                )

        # 将累积的元数据添加到输入中
        if accumulated_metadata:
            inputs['_metadata'] = accumulated_metadata

        return inputs

    def execute_sub_operation(self, node, operation):
        """执行节点子操作"""
        try:
            # 获取操作函数
            op_func = getattr(node['module'], f"sub_{operation}")

            # 获取节点参数
            params = {name: param_info['value'] for name, param_info in node['params'].items()}

            # 获取节点的输入数据
            input_data = self.get_node_inputs(node)

            # 创建上下文信息
            context = {
                'app': self,  # 传递应用实例
                'work_folder': self.work_folder,
                'current_image_path': self.current_image_path if hasattr(self, 'current_image_path') else None,
                'temp_folder': self.temp_folder,
                'scripts_folder': self.scripts_folder,
                'node_id': node['id'],
                'node_title': node['title']
            }

            # 执行操作，传递参数、输入数据和上下文
            result = op_func(params, input_data, context)

            # 处理结果
            if result and isinstance(result, dict) and 'success' in result:
                if result['success']:
                    # 显示成功消息
                    if 'message' in result:
                        QMessageBox.information(self, "操作成功", result['message'])

                    # 判断是否需要全部重新处理
                    if 'affects_all_nodes' in result and result['affects_all_nodes']:
                        print("子操作影响所有节点，执行完整重新计算")
                        self.process_node_graph()
                    else:
                        # 默认只处理当前节点及其下游节点
                        print(f"子操作只影响节点 '{node['title']}' 及其下游节点")
                        self.process_node_graph(changed_nodes=[node])
                else:
                    # 显示错误消息
                    if 'error' in result:
                        QMessageBox.critical(self, "操作失败", result['error'])

        except Exception as e:
            QMessageBox.critical(self, "操作错误", f"执行操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_preview(self, force_refresh=False):
        """
        更新预览图像

        参数:
            force_refresh (bool): 如果为True，则强制重新处理所有节点
        """
        # 如果需要强制刷新
        if force_refresh:
            try:
                # 设置标志
                self._force_reprocess_all = True

                # 重新处理整个节点图
                self.process_node_graph(suppress_auto_save=True)  # 抑制自动保存，避免频繁IO操作

                # 查找预览节点
                preview_node = None
                for node in self.nodes:
                    if node['title'] == '预览节点':
                        preview_node = node
                        break

                # 如果找到预览节点，确保更新显示
                if preview_node:
                    # 先清空处理缓存
                    if 'processed_outputs' in preview_node:
                        del preview_node['processed_outputs']
                    # 处理节点
                    self.process_node(preview_node)
                    # 更新预览显示
                    self.update_preview_from_node(preview_node)
                    # 强制UI更新
                    QApplication.processEvents()

                return  # 已完成所有处理，直接返回
            finally:
                # 清除标志，无论处理成功还是失败
                self._force_reprocess_all = False

        # 正常更新流程（非强制刷新）
        # 查找预览节点
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        # 确保预览节点和所有上游节点都已被处理
        if preview_node:
            # 检查是否有未处理的上游节点
            self._ensure_preview_dependencies_processed(preview_node)
            # 更新预览显示
            self.update_preview_from_node(preview_node)
            # 强制更新UI
            QApplication.processEvents()

    def _ensure_preview_dependencies_processed(self, preview_node):
        """确保预览节点的所有上游依赖都被处理"""
        nodes_to_process = []
        # 使用深度优先搜索找出所有上游节点
        visited = set()
        stack = [preview_node]

        while stack:
            current = stack.pop()
            if current['id'] in visited:
                continue

            visited.add(current['id'])

            # 如果节点未处理，添加到需要处理的列表
            if 'processed_outputs' not in current:
                nodes_to_process.append(current)

            # 查找所有输入连接
            for conn in self.connections:
                if conn['input_node'] == current:
                    stack.append(conn['output_node'])

        # 如果有需要处理的节点，先处理这些节点
        if nodes_to_process:
            print(f"预览需要处理 {len(nodes_to_process)} 个上游节点")
            # 反转列表，确保先处理最上游的节点
            nodes_to_process.reverse()
            for node in nodes_to_process:
                try:
                    self.process_node(node)
                except Exception as e:
                    print(f"处理上游节点 {node['title']} 时出错: {e}")
                    import traceback
                    traceback.print_exc()

    def update_preview_from_node(self, node):
        """从预览节点更新预览图像"""
        # 如果节点未处理，先处理
        if 'processed_outputs' not in node:
            # 可能需要考虑：如果 process_node 出错怎么办？
            try:
                self.process_node(node)
            except Exception as e:
                print(f"Error processing preview node in update_preview_from_node: {e}")
                # 可以考虑在此处清除预览或显示错误信息
                if hasattr(self, 'preview_display_widget'):
                    self.preview_display_widget.set_image(None) # 清除图像
                return # 提前返回

        # 获取输出图像
        img = None # 初始化 img
        if 'processed_outputs' in node and node['processed_outputs']: # 检查 processed_outputs 是否存在且非空
            if 'f32bmp' in node['processed_outputs']:
                img = node['processed_outputs']['f32bmp']
            elif 'tif16' in node['processed_outputs']:
                img = node['processed_outputs']['tif16']
            # 添加一个检查，如果 img 仍然是 None，则退出
            if img is None:
                 print("Warning: Preview node processed but no compatible output found ('f32bmp' or 'tif16').")
                 # 清除预览?
                 if hasattr(self, 'preview_display_widget'):
                    self.preview_display_widget.set_image(None) # 清除图像
                 return
        else:
             print("Warning: Preview node has no 'processed_outputs' after processing.")
             # 清除预览?
             if hasattr(self, 'preview_display_widget'):
                 self.preview_display_widget.set_image(None) # 清除图像
             return # 如果没有输出或处理失败，直接返回

        # 转换图像用于显示 (保持不变)
        if img is not None:
            # ... (图像转换逻辑保持不变) ...
            if img.dtype == np.float32:
                img_display = (img * 255).clip(0, 255).astype(np.uint8)
            elif img.dtype == np.uint16:
                img_display = (img / 256).astype(np.uint8)
            else:
                img_display = img

            if len(img_display.shape) == 3:
                if img_display.shape[2] == 3:
                    img_display = cv2.cvtColor(img_display, cv2.COLOR_RGB2BGR)
                elif img_display.shape[2] == 4:
                    img_display = cv2.cvtColor(img_display, cv2.COLOR_RGBA2BGRA)

            # 获取原始尺寸
            orig_height, orig_width = img_display.shape[:2]

            # --- 将缩放逻辑移交给 PreviewDisplayWidget ---
            # 1. 将原始图像数据转换为 QImage (不进行缩放) - 避免不必要的深拷贝
            qimage = None
            try:
                if len(img_display.shape) == 3:
                    if img_display.shape[2] == 4:  # RGBA图像
                        bytesPerLine = 4 * img_display.shape[1]
                        qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_ARGB32)
                    else:  # RGB图像
                        bytesPerLine = 3 * img_display.shape[1]
                        qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_BGR888)
                else:  # 灰度图像
                    bytesPerLine = img_display.shape[1]
                    qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_Grayscale8)
            except Exception as e:
                print(f"创建QImage时出错: {e}")
                import traceback
                traceback.print_exc()

            # 2. 将原始 QImage 传递给 PreviewDisplayWidget
            if hasattr(self, 'preview_display_widget') and qimage and not qimage.isNull():
                try:
                    # 注意：这里传递的是未缩放的原始 QImage
                    pixmap = QPixmap.fromImage(qimage)
                    if not pixmap.isNull():
                        self.preview_display_widget.set_image(pixmap)
                        # 强制更新界面
                        self.preview_display_widget.update()
                        # 确保预览区滚动到可见位置
                        if hasattr(self, 'preview_scroll'):
                            self.preview_scroll.ensureWidgetVisible(self.preview_display_widget)
                except Exception as e:
                    print(f"设置预览图像时出错: {e}")
                    import traceback
                    traceback.print_exc()

                # 可能需要触发 PreviewDisplayWidget 的更新来应用当前的缩放/平移
                # self.preview_display_widget.update() # 或者 set_image 内部会处理

            # --- 更新UI标签 ---
            # 更新缩放信息 (可能需要从 preview_display_widget 获取 zoom level)
            if hasattr(self, 'zoom_info') and hasattr(self, 'preview_display_widget'):
                 current_zoom = self.preview_display_widget.zoom_level # 假设 widget 有 zoom_level 属性
                 zoom_percent = int(current_zoom * 100)
                 self.zoom_info.setText(f"缩放: {zoom_percent}%")

            # 更新图像尺寸标签 (使用原始尺寸)
            if hasattr(self, 'image_size_label'):
                 self.image_size_label.setText(f"尺寸: {orig_width} x {orig_height}")

            # 保存当前原始 NumPy 图像供像素信息使用
            self.current_image = img
    def refresh_preview_display(self):
        """强制刷新预览显示，确保预览图像可见"""
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        if preview_node and 'processed_outputs' in preview_node:
            # 重新更新预览，确保显示图像
            self.update_preview_from_node(preview_node)

            # 如果预览组件存在但没有显示图像，强制刷新
            if hasattr(self, 'preview_display_widget'):
                # 获取当前显示的图像
                current_image = self.preview_display_widget.get_image()
                if current_image is None or current_image.isNull():
                    print("检测到预览图像为空，强制刷新")
                    self.update_preview_from_node(preview_node)

                # 强制刷新界面
                self.preview_display_widget.update()
                if hasattr(self, 'preview_scroll'):
                    self.preview_scroll.update()

                # 处理事件队列
                QApplication.processEvents()

    def update_preview_with_zoom(self):
        """根据缩放级别更新预览图像"""
        # 查找预览节点
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        if not preview_node:
            return

        # 如果节点未处理，先处理
        if 'processed_outputs' not in preview_node:
            self.process_node(preview_node)

        # 获取输出图像
        if 'processed_outputs' in preview_node:
            img = None
            if 'f32bmp' in preview_node['processed_outputs']:
                img = preview_node['processed_outputs']['f32bmp']
            elif 'tif16' in preview_node['processed_outputs']:
                img = preview_node['processed_outputs']['tif16']
            else:
                return

            # 转换图像用于显示
            if img is not None:
                # 根据图像类型进行适当的转换
                if img.dtype == np.float32:
                    # 将32位浮点图像转换为8位用于显示
                    img_display = (img * 255).clip(0, 255).astype(np.uint8)
                elif img.dtype == np.uint16:
                    # 将16位图像转换为8位用于显示
                    img_display = (img / 256).astype(np.uint8)
                else:
                    img_display = img

                # 确保图像是BGR格式（Qt期望的格式）
                if len(img_display.shape) == 3:
                    if img_display.shape[2] == 3:
                        # 从RGB转为BGR
                        img_display = cv2.cvtColor(img_display, cv2.COLOR_RGB2BGR)
                    elif img_display.shape[2] == 4:
                        # 从RGBA转为BGRA
                        img_display = cv2.cvtColor(img_display, cv2.COLOR_RGBA2BGRA)

                # 获取原始尺寸
                orig_height, orig_width = img_display.shape[:2]

                # 应用缩放计算新尺寸
                new_width = int(orig_width * self.zoom_level)
                new_height = int(orig_height * self.zoom_level)

                # 创建QImage（基于原始图像）- 避免不必要的复制，在创建QPixmap时会自动复制
                if len(img_display.shape) == 3:
                    if img_display.shape[2] == 4:  # RGBA图像
                        bytesPerLine = 4 * img_display.shape[1]
                        qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_ARGB32)
                    else:  # RGB图像
                        bytesPerLine = 3 * img_display.shape[1]
                        qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_BGR888)
                else:  # 灰度图像
                    bytesPerLine = img_display.shape[1]
                    qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_Grayscale8)

                # 使用Qt的渲染提示以提高显示质量
                qimage = qimage.convertToFormat(QImage.Format_ARGB32_Premultiplied)

                # 创建高质量缩放的QImage
                scaled_qimage = qimage.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.FastTransformation)

                # 创建像素图
                pixmap = QPixmap.fromImage(scaled_qimage)

                # --- 移除旧的 QToolButton 逻辑 ---
                # if not hasattr(self, 'preview_tool_button'):
                #     ...
                # self.preview_tool_button.setIcon(icon)
                # ...
                # self.preview_tool_button.show()

                # --- 使用新的 PreviewDisplayWidget ---
                if hasattr(self, 'preview_display_widget'):
                    self.preview_display_widget.set_image(pixmap)
                else:
                    print("错误: preview_display_widget 未初始化！")

                # 保存预览图像引用 (现在由 PreviewDisplayWidget 内部管理，但保留可能有用)
                self.preview_image = pixmap # 可以考虑移除这个，直接从 widget 获取

                # 更新缩放信息
                if hasattr(self, 'zoom_info'):
                    zoom_percent = int(self.zoom_level * 100)
                    self.zoom_info.setText(f"缩放: {zoom_percent}%")

                # 更新图像尺寸标签
                if hasattr(self, 'image_size_label'):
                    self.image_size_label.setText(f"尺寸: {orig_width} x {orig_height}")

                # 保存当前图像供像素信息使用
                self.current_image = img
            """根据缩放级别更新预览图像"""
            # 查找预览节点
            preview_node = None
            for node in self.nodes:
                if node['title'] == '预览节点':
                    preview_node = node
                    break

            if not preview_node:
                return

            # 如果节点未处理，先处理
            if 'processed_outputs' not in preview_node:
                self.process_node(preview_node)

            # 获取输出图像
            if 'processed_outputs' in preview_node:
                img = None
                if 'f32bmp' in preview_node['processed_outputs']:
                    img = preview_node['processed_outputs']['f32bmp']
                elif 'tif16' in preview_node['processed_outputs']:
                    img = preview_node['processed_outputs']['tif16']
                else:
                    return

                # 转换图像用于显示
                if img is not None:
                    # 根据图像类型进行适当的转换
                    if img.dtype == np.float32:
                        # 将32位浮点图像转换为8位用于显示
                        img_display = (img * 255).clip(0, 255).astype(np.uint8)
                    elif img.dtype == np.uint16:
                        # 将16位图像转换为8位用于显示
                        img_display = (img / 256).astype(np.uint8)
                    else:
                        img_display = img

                    # 确保图像是BGR格式（Qt期望的格式）
                    if len(img_display.shape) == 3:
                        if img_display.shape[2] == 3:
                            # 从RGB转为BGR
                            img_display = cv2.cvtColor(img_display, cv2.COLOR_RGB2BGR)
                        elif img_display.shape[2] == 4:
                            # 从RGBA转为BGRA
                            img_display = cv2.cvtColor(img_display, cv2.COLOR_RGBA2BGRA)

                    # 获取原始尺寸
                    orig_height, orig_width = img_display.shape[:2]

                    # 应用缩放计算新尺寸
                    new_width = int(orig_width * self.zoom_level)
                    new_height = int(orig_height * self.zoom_level)

                    # 创建QImage（基于原始图像）
                    if len(img_display.shape) == 3:
                        if img_display.shape[2] == 4:  # RGBA图像
                            bytesPerLine = 4 * img_display.shape[1]
                            qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_ARGB32).copy()
                        else:  # RGB图像
                            bytesPerLine = 3 * img_display.shape[1]
                            qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_BGR888).copy()
                    else:  # 灰度图像
                        bytesPerLine = img_display.shape[1]
                        qimage = QImage(img_display.data, img_display.shape[1], img_display.shape[0], bytesPerLine, QImage.Format_Grayscale8).copy()

                    # 使用Qt的渲染提示以提高显示质量
                    qimage = qimage.convertToFormat(QImage.Format_ARGB32_Premultiplied)

                    # 创建高质量缩放的QImage
                    scaled_qimage = qimage.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.FastTransformation)

                    # 创建像素图
                    pixmap = QPixmap.fromImage(scaled_qimage)

                    # --- 移除旧的 QToolButton 逻辑 ---
                    # if not hasattr(self, 'preview_tool_button'):
                    #     ...
                    # self.preview_tool_button.setIcon(icon)
                    # ...
                    # self.preview_tool_button.show()

                    # --- 使用新的 PreviewDisplayWidget ---
                    if hasattr(self, 'preview_display_widget'):
                        self.preview_display_widget.set_image(pixmap)
                    else:
                        print("错误: preview_display_widget 未初始化！")

                    # 保存预览图像引用 (现在由 PreviewDisplayWidget 内部管理，但保留可能有用)
                    self.preview_image = pixmap # 可以考虑移除这个，直接从 widget 获取

                    # 更新缩放信息
                    if hasattr(self, 'zoom_info'):
                        zoom_percent = int(self.zoom_level * 100)
                        self.zoom_info.setText(f"缩放: {zoom_percent}%")

                    # 更新图像尺寸标签
                    if hasattr(self, 'image_size_label'):
                        self.image_size_label.setText(f"尺寸: {orig_width} x {orig_height}")

                    # 保存当前图像供像素信息使用
                    self.current_image = img

    def copy_image_to_clipboard(self):
        """复制当前预览图像到剪贴板"""
        if hasattr(self, 'preview_image') and self.preview_image:
            try:
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setPixmap(self.preview_image)
                QMessageBox.information(self, "复制成功", "图像已复制到剪贴板")
            except Exception as e:
                QMessageBox.critical(self, "复制错误", f"复制图像失败: {str(e)}")
        else:
            QMessageBox.information(self, "提示", "没有可复制的图像")

    def export_current_view(self):
        """导出当前预览视图"""
        # 检查是否有预览节点，确保节点的依赖关系已处理
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        if preview_node:
            # 确保预览节点和其所有上游节点都已处理
            self._ensure_preview_dependencies_processed(preview_node)

        if hasattr(self, 'preview_image') and self.preview_image:
            try:
                # 获取保存路径
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "导出当前视图",
                    self.work_folder,
                    "JPEG文件 (*.jpg);;PNG文件 (*.png);;TIFF文件 (*.tif);;所有文件 (*.*)"
                )

                if not file_path:
                    return

                # 确保文件有正确的扩展名
                if not any(file_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']):
                    file_path += '.jpg'  # 默认添加jpg扩展名

                # 保存图像
                self.preview_image.save(file_path)
                QMessageBox.information(self, "导出成功", f"当前视图已导出到:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "导出错误", f"导出视图失败: {str(e)}")
        else:
            QMessageBox.information(self, "提示", "没有可导出的图像")

    # 注: 原auto_save_node_graph方法已移除
    def create_film_preview(self):
        print(f"CREATE_FILM_PREVIEW (loc 4157 or similar) CALLED! Current self.film_preview_list ID (before creation): {id(getattr(self, 'film_preview_list', None))}")
        """创建底部胶片预览区，并使用 QListWidget 支持换行 (Aero 风格)"""
        self.film_preview_list = QListWidget()
        self.film_preview_list.setViewMode(QListView.IconMode)
        self.film_preview_list.setFlow(QListView.LeftToRight)
        self.film_preview_list.setWrapping(True)
        self.film_preview_list.setResizeMode(QListView.Adjust)
        self.film_preview_list.setMovement(QListView.Static)
        self.film_preview_list.setSpacing(12) # 增加间距
        self.film_preview_list.setIconSize(QSize(55, 40)) # 增大图标尺寸
        self.film_preview_list.setUniformItemSizes(True)
        # 应用 Aero 风格样式表
        self.film_preview_list.setObjectName("film_preview_list")
        self.film_preview_list.itemDoubleClicked.connect(self.on_film_item_double_clicked)

    def create_paned_areas(self):
        """创建可调整的工作区面板，将预览和胶片区垂直排列"""
        # 创建主工作区布局
        work_layout = QVBoxLayout(self.work_area)
        work_layout.setContentsMargins(0, 0, 0, 0)

        # 创建主水平分割器，左侧是预览+胶片，右侧是节点图+设置
        self.main_splitter = QSplitter(Qt.Horizontal)
        work_layout.addWidget(self.main_splitter)

        # --- 创建左侧的垂直分割器，用于放置预览区和胶片预览区 ---
        self.left_splitter = QSplitter(Qt.Vertical)

        # 创建预览区域 Frame (实际内容由 create_preview_area 填充)
        self.preview_area = QFrame()
        self.preview_area.setObjectName("preview_area_frame") # 给 Frame 一个名字
        # 设置一个最小高度，防止被过度压缩
        self.preview_area.setMinimumHeight(200)

        # --- 注意：create_film_preview 需要在添加到 Splitter 之前调用 ---
        # 它会创建 self.film_preview_list
        self.create_film_preview()

        # 将预览区 Frame 和胶片预览 QListWidget 添加到左侧垂直分割器
        self.left_splitter.addWidget(self.preview_area)
        self.left_splitter.addWidget(self.film_preview_list) # 添加 QListWidget

        # 设置拉伸因子和初始大小 (可以根据需要调整比例)
        self.left_splitter.setStretchFactor(0, 6) # 预览区域占大部分
        self.left_splitter.setStretchFactor(1, 1) # 胶片区域占小部分
        # 你也可以设置初始大小比例
        # total_height = self.left_splitter.size().height() if self.left_splitter.size().height() > 0 else 600
        # self.left_splitter.setSizes([int(total_height * 0.8), int(total_height * 0.2)])
        # --------------------------------------------------------

        # 创建右侧面板的容器 Widget 和布局
        self.right_pane_widget = QWidget()
        right_pane_layout = QVBoxLayout(self.right_pane_widget)
        right_pane_layout.setContentsMargins(0, 0, 0, 0)

        # 将左侧垂直分割器和右侧面板添加到主水平分割器
        self.main_splitter.addWidget(self.left_splitter) # 添加左侧垂直分割器
        self.main_splitter.addWidget(self.right_pane_widget)
        # 设置主分割器的拉伸因子或初始大小
        self.main_splitter.setStretchFactor(0, 1) # 左侧比例
        self.main_splitter.setStretchFactor(1, 1) # 右侧比例
        # total_width = self.main_splitter.size().width() if self.main_splitter.size().width() > 0 else 1000
        # self.main_splitter.setSizes([int(total_width * 0.5), int(total_width * 0.5)])

        # 创建右侧面板的垂直分割器
        self.right_splitter = QSplitter(Qt.Vertical)
        right_pane_layout.addWidget(self.right_splitter)

        # 创建节点图区域和节点设置区域 Frame (实际内容由相应函数填充)
        self.node_graph_area = QFrame()
        self.node_graph_area.setObjectName("node_graph_area_frame")
        self.node_graph_area.setMinimumHeight(200) # 设置最小高度
        self.node_settings_area = QFrame()
        self.node_settings_area.setObjectName("node_settings_area_frame")
        self.node_settings_area.setMinimumHeight(100) # 设置最小高度

        # 将节点图区域和设置区域添加到右侧垂直分割器
        self.right_splitter.addWidget(self.node_graph_area)
        self.right_splitter.addWidget(self.node_settings_area)
        self.right_splitter.setStretchFactor(0, 3) # 节点图占 75%
        self.right_splitter.setStretchFactor(1, 1) # 设置面板占 25%
        # total_height_right = self.right_splitter.size().height() if self.right_splitter.size().height() > 0 else 600
        # self.right_splitter.setSizes([int(total_height_right * 0.7), int(total_height_right * 0.3)])

        # --- 创建各个区域的内容 ---
        # 注意调用顺序：film_preview 已经被调用
        self.create_preview_area() # 初始化 preview_area 的内容
        self.create_node_graph_area() # 初始化 node_graph_area 的内容
        self.create_node_settings_area() # 初始化 node_settings_area 的内容
        self.update_film_preview()
        # 设置滚动区域和视口的 objectName (如果存在于 preview_area 中)
        if hasattr(self, 'preview_scroll'):
            self.preview_scroll.setObjectName("preview_scroll")
            if self.preview_scroll.widget():
                self.preview_scroll.widget().setObjectName("preview_scroll_viewport_widget")
        print(f"CREATE_PANED_AREAS END: self.film_preview_list ID={id(self.film_preview_list)}, Parent={self.film_preview_list.parentWidget()}, Visible={self.film_preview_list.isVisible()}")
        if self.film_preview_list.parentWidget():
            print(f"  Parent is: {self.film_preview_list.parentWidget().objectName()} of type {type(self.film_preview_list.parentWidget())}")
        # 像素信息和右键菜单由 PreviewDisplayWidget 内部处理


    def update_film_preview(self):
        """更新胶片预览，使用 QListWidget 显示节点图缩略图"""
        print(f"FILM_PREVIEW STATE (Start/End): ID={id(self.film_preview_list)}, Parent={self.film_preview_list.parentWidget()}, Visible={self.film_preview_list.isVisible()}, Size={self.film_preview_list.size()}, Geometry={self.film_preview_list.geometry()}, count={self.film_preview_list.count()}")
        print(f"  Splitter (Parent) Sizes: {self.film_preview_list.parentWidget().sizes() if isinstance(self.film_preview_list.parentWidget(), QSplitter) else 'Not a Splitter or No Parent'}")
        print(f"  IsUpdatesEnabled: {self.film_preview_list.updatesEnabled()}")
        # 如果可以，甚至可以获取它的 viewport 的一些状态
        vp = self.film_preview_list.viewport()
        print(f"  Viewport: ID={id(vp)}, Parent={vp.parentWidget()}, Visible={vp.isVisible()}, Size={vp.size()}, Geometry={vp.geometry()}")
            # 检查 film_preview_list 是否已创建
        if not hasattr(self, 'film_preview_list') or not self.film_preview_list:
            print("警告: film_preview_list 尚未创建，无法更新胶片预览。")
            return

        # --- 清理旧内容 ---
        self.film_preview_list.clear()

        # 确保节点图文件夹存在
        if not hasattr(self, 'nodegraphs_folder') or not self.nodegraphs_folder:
            print("节点图文件夹未设置")
            # 可以添加一个提示标签到 ListWidget
            placeholder_item = QListWidgetItem("未找到节点图文件夹")
            placeholder_item.setFlags(Qt.NoItemFlags) # 不可选
            self.film_preview_list.addItem(placeholder_item)
            return

        if not os.path.exists(self.nodegraphs_folder):
            print(f"节点图文件夹不存在: {self.nodegraphs_folder}")
            # 可以添加一个提示标签到 ListWidget
            placeholder_item = QListWidgetItem("未找到节点图文件夹")
            placeholder_item.setFlags(Qt.NoItemFlags) # 不可选
            self.film_preview_list.addItem(placeholder_item)
            return

        # 获取节点图文件夹中的节点图文件
        nodegraph_files = []
        try:
            for file in os.listdir(self.nodegraphs_folder):
                file_path = os.path.join(self.nodegraphs_folder, file)
                if os.path.isfile(file_path) and file.lower().endswith('.json'):
                    nodegraph_files.append(file)
        except FileNotFoundError:
            print(f"节点图文件夹不存在: {self.nodegraphs_folder}")
            # 添加提示标签
            placeholder_item = QListWidgetItem("未找到节点图文件夹")
            placeholder_item.setFlags(Qt.NoItemFlags)
            self.film_preview_list.addItem(placeholder_item)
            return
        except Exception as e:
            print(f"扫描节点图文件夹时出错: {e}")
            return

        if not nodegraph_files:
            # 添加提示标签
            placeholder_item = QListWidgetItem("无节点图")
            placeholder_item.setFlags(Qt.NoItemFlags)
            self.film_preview_list.addItem(placeholder_item)
            return

        print(f"FILM_PREVIEW: 找到 {len(nodegraph_files)} 个节点图文件")
        thumbnail_size = self.film_preview_list.iconSize()

        processed_count = 0
        for nodegraph_file in nodegraph_files:
            # 跳过temp文件夹和thumbnails文件夹中的文件，以及包含"_auto_"的自动保存文件
            if 'temp/' in nodegraph_file or 'thumbnails/' in nodegraph_file or '_auto_' in nodegraph_file:
                continue

            nodegraph_path = os.path.join(self.nodegraphs_folder, nodegraph_file)
            nodegraph_name = os.path.splitext(nodegraph_file)[0]

            # 尝试加载缩略图
            thumbnail_path = os.path.join(self.thumbnails_folder, f"{nodegraph_name}.png")

            pixmap = None
            if os.path.exists(thumbnail_path):
                # 如果缩略图存在，直接加载
                pixmap = QPixmap(thumbnail_path)
            else:
                # 如果缩略图不存在，使用默认缩略图
                pixmap = self.default_thumbnail

            # 创建列表项
            if pixmap and not pixmap.isNull():
                # 读取节点图关联的图像路径
                image_path = None
                try:
                    import json
                    with open(nodegraph_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        image_path = data.get('current_image_path')
                except Exception as e:
                    print(f"读取节点图 {nodegraph_file} 的图像路径时出错: {e}")

                # 创建显示名称 (直接使用节点图名称)
                display_name = nodegraph_name

                item = QListWidgetItem(QIcon(pixmap), display_name)
                item.setData(Qt.UserRole, nodegraph_path)  # 储存节点图路径而不是图像路径
                item.setToolTip(f"节点图: {nodegraph_name}")
                item.setTextAlignment(Qt.AlignBottom | Qt.AlignHCenter)
                item.setSizeHint(QSize(thumbnail_size.width() + 10, thumbnail_size.height() + 30))

                self.film_preview_list.addItem(item)
                processed_count += 1

        # 更新界面
        self.film_preview_list.repaint()
        QApplication.processEvents()
    def on_film_item_double_clicked(self, item: QListWidgetItem): # 指定item类型，方便代码提示
        """当胶片预览中的项目被双击时调用"""
        if item:
            nodegraph_path = item.data(Qt.UserRole) # 从 UserRole 获取节点图完整路径
            if nodegraph_path and os.path.exists(nodegraph_path):
                print(f"FILM_PREVIEW: Item double-clicked, nodegraph_path: {nodegraph_path}")

                # 【DEBUG】: 打印当前节点图状态（切换前）
                print("\n========== 胶片项目双击 - 切换前节点图状态 ==========")
                print(f"当前节点图路径: {self.current_nodegraph_path}")
                print(f"节点图是否为新创建: {self.is_new_nodegraph if hasattr(self, 'is_new_nodegraph') else '未定义'}")
                print(f"节点图是否被修改: {self.nodegraph_modified if hasattr(self, 'nodegraph_modified') else '未定义'}")
                print(f"节点数量: {len(self.nodes) if hasattr(self, 'nodes') else 0}")
                print(f"窗口标题: {self.windowTitle()}")
                print("===================================================\n")

                # 自动保存当前节点图 (如果有且被修改)
                if hasattr(self, 'current_nodegraph_path') and self.current_nodegraph_path and self.nodes and hasattr(self, 'nodegraph_modified') and self.nodegraph_modified:
                    try:
                        print(f"当前节点图已修改，准备自动保存: {self.current_nodegraph_path}")
                        # 自动保存当前节点图，不显示消息框
                        success = self.save_node_graph_to_file(self.current_nodegraph_path)
                        if success:
                            print(f"自动保存当前节点图成功: {self.current_nodegraph_path}")
                            # 重置修改状态，但保持其他状态不变
                            self.set_nodegraph_state(modified=False)
                        else:
                            print(f"自动保存当前节点图失败")
                    except Exception as e:
                        print(f"保存当前节点图时出错: {e}")
                else:
                    print(f"当前节点图无需保存: 路径={self.current_nodegraph_path}, 节点数={len(self.nodes) if hasattr(self, 'nodes') else 0}, 修改状态={self.nodegraph_modified if hasattr(self, 'nodegraph_modified') else None}")

                # 胶片预览中的节点图应该都在工作文件夹内，直接加载
                # 因为胶片预览只会显示工作文件夹中的节点图
                try:
                    # 直接加载所选的节点图
                    if self.load_node_graph_from_file(nodegraph_path):
                        # 注意：不需要再次设置状态，load_node_graph_from_file 已经正确设置

                        # 处理节点图
                        self.process_node_graph(suppress_auto_save=True)  # 不要在这里触发自动保存

                        # 更新界面
                        self.update_preview_with_zoom()
                        self.zoom_fit()

                        # 更新状态栏
                        self.task_label.setText(f"已打开节点图: {os.path.basename(nodegraph_path)}")

                        # 【DEBUG】: 打印当前节点图状态（切换后）
                        print("\n========== 胶片项目双击 - 切换后节点图状态 ==========")
                        print(f"当前节点图路径: {self.current_nodegraph_path}")
                        print(f"节点图是否为新创建: {self.is_new_nodegraph}")
                        print(f"节点图是否被修改: {self.nodegraph_modified}")
                        print(f"节点数量: {len(self.nodes)}")
                        print(f"窗口标题: {self.windowTitle()}")
                        print("===================================================\n")
                    else:
                        QMessageBox.critical(self, "加载错误", "加载节点图时出错")
                except Exception as e:
                    print(f"加载节点图时出错: {e}")
                    QMessageBox.critical(self, "错误", f"无法加载节点图: {str(e)}")
            else:
                # 如果路径无效，也打印一个警告或消息框
                QMessageBox.warning(self, "错误", f"无法打开节点图，路径无效或文件不存在: {nodegraph_path}")
                print(f"FILM_PREVIEW_ERROR: Double-clicked item's nodegraph_path invalid or file does not exist: {nodegraph_path}")


    def save_preview_as_thumbnail(self, nodegraph_path):
        """保存当前预览图像作为节点图的缩略图，覆盖以前的缩略图避免文件污染"""
        try:
            # 创建缩略图文件名 (使用节点图文件名，但扩展名为.png)
            nodegraph_basename = os.path.basename(nodegraph_path)
            nodegraph_name = os.path.splitext(nodegraph_basename)[0]
            thumbnail_path = os.path.join(self.thumbnails_folder, f"{nodegraph_name}.png")

            # 如果旧的缩略图存在，先删除以确保完全覆盖
            if os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                    print(f"已删除旧缩略图: {thumbnail_path}")
                except Exception as e:
                    print(f"删除旧缩略图失败: {e}")

            if not hasattr(self, 'preview_display_widget') or self.preview_display_widget is None:
                # 如果没有预览窗口，创建一个空白的缩略图
                empty_pixmap = QPixmap(128, 128)
                empty_pixmap.fill(Qt.white)

                # 在空白图上绘制文本
                painter = QPainter(empty_pixmap)
                painter.setPen(Qt.black)
                painter.setFont(QFont("Arial", 10))
                painter.drawText(empty_pixmap.rect(), Qt.AlignCenter, "空白节点图")
                painter.end()

                # 保存缩略图
                success = empty_pixmap.save(thumbnail_path, "PNG")
                if success:
                    print(f"已保存空白节点图缩略图至: {thumbnail_path}")
                else:
                    print(f"保存空白节点图缩略图失败: {thumbnail_path}")

                return success

            # 获取当前预览图像
            pixmap = self.preview_display_widget.get_image()
            if pixmap is None or pixmap.isNull():
                # 创建一个空白的缩略图
                empty_pixmap = QPixmap(128, 128)
                empty_pixmap.fill(Qt.lightGray)

                # 在空白图上绘制文本
                painter = QPainter(empty_pixmap)
                painter.setPen(Qt.black)
                painter.setFont(QFont("Arial", 10))
                painter.drawText(empty_pixmap.rect(), Qt.AlignCenter, "无预览")
                painter.end()

                pixmap = empty_pixmap

            # 创建缩略图 (128x128)
            thumbnail = pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            # 保存缩略图，覆盖旧文件
            success = thumbnail.save(thumbnail_path, "PNG")
            if success:
                print(f"已保存节点图缩略图至: {thumbnail_path}")
            else:
                print(f"保存节点图缩略图失败: {thumbnail_path}")

            return success
        except Exception as e:
            print(f"保存缩略图时出错: {str(e)}")
            return False

    def cleanup_orphaned_thumbnails(self):
        """清理孤立的缩略图文件（没有对应节点图文件的缩略图）"""
        try:
            if not os.path.exists(self.thumbnails_folder):
                return

            # 获取所有节点图文件名（不含扩展名）
            nodegraph_names = set()
            if os.path.exists(self.nodegraphs_folder):
                for filename in os.listdir(self.nodegraphs_folder):
                    if filename.endswith('.json') and not filename.startswith('_auto_'):
                        nodegraph_name = os.path.splitext(filename)[0]
                        nodegraph_names.add(nodegraph_name)

            # 检查缩略图文件夹中的文件
            orphaned_count = 0
            for filename in os.listdir(self.thumbnails_folder):
                if filename.endswith('.png'):
                    thumbnail_name = os.path.splitext(filename)[0]
                    if thumbnail_name not in nodegraph_names:
                        # 这是一个孤立的缩略图，删除它
                        thumbnail_path = os.path.join(self.thumbnails_folder, filename)
                        try:
                            os.remove(thumbnail_path)
                            orphaned_count += 1
                            print(f"已删除孤立缩略图: {filename}")
                        except Exception as e:
                            print(f"删除孤立缩略图失败 {filename}: {e}")

            if orphaned_count > 0:
                print(f"清理完成，共删除 {orphaned_count} 个孤立缩略图")
            else:
                print("没有发现孤立的缩略图文件")

        except Exception as e:
            print(f"清理孤立缩略图时出错: {e}")

    def _save_node_graph_to_file_internal(self, file_path):
        """内部方法：仅保存节点图数据到文件，不修改当前节点图状态"""
        try:
            print(f"[内部] 正在保存节点图到文件: {file_path}")

            # 创建保存数据
            data = {
                'current_image_path': self.current_image_path if hasattr(self, 'current_image_path') else None,
                'nodes': [],
                'connections': []
            }

            # 保存节点数据
            for node in self.nodes:
                node_data = {
                    'id': node['id'],
                    'x': node['x'],
                    'y': node['y'],
                    'script_path': node['script_path'],
                    'title': node['title'],
                    'params': {k: v['value'] for k, v in node['params'].items()},
                    # 保存灵活端口信息
                    'flexible_ports': node.get('flexible_ports', {'inputs': [], 'outputs': []}),
                    # 保存端口计数
                    'port_counts': node.get('port_counts', {'inputs': 0, 'outputs': 0}),
                    # 保存元数据
                    'metadata': node.get('metadata', {})
                }
                data['nodes'].append(node_data)

            # 保存连接数据
            for conn in self.connections:
                conn_data = {
                    'output_node_id': conn['output_node']['id'],
                    'output_port': conn['output_port'],
                    'input_node_id': conn['input_node']['id'],
                    'input_port': conn['input_port']
                }
                data['connections'].append(conn_data)

            # 保存到文件
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 保存预览图像作为缩略图 (对于自动保存也需要)
            self.save_preview_as_thumbnail(file_path)

            print(f"[内部] 节点图数据已保存到文件: {file_path}")

            return True
        except Exception as e:
            print(f"[内部] 保存节点图数据到文件出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def save_node_graph_to_file(self, file_path):
        """保存节点图到指定文件并更新状态"""
        try:
            print(f"正在保存节点图到文件: {file_path}")

            # 使用内部方法保存数据
            success = self._save_node_graph_to_file_internal(file_path)

            if success:
                # 只有在成功保存后才更新节点图状态
                # 统一管理节点图状态 - 更新路径、标记为非新建、重置修改状态
                self.set_nodegraph_state(
                    path=file_path,
                    is_new=False,
                    modified=False
                )

                print(f"已成功保存节点图，当前节点图路径: {self.current_nodegraph_path}")

            return success
        except Exception as e:
            print(f"保存节点图到文件出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _clean_node_data_for_serialization(self, node):
        """清理节点数据以便JSON序列化，移除所有Qt对象和不可序列化的对象

        Args:
            node: 原始节点数据

        Returns:
            dict: 清理后的节点数据
        """
        def is_serializable(obj):
            """检查对象是否可以JSON序列化"""
            try:
                # 检查是否是Qt对象
                if hasattr(obj, 'metaObject'):
                    return False

                # 检查是否是QFrame或其他Qt类型
                if hasattr(obj, '__class__'):
                    class_name = obj.__class__.__name__
                    obj_type_str = str(type(obj))
                    # 适配PySide6和PyQt5
                    if class_name.startswith('Q') and ('PySide' in obj_type_str or 'PyQt' in obj_type_str):
                        return False

                # 尝试JSON序列化测试
                import json
                json.dumps(obj)
                return True
            except (TypeError, ValueError):
                return False

        def clean_value(value):
            """递归清理值"""
            if value is None:
                return None
            elif isinstance(value, (str, int, float, bool)):
                return value
            elif isinstance(value, list):
                return [clean_value(item) for item in value if is_serializable(item)]
            elif isinstance(value, dict):
                cleaned_dict = {}
                for k, v in value.items():
                    if is_serializable(v):
                        cleaned_dict[k] = clean_value(v)
                return cleaned_dict
            elif is_serializable(value):
                return value
            else:
                return None  # 跳过不可序列化的对象

        # 定义需要排除的键（包含Qt对象的键）
        excluded_keys = {
            'widget', 'pixmap', 'qt_objects', 'port_widgets',
            'input_widgets', 'output_widgets', 'param_widgets',
            'layout', 'parent', 'children'  # 添加更多可能包含Qt对象的键
        }

        clean_node = {}
        for key, value in node.items():
            if key not in excluded_keys:
                cleaned_value = clean_value(value)
                if cleaned_value is not None:
                    clean_node[key] = cleaned_value

        return clean_node

    def load_node_graph_from_file(self, file_path, suppress_auto_save=False):
        """从文件加载节点图"""
        try:
            # 显示加载指示器
            self.task_label.setText("正在加载节点图...")
            QApplication.processEvents()  # 强制更新UI

            # 设置节点图状态 - 这是从文件加载的节点图
            self.set_nodegraph_state(
                path=file_path,  # 确保设置正确的路径
                is_new=False,    # 从文件加载的不是新创建的
                modified=False   # 初始状态为未修改
            )

            # 读取文件
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 清除当前节点图 - 传递 suppress_auto_save 参数
            self.clear_node_graph(suppress_auto_save=True) # 强制抑制清除时的保存

            # 设置图像路径
            if 'current_image_path' in data and data['current_image_path']:
                self.current_image_path = data['current_image_path']
                # 验证图像文件是否存在
                if not os.path.exists(self.current_image_path):
                    QMessageBox.warning(
                        self,
                        "加载警告",
                        f"无法找到原始图像: {self.current_image_path}\\n将继续加载节点图但没有原始图像。"
                    )
                    # 不设置current_image_path，因为文件不存在
                    self.current_image_path = None

            # 加载节点
            nodes_map = {}  # 用于映射旧节点ID到新节点

            # 分批创建节点，以避免UI冻结
            batch_size = 5
            for i in range(0, len(data['nodes']), batch_size):
                batch = data['nodes'][i:i+batch_size]

                for node_data in batch:
                    # 查找脚本信息
                    script_path = node_data['script_path']
                    script_info = None

                    # 遍历注册表找到脚本信息
                    def find_script_info(registry, path):
                        for key, value in registry.items():
                            if isinstance(value, dict):
                                if 'path' in value and value['path'] == path:
                                    return value['info']
                                else:
                                    result = find_script_info(value, path)
                                    if result:
                                        return result
                        return None

                    script_info = find_script_info(self.script_registry, script_path)

                    if not script_info:
                        QMessageBox.warning(
                            self,
                            "加载警告",
                            f"找不到脚本: {script_path}\n该节点将被跳过。"
                        )
                        continue

                    # 创建节点
                    node = self.add_node(script_path, script_info)

                    # 设置节点位置
                    node['x'] = node_data['x']
                    node['y'] = node_data['y']
                    if 'widget' in node and node['widget']:
                        node['widget'].move(node['x'], node['y'])

                    # 设置节点参数
                    if 'params' in node_data:
                        for param_name, param_value in node_data['params'].items():
                            if param_name in node['params']:
                                node['params'][param_name]['value'] = param_value

                    # 恢复灵活端口信息
                    if 'flexible_ports' in node_data:
                        node['flexible_ports'] = node_data['flexible_ports']

                    # 恢复端口计数
                    if 'port_counts' in node_data:
                        node['port_counts'] = node_data['port_counts']

                    # 恢复元数据
                    if 'metadata' in node_data:
                        node['metadata'] = node_data['metadata']
                    else:
                        # 如果没有元数据，创建默认元数据
                        node['metadata'] = self.metadata_manager.create_metadata(
                            node_id=node['id'],
                            node_title=node['title'],
                            script_path=node['script_path']
                        )

                    # 重建灵活端口视觉组件 - 确保与端口计数一致
                    if 'port_counts' in node and 'flexible_ports' in node:
                        # 对于输入端口
                        if 'inputs' in node['flexible_ports'] and node['flexible_ports']['inputs']:
                            # 获取基本端口数量
                            base_input_count = len(node['script_info'].get('inputs', []))
                            # 获取已保存的端口总数
                            saved_input_count = node['port_counts'].get('inputs', base_input_count)

                            # 创建缺失的灵活端口
                            for port_idx in range(base_input_count, saved_input_count):
                                # 获取灵活端口类型，使用第一个灵活类型
                                if node['flexible_ports']['inputs']:
                                    flex_type = node['flexible_ports']['inputs'][0]
                                    # 创建视觉端口
                                    port_color = self.get_port_color(flex_type)
                                    port_widget = QFrame(node['widget'])
                                    port_widget.setStyleSheet(f"""
                                        QFrame {{
                                            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                         stop:0 #FFFFFF, stop:1 {port_color}); /* 白色到端口颜色的渐变 */
                                            border: 1px solid {QColor(port_color).darker(130).name()}; /* 端口边框颜色加深 */
                                            border-radius: 5px; /* 圆角端口 */
                                        }}
                                    """)
                                    port_widget.setFixedSize(10, 16)

                                    # 计算端口位置
                                    port_x = -3
                                    port_y = 20 + port_idx * 20
                                    port_widget.move(port_x, port_y)

                                    # 设置工具提示
                                    port_widget.setToolTip(f"input端口: {flex_type}")

                                    # 保存端口信息
                                    if 'port_widgets' not in node:
                                        node['port_widgets'] = {'inputs': {}, 'outputs': {}}

                                    node['port_widgets']['inputs'][port_idx] = {
                                        'widget': port_widget,
                                        'type': flex_type,
                                        'pos': QPoint(port_x + 5, port_y + 8)
                                    }

                                    # 设置鼠标事件
                                    def create_press_handler(n, idx, t):
                                        return lambda event: self.on_port_click(event, n, idx, t)

                                    def create_context_menu_handler(n, idx, t):
                                        return lambda pos: self.show_port_context_menu(pos, n, idx, t)

                                    port_widget.mousePressEvent = create_press_handler(node, port_idx, 'input')
                                    port_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                                    port_widget.customContextMenuRequested.connect(
                                        create_context_menu_handler(node, port_idx, 'input')
                                    )

                                    # 显示新端口
                                    port_widget.show()

                        # 对于输出端口 - 同样处理逻辑
                        if 'outputs' in node['flexible_ports'] and node['flexible_ports']['outputs']:
                            # 获取基本端口数量
                            base_output_count = len(node['script_info'].get('outputs', []))
                            # 获取已保存的端口总数
                            saved_output_count = node['port_counts'].get('outputs', base_output_count)

                            # 创建缺失的灵活端口
                            for port_idx in range(base_output_count, saved_output_count):
                                # 获取灵活端口类型，使用第一个灵活类型
                                if node['flexible_ports']['outputs']:
                                    flex_type = node['flexible_ports']['outputs'][0]
                                    # 创建视觉端口
                                    port_color = self.get_port_color(flex_type)
                                    port_widget = QFrame(node['widget'])
                                    port_widget.setStyleSheet(f"""
                                        QFrame {{
                                            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                         stop:0 #FFFFFF, stop:1 {port_color}); /* 白色到端口颜色的渐变 */
                                            border: 1px solid {QColor(port_color).darker(130).name()}; /* 端口边框颜色加深 */
                                            border-radius: 5px; /* 圆角端口 */
                                        }}
                                    """)
                                    port_widget.setFixedSize(10, 16)

                                    # 计算端口位置
                                    port_x = node['width'] - 7
                                    port_y = 20 + port_idx * 20
                                    port_widget.move(port_x, port_y)

                                    # 设置工具提示
                                    port_widget.setToolTip(f"output端口: {flex_type}")

                                    # 保存端口信息
                                    if 'port_widgets' not in node:
                                        node['port_widgets'] = {'inputs': {}, 'outputs': {}}

                                    node['port_widgets']['outputs'][port_idx] = {
                                        'widget': port_widget,
                                        'type': flex_type,
                                        'pos': QPoint(port_x + 5, port_y + 8)
                                    }

                                    # 设置鼠标事件
                                    def create_press_handler(n, idx, t):
                                        return lambda event: self.on_port_click(event, n, idx, t)

                                    def create_context_menu_handler(n, idx, t):
                                        return lambda pos: self.show_port_context_menu(pos, n, idx, t)

                                    port_widget.mousePressEvent = create_press_handler(node, port_idx, 'output')
                                    port_widget.setContextMenuPolicy(Qt.CustomContextMenu)
                                    port_widget.customContextMenuRequested.connect(
                                        create_context_menu_handler(node, port_idx, 'output')
                                    )

                                    # 显示新端口
                                    port_widget.show()

                        # 调整节点高度
                        max_ports = max(node['port_counts'].get('inputs', 0), node['port_counts'].get('outputs', 0))
                        node['height'] = max(80, 40 + max_ports * 20)
                        node['widget'].setFixedHeight(node['height'])

                    # 记录节点映射
                    nodes_map[node_data['id']] = node

                # 每处理一批节点后更新UI
                QApplication.processEvents()

            self.task_label.setText("正在创建连接...")
            QApplication.processEvents()

            # 创建连接
            for conn_data in data['connections']:
                output_node_id = conn_data['output_node_id']
                input_node_id = conn_data['input_node_id']

                # 检查节点是否存在
                if output_node_id in nodes_map and input_node_id in nodes_map:
                    output_node = nodes_map[output_node_id]
                    input_node = nodes_map[input_node_id]
                    output_port = conn_data['output_port']
                    input_port = conn_data['input_port']

                    # 使用create_connection方法创建连接，但抑制节点图处理
                    # 这样可以确保灵活端口处理正确执行
                    orig_result = self.create_connection(output_node, output_port, input_node, input_port)

                    # 如果连接创建成功，处理灵活端口
                    if orig_result:
                        # 手动调用灵活端口处理（create_connection内部会调用，但为确保灵活端口处理正确，这里再次显式调用）
                        self._handle_flexible_port(output_node, output_port, 'outputs')
                        self._handle_flexible_port(input_node, input_port, 'inputs')

            self.task_label.setText("正在更新节点图...")
            QApplication.processEvents()

            # 加载完成后，只处理必要的节点 - 查找没有输入的根节点
            root_nodes = []
            for node in self.nodes:
                has_input = False
                for conn in self.connections:
                    if conn['input_node'] == node:
                        has_input = True
                        break
                if not has_input:
                    root_nodes.append(node)

            print(f"找到{len(root_nodes)}个根节点，只处理这些节点及其下游节点")

                        # 处理节点图 - 确保预览显示正确
            # 查找预览节点
            preview_node = None
            for node in self.nodes:
                if node['title'] == '预览节点':
                    preview_node = node
                    break

            if preview_node:
                # 首先，处理所有节点，确保预览节点的所有依赖都处理
                # 使用force_refresh=True强制处理所有节点
                print("加载图表后强制处理所有节点，确保预览正确...")
                self.update_preview(force_refresh=True)
            else:
                # 如果没有预览节点，则正常处理
                if root_nodes:
                    self.process_node_graph(suppress_auto_save=suppress_auto_save, changed_nodes=root_nodes)
                else:
                    print("没有找到根节点，将处理所有节点")
                    self.process_node_graph(suppress_auto_save=suppress_auto_save)

            # 更新画布
            self.node_canvas_widget.update()

            self.task_label.setText("节点图加载完成")

            # 自动适应视图大小
            QTimer.singleShot(100, self.zoom_fit)

            # 更新胶片预览，确保新加载的节点图会在胶片预览中显示
            self.update_film_preview()

            # 不再需要这里的自动保存判断，由 process_node_graph 控制
            # if not suppress_auto_save:
            #     self.auto_save_node_graph()

            return True

        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"加载节点图失败: {str(e)}")
            import traceback
            traceback.print_exc()
            self.task_label.setText("节点图加载失败")
            return False

    def clear_node_graph(self, suppress_auto_save=False):
        """清除当前节点图"""
        # 清除LRU缓存 - 清空节点图时需要清除缓存
        if hasattr(self, 'node_cache'):
            self.node_cache.clear()
            print("已清除节点处理缓存。")

        # 清除连接
        self.connections = []

        # 清除节点及其端口
        for node in self.nodes:
            # --- 新增：先删除关联的端口部件 ---
            if 'port_widgets' in node:
                 for port_type in ['inputs', 'outputs']:
                     if port_type in node['port_widgets']:
                         for port_idx, port_info in node['port_widgets'][port_type].items():
                             if 'widget' in port_info and port_info['widget']:
                                 port_info['widget'].deleteLater()
            # --- 结束端口删除 ---

            if 'widget' in node and node['widget']:
                node['widget'].setParent(None)

        self.nodes = []
        self.next_node_id = 0
        self.selected_node = None

        # 清除设置区域
        for i in reversed(range(self.settings_content_layout.count())):
            widget = self.settings_content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 不显示任何提示，保持空白
        # self.no_node_label = QLabel("")
        # self.no_node_label.setAlignment(Qt.AlignCenter)
        # self.settings_content_layout.addWidget(self.no_node_label)

        # 更新画布
        self.node_canvas_widget.update()

        # 注: 此处原自动保存代码已移除

    def create_empty_node_graph(self, nodegraph_name):
        """创建完全空白的节点图

        参数:
            nodegraph_name: 节点图的名称(不包含扩展名)
        """
        # 清除当前节点图
        self.clear_node_graph(suppress_auto_save=True)

        # 创建节点图文件路径
        nodegraph_path = os.path.join(self.nodegraphs_folder, f"{nodegraph_name}.json")

        # 使用统一的节点图状态管理
        self.set_nodegraph_state(
            path=nodegraph_path,  # 设置节点图路径
            is_new=True,          # 标记为新创建的节点图
            modified=False        # 初始状态未修改
        )

        # 保存空节点图
        if self.save_node_graph_to_file(nodegraph_path):
            print(f"已创建空白节点图: {nodegraph_path}")
            # 更新胶片预览
            self.update_film_preview()
            # 更新状态栏
            self.task_label.setText(f"已创建空白节点图: {nodegraph_name}")
            return True
        else:
            print(f"创建空白节点图失败: {nodegraph_path}")
            return False

    def create_new_node_graph(self):
        """创建新节点图，弹出对话框询问名称"""
        # 先保存当前节点图（如果有）
        if hasattr(self, 'current_nodegraph_path') and self.current_nodegraph_path and self.nodes:
            try:
                # 自动保存当前节点图
                self.save_node_graph_to_file(self.current_nodegraph_path)
                print(f"自动保存当前节点图: {self.current_nodegraph_path}")
            except Exception as e:
                print(f"保存当前节点图时出错: {e}")
                # 如果保存失败，提示用户
                reply = QMessageBox.question(
                    self,
                    "保存错误",
                    f"保存当前节点图时出错:\n{str(e)}\n是否继续创建新节点图?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        elif self.nodes:
            # 如果有节点但没有保存路径，询问用户是否保存
            reply = QMessageBox.question(
                self,
                "保存当前节点图",
                "当前节点图尚未保存，是否保存?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                # 调用保存函数
                self.save_node_graph()
                # 检查是否成功保存（如果用户取消了保存对话框）
                if not hasattr(self, 'current_nodegraph_path') or not self.current_nodegraph_path:
                    # 用户可能取消了保存，询问是否继续创建新节点图
                    reply = QMessageBox.question(
                        self,
                        "创建新节点图",
                        "当前节点图未保存，是否继续创建新节点图?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return

        # 弹出对话框，询问节点图名称
        nodegraph_name, ok = QInputDialog.getText(
            self,
            "创建新节点图",
            "请输入节点图名称:",
            QLineEdit.Normal,
            f"新节点图_{time.strftime('%Y%m%d_%H%M%S')}"
        )

        if not ok or not nodegraph_name:
            return  # 用户取消

        # 清理名称中的非法字符
        import re
        nodegraph_name = re.sub(r'[\\/*?:"<>|]', '_', nodegraph_name)

        # 检查节点图是否已存在
        nodegraph_path = os.path.join(self.nodegraphs_folder, f"{nodegraph_name}.json")
        if os.path.exists(nodegraph_path):
            reply = QMessageBox.question(
                self,
                "节点图已存在",
                f"节点图 '{nodegraph_name}' 已存在，是否覆盖?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return  # 用户取消覆盖

        # 创建空白节点图
        self.create_empty_node_graph(nodegraph_name)

    def create_default_node_graph(self):
        """创建默认节点图 - 自动换行布局"""
        # 先清除任何现有节点
        self.clear_node_graph()

        # 使用统一的节点图状态管理
        self.set_nodegraph_state(
            path=None,  # 新节点图没有路径
            is_new=True,
            modified=False
        )

        # 重置节点ID计数器
        self.next_node_id = 0

        try:
            # 查找默认脚本
            image_script = os.path.join(self.scripts_folder, "图像节点.py")
            decode_script = os.path.join(self.scripts_folder, "解码节点.py")
            process_script = os.path.join(self.scripts_folder, "基本处理.py")
            preview_script = os.path.join(self.scripts_folder, "预览节点.py")
            export_script = os.path.join(self.scripts_folder, "导出节点.py")

            # 检查脚本是否存在
            missing_scripts = []
            for script in [image_script, decode_script, process_script, preview_script, export_script]:
                if not os.path.exists(script):
                    missing_scripts.append(os.path.basename(script))

            if missing_scripts:
                QMessageBox.critical(self, "缺少脚本", f"缺少以下默认节点脚本文件:\n{', '.join(missing_scripts)}")
                # 如果缺少默认脚本，创建简单的默认节点图
                self.create_simple_default_node_graph()
                return

            # 解析脚本信息
            scripts_info = {}
            for script in [image_script, decode_script, process_script, preview_script, export_script]:
                info = self.parse_script_header(script)
                if info:
                    scripts_info[script] = info
                else:
                    QMessageBox.critical(self, "脚本解析错误", f"无法解析脚本信息: {os.path.basename(script)}")
                    # 如果解析失败，回退到简单默认图
                    self.create_simple_default_node_graph()
                    return

            # 获取可见区域宽度，用于计算节点布局
            visible_width = self.node_scroll.width()
            if visible_width < 100:  # 如果宽度太小，使用默认值
                visible_width = 800

            # 节点间距和节点尺寸
            node_spacing_x = 150  # 水平间距
            node_spacing_y = 120  # 垂直间距
            node_width = 120  # 节点宽度

            # 计算每行可容纳的最大节点数
            nodes_per_row = max(2, (visible_width - 100) // (node_width + node_spacing_x))

            # 创建节点脚本和放置信息
            node_scripts = [
                image_script,
                decode_script,
                process_script,
                preview_script,
                export_script
            ]

            # 创建所有节点
            nodes = []
            for i, script in enumerate(node_scripts):
                # 计算行和列位置
                row = i // nodes_per_row
                col = i % nodes_per_row

                # 计算节点坐标
                x = 50 + col * (node_width + node_spacing_x)
                y = 50 + row * node_spacing_y

                # 创建节点
                node = self.add_node(script, scripts_info[script])

                # 设置节点位置
                node['x'], node['y'] = x, y
                node['widget'].move(x, y)

                nodes.append(node)

            # 创建连接 - 按照顺序连接节点
            for i in range(len(nodes) - 1):
                # 使用输出的第一个端口和输入的第一个端口
                output_idx = 0
                input_idx = 0

                self.create_connection(nodes[i], output_idx, nodes[i + 1], input_idx)

            # 更新连接线
            self.update_connections()

            # 如果有当前打开的图像，为图像节点设置路径参数
            if self.current_image_path and 'params' in nodes[0] and 'image_path' in nodes[0]['params']:
                nodes[0]['params']['image_path']['value'] = self.current_image_path

            # 处理节点图并更新预览
            # 预览节点通常是第4个
            preview_node = nodes[3] if len(nodes) > 3 else None
            if preview_node and preview_node['title'] == '预览节点':
                # 使用强制刷新确保所有节点都被处理
                self.update_preview(force_refresh=True)
            else:
                # 如果找不到预览节点，进行常规处理
                self.process_node_graph()

            # 自动适应视图大小
            QTimer.singleShot(100, self.zoom_fit)

        except Exception as e:
            print(f"创建默认节点图出错: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "节点图创建错误", f"创建默认节点图出错: {str(e)}")
            # 回退到简单默认图
            self.create_simple_default_node_graph()
    def create_simple_default_node_graph(self):
        """创建简单的默认节点图（当缺少完整脚本时）"""
        # 清除当前节点图
        self.clear_node_graph()

        # 使用统一的节点图状态管理
        self.set_nodegraph_state(
            path=None,  # 新节点图没有路径
            is_new=True,
            modified=False
        )

        try:
            # 查找图像节点脚本
            image_node = None
            preview_node = None

            # 查找图像节点脚本
            def find_image_script(registry):
                for key, value in registry.items():
                    if isinstance(value, dict):
                        if 'path' in value:
                            script_path = value['path']
                            if 'image' in os.path.basename(script_path).lower():
                                return value['path'], value['info']
                        else:
                            result = find_image_script(value)
                            if result:
                                return result
                return None

            # 创建图像节点
            image_script_info = find_image_script(self.script_registry)
            if image_script_info:
                image_script, image_info = image_script_info

                # 创建图像节点
                image_node = self.add_node(image_script, image_info)

                # 设置节点位置
                image_node['x'] = 100
                image_node['y'] = 100
                if 'widget' in image_node:
                    image_node['widget'].move(image_node['x'], image_node['y'])

                # 设置图像路径
                if self.current_image_path and 'params' in image_node and 'image_path' in image_node['params']:
                    image_node['params']['image_path']['value'] = self.current_image_path

            # 查找预览节点脚本
            def find_preview_script(registry):
                for key, value in registry.items():
                    if isinstance(value, dict):
                        if 'path' in value:
                            script_path = value['path']
                            if 'preview' in os.path.basename(script_path).lower():
                                return value['path'], value['info']
                        else:
                            result = find_preview_script(value)
                            if result:
                                return result
                return None

            # 创建预览节点
            preview_script_info = find_preview_script(self.script_registry)
            if preview_script_info:
                preview_script, preview_info = preview_script_info

                # 创建预览节点
                preview_node = self.add_node(preview_script, preview_info)

                # 设置节点位置
                preview_node['x'] = 300
                preview_node['y'] = 100
                if 'widget' in preview_node:
                    preview_node['widget'].move(preview_node['x'], preview_node['y'])

            # 连接图像节点到预览节点
            if image_node and preview_node:
                if len(image_node['script_info']['outputs']) > 0 and len(preview_node['script_info']['inputs']) > 0:
                    self.create_connection(image_node, 0, preview_node, 0)

            # 更新连接线
            self.update_connections()

            # 处理节点图
            self.process_node_graph()

            # 确保预览节点显示
            if preview_node:
                print("确保预览节点及其依赖已处理")
                self._ensure_preview_dependencies_processed(preview_node)
                self.update_preview_from_node(preview_node)

                # 强制预览界面刷新
                if hasattr(self, 'preview_display_widget'):
                    self.preview_display_widget.update()
                    QApplication.processEvents()  # 强制处理事件队列

                # 确保预览图像被显示
                QTimer.singleShot(100, lambda: self.refresh_preview_display())

                # 自动适应视图大小
                QTimer.singleShot(150, self.zoom_fit)

        except Exception as e:
            print(f"创建简单默认节点图出错: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "创建节点图", "无法创建默认节点图。\n请手动添加节点。")

    def disconnect_port(self):
        """断开选中端口的连接"""
        if not hasattr(self, 'selected_port') or not self.selected_port:
            return

        node = self.selected_port['node']
        port_idx = self.selected_port['port_idx']
        port_type = self.selected_port['port_type']

        # 查找与选中端口相关的连接
        conn_to_remove = []
        for conn in self.connections:
            if (port_type == 'input' and conn['input_node'] == node and conn['input_port'] == port_idx) or \
               (port_type == 'output' and conn['output_node'] == node and conn['output_port'] == port_idx):
                conn_to_remove.append(conn)

        # 从连接列表中移除
        for conn in conn_to_remove:
            self.connections.remove(conn)

        # 设置节点图为已修改状态
        self.set_nodegraph_state(modified=True)

        # 处理灵活端口 - 检查这是否是最后一个添加的灵活端口
        port_count_key = port_type + 's'  # 'input' -> 'inputs', 'output' -> 'outputs'

        # 只有当断开的是最大索引的端口，并且是灵活端口类型，我们才移除它
        if hasattr(node, 'port_counts') and port_count_key in node['port_counts']:
            flexible_ports = node.get('flexible_ports', {}).get(port_count_key, [])

            if flexible_ports and port_idx > 0:  # 索引 0 的端口永远不移除
                # 获取端口类型
                port_widget_info = node['port_widgets'][port_count_key].get(port_idx)
                if port_widget_info and port_widget_info['type'] in flexible_ports:
                    # 检查是否是当前最大索引的端口
                    max_port_idx = max(node['port_widgets'][port_count_key].keys())
                    if port_idx == max_port_idx and port_idx == node['port_counts'][port_count_key] - 1:
                        # 移除端口部件
                        port_widget = port_widget_info['widget']
                        if port_widget:
                            port_widget.setParent(None)
                            port_widget.deleteLater()

                        # 从 port_widgets 中移除
                        del node['port_widgets'][port_count_key][port_idx]

                        # 更新端口计数
                        node['port_counts'][port_count_key] -= 1

                        # 调整节点高度
                        max_ports = max(node['port_counts']['inputs'], node['port_counts']['outputs'])
                        new_height = max(80, 40 + max_ports * 20)
                        if new_height < node['height']:
                            node['height'] = new_height
                            node['widget'].setFixedHeight(new_height)

                        print(f"已移除节点 {node['title']} 的灵活{port_type}端口 {port_idx}")

        # 处理节点图并更新预览 - 只处理受影响的节点
        affected_node = node
        if port_type == 'input':
            # 断开输入端口，只影响当前节点和其下游节点
            self.process_node_graph(changed_nodes=[affected_node])
        else:  # port_type == 'output'
            # 断开输出端口，找出所有连接到这个输出的节点
            affected_nodes = [affected_node]
            for conn in self.connections:
                if conn['output_node'] == node and conn['output_port'] == port_idx:
                    affected_nodes.append(conn['input_node'])
            self.process_node_graph(changed_nodes=affected_nodes)

        # 通知用户
        print(f"已断开节点 {node['title']} 的 {port_type} 端口 {port_idx} 的连接")

        # 更新画布
        self.node_canvas_widget.update()
        # 注: 此处原自动保存代码已移除

    def scan_scripts(self):
        """扫描并加载脚本"""
        print("扫描脚本文件夹:", self.scripts_folder)
        if not os.path.exists(self.scripts_folder):
            os.makedirs(self.scripts_folder)
            print("创建脚本文件夹")

            # 创建默认脚本
            self.create_default_scripts()

        # 清除旧的脚本注册
        self.script_registry = {}

        # 递归遍历脚本文件夹
        for root, dirs, files in os.walk(self.scripts_folder):
            # 计算相对路径
            rel_path = os.path.relpath(root, self.scripts_folder)

            # 如果是基础目录，则使用空字符串
            if rel_path == '.':
                rel_path = ''

            # 扫描当前文件夹中的Python脚本
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    self.register_script(file_path, rel_path, file)

    def register_script(self, file_path, rel_path, file_name):
        """注册脚本到系统"""
        try:
            # 解析脚本头部信息
            script_info = self.parse_script_header(file_path)
            if not script_info:
                print(f"不符合格式的脚本或解析失败: {file_path}")
                return

            # 加载脚本模块
            try:
                spec = importlib.util.spec_from_file_location("module.name", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"加载模块出错: {file_path} - {str(e)}")
                return

            # 创建注册表路径
            path_components = rel_path.split(os.sep) if rel_path else []
            # 确保没有空组件
            path_components = [p for p in path_components if p]

            # 添加到注册表
            current_dict = self.script_registry
            for component in path_components:
                if component not in current_dict:
                    current_dict[component] = {}
                current_dict = current_dict[component]

            # 添加脚本信息
            script_name = os.path.splitext(file_name)[0]
            current_dict[script_name] = {
                'path': file_path,
                'info': script_info,
                'module': module
            }

            print(f"已注册脚本: {script_name}")

        except Exception as e:
            print(f"注册脚本出错 {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
    def parse_script_header(self, file_path):
        """
        解析脚本头部信息，包括：
        1. 前四行注释：inputs、outputs、description、color
        2. 可选第五行：Type:NeoScript 标记（识别 NeoScript）
        3. 可选的SupportedFeatures特性标记，格式为：
           #SupportedFeatures:Feature1=True,Feature2=42,Feature3="字符串值"
        返回值字典包含：
           - inputs: 输入参数列表（字符串列表）
           - outputs: 输出参数列表
           - description: 脚本描述（字符串）
           - color: 颜色字符串（支持自动在 6 位十六进制前添加 “#”）
           - script_type: 'legacy' 或 'neo'
           - supported_features: 支持特性字典，键为特性名，值为 bool/int/float/str
           - flexible_inputs/outputs: 灵活端口列表
        """
        try:
            import os, re

            # 读取并剔除首尾空白
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = [line.strip() for line in file.readlines()]

            # --- 基本注释行检查 ---
            if len(lines) < 4:
                print(f"脚本 {file_path} 行数不足，至少需要4行注释头")
                return None
            if not all(line.startswith('#') for line in lines[:4]):
                print(f"脚本 {file_path} 前4行应当是注释")
                return None

            # --- 提取前四行信息 ---
            # 第一行：inputs 列表，逗号分隔
            inputs = lines[0][1:].strip()
            # 第二行：outputs 列表
            outputs = lines[1][1:].strip()
            # 第三行：description 描述
            description = lines[2][1:].strip()
            # 第四行：color 字符串（可能需要加 #）
            raw_color_str = lines[3][1:].strip()

            # --- 颜色格式修正 ---
            processed_color = raw_color_str
            if re.match(r'^[0-9a-fA-F]{6}$', raw_color_str):
                processed_color = '#' + raw_color_str
                print(f"  Info: Detected 6-char hex '{raw_color_str}', adding #: '{processed_color}'")

            # --- NeoScript 类型检测（可选第五行） ---
            script_type = 'legacy'  # 默认为旧版脚本
            if len(lines) >= 5 and lines[4].startswith('#') and 'Type:NeoScript' in lines[4]:
                script_type = 'neo'
                print(f"检测到 NeoScript: {os.path.basename(file_path)}")

            # --- 新的SupportedFeatures解析系统 ---
            supported_features = {}

            # 检查所有行，找到SupportedFeatures标记
            script_name = os.path.basename(file_path)
            print(f"解析脚本特性: {script_name}")

            for line in lines[4:]:  # 从第五行开始检查
                if line.startswith('#SupportedFeatures:'):
                    print(f"  发现SupportedFeatures标记: {line}")
                    # 去掉注释符号和标记，保留冒号后的内容
                    features_str = line[len('#SupportedFeatures:'):].strip()

                    # 如果特性字符串为空，跳过解析
                    if not features_str:
                        print(f"  空特性字符串，跳过解析")
                        continue

                    # 按逗号分隔特性列表
                    feature_items = features_str.split(',')
                    print(f"  特性列表: {feature_items}")

                    for item in feature_items:
                        item = item.strip()
                        # 跳过空项
                        if not item:
                            continue

                        # 使用等号分隔键值对
                        if '=' in item:
                            key, val_str = item.split('=', 1)
                            key = key.strip()
                            val_str = val_str.strip()
                            print(f"  解析特性: {key} = {val_str}")

                            # 处理引号包围的字符串
                            if (val_str.startswith('"') and val_str.endswith('"')) or \
                               (val_str.startswith("'") and val_str.endswith("'")):
                                val = val_str[1:-1]  # 去除引号
                            # 尝试类型转换
                            else:
                                try:
                                    if val_str.lower() == 'true':
                                        val = True
                                    elif val_str.lower() == 'false':
                                        val = False
                                    elif '.' in val_str:
                                        val = float(val_str)
                                    else:
                                        val = int(val_str)
                                except ValueError:
                                    val = val_str

                            supported_features[key] = val
                                            # 特性已经在解析时输出，这里不需要单独处理

            # --- 处理输入输出类型，识别灵活端口 ---
            input_list = []
            flexible_inputs = []
            if inputs:
                for i in inputs.split(','):
                    i = i.strip()
                    if i.endswith(':'):  # 检测灵活端口
                        flexible_inputs.append(i[:-1])  # 去掉冒号保存
                        input_list.append(i[:-1])  # 同时加入普通输入列表（去掉冒号）
                    else:
                        input_list.append(i)

            output_list = []
            flexible_outputs = []
            if outputs:
                for o in outputs.split(','):
                    o = o.strip()
                    if o.endswith(':'):  # 检测灵活端口
                        flexible_outputs.append(o[:-1])  # 去掉冒号保存
                        output_list.append(o[:-1])  # 同时加入普通输出列表（去掉冒号）
                    else:
                        output_list.append(o)

            # --- 输出灵活端口信息 ---
            if flexible_inputs:
                print(f"检测到灵活输入端口: {', '.join(flexible_inputs)}")
            if flexible_outputs:
                print(f"检测到灵活输出端口: {', '.join(flexible_outputs)}")

            # --- 构造并返回结果字典 ---
            # 输出解析结果总结
            if supported_features:
                print(f"脚本 {os.path.basename(file_path)} 解析到的特性:")
                for feature_key, feature_value in supported_features.items():
                    print(f"  - {feature_key}: {feature_value} (类型: {type(feature_value).__name__})")
            else:
                print(f"脚本 {os.path.basename(file_path)} 没有特性定义")

            return {
                'inputs': input_list,
                'outputs': output_list,
                'description': description,
                'color': processed_color,
                'script_type': script_type,
                'supported_features': supported_features,
                'flexible_inputs': flexible_inputs,
                'flexible_outputs': flexible_outputs
            }

        except Exception as e:
            print(f"解析脚本头部出错 {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    def paste_node(self):
        """粘贴之前复制的节点"""
        if not hasattr(self, 'copied_node') or not self.copied_node:
            return

        # 从复制的数据创建新节点
        script_path = self.copied_node['script_path']
        script_info = self.copied_node['script_info']

        # 创建新节点，默认放置在原节点附近
        new_node = self.add_node(script_path, script_info)

        # 设置参数值
        for param_name, param_value in self.copied_node['params'].items():
            if param_name in new_node['params']:
                new_node['params'][param_name]['value'] = param_value

        # 偏移新节点位置
        if self.selected_node:
            offset_x = 50
            offset_y = 50
            new_node['x'] = self.selected_node['x'] + offset_x
            new_node['y'] = self.selected_node['y'] + offset_y
            new_node['widget'].move(new_node['x'], new_node['y'])

        # 处理节点图并更新预览
        self.process_node_graph()

        # 选择新节点
        self.select_node(new_node)

        # 通知用户
        self.task_label.setText(f"已粘贴节点: {new_node['title']}")

    def arrange_nodes(self):
        """自动排列节点"""
        if not self.nodes:
            return

        # 保存当前排列状态用于撤销
        self.save_undo_state()

        # 首先按层级排序节点
        layers = self.sort_nodes_by_layer()

        # 设置初始位置和间距
        start_x = 50
        start_y = 50
        x_spacing = 150
        y_spacing = 120

        # 逐层放置节点
        for layer_idx, layer in enumerate(layers):
            # 计算此层的y坐标
            y = start_y + layer_idx * y_spacing

            # 逐个放置节点
            for node_idx, node in enumerate(layer):
                # 计算x坐标
                x = start_x + node_idx * x_spacing

                # 设置节点位置
                node['x'] = x
                node['y'] = y
                node['widget'].move(x, y)

        # 更新连接线
        self.update_connections()

        # 通知用户
        self.task_label.setText("已自动排列节点")
        # 注: 此处原自动保存代码已移除

    def sort_nodes_by_layer(self):
        """按处理层级对节点进行排序"""
        # 没有连接的节点(输入节点)属于第0层
        layers = []

        # 创建入度映射(每个节点有多少个输入)
        in_degree = {node['id']: 0 for node in self.nodes}

        # 计算每个节点的入度
        for conn in self.connections:
            in_node_id = conn['input_node']['id']
            in_degree[in_node_id] += 1

        # 查找入度为0的节点(无输入节点)
        layer0 = []
        for node in self.nodes:
            if in_degree[node['id']] == 0:
                layer0.append(node)

        # 如果没有入度为0的节点，但有节点存在，则取第一个节点作为起点
        if not layer0 and self.nodes:
            layer0 = [self.nodes[0]]

        # 将第0层添加到层级列表
        layers.append(layer0)

        # 已处理的节点ID
        processed = {node['id'] for node in layer0}

        # 继续处理直到所有节点都被分配层级
        while len(processed) < len(self.nodes):
            next_layer = []

            # 查找当前已处理节点的所有输出连接到的节点
            for node in self.nodes:
                if node['id'] in processed:
                    continue

                # 检查此节点的所有输入是否都已处理
                all_inputs_processed = True
                for conn in self.connections:
                    if conn['input_node'] == node:
                        if conn['output_node']['id'] not in processed:
                            all_inputs_processed = False
                            break

                # 如果所有输入都已处理，则添加到下一层
                if all_inputs_processed:
                    next_layer.append(node)
                    processed.add(node['id'])

            # 如果没有找到新节点但还有未处理的节点，选择一个未处理的节点添加
            if not next_layer:
                for node in self.nodes:
                    if node['id'] not in processed:
                        next_layer.append(node)
                        processed.add(node['id'])
                        break

            # 添加下一层到层级列表
            layers.append(next_layer)

        return layers

    def save_undo_state(self):
        """保存当前状态用于撤销操作（已禁用）"""
        # 撤销功能已禁用，此方法不再执行任何操作
        print("撤销状态保存功能已禁用")

    def is_upstream_of_preview(self, target_node):
        """检查 target_node 是否是活动预览节点的上游（直接或间接）"""
        preview_node = None
        for node in self.nodes:
            if node.get('title') == '预览节点':
                preview_node = node
                break

        if not preview_node:
            return False # 没有预览节点，无法判断

        if target_node == preview_node: # 目标本身就是预览节点
            return True

        # 使用 DFS (深度优先搜索) 或 BFS (广度优先搜索) 从预览节点向上游遍历
        queue = [preview_node]
        visited = {preview_node['id']}

        while queue:
            current_node = queue.pop(0)

            # 查找连接到 current_node 输入端口的连接
            for conn in self.connections:
                if conn['input_node'] == current_node:
                    upstream_node = conn['output_node']
                    if upstream_node == target_node:
                        return True # 找到了目标节点
                    if upstream_node['id'] not in visited:
                        visited.add(upstream_node['id'])
                        queue.append(upstream_node)

        return False # 遍历完成未找到目标节点

    def undo_node_graph(self, event=None):
        """撤销功能（已禁用）"""
        # 自动保存系统已被移除，撤销功能不再可用
        QMessageBox.information(self, "撤销不可用", "撤销功能已禁用，因为自动保存系统已被移除。")
        self.task_label.setText("撤销功能已禁用")
        print("撤销功能已禁用，因为自动保存系统已被移除。")
    def pil_to_qimage(self, pil_image):
        """将PIL图像转换为QImage，使用OpenCV处理颜色通道"""
        try:
            # 确保PIL图像在合适的模式下
            if pil_image.mode != "RGB" and pil_image.mode != "RGBA" and pil_image.mode != "L":
                pil_image = pil_image.convert("RGB")

            # 转换为numpy数组
            im_arr = np.array(pil_image)

            # 处理浮点数据
            if im_arr.dtype == np.float32 or im_arr.dtype == np.float64:
                # 确保数据范围在0-1之间并转换为uint8
                im_arr = (np.clip(im_arr, 0, 1) * 255).astype(np.uint8)

            # 根据图像模式处理
            if pil_image.mode == "RGB":
                # RGB转BGR (OpenCV/Qt风格)
                im_arr = cv2.cvtColor(im_arr, cv2.COLOR_RGB2BGR)
                height, width, channel = im_arr.shape
                bytesPerLine = 3 * width
                return QImage(im_arr.data, width, height, bytesPerLine, QImage.Format_BGR888).copy()

            elif pil_image.mode == "RGBA":
                # RGBA转BGRA
                im_arr = cv2.cvtColor(im_arr, cv2.COLOR_RGBA2BGRA)
                height, width, channel = im_arr.shape
                bytesPerLine = 4 * width
                return QImage(im_arr.data, width, height, bytesPerLine, QImage.Format_ARGB32).copy()

            elif pil_image.mode == "L":
                # 灰度图像
                height, width = im_arr.shape
                bytesPerLine = width
                return QImage(im_arr.data, width, height, bytesPerLine, QImage.Format_Grayscale8).copy()

            return None
        except Exception as e:
            print(f"pil_to_qimage 转换失败: {e}")
            return None

    def closeEvent(self, event):
        """窗口关闭时询问是否保存节点图"""
        if self.nodes:
            # 询问是否保存当前节点图
            reply = QMessageBox.question(
                self,
                "退出",
                "是否保存当前节点图？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                # 取消关闭
                event.ignore()
                return

            if reply == QMessageBox.Yes:
                if hasattr(self, 'current_nodegraph_path') and self.current_nodegraph_path:
                    # 如果有现有节点图文件路径，使用它来保存
                    file_path = self.current_nodegraph_path
                elif self.current_image_path:
                    # 如果没有节点图路径但有图像路径，则基于图像名创建新文件
                    image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]
                    filename = f"{image_filename}.json"
                    file_path = os.path.join(self.nodegraphs_folder, filename)
                else:
                    # 如果都没有，使用时间戳创建新文件
                    import time
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"nodegraph_{timestamp}.json"
                    file_path = os.path.join(self.nodegraphs_folder, filename)

                if not self.save_node_graph_to_file(file_path):
                    # 保存失败，提示用户并阻止关闭
                    QMessageBox.critical(self, "保存错误", f"无法保存节点图到:\\n{file_path}")
                    event.ignore() # 阻止窗口关闭
                    return

        # 接受关闭事件 (仅在未取消或保存成功时执行)
        event.accept()

    def arrange_nodes_dense(self):
        """密集排列节点"""
        if not self.nodes:
            return

        # 保存当前排列状态用于撤销
        self.save_undo_state()

        # 首先按层级排序节点
        layers = self.sort_nodes_by_layer()

        # 设置初始位置和间距
        start_x = 50
        start_y = 50
        x_spacing = 130  # 减小水平间距
        y_spacing = 90   # 减小垂直间距

        # 逐层放置节点
        for layer_idx, layer in enumerate(layers):
            # 计算此层的y坐标
            y = start_y + layer_idx * y_spacing

            # 逐个放置节点
            for node_idx, node in enumerate(layer):
                # 计算x坐标
                x = start_x + node_idx * x_spacing

                # 设置节点位置
                node['x'] = x
                node['y'] = y
                node['widget'].move(x, y)

        # 更新连接线
        self.update_connections()

        # 通知用户
        self.task_label.setText("已密集排列节点")
        # 注: 此处原自动保存代码已移除


    def sort_nodes_by_layer(self):
        """按处理层级对节点进行排序"""
        # 没有连接的节点(输入节点)属于第0层
        layers = []

        # 创建入度映射(每个节点有多少个输入)
        in_degree = {node['id']: 0 for node in self.nodes}

        # 计算每个节点的入度
        for conn in self.connections:
            in_node_id = conn['input_node']['id']
            in_degree[in_node_id] += 1

        # 查找入度为0的节点(无输入节点)
        layer0 = []
        for node in self.nodes:
            if in_degree[node['id']] == 0:
                layer0.append(node)

        # 如果没有入度为0的节点，但有节点存在，则取第一个节点作为起点
        if not layer0 and self.nodes:
            layer0 = [self.nodes[0]]

        # 将第0层添加到层级列表
        layers.append(layer0)

        # 已处理的节点ID
        processed = {node['id'] for node in layer0}

        # 继续处理直到所有节点都被分配层级
        while len(processed) < len(self.nodes):
            next_layer = []

            # 查找当前已处理节点的所有输出连接到的节点
            for node in self.nodes:
                if node['id'] in processed:
                    continue

                # 检查此节点的所有输入是否都已处理
                all_inputs_processed = True
                for conn in self.connections:
                    if conn['input_node'] == node:
                        if conn['output_node']['id'] not in processed:
                            all_inputs_processed = False
                            break

                # 如果所有输入都已处理，则添加到下一层
                if all_inputs_processed:
                    next_layer.append(node)
                    processed.add(node['id'])

            # 如果没有找到新节点但还有未处理的节点，选择一个未处理的节点添加
            if not next_layer:
                for node in self.nodes:
                    if node['id'] not in processed:
                        next_layer.append(node)
                        processed.add(node['id'])
                        break

            # 添加下一层到层级列表
            layers.append(next_layer)

        return layers

    # 注: 原delayed_auto_save方法已移除

    # 注: 原get_auto_save_files和can_undo方法已移除

    def copy_node(self):
        """复制当前选中的节点"""
        if not self.selected_node:
            return

        # 复制节点数据
        self.copied_node = {
            'script_path': self.selected_node['script_path'],
            'script_info': self.selected_node['script_info'],
            'params': {k: v['value'] for k, v in self.selected_node['params'].items()}
        }

        # 通知用户
        self.task_label.setText(f"已复制节点: {self.selected_node['title']}")

    def set_scroll_values(self, x, y):
        """辅助函数，用于延迟设置滚动条值"""
        # 在实际设置前重新获取滚动条对象，确保获取的是最新状态
        try:
            h_scrollbar = self.preview_scroll.horizontalScrollBar()
            v_scrollbar = self.preview_scroll.verticalScrollBar()
            h_scrollbar.setValue(x)
            v_scrollbar.setValue(y)
            # --- 移除旧的打印，因为 set_scroll_values 现在可能被多次调用 ---
            # print(f"Deferred scroll set: H={x} (max={h_scrollbar.maximum()}), V={y} (max={v_scrollbar.maximum()})") # DEBUG
            # --- 添加新的打印 ---
            print(f"DEBUG: Zoom - set_scroll_values called with H={x}, V={y}. Current Range: H(0-{h_scrollbar.maximum()}), V(0-{v_scrollbar.maximum()})") # DEBUG
        except Exception as e:
            print(f"Error in set_scroll_values: {e}")

    def find_port_at_position(self, pos):
        """查找指定位置的端口"""
        # 保存最近的端口和距离
        closest_node = None
        closest_port_idx = None
        closest_port_type = None
        min_distance = 30  # 增加检测范围到30像素

        # 遍历所有节点和端口
        for node in self.nodes:
            # 检查输入端口
            for port_idx, port_info in node['port_widgets']['inputs'].items():
                # 计算端口的全局位置
                global_port_pos = node['widget'].mapToGlobal(port_info['pos'])
                # 转换为画布坐标
                canvas_port_pos = self.node_canvas_widget.mapFromGlobal(global_port_pos)

                # 检查距离
                distance = ((canvas_port_pos.x() - pos.x()) ** 2 + (canvas_port_pos.y() - pos.y()) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    closest_node = node
                    closest_port_idx = port_idx
                    closest_port_type = 'input'

            # 检查输出端口
            for port_idx, port_info in node['port_widgets']['outputs'].items():
                # 计算端口的全局位置
                global_port_pos = node['widget'].mapToGlobal(port_info['pos'])
                # 转换为画布坐标
                canvas_port_pos = self.node_canvas_widget.mapFromGlobal(global_port_pos)

                # 检查距离
                distance = ((canvas_port_pos.x() - pos.x()) ** 2 + (canvas_port_pos.y() - pos.y()) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    closest_node = node
                    closest_port_idx = port_idx
                    closest_port_type = 'output'

        return closest_node, closest_port_idx, closest_port_type

    def switch_to_node_tab(self):
        """切换到节点标签页"""
        if hasattr(self, 'node_tab_index') and self.node_tab_index is not None:
            self.ribbon_widget.setCurrentIndex(self.node_tab_index)

    def init_zoom_functionality(self):
        """初始化和配置缩放功能"""
        # 确保缩放级别已初始化
        self.zoom_level = 1.0

        # 更新缩放信息显示
        if hasattr(self, 'zoom_info'):
            self.zoom_info.setText("缩放: 100%")

        # --- 移除旧的鼠标滚轮事件处理 ---
        # 添加鼠标滚轮事件处理
        # self.preview_canvas.wheelEvent = self.on_preview_mousewheel
        # 滚轮事件现在通过 preview_scroll.viewport() 的事件过滤器处理

        # 添加键盘快捷键
        self.add_zoom_keyboard_shortcuts()

    def add_zoom_keyboard_shortcuts(self):
        """添加缩放相关的键盘快捷键"""
        # 放大快捷键 - Ctrl+加号
        zoom_in_shortcut = QAction("放大", self)
        zoom_in_shortcut.setShortcut("Ctrl++")
        zoom_in_shortcut.triggered.connect(self.zoom_in)
        self.addAction(zoom_in_shortcut)

        # 放大快捷键 - Ctrl+等号(兼容不需要Shift的键盘)
        zoom_in_shortcut2 = QAction("放大2", self)
        zoom_in_shortcut2.setShortcut("Ctrl+=")
        zoom_in_shortcut2.triggered.connect(self.zoom_in)
        self.addAction(zoom_in_shortcut2)

        # 缩小快捷键 - Ctrl+减号
        zoom_out_shortcut = QAction("缩小", self)
        zoom_out_shortcut.setShortcut("Ctrl+-")
        zoom_out_shortcut.triggered.connect(self.zoom_out)
        self.addAction(zoom_out_shortcut)

        # 适应窗口快捷键 - Ctrl+0
        zoom_fit_shortcut = QAction("适应窗口", self)
        zoom_fit_shortcut.setShortcut("Ctrl+0")
        zoom_fit_shortcut.triggered.connect(self.zoom_fit)
        self.addAction(zoom_fit_shortcut)

        # 删除节点快捷键 - Delete
        delete_node_shortcut = QAction("删除节点", self)
        delete_node_shortcut.setShortcut("Delete")
        delete_node_shortcut.triggered.connect(self.delete_selected_node)
        self.addAction(delete_node_shortcut)

        # 复制节点快捷键 - Ctrl+C
        copy_node_shortcut = QAction("复制节点", self)
        copy_node_shortcut.setShortcut("Ctrl+C")
        copy_node_shortcut.triggered.connect(self.copy_node)
        self.addAction(copy_node_shortcut)

        # 粘贴节点快捷键 - Ctrl+V
        paste_node_shortcut = QAction("粘贴节点", self)
        paste_node_shortcut.setShortcut("Ctrl+V")
        paste_node_shortcut.triggered.connect(self.paste_node)
        self.addAction(paste_node_shortcut)

        # 撤销快捷键 - Ctrl+Z
        undo_shortcut = QAction("撤销", self)
        undo_shortcut.setShortcut("Ctrl+Z")
        undo_shortcut.triggered.connect(self.undo_node_graph)
        self.addAction(undo_shortcut)

        # 排列节点快捷键 - Ctrl+A
        arrange_shortcut = QAction("排列节点", self)
        arrange_shortcut.setShortcut("Ctrl+A")
        arrange_shortcut.triggered.connect(self.arrange_nodes)
        self.addAction(arrange_shortcut)

# 创建自定义QWidget类处理节点画布的绘制
class NodeCanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = None  # 引用主应用程序
        self.setMinimumSize(1000, 1000)  # 设置最小尺寸以确保有足够空间
        # 启用鼠标追踪，以便在不按下鼠标按钮时也能接收到鼠标移动事件
        self.setMouseTracking(True)
    def paintEvent(self, event):
        """处理绘制事件"""
        super().paintEvent(event)

        if not self.parent_app:
            return

        painter = QPainter(self)
        try:
            # 设置高质量渲染
            painter.setRenderHint(QPainter.Antialiasing, True)  # 抗锯齿
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)  # 平滑像素图变换
            painter.setRenderHint(QPainter.TextAntialiasing, True)  # 文本抗锯齿

            # 首先绘制网格（添加这部分代码）
            grid_size = 20
            width = self.width()
            height = self.height()

            # 使用稍深一点的蓝灰色，增加对比度使网格可见
            pen = QPen(QColor("#CCDFED"), 1)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)

            # 绘制网格线
            for x in range(0, width, grid_size):
                painter.drawLine(x, 0, x, height)

            for y in range(0, height, grid_size):
                painter.drawLine(0, y, width, y)

            # 获取Ctrl键状态用于绘制彩虹线
            modifiers = QApplication.keyboardModifiers()
            ctrl_pressed = bool(modifiers & Qt.ControlModifier)

            # 绘制Ctrl拖拽彩虹线
            if ctrl_pressed and hasattr(self.parent_app, 'ctrl_dragging') and self.parent_app.ctrl_dragging:
                if hasattr(self.parent_app, 'rainbow_line_start') and hasattr(self.parent_app, 'rainbow_line_end'):
                    start_pos = self.parent_app.rainbow_line_start
                    end_pos = self.parent_app.rainbow_line_end

                    # 打印彩虹线坐标信息进行调试
                    print(f"绘制彩虹线: 开始=({start_pos.x()}, {start_pos.y()}), 结束=({end_pos.x()}, {end_pos.y()})")

                    # 创建彩虹渐变
                    gradient = QLinearGradient(start_pos, end_pos)
                    gradient.setColorAt(0.0, QColor(255, 0, 0, 230))  # 红色
                    gradient.setColorAt(0.2, QColor(255, 165, 0, 230))  # 橙色
                    gradient.setColorAt(0.4, QColor(255, 255, 0, 230))  # 黄色
                    gradient.setColorAt(0.6, QColor(0, 255, 0, 230))  # 绿色
                    gradient.setColorAt(0.8, QColor(0, 0, 255, 230))  # 蓝色
                    gradient.setColorAt(1.0, QColor(128, 0, 128, 230))  # 紫色

                    # 设置彩虹笔刷 - 使用渐变和粗线条
                    pen = QPen(QBrush(gradient), 8)  # 增加线宽到5像素
                    pen.setCapStyle(Qt.RoundCap)  # 圆形线端点
                    pen.setJoinStyle(Qt.RoundJoin)  # 圆形连接点
                    painter.setPen(pen)

                    # 绘制彩虹线
                    path = QPainterPath(start_pos)
                    control1 = QPoint(start_pos.x() + 80, start_pos.y())
                    control2 = QPoint(end_pos.x() - 80, end_pos.y())
                    path.cubicTo(control1, control2, end_pos)
                    painter.drawPath(path)

            # 绘制所有连接
            for conn in self.parent_app.connections:
                # 获取两个端口的位置
                output_node = conn['output_node']
                input_node = conn['input_node']

                if ('widget' not in output_node or not output_node['widget'] or
                    'widget' not in input_node or not input_node['widget']):
                    continue

                # 安全检查：确保端口在port_widgets中
                if ('port_widgets' not in output_node or 'outputs' not in output_node['port_widgets']):
                    continue

                if ('port_widgets' not in input_node or 'inputs' not in input_node['port_widgets']):
                    continue

                # 检查端口索引是否存在 - 但不立即跳过，稍后会有更详细的错误处理
                output_port_exists = conn['output_port'] in output_node['port_widgets']['outputs']
                input_port_exists = conn['input_port'] in input_node['port_widgets']['inputs']

                # 如果端口不存在，尝试处理灵活端口
                if not output_port_exists:
                    # 尝试创建灵活端口
                    self.parent_app._handle_flexible_port(output_node, conn['output_port'], 'outputs')
                    # 再次检查端口是否已创建
                    output_port_exists = conn['output_port'] in output_node['port_widgets']['outputs']
                    if not output_port_exists:
                        print(f"警告: 节点 {output_node['title']} (ID: {output_node['id']}) 的输出端口 {conn['output_port']} 不存在")
                        continue

                if not input_port_exists:
                    # 尝试创建灵活端口
                    self.parent_app._handle_flexible_port(input_node, conn['input_port'], 'inputs')
                    # 再次检查端口是否已创建
                    input_port_exists = conn['input_port'] in input_node['port_widgets']['inputs']
                    if not input_port_exists:
                        print(f"警告: 节点 {input_node['title']} (ID: {input_node['id']}) 的输入端口 {conn['input_port']} 不存在")
                        continue

                try:
                    # 获取输出端口信息
                    output_port_info = output_node['port_widgets']['outputs'][conn['output_port']]
                    output_pos = output_node['widget'].mapTo(self, output_port_info['pos'])

                    # 获取输入端口信息
                    input_port_info = input_node['port_widgets']['inputs'][conn['input_port']]
                    input_pos = input_node['widget'].mapTo(self, input_port_info['pos'])
                except (KeyError, Exception) as e:
                    # 如果发生任何错误，跳过这个连接
                    print(f"绘制连接线时发生错误: {e}")
                    continue

                # 设置连接线颜色
                port_type = output_port_info['type']
                base_line_color = QColor(self.parent_app.get_port_color(port_type))
                line_color = base_line_color.darker(130).name() # 加深颜色
                pen = QPen(QColor(line_color), 2.5)
                pen.setStyle(Qt.SolidLine)
                painter.setPen(pen) # 加粗线条

                # 绘制连接线 - 使用曲线使其更美观
                path = QPainterPath(output_pos)
                control1 = QPoint(output_pos.x() + 50, output_pos.y())
                control2 = QPoint(input_pos.x() - 50, input_pos.y())
                path.cubicTo(control1, control2, input_pos)
                painter.drawPath(path)

            # 绘制临时连接线（如果正在创建连接）
            if hasattr(self.parent_app, 'connecting_from') and self.parent_app.connecting_from:
                if hasattr(self.parent_app, 'connection_start_pos') and hasattr(self.parent_app, 'connection_current_pos'):
                    start_pos = self.parent_app.connection_start_pos
                    current_pos = self.parent_app.connection_current_pos

                    # 提取连接起点的端口类型，以便使用相应的颜色
                    try:
                        source_node, source_port_idx, source_port_type = self.parent_app.connecting_from

                        # 安全检查：确保端口存在
                        if ('port_widgets' not in source_node or
                            (source_port_type == 'output' and
                            ('outputs' not in source_node['port_widgets'] or
                            source_port_idx not in source_node['port_widgets']['outputs'])) or
                            (source_port_type == 'input' and
                            ('inputs' not in source_node['port_widgets'] or
                            source_port_idx not in source_node['port_widgets']['inputs']))):
                            raise KeyError(f"端口不存在: {source_port_type} {source_port_idx}")

                        if source_port_type == 'output':
                            port_info = source_node['port_widgets']['outputs'][source_port_idx]
                        else:
                            port_info = source_node['port_widgets']['inputs'][source_port_idx]
                    except (KeyError, Exception) as e:
                        # 如果发生错误，使用默认颜色
                        print(f"绘制临时连接线时发生错误: {e}")
                        port_type = 'f32bmp'  # 默认使用图像端口类型
                        base_line_color = QColor("#88CCFF")
                        line_color = base_line_color.darker(130).name()

                        # 设置临时线条样式并直接绘制
                        pen = QPen(QColor(line_color), 2.5)
                        pen.setStyle(Qt.DashLine)
                        painter.setPen(pen)
                        path = QPainterPath(start_pos)
                        control1 = QPoint(start_pos.x() + 50, start_pos.y())
                        control2 = QPoint(current_pos.x() - 50, current_pos.y())
                        path.cubicTo(control1, control2, current_pos)
                        painter.drawPath(path)
                        return  # 绘制完成后直接返回，不执行后续代码

                    port_type = port_info['type']
                    base_line_color = QColor(self.parent_app.get_port_color(port_type))
                    line_color = base_line_color.darker(130).name() # 加深颜色

                    # 设置临时线条样式
                    pen = QPen(QColor(line_color), 2.5)
                    pen.setStyle(Qt.DashLine)
                    painter.setPen(pen) # 加粗线条

                    # 绘制临时线
                    path = QPainterPath(start_pos)
                    control1 = QPoint(start_pos.x() + 50, start_pos.y())
                    control2 = QPoint(current_pos.x() - 50, current_pos.y())
                    path.cubicTo(control1, control2, current_pos)
                    painter.drawPath(path)
        finally:
            # 确保painter被正确关闭
            painter.end()
    # 保留原始的show_node_settings作为兼容方法
    def show_node_settings(self, node):
        """显示节点设置UI - 直接调用update_node_settings方法"""
        self.update_node_settings(node)

class PreviewDisplayWidget(QWidget):
    """高性能图像预览显示组件，完全重写缩放与导航逻辑"""
    def __init__(self, parent_app=None):
        super().__init__(parent_app.preview_scroll.widget()) # 父级应为滚动区域的视图或小部件
        self.parent_app = parent_app

        # 图像相关属性
        self._original_pixmap = QPixmap()  # 原始未缩放图像
        self._display_pixmap = QPixmap()   # 当前展示的缩放后图像
        self._image_rect = QRectF()        # 图像实际显示区域

        # 缩放相关属性
        self.zoom_level = 1.0              # 当前缩放级别
        self.min_zoom = 0.01               # 最小缩放级别
        self.max_zoom = 20.0               # 最大缩放级别
        self.zoom_factor = 1.15            # 每次缩放的倍数

        # 交互状态相关属性
        self.is_panning = False            # 是否正在平移
        self.pan_last_mouse_pos = QPoint() # 平移时上一次鼠标位置
        self.setMouseTracking(True)        # 启用鼠标跟踪

        # 优化配置
        self.setMinimumSize(100, 100)
        self.antialiasing_enabled = True

        # NeoScript 交互状态缓存
        self._neo_context_cache = {}
        self.processed_in_last_run = set()

    def set_image(self, pixmap):
        """设置要显示的图像，保存原始图像并按当前缩放比例显示"""
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            # 保存原始图像
            self._original_pixmap = pixmap
            # 按当前缩放比例更新显示图像
            self._update_display_pixmap()
            # 调整部件大小以匹配图像
            self.setFixedSize(self._display_pixmap.size())
            # 强制立即重绘
            self.repaint()
        elif pixmap is None:
            # 清空图像
            self._original_pixmap = QPixmap()
            self._display_pixmap = QPixmap()
            self.setFixedSize(0, 0)
            self.repaint()

    def _update_display_pixmap(self):
        """根据当前缩放级别更新显示图像"""
        if self._original_pixmap.isNull():
            self._display_pixmap = QPixmap()
            return

        # 计算缩放后尺寸
        orig_size = self._original_pixmap.size()
        new_width = max(1, int(orig_size.width() * self.zoom_level))
        new_height = max(1, int(orig_size.height() * self.zoom_level))
        # 根据性能模式选择不同的转换方式
        transformation_mode = Qt.FastTransformation if (self.parent_app and hasattr(self.parent_app, 'performance_mode_enabled') and self.parent_app.performance_mode_enabled) else Qt.SmoothTransformation

        # 创建缩放后的图像，根据缩放比例选择不同的转换模式
        if self.zoom_level >= 1.0:
            # 放大时使用平滑转换
            self._display_pixmap = self._original_pixmap.scaled(
                new_width, new_height,
                Qt.KeepAspectRatio,
                transformation_mode
            )
        else:
            # 缩小时也使用平滑转换，但性能略低，可考虑根据性能需求调整
            self._display_pixmap = self._original_pixmap.scaled(
                new_width, new_height,
                Qt.KeepAspectRatio,
                transformation_mode
            )

        # 更新显示区域
        self._image_rect = QRectF(0, 0, self._display_pixmap.width(), self._display_pixmap.height())

        # 通知父级应用更新缩放信息显示
        self._update_zoom_info()

    def _update_zoom_info(self):
        """更新缩放信息显示"""
        if self.parent_app and hasattr(self.parent_app, 'zoom_info'):
            zoom_percent = int(self.zoom_level * 100)
            self.parent_app.zoom_info.setText(f"缩放: {zoom_percent}%")

        # 更新尺寸信息
        if self.parent_app and hasattr(self.parent_app, 'image_size_label') and not self._original_pixmap.isNull():
            orig_width = self._original_pixmap.width()
            orig_height = self._original_pixmap.height()
            self.parent_app.image_size_label.setText(f"尺寸: {orig_width} x {orig_height}")

        # 更新主应用的缩放级别
        if self.parent_app:
            self.parent_app.zoom_level = self.zoom_level

    def get_image(self):
        """获取当前显示的图像"""
        return self._display_pixmap

    def get_original_image(self):
        """获取原始未缩放图像"""
        return self._original_pixmap

    def set_zoom(self, new_zoom, center_point=None):
        """设置特定缩放级别，可指定缩放中心点"""
        # 限制缩放范围
        old_zoom = self.zoom_level
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, new_zoom))

        # 检查缩放是否发生变化
        if abs(old_zoom - self.zoom_level) < 1e-6:
            return False

        # 当前滚动位置
        h_bar = self.parent_app.preview_scroll.horizontalScrollBar()
        v_bar = self.parent_app.preview_scroll.verticalScrollBar()
        old_scroll_x = h_bar.value()
        old_scroll_y = v_bar.value()

        # 有指定缩放中心点时保存原始对应位置
        if center_point:
            # 计算缩放中心点在原始图像中的位置
            orig_x = (old_scroll_x + center_point.x()) / old_zoom
            orig_y = (old_scroll_y + center_point.y()) / old_zoom

        # 更新缩放后的图像
        old_size = self._display_pixmap.size()
        self._update_display_pixmap()
        new_size = self._display_pixmap.size()

        # 更新部件大小
        self.setFixedSize(new_size)

        # 如果有指定缩放中心点，调整滚动位置保持该点不变
        if center_point:
            # 计算新的滚动位置，使缩放中心点保持在视野中相同位置
            new_scroll_x = orig_x * self.zoom_level - center_point.x()
            new_scroll_y = orig_y * self.zoom_level - center_point.y()

            # 应用新的滚动位置
            h_bar.setValue(int(new_scroll_x))
            v_bar.setValue(int(new_scroll_y))
        else:
            # 默认保持当前视口中心点
            scale_factor = self.zoom_level / old_zoom
            viewport_size = self.parent_app.preview_scroll.viewport().size()

            # 计算视口中心在原先缩放下的图像坐标
            viewport_center_x = old_scroll_x + viewport_size.width() / 2
            viewport_center_y = old_scroll_y + viewport_size.height() / 2

            # 换算成在原始图像中的坐标
            orig_center_x = viewport_center_x / old_zoom
            orig_center_y = viewport_center_y / old_zoom

            # 计算新的滚动位置
            new_center_x = orig_center_x * self.zoom_level
            new_center_y = orig_center_y * self.zoom_level

            new_scroll_x = new_center_x - viewport_size.width() / 2
            new_scroll_y = new_center_y - viewport_size.height() / 2

            # 应用新的滚动位置
            h_bar.setValue(int(new_scroll_x))
            v_bar.setValue(int(new_scroll_y))

        return True

    def zoom_in(self, center_point=None):
        """放大图像"""
        return self.set_zoom(self.zoom_level * self.zoom_factor, center_point)

    def zoom_out(self, center_point=None):
        """缩小图像"""
        return self.set_zoom(self.zoom_level / self.zoom_factor, center_point)

    def zoom_fit(self):
        """适应窗口大小"""
        if self._original_pixmap.isNull():
            return False

        # 获取滚动区域视口大小
        viewport_size = self.parent_app.preview_scroll.viewport().size()

        # 如果视口尺寸为0，返回
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return False

        # 计算适应窗口的缩放级别
        orig_size = self._original_pixmap.size()
        scale_x = viewport_size.width() / float(orig_size.width())
        scale_y = viewport_size.height() / float(orig_size.height())

        # 取最小值确保完整显示
        fit_zoom = min(scale_x, scale_y) * 1

        # 设置缩放
        return self.set_zoom(fit_zoom)

    def wheelEvent(self, event):
        """处理滚轮事件进行缩放"""
        # 标记事件已处理以防止父级重复处理
        if hasattr(event, '_zoom_handled') and event._zoom_handled:
            event.accept()
            return

        event._zoom_handled = True

        # 获取鼠标位置
        mouse_pos = event.position().toPoint()

        # 检查鼠标是否在图像显示区域内
        if self._display_pixmap.isNull():
            # 如果没有图像，不处理滚轮事件
            event.accept()
            return

        # 确定图像边界
        image_rect = QRect(0, 0, self._display_pixmap.width(), self._display_pixmap.height())
        if not image_rect.contains(mouse_pos):
            # 如果鼠标不在图像区域内，不进行缩放操作
            event.accept()
            return

        # 获取滚轮增量
        delta = event.angleDelta().y()

        if delta > 0:
            # 向上滚动，放大
            self.zoom_in(mouse_pos)
        else:
            # 向下滚动，缩小
            self.zoom_out(mouse_pos)

        event.accept()

    def paintEvent(self, event):
        """绘制图像和叠加层"""
        super().paintEvent(event)
        painter = QPainter(self)

        # 开启抗锯齿，提高绘制质量
        if self.antialiasing_enabled:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 绘制图像
        if not self._display_pixmap.isNull():
            painter.drawPixmap(0, 0, self._display_pixmap)

        # 绘制 NeoScript 叠加层
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            overlay_widget_size = self.size()

            for node in self.parent_app.nodes:
                # 只有当节点为 NeoScript、有绘制函数且连接到预览节点时才绘制叠加层
                if (node.get('script_type') == 'neo' and
                    node.get('render_overlay_func') and
                    self.parent_app.is_upstream_of_preview(node)):

                    # 保存画家状态
                    painter.save()

                    # 获取绘制函数
                    render_func = node['render_overlay_func']

                    # 创建绘制上下文
                    context = {
                        'painter': painter,
                        'app': self.parent_app,
                        'overlay_widget_size': overlay_widget_size,
                        'zoom_level': self.zoom_level,
                        'processed_in_last_run': node['id'] in self.processed_in_last_run,
                        **self.parent_app.get_application_context(node),
                        **self._neo_context_cache.get(node['id'], {})
                    }

                    # 调用绘制函数
                    try:
                        render_func(node.get('params', {}), context)

                    except Exception as e:
                        import traceback
                        traceback.print_exc()

                    # 恢复画家状态
                    painter.restore()

    def mousePressEvent(self, event):
        """处理鼠标按下事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_press_func'):
                    handler = node['handle_mouse_press_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})}
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # 检查是否为平移操作（中键或Alt+左键）
            if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
                self.is_panning = True
                self.pan_last_mouse_pos = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)

        """处理鼠标按下事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_press_func'):
                    handler = node['handle_mouse_press_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})}
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # 处理平移开始
            if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
                self.is_panning = True
                self.pan_last_mouse_pos = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_move_func'):
                    handler = node['handle_mouse_move_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})}
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # 如果正在平移，执行滚动操作
            if self.is_panning:
                # 计算鼠标位移
                current_mouse_pos = event.pos()
                delta = current_mouse_pos - self.pan_last_mouse_pos

                # 获取滚动条并应用平移
                h_bar = self.parent_app.preview_scroll.horizontalScrollBar()
                v_bar = self.parent_app.preview_scroll.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())

                # 更新鼠标位置记录
                self.pan_last_mouse_pos = current_mouse_pos
                event.accept()
            else:
                # 更新像素信息
                if self.parent_app:
                    self.parent_app.update_pixel_info(event)
                super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_release_func'):
                    handler = node['handle_mouse_release_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})}
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # 处理平移结束
            if self.is_panning and (event.button() == Qt.MiddleButton or
                                   (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier)):
                self.is_panning = False
                self.setCursor(Qt.ArrowCursor)
                event.accept()
            else:
                super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单处理"""
        if self.parent_app:
            # 调用主应用的菜单显示函数
            self.parent_app.show_preview_context_menu(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)
import functools
from collections import OrderedDict

class LRUCache:
    """实现LRU(最近最少使用)缓存机制"""
    def __init__(self, max_size=100):
        """
        初始化LRU缓存

        参数:
            max_size: 缓存的最大容量，超出后将移除最久未使用的项目
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key):
        """
        从缓存中获取值，如果存在则移动到最近使用位置

        参数:
            key: 缓存键

        返回:
            缓存的值，如果不存在则返回None
        """
        if key in self.cache:
            # 移到最近使用的位置
            value = self.cache.pop(key)
            self.cache[key] = value
            self.hits += 1
            return value
        self.misses += 1
        return None

    def put(self, key, value):
        """
        将键值对放入缓存，如果键已存在则更新值并移动到最近使用位置，
        如果缓存已满则移除最久未使用的项

        参数:
            key: 缓存键
            value: 要缓存的值
        """
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            # 移除最久未使用的项目(OrderedDict的第一项)
            self.cache.popitem(last=False)
        self.cache[key] = value

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def get_hit_rate(self):
        """
        返回缓存命中率

        返回:
            缓存命中率，范围为0.0到1.0
        """
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self):
        """
        返回缓存统计信息

        返回:
            包含缓存统计信息的字典
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total_requests': total,
            'hit_rate': hit_rate,
            'current_size': len(self.cache),
            'max_size': self.max_size
        }
def eventFilter(self, watched, event):
    """事件过滤器，主要用于节点连接拖拽"""
    # 预览区域的滚轮缩放直接由 PreviewDisplayWidget.wheelEvent 处理，不再在这里处理

    if (hasattr(self, '_is_connecting_filter_active') and self._is_connecting_filter_active and
            watched == self.node_canvas_widget and self.connecting_from):

        if event.type() == QEvent.MouseMove:
            # 处理鼠标移动
            current_pos = event.pos()
            self.connection_current_pos = current_pos
            # 使用 repaint() 强制立即重绘
            self.node_canvas_widget.repaint()
            return True # 事件已处理

        elif event.type() == QEvent.MouseButtonRelease:
            # 处理鼠标释放
            if event.button() == Qt.LeftButton: # 仅处理左键释放
                release_pos = event.pos()

                # 查找目标端口
                target_node, target_port_idx, target_port_type = self.find_port_at_position(release_pos)

                # 获取起点信息
                source_node, source_port_idx, source_port_type = self.connecting_from

                # 先清理状态，移除过滤器，释放鼠标
                self.stop_connection_drag()

                # 再进行验证和连接创建（如果找到有效目标）
                if target_node and target_port_type == 'input':
                     if source_node == target_node:
                         QMessageBox.warning(self, "无效连接", "节点不能连接到自身")
                     else:
                         # 检查类型兼容性
                         try:
                             output_type = source_node['script_info']['outputs'][source_port_idx]
                             input_type = target_node['script_info']['inputs'][target_port_idx]

                             if output_type == input_type or output_type == 'any' or input_type == 'any':
                                 # 尝试连接
                                 success = self.create_connection(source_node, source_port_idx, target_node, target_port_idx)
                             else:
                                 QMessageBox.warning(self, "类型不匹配", f"输出端口类型 '{output_type}' 与输入端口类型 '{input_type}' 不兼容")
                         except (KeyError, IndexError) as e:
                             QMessageBox.warning(self, "连接错误", "检查端口类型时出错")

                return True # 事件已处理

    # 如果事件不是我们在此过滤器中处理的，则调用基类实现，允许默认处理
    return super().eventFilter(watched, event)
    def mousePressEvent(self, event):
        """处理鼠标按下事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_press_func'):
                    handler = node['handle_mouse_press_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})} # 合并节点状态
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break # 第一个处理的 NeoScript 优先
                    except Exception as e:
                        print(f"Error in handle_mouse_press for node {node['title']}: {e}")
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # NeoScript 未处理，执行平移逻辑
            if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier):
                self.is_panning = True
                self.pan_last_mouse_pos = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event) # 其他按钮传递给父类

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_move_func'):
                    handler = node['handle_mouse_move_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})} # 合并节点状态
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        print(f"Error in handle_mouse_move for node {node['title']}: {e}")
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # NeoScript 未处理，执行平移逻辑
            if self.is_panning:
                current_mouse_pos = event.pos()
                delta = current_mouse_pos - self.pan_last_mouse_pos # 计算相对上次的位移

                # 获取滚动条并应用平移
                h_bar = self.parent_app.preview_scroll.horizontalScrollBar()
                v_bar = self.parent_app.preview_scroll.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())

                # 更新上一次鼠标位置
                self.pan_last_mouse_pos = current_mouse_pos
                event.accept()
            else:
                # 更新像素信息（如果需要）
                if self.parent_app:
                    self.parent_app.update_pixel_info(event)
                super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件，优先传递给 NeoScript"""
        # 先检查 NeoScript 是否处理
        handled_by_neo = False
        if self.parent_app and hasattr(self.parent_app, 'nodes'):
            context = {
                'event': event,
                'app': self.parent_app,
                'overlay_widget_size': self.size(),
                'zoom_level': self.zoom_level,
                **self.parent_app.get_application_context()
            }
            for node in self.parent_app.nodes:
                if node.get('script_type') == 'neo' and node.get('handle_mouse_release_func'):
                    handler = node['handle_mouse_release_func']
                    node_context = {**context, **self._neo_context_cache.get(node['id'], {})} # 合并节点状态
                    try:
                        if handler(node.get('params', {}), node_context, lambda: self.update()):
                            # 更新缓存
                            self._neo_context_cache[node['id']] = {
                                k: v for k, v in node_context.items()
                                if k in ['_interactive_shape_bounds', '_shape_dragging',
                                        '_shape_center_x', '_shape_center_y',
                                        '_drag_offset_x', '_drag_offset_y', '_current_mouse_pos']
                            }
                            handled_by_neo = True
                            event.accept()
                            break
                    except Exception as e:
                        print(f"Error in handle_mouse_release for node {node['title']}: {e}")
                        import traceback
                        traceback.print_exc()

        if not handled_by_neo:
            # NeoScript 未处理，执行平移逻辑结束处理
            if self.is_panning and (event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier)):
                self.is_panning = False
                self.setCursor(Qt.ArrowCursor)
                event.accept()
            else:
                super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单处理"""
        current_time = time.time()

        # 如果距离上次菜单显示不到0.5秒，则忽略此次右键点击
        if current_time - self.last_context_menu_time > 0.5:
            if self.parent_app:
                # 调用主应用的菜单显示函数
                self.parent_app.show_preview_context_menu(event.globalPos())
                self.last_context_menu_time = current_time  # 更新时间戳
                event.accept()
            else:
                super().contextMenuEvent(event)
        else:
            # 时间太短，忽略此次右键菜单事件
            event.accept()


# 修改主程序的main函数
def main():
    """主函数"""
    # 保存原始的print函数
    original_print = print

    # 调试模式标志（可以从配置文件、命令行参数或环境变量获取）
    DEBUG_MODE = True  # 默认关闭调试输出

    # 重载print函数
    # def custom_print(*args, **kwargs):
    #     if DEBUG_MODE:
    #         # 如果调试模式开启，使用原始print函数
    #         original_print(*args, **kwargs)
    #     # 如果调试模式关闭，什么也不做

    # # 替换当前模块的print函数
    # import builtins
    # builtins.print = custom_print
    # 设置高DPI支持
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 添加全局图像缩放质量设置
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QImageReader.setAllocationLimit(0)  # 不限制图像内存分配

    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建应用实例
    window = TunnelNX()

    # 创建自定义节点画布并设置父应用引用
    custom_node_canvas = NodeCanvasWidget()
    custom_node_canvas.parent_app = window
    window.node_canvas_widget = custom_node_canvas

    # 将自定义画布添加到滚动区域
    window.node_scroll.setWidget(custom_node_canvas)

    # 为 NodeCanvasWidget 设置上下文菜单
    custom_node_canvas.setContextMenuPolicy(Qt.CustomContextMenu)
    custom_node_canvas.customContextMenuRequested.connect(window.on_canvas_right_click)

    # 显示窗口
    window.show()

    # 运行主循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
