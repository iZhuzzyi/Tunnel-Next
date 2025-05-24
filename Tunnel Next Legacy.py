import os
import sys
import time
import importlib.util
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import cv2
import numpy as np
from PIL import Image, ImageTk
import shutil


class TunnelNX:
    def __init__(self, root):
        self.root = root
        self.root.title("Tunnel NX Legacy")
        self.root.geometry("1280x720")  # 16:9 初始尺寸
        self.root.minsize(1024, 576)

        # 设置现代Aero风格
        self.style = ttkb.Style(theme="darkly")

        # 改进的Aero样式配置
        self.configure_aero_styles()

        # 创建主框架 - 使用网格布局代替pack
        self.main_frame = ttk.Frame(self.root, style="Aero.TFrame")
        self.main_frame.pack(fill="both", expand=True)

        # 创建主网格布局
        self.setup_main_layout()

        # 初始化节点管理
        self.nodes = []  # 节点列表
        self.connections = []  # 节点连接列表
        self.next_node_id = 0  # 下一个节点ID
        self.selected_node = None  # 当前选择的节点
        self.dragging = False  # 是否正在拖拽
        self.connecting_from = None  # 拖拽连接的起始点
        self.selected_port = None  # 当前选择的端口

        # 初始化图像数据
        self.current_image = None  # 当前处理的图像
        self.current_image_path = None  # 当前图像路径
        WORKFOLDER_FILE = "WORKFOLDER"
        if os.path.exists(WORKFOLDER_FILE):
            # 如果存在，读取文件内容并赋值给self.work_folder
            with open(WORKFOLDER_FILE, 'r') as f:
                self.work_folder = f.read().strip()  # 使用strip()去除可能的空白字符
        else:
            # 如果不存在，设置默认值并创建文件
            self.work_folder = "C:\\photos"
            with open(WORKFOLDER_FILE, 'w') as f:
                f.write(self.work_folder)  # 默认工作文件夹
        self.zoom_level = 1.0  # 添加缩放级别追踪

        # 确保工作文件夹存在
        os.makedirs(self.work_folder, exist_ok=True)

        # 确保nodegraphs文件夹存在
        self.nodegraphs_folder = os.path.join(self.work_folder, "nodegraphs")
        os.makedirs(self.nodegraphs_folder, exist_ok=True)

        # 确保temp文件夹存在
        self.temp_folder = os.path.join(self.nodegraphs_folder, "temp")
        os.makedirs(self.temp_folder, exist_ok=True)

        # 确保脚本文件夹存在
        self.scripts_folder = "TunnelNX_scripts"
        os.makedirs(self.scripts_folder, exist_ok=True)

        # 添加工具栏按钮
        self.create_toolbar_buttons()

        # 扫描并加载脚本
        self.script_registry = {}  # 脚本注册表
        self.scan_scripts()

        # 初始化胶片预览
        self.film_preview.pack(fill="both", expand=True)
        self.update_film_preview()

        # 创建右键菜单
        self.create_context_menu()

        # 绑定事件 - 添加这一行是关键
        self.bind_events()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # 初始化图像数据 - 修改这一部分
        self.current_image = None  # 当前处理的图像
        self.current_image_path = None  # 当前图像路径
        self.work_folder = "C:\\photos"  # 默认工作文件夹
        self.zoom_level = 1.0  # 添加缩放级别追踪
        # 添加这一行在方法的最后，确保所有UI元素都已创建
        self.init_zoom_functionality()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_zoom_functionality(self):
        """初始化和配置缩放功能"""
        # 确保缩放级别已初始化
        self.zoom_level = 1.0

        # 更新缩放信息显示
        if hasattr(self, 'zoom_info'):
            self.zoom_info.config(text="缩放: 100%")

        # 添加缩放键盘快捷键和右键菜单
        self.add_zoom_keyboard_shortcuts()

        # 启用图像拖动功能
        self.enable_image_panning()

        # 添加鼠标滚轮缩放
        def on_mousewheel(event):
            # Windows 滚轮事件处理
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

        def on_mousewheel_linux(event):
            # Linux 滚轮事件处理
            if event.num == 4:
                self.zoom_in()
            elif event.num == 5:
                self.zoom_out()

        # 绑定鼠标滚轮事件到预览画布
        if sys.platform == 'win32':
            self.preview_canvas.bind("<MouseWheel>", on_mousewheel)
        else:
            self.preview_canvas.bind("<Button-4>", on_mousewheel_linux)
            self.preview_canvas.bind("<Button-5>", on_mousewheel_linux)

        # 添加键盘快捷键提示到缩放按钮的工具提示
        if hasattr(self, 'create_tooltip'):
            for widget in self.preview_area.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Frame):
                            for button in child.winfo_children():
                                if isinstance(button, ttk.Button):
                                    if button['text'] == "+":
                                        self.create_tooltip(button, "放大 (Ctrl+加号)")
                                    elif button['text'] == "-":
                                        self.create_tooltip(button, "缩小 (Ctrl+减号)")
                                    elif button['text'] == "□":
                                        self.create_tooltip(button, "适应窗口 (Ctrl+0)")
    def configure_aero_styles(self):
        """Improve dark theme style configuration"""
        # Main background color - darker
        self.root.configure(bg="#1a1a1a")

        # Base frame style - darker
        self.style.configure("Aero.TFrame",
                             background="#1a1a1a")

        # Simplified border effect - ensure dark background
        self.style.configure("Glass.TFrame",
                             background="#1a1a1a",
                             relief="flat",
                             borderwidth=0)

        # Panel effect - darker
        self.style.configure("Panel.TFrame",
                             background="#222222")

        # Active panel effect - darker
        self.style.configure("ActivePanel.TFrame",
                             background="#2a2a2a")

        # Improved button style - darker background
        self.style.configure("Aero.TButton",
                             font=("微软雅黑", 9),
                             background="#333333",
                             foreground="#ffffff",
                             relief="flat",
                             padding=4)

        # Button state changes - darker colors
        self.style.map("Aero.TButton",
                       background=[('active', '#444444'), ('pressed', '#222222')],
                       relief=[('pressed', 'flat')])

        # Tool button style - darker
        self.style.configure("Tool.TButton",
                             font=("微软雅黑", 9),
                             padding=6,
                             width=6,
                             background="#333333")

        # Label style - darker
        self.style.configure("Aero.TLabel",
                             font=("微软雅黑", 9),
                             background="#222222",
                             foreground="#ffffff")

        # Title style - darker
        self.style.configure("Title.TLabel",
                             font=("微软雅黑", 10, "bold"),
                             background="#1a1a1a",
                             foreground="#ffffff")

        # Settings panel style - darker
        self.style.configure("Settings.TFrame",
                             background="#222222",
                             padding=3)

        # Node style - darker
        self.style.configure("Node.TFrame",
                             background="#333333",
                             relief="flat",
                             borderwidth=0)

        # Port style - darker
        self.style.configure("Port.TFrame",
                             background="#555555",
                             relief="flat",
                             borderwidth=0)

        # Scrollbar style - darker
        self.style.configure("Aero.Vertical.TScrollbar",
                             troughcolor="#222222",
                             background="#333333",
                             arrowcolor="#ffffff")

        # Also configure paned window styles to ensure dark theme consistency
        self.style.configure("VPaned.TPanedwindow",
                             background="#1a1a1a")
        self.style.configure("HPaned.TPanedwindow",
                             background="#1a1a1a")

    def setup_main_layout(self):
        """设置主布局 - 使用更灵活的布局方案"""
        # 创建顶部工具栏 (8% 高度)
        self.top_bar = ttk.Frame(self.main_frame, style="Glass.TFrame")
        self.top_bar.pack(fill="x", side="top", pady=3, ipady=3)

        # 左侧工具区
        self.top_tools_frame = ttk.Frame(self.top_bar, style="Aero.TFrame")
        self.top_tools_frame.pack(side="left", fill="x", expand=True)

        # 右侧任务区
        self.top_task_frame = ttk.Frame(self.top_bar, style="Aero.TFrame")
        self.top_task_frame.pack(side="right", fill="x", expand=True)

        # 设置任务区默认显示
        self.task_label = ttk.Label(self.top_task_frame, text="Tunnel NX Legacy (Deprecated)",
                                    font=("微软雅黑", 12), style="Aero.TLabel")
        self.task_label.pack(side="top", pady=5)

        # 创建中间工作区 - 使用可调整的面板
        self.work_area = ttk.Frame(self.main_frame, style="Aero.TFrame")
        self.work_area.pack(fill="both", expand=True, pady=3)

        # 移除底部选项卡区域，改为直接使用简单的底部预览区
        self.bottom_preview = ttk.Frame(self.main_frame, style="Glass.TFrame")
        self.bottom_preview.pack(fill="x", side="bottom", pady=3)

        # 创建简单的胶片预览区
        self.film_preview = ttk.Frame(self.bottom_preview, style="Panel.TFrame")
        self.film_preview.pack(fill="both", expand=True)

        # 创建可调整的工作区域
        self.create_paned_areas()

        # 添加预览区UI
        self.create_preview_area()

        # 添加节点图区域UI
        self.create_node_graph_area()

        # 添加节点设置区域UI
        self.create_node_settings_area()

        # 添加信息面板
        self.create_info_panel()

    def create_paned_areas(self):
        """创建可调整的工作区面板 - 改进的面板设计"""
        # 垂直分割 - 使用样式
        self.vertical_paned = ttk.PanedWindow(self.work_area, orient=tk.VERTICAL, style="VPaned.TPanedwindow")
        self.vertical_paned.pack(fill="both", expand=True)

        # 上部分的水平分割 - 使用样式
        self.top_paned = ttk.PanedWindow(self.vertical_paned, orient=tk.HORIZONTAL, style="HPaned.TPanedwindow")

        # 下部分的水平分割 - 使用样式
        self.bottom_paned = ttk.PanedWindow(self.vertical_paned, orient=tk.HORIZONTAL, style="HPaned.TPanedwindow")

        # 创建四个区域 - 使用玻璃效果边框
        self.preview_area = ttk.Frame(self.top_paned, style="Glass.TFrame")
        self.node_graph_area = ttk.Frame(self.top_paned, style="Glass.TFrame")

        # 添加信息面板区域
        self.info_panel = ttk.Frame(self.bottom_paned, style="Glass.TFrame")
        self.node_settings_area = ttk.Frame(self.bottom_paned, style="Glass.TFrame")

        # 添加到面板中 - 设置更合理的权重
        self.top_paned.add(self.preview_area, weight=55)
        self.top_paned.add(self.node_graph_area, weight=45)

        self.bottom_paned.add(self.info_panel, weight=30)
        self.bottom_paned.add(self.node_settings_area, weight=70)

        # 将上下面板添加到垂直面板 - 设置更合理的权重
        self.vertical_paned.add(self.top_paned, weight=70)
        self.vertical_paned.add(self.bottom_paned, weight=30)

    def create_toolbar_buttons(self):
        """创建改进的工具栏按钮 - 更好的视觉效果和分组"""
        # 创建工具栏
        self.toolbar = ttk.Frame(self.top_tools_frame, style="Panel.TFrame")
        self.toolbar.pack(side="left", fill="x", padx=5)

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
            group_frame = ttk.Frame(self.toolbar, style="Glass.TFrame")
            group_frame.pack(side="left", padx=10, pady=5)

            # 添加工具组中的按钮
            for tool in group:
                # 创建工具按钮框架
                btn_frame = ttk.Frame(group_frame, style="Glass.TFrame")
                btn_frame.pack(side="left", padx=3, pady=3)

                # 创建按钮 - 使用更美观的样式
                btn = ttk.Button(btn_frame,
                                 text=f"{tool['emoji']}\n{tool['text']}",
                                 command=tool["command"],
                                 style="Tool.TButton")
                btn.pack(padx=1, pady=1)

                # 存储按钮引用
                self.toolbar_buttons.append(btn)

                # 设置工具提示
                self.create_tooltip(btn, tool["tooltip"])

                # 绑定悬停事件创建发光效果
                btn.bind("<Enter>", lambda e, b=btn: self.button_hover_on(e, b))
                btn.bind("<Leave>", lambda e, b=btn: self.button_hover_off(e, b))

    def create_tooltip(self, widget, text):
        """为控件创建工具提示"""
        tooltip = tk.Label(self.root, text=text, bg="#666666", fg="white",
                           relief="solid", borderwidth=1, font=("微软雅黑", 9))
        tooltip.place_forget()

        def enter(event):
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            tooltip.place(x=x, y=y, anchor="n")

        def leave(event):
            tooltip.place_forget()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def button_hover_on(self, event, button):
        """按钮悬停开始效果 - 增强发光效果"""
        # 改变按钮样式实现发光效果
        if hasattr(button, 'master'):
            button.master.configure(background="#666666")

        # 添加更明亮的边框
        if button["style"] == "Tool.TButton":
            button.configure(style="Aero.TButton")

    def button_hover_off(self, event, button):
        """按钮悬停结束效果"""
        # 恢复原始样式
        if hasattr(button, 'master'):
            button.master.configure(background="#444444")

        # 恢复原始按钮样式
        if button["style"] == "Aero.TButton" and "Tool.TButton" in self.style.layout_names():
            button.configure(style="Tool.TButton")

    def create_preview_area(self):
        """创建改进的预览区UI"""
        # 预览区标题栏
        preview_header = ttk.Frame(self.preview_area, style="Panel.TFrame")
        preview_header.pack(side="top", fill="x")

        # 预览区标题
        preview_title = ttk.Label(preview_header, text="图像预览", style="Title.TLabel")
        preview_title.pack(side="left", padx=10, pady=5)

        # 添加缩放信息
        self.zoom_info = ttk.Label(preview_header, text="缩放: 100%", style="Aero.TLabel")
        self.zoom_info.pack(side="right", padx=10, pady=5)

        # 添加缩放控制按钮
        zoom_controls = ttk.Frame(preview_header, style="Panel.TFrame")
        zoom_controls.pack(side="right", padx=5)

        zoom_in_btn = ttk.Button(zoom_controls, text="+", width=2,
                                 command=self.zoom_in, style="Aero.TButton")
        zoom_in_btn.pack(side="left", padx=2)

        zoom_fit_btn = ttk.Button(zoom_controls, text="□", width=2,
                                  command=self.zoom_fit, style="Aero.TButton")
        zoom_fit_btn.pack(side="left", padx=2)

        zoom_out_btn = ttk.Button(zoom_controls, text="-", width=2,
                                  command=self.zoom_out, style="Aero.TButton")
        zoom_out_btn.pack(side="left", padx=2)

        # 创建预览区画布框架 - 确保背景色一致
        preview_frame = ttk.Frame(self.preview_area, style="Panel.TFrame")
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 添加预览区滚动条
        preview_v_scroll = ttk.Scrollbar(preview_frame, orient="vertical", style="Aero.Vertical.TScrollbar")
        preview_h_scroll = ttk.Scrollbar(preview_frame, orient="horizontal")
        preview_v_scroll.pack(side="right", fill="y")
        preview_h_scroll.pack(side="bottom", fill="x")

        # 预览区画布 - 支持滚动 (确保背景色设置正确)
        self.preview_canvas = tk.Canvas(preview_frame,
                                        bg="#222222",  # Dark background
                                        highlightthickness=0,
                                        xscrollcommand=preview_h_scroll.set,
                                        yscrollcommand=preview_v_scroll.set)
        self.preview_canvas.pack(fill="both", expand=True)

        # 配置滚动条
        preview_v_scroll.config(command=self.preview_canvas.yview)
        preview_h_scroll.config(command=self.preview_canvas.xview)

        # 初始化缩放状态
        self.zoom_level = 1.0

        # 添加右键菜单
        self.preview_context_menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")
        self.preview_context_menu.add_command(label="放大 (+)", command=self.zoom_in)
        self.preview_context_menu.add_command(label="缩小 (-)", command=self.zoom_out)
        self.preview_context_menu.add_command(label="适应窗口 (□)", command=self.zoom_fit)
        self.preview_context_menu.add_separator()
        self.preview_context_menu.add_command(label="复制到剪贴板", command=self.copy_image_to_clipboard)
        self.preview_context_menu.add_command(label="导出当前视图", command=self.export_current_view)

        # 绑定右键菜单
        self.preview_canvas.bind("<Button-3>", self.show_preview_context_menu)
        # 添加状态栏
        self.preview_status_bar = ttk.Frame(self.preview_area, style="Panel.TFrame")
        self.preview_status_bar.pack(side="bottom", fill="x")

        # 创建状态栏标签
        self.pixel_info_label = ttk.Label(self.preview_status_bar, text="坐标: -- , --  RGB: --, --, --",
                                          style="Aero.TLabel")
        self.pixel_info_label.pack(side="left", padx=10)

        self.image_size_label = ttk.Label(self.preview_status_bar, text="尺寸: -- x --",
                                          style="Aero.TLabel")
        self.image_size_label.pack(side="right", padx=10)

        # 绑定鼠标移动事件以更新坐标信息
        self.preview_canvas.bind("<Motion>", self.update_pixel_info)
    def update_pixel_info(self, event):
        """更新像素信息显示"""
        if not hasattr(self, 'preview_image') or not self.preview_image:
            return

        # 获取Canvas坐标
        canvas_x = self.preview_canvas.canvasx(event.x)
        canvas_y = self.preview_canvas.canvasy(event.y)

        # 获取图像项的坐标
        image_item = self.preview_canvas.find_withtag("preview_image")
        if not image_item:
            return

        # 获取图像位置
        img_x, img_y = self.preview_canvas.coords(image_item)

        # 计算相对于图像的坐标
        rel_x = int((canvas_x - img_x) / self.zoom_level)
        rel_y = int((canvas_y - img_y) / self.zoom_level)

        # 检查坐标是否在图像范围内
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
            self.image_size_label.config(text=f"尺寸: {img_width} x {img_height}")

            # 检查坐标是否在图像范围内
            if 0 <= rel_x < img_width and 0 <= rel_y < img_height:
                # 获取像素颜色
                try:
                    if len(self.current_image.shape) == 3:  # 彩色图像
                        # 根据图像类型获取像素值
                        if self.current_image.dtype == np.float32:
                            r, g, b = self.current_image[rel_y, rel_x]
                            # 将浮点值缩放到0-255范围
                            r = int(r * 255)
                            g = int(g * 255)
                            b = int(b * 255)
                        elif self.current_image.dtype == np.uint16:
                            r, g, b = self.current_image[rel_y, rel_x]
                            r = int(r / 256)
                            g = int(g / 256)
                            b = int(b / 256)
                        else:
                            r, g, b = self.current_image[rel_y, rel_x]

                        # 更新像素信息
                        self.pixel_info_label.config(text=f"坐标: {rel_x}, {rel_y}  RGB: {r}, {g}, {b}")
                    else:  # 灰度图像
                        if self.current_image.dtype == np.float32:
                            value = self.current_image[rel_y, rel_x]
                            # 将浮点值缩放到0-255范围
                            value = int(value * 255)
                        elif self.current_image.dtype == np.uint16:
                            value = int(self.current_image[rel_y, rel_x] / 256)
                        else:
                            value = self.current_image[rel_y, rel_x]

                        # 更新像素信息
                        self.pixel_info_label.config(text=f"坐标: {rel_x}, {rel_y}  值: {value}")
                except IndexError:
                    # 索引错误时更新为默认值
                    self.pixel_info_label.config(text=f"坐标: {rel_x}, {rel_y}  RGB: --, --, --")
            else:
                # 超出图像范围时更新为默认值
                self.pixel_info_label.config(text=f"坐标: -- , --  RGB: --, --, --")

    def show_preview_context_menu(self, event):
        """显示预览区右键菜单"""
        # 确保预览区有图像才显示菜单
        if hasattr(self, 'preview_image') and self.preview_image:
            self.preview_context_menu.tk_popup(event.x_root, event.y_root)
    def create_node_graph_area(self):
        """创建改进的节点图区域UI"""
        # 节点图标题栏
        node_header = ttk.Frame(self.node_graph_area, style="Panel.TFrame")
        node_header.pack(side="top", fill="x")

        # 节点图标题
        node_graph_title = ttk.Label(node_header, text="节点图", style="Title.TLabel")
        node_graph_title.pack(side="left", padx=10, pady=5)

        # 添加节点按钮组
        node_buttons = ttk.Frame(node_header, style="Panel.TFrame")
        node_buttons.pack(side="right", padx=5)

        # 添加节点按钮
        add_node_btn = ttk.Button(node_buttons, text="+ 添加节点",
                                  style="Aero.TButton",
                                  command=self.show_node_menu)
        add_node_btn.pack(side="right", padx=5, pady=3)

        # 添加删除节点按钮
        del_node_btn = ttk.Button(node_buttons, text="- 删除节点",
                                  style="Aero.TButton",
                                  command=self.delete_selected_node)
        del_node_btn.pack(side="right", padx=5, pady=3)

        # 创建节点图框架 - 确保背景色一致
        node_frame = ttk.Frame(self.node_graph_area, style="Panel.TFrame")
        node_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 添加节点图滚动条
        node_v_scroll = ttk.Scrollbar(node_frame, orient="vertical", style="Aero.Vertical.TScrollbar")
        node_h_scroll = ttk.Scrollbar(node_frame, orient="horizontal")
        node_v_scroll.pack(side="right", fill="y")
        node_h_scroll.pack(side="bottom", fill="x")

        # 节点图画布 - 支持滚动 (确保背景色设置正确)
        self.node_canvas = tk.Canvas(node_frame,
                                     bg="#000000",  # Light gray background instead of dark
                                     highlightthickness=0,
                                     xscrollcommand=node_h_scroll.set,
                                     yscrollcommand=node_v_scroll.set)
        self.node_canvas.pack(fill="both", expand=True)

        # 配置滚动条
        node_v_scroll.config(command=self.node_canvas.yview)
        node_h_scroll.config(command=self.node_canvas.xview)

        # 用于绘制连接线的临时变量
        self.temp_line = None

        # 添加网格背景绘制
        self.draw_node_grid()

    def copy_image_to_clipboard(self):
        """复制当前预览图像到剪贴板"""
        # 获取当前显示的图像
        if hasattr(self, 'preview_image'):
            try:
                # 对于Windows，使用win32clipboard
                if sys.platform == 'win32':
                    try:
                        import win32clipboard
                        from io import BytesIO

                        # 获取PIL图像对象
                        if hasattr(self.preview_image, 'tk'):
                            image = self.preview_image._PhotoImage__photo.subsample(1)
                            # 将TkImage转换为PIL Image
                            from PIL import ImageTk
                            pil_img = ImageTk._get_image_from_kw(image)
                        else:
                            # 查找预览节点并获取原始图像
                            preview_node = None
                            for node in self.nodes:
                                if node['title'] == '预览节点':
                                    preview_node = node
                                    break

                            if preview_node and 'processed_outputs' in preview_node:
                                if 'f32bmp' in preview_node['processed_outputs']:
                                    img = preview_node['processed_outputs']['f32bmp']
                                    if img.dtype == np.float32:
                                        # 将32位浮点图像转换为8位用于显示
                                        img_display = (img * 255).clip(0, 255).astype(np.uint8)
                                    else:
                                        img_display = img
                                elif 'tif16' in preview_node['processed_outputs']:
                                    img = preview_node['processed_outputs']['tif16']
                                    if img.dtype == np.uint16:
                                        img_display = (img / 256).astype(np.uint8)
                                    else:
                                        img_display = img
                                else:
                                    messagebox.showinfo("提示", "没有可复制的图像")
                                    return
                                
                                pil_img = Image.fromarray(img_display)
                            else:
                                messagebox.showinfo("提示", "没有可复制的图像")
                                return

                        # 将图像保存到内存中
                        output = BytesIO()
                        pil_img.convert('RGB').save(output, 'BMP')
                        data = output.getvalue()[14:]  # 去掉BMP文件头
                        output.close()

                        # 复制到剪贴板
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                        win32clipboard.CloseClipboard()

                        messagebox.showinfo("复制成功", "图像已复制到剪贴板")
                    except ImportError:
                        messagebox.showinfo("提示", "复制到剪贴板需要安装pywin32库")
                else:
                    # 对于其他平台，提示不支持
                    messagebox.showinfo("提示", "当前平台不支持复制图像到剪贴板")
            except Exception as e:
                messagebox.showerror("复制错误", f"复制图像失败: {str(e)}")
        else:
            messagebox.showinfo("提示", "没有可复制的图像")
    def draw_node_grid(self):
        """Draw grid background for node graph area"""
        # Clear existing grid
        self.node_canvas.delete("grid")

        # Get canvas dimensions
        width = self.node_canvas.winfo_width()
        height = self.node_canvas.winfo_height()

        # If dimensions are too small, set minimum values
        width = max(width, 1000)
        height = max(height, 1000)

        # Set grid size
        grid_size = 20

        # Draw grid lines with dark gray color
        for x in range(0, width, grid_size):
            # Vertical lines
            self.node_canvas.create_line(x, 0, x, height,
                                         fill="#776d91", tags="grid")  # Changed to dark gray

        for y in range(0, height, grid_size):
            # Horizontal lines
            self.node_canvas.create_line(0, y, width, y,
                                         fill="#776d91", tags="grid")  # Changed to dark gray

        # Ensure grid is at the bottom layer
        self.node_canvas.tag_lower("grid")

        # Set scroll region
        self.node_canvas.config(scrollregion=(0, 0, width, height))

    def create_node_settings_area(self):
        """显示节点设置UI"""
        # 节点设置标题栏
        settings_header = ttk.Frame(self.node_settings_area, style="Panel.TFrame")
        settings_header.pack(side="top", fill="x")

        # 节点设置标题
        self.settings_title = ttk.Label(settings_header, text="节点设置", style="Title.TLabel")
        self.settings_title.pack(side="left", padx=10, pady=5)

        # 创建设置框架直接在node_settings_area中
        self.settings_frame = ttk.Frame(self.node_settings_area, style="Settings.TFrame")
        self.settings_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 默认显示"无选中节点"提示
        self.no_node_label = ttk.Label(self.settings_frame,
                                       text="请选择一个节点查看设置",
                                       style="Aero.TLabel")
        self.no_node_label.pack(expand=True, pady=20)

    def create_info_panel(self):
        """创建信息面板 - 显示图像和处理信息"""
        # 信息面板标题栏
        info_header = ttk.Frame(self.info_panel, style="Panel.TFrame")
        info_header.pack(side="top", fill="x")

        # 信息面板标题
        info_title = ttk.Label(info_header, text="图像信息", style="Title.TLabel")
        info_title.pack(side="left", padx=10, pady=5)

        # 创建信息内容区域
        info_content = ttk.Frame(self.info_panel, style="Panel.TFrame")
        info_content.pack(fill="both", expand=True, padx=20, pady=5)

        # 图像信息标签
        self.image_info = {
            "文件名": ttk.Label(info_content, text="文件名: 未加载", style="Aero.TLabel"),
            "尺寸": ttk.Label(info_content, text="尺寸: 0 x 0", style="Aero.TLabel"),
            "类型": ttk.Label(info_content, text="类型: 未知", style="Aero.TLabel"),
            "节点数": ttk.Label(info_content, text="节点数: 0", style="Aero.TLabel")
        }

        # 放置信息标签
        row = 0
        for label in self.image_info.values():
            label.grid(row=row, column=0, sticky="w", padx=5, pady=3)
            row += 1

    def export_current_view(self):
        """导出当前预览视图"""
        if hasattr(self, 'preview_image'):
            try:
                # 获取保存路径
                file_path = filedialog.asksaveasfilename(
                    initialdir=self.work_folder,
                    title="导出当前视图",
                    filetypes=(("JPEG 文件", "*.jpg"), ("PNG 文件", "*.png"),
                               ("TIFF 文件", "*.tif"), ("所有文件", "*.*"))
                )

                if not file_path:
                    return

                # 确保文件有正确的扩展名
                if not any(file_path.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']):
                    file_path += '.jpg'  # 默认添加jpg扩展名

                # 获取当前显示的图像
                if hasattr(self.preview_image, 'tk'):
                    # 从TkImage获取PIL图像
                    image = self.preview_image._PhotoImage__photo
                    # 将TkImage转换为PIL Image
                    from PIL import ImageTk
                    pil_img = ImageTk._get_image_from_kw(image)
                else:
                    # 从预览节点获取图像并应用当前缩放
                    preview_node = None
                    for node in self.nodes:
                        if node['title'] == '预览节点':
                            preview_node = node
                            break

                    if preview_node and 'processed_outputs' in preview_node:
                        if 'f32bmp' in preview_node['processed_outputs']:
                            img = preview_node['processed_outputs']['f32bmp']
                            if img.dtype == np.float32:
                                # 将32位浮点图像转换为8位用于显示
                                img_display = (img * 255).clip(0, 255).astype(np.uint8)
                            else:
                                img_display = img
                        elif 'tif16' in preview_node['processed_outputs']:
                            img = preview_node['processed_outputs']['tif16']
                            if img.dtype == np.uint16:
                                img_display = (img / 256).astype(np.uint8)
                            else:
                                img_display = img
                        else:
                            messagebox.showinfo("提示", "没有可导出的图像")
                            return
                            
                        pil_img = Image.fromarray(img_display)

                        # 应用当前缩放
                        orig_width, orig_height = pil_img.size
                        new_width = int(orig_width * self.zoom_level)
                        new_height = int(orig_height * self.zoom_level)

                        if self.zoom_level < 1.0:
                            pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                        else:
                            pil_img = pil_img.resize((new_width, new_height), Image.BICUBIC)
                    else:
                        messagebox.showinfo("提示", "没有可导出的图像")
                        return

                # 保存图像
                pil_img.save(file_path)
                messagebox.showinfo("导出成功", f"当前视图已导出到:\n{file_path}")

            except Exception as e:
                messagebox.showerror("导出错误", f"导出视图失败: {str(e)}")
        else:
            messagebox.showinfo("提示", "没有可导出的图像")

    def show_port_context_menu(self, event, node, port_idx, port_type):
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

        # 清除菜单项
        self.port_menu.delete(0, tk.END)

        # 添加菜单项
        if has_connection:
            self.port_menu.add_command(label="断开此连接", command=self.disconnect_port)
        else:
            self.port_menu.add_command(label="创建连接",
                                       command=lambda: self.start_connection(event, node, port_idx, port_type))

        # 显示菜单
        try:
            self.port_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.port_menu.grab_release()

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
                self.node_canvas.delete(conn['line_id'])
                conn_to_remove.append(conn)

        # 从连接列表中移除
        for conn in conn_to_remove:
            self.connections.remove(conn)

        # 处理节点图并更新预览
        self.process_node_graph()

        # 通知用户
        print(f"已断开节点 {node['title']} 的 {port_type} 端口 {port_idx} 的连接")

    def create_context_menu(self):
        """创建右键菜单 - 改进样式和选项"""
        # 创建节点右键菜单
        self.node_menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")

        # 添加菜单项
        self.node_menu.add_command(label="编辑节点", command=self.show_node_settings)
        self.node_menu.add_command(label="删除节点", command=self.delete_selected_node)
        self.node_menu.add_separator()
        self.node_menu.add_command(label="连接到...", command=self.start_connection)
        self.node_menu.add_command(label="断开连接", command=self.disconnect_node)
        self.node_menu.add_separator()
        self.node_menu.add_command(label="复制节点", command=self.copy_node)
        self.node_menu.add_command(label="粘贴节点", command=self.paste_node)

        # 创建画布右键菜单
        self.canvas_menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")
        self.canvas_menu.add_command(label="添加节点", command=self.show_node_menu)
        self.canvas_menu.add_command(label="整理节点", command=self.arrange_nodes)
        self.canvas_menu.add_command(label="密集整理节点", command=self.arrange_nodes_dense)  # 添加新的密集整理选项
        self.canvas_menu.add_command(label="清除所有节点", command=self.clear_all_nodes)

        # 添加端口右键菜单
        self.port_menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")
        # 菜单项会在显示菜单时动态添加

    def bind_events(self):
        """绑定事件处理"""
        # 节点画布事件
        self.node_canvas.bind("<Button-1>", self.on_canvas_click)
        self.node_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.node_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.node_canvas.bind("<Button-3>", self.on_canvas_right_click)

        # 窗口大小变化事件
        self.root.bind("<Configure>", self.on_window_resize)

        # 添加Ctrl+Z事件绑定
        self.root.bind("<Control-z>", self.undo_node_graph)

        # 添加Del键删除选中节点的绑定
        self.root.bind("<Delete>", self.delete_selected_node_key)

        # 添加键盘快捷键 - 缩放相关
        self.root.bind("<Control-plus>", lambda event: self.zoom_in())
        self.root.bind("<Control-equal>", lambda event: self.zoom_in())  # Ctrl+= 也是放大
        self.root.bind("<Control-minus>", lambda event: self.zoom_out())
        self.root.bind("<Control-0>", lambda event: self.zoom_fit())  # Ctrl+0 重置缩放

        # 添加数字键快捷键
        self.root.bind("1", lambda event: self.set_zoom_level(1.0))
        self.root.bind("2", lambda event: self.set_zoom_level(2.0))
        self.root.bind("3", lambda event: self.set_zoom_level(3.0))
        self.root.bind("4", lambda event: self.set_zoom_level(4.0))
        self.root.bind("5", lambda event: self.set_zoom_level(5.0))

        # 箭头键移动图像
        self.root.bind("<Up>", lambda event: self.pan_image(0, -20))
        self.root.bind("<Down>", lambda event: self.pan_image(0, 20))
        self.root.bind("<Left>", lambda event: self.pan_image(-20, 0))
        self.root.bind("<Right>", lambda event: self.pan_image(20, 0))

    def delete_selected_node_key(self, event=None):
        """处理Del键删除选中节点的事件"""
        if self.selected_node:
            self.delete_selected_node()

    def set_zoom_level(self, level):
        """设置指定的缩放级别"""
        if not self.current_image_path:
            return

        # 设置缩放级别
        self.zoom_level = level

        # 更新缩放信息显示
        self.zoom_info.config(text=f"缩放: {int(self.zoom_level * 100)}%")

        # 重新绘制图像
        self.update_preview_with_zoom()

    def pan_image(self, dx, dy):
        """平移图像视图"""
        if not hasattr(self, 'preview_canvas') or not self.preview_canvas.winfo_exists():
            return

        # 获取当前滚动位置
        x = self.preview_canvas.canvasx(0)
        y = self.preview_canvas.canvasy(0)

        # 向指定方向移动
        self.preview_canvas.xview_scroll(dx, "units")
        self.preview_canvas.yview_scroll(dy, "units")

    def disconnect_node(self):
        """断开选中节点的连接"""
        if not self.selected_node:
            return

        # 查找所有与选中节点相关的连接
        conn_to_remove = []
        for conn in self.connections:
            if conn['input_node'] == self.selected_node or conn['output_node'] == self.selected_node:
                self.node_canvas.delete(conn['line_id'])
                conn_to_remove.append(conn)

        # 从连接列表中移除
        for conn in conn_to_remove:
            self.connections.remove(conn)

        # 处理节点图并更新预览
        self.process_node_graph()

    def copy_node(self):
        """复制选中的节点"""
        if not self.selected_node:
            return

        # 将选中节点保存到剪贴板
        self.clipboard_node = {
            'script_path': self.selected_node['script_path'],
            'script_info': self.selected_node['script_info'],
            'params': {k: v.copy() if isinstance(v, dict) else v for k, v in self.selected_node['params'].items()}
        }

        messagebox.showinfo("复制成功", "节点已复制到剪贴板")

    def paste_node(self):
        """粘贴复制的节点"""
        if not hasattr(self, 'clipboard_node') or not self.clipboard_node:
            messagebox.showinfo("粘贴失败", "剪贴板中没有节点")
            return

        # 创建新节点
        node = self.add_node(
            self.clipboard_node['script_path'],
            self.clipboard_node['script_info']
        )

        # 复制参数
        for param_name, param_value in self.clipboard_node['params'].items():
            if param_name in node['params']:
                node['params'][param_name]['value'] = param_value['value'] if isinstance(param_value,
                                                                                         dict) else param_value

        # 更新位置 - 略微偏移，使其可见
        node['x'] += 30
        node['y'] += 30
        self.node_canvas.delete(node['canvas_id'])
        self.draw_node(node)

        # 选择新节点
        self.select_node(node)

        # 处理节点图并更新预览
        self.process_node_graph()

    def arrange_nodes(self):
        """自动整理节点位置"""
        if not self.nodes:
            return

        # 简单的网格排列算法
        grid_width = 150  # 网格宽度
        grid_height = 100  # 网格高度
        max_cols = 4  # 最大列数

        # 按层级排序节点（输入节点在前，输出节点在后）
        layers = self.sort_nodes_by_layer()

        # 为每一层排列节点
        y_offset = 50
        for layer, nodes in enumerate(layers):
            # 计算该层的列数
            cols = min(len(nodes), max_cols)
            rows = (len(nodes) + cols - 1) // cols  # 向上取整

            # 计算该层的起始x坐标（居中）
            x_start = 50 + (max_cols - cols) * grid_width // 2

            # 排列节点
            for i, node in enumerate(nodes):
                row = i // cols
                col = i % cols

                # 设置节点位置
                node['x'] = x_start + col * grid_width
                node['y'] = y_offset + row * grid_height

                # 重绘节点
                self.node_canvas.delete(f"node_{node['id']}")
                self.draw_node(node)

            # 更新下一层的y偏移
            y_offset += rows * grid_height + 50

        # 更新连接
        self.update_connections()

        # 处理节点图并更新预览
        self.process_node_graph()

    def sort_nodes_by_layer(self):
        """按处理层级对节点进行排序"""
        # 创建层级列表
        layers = []
        processed = set()

        # 首先找出没有输入的节点（起始节点）
        start_nodes = []
        for node in self.nodes:
            has_inputs = False
            for conn in self.connections:
                if conn['input_node'] == node:
                    has_inputs = True
                    break
            if not has_inputs:
                start_nodes.append(node)
                processed.add(node['id'])

        if start_nodes:
            layers.append(start_nodes)

        # 按层级添加剩余节点
        while len(processed) < len(self.nodes):
            current_layer = []

            for node in self.nodes:
                if node['id'] in processed:
                    continue

                # 检查所有输入节点是否已处理
                all_inputs_processed = True
                for conn in self.connections:
                    if conn['input_node'] == node and conn['output_node']['id'] not in processed:
                        all_inputs_processed = False
                        break

                if all_inputs_processed:
                    current_layer.append(node)
                    processed.add(node['id'])

            if current_layer:
                layers.append(current_layer)
            else:
                # 处理循环依赖
                for node in self.nodes:
                    if node['id'] not in processed:
                        current_layer.append(node)
                        processed.add(node['id'])
                if current_layer:
                    layers.append(current_layer)

        return layers

    def clear_all_nodes(self):
        """清除所有节点"""
        if not self.nodes:
            return

        # 确认是否清除
        if messagebox.askyesno("确认", "确认清除所有节点？"):
            self.clear_node_graph()

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
            # 加载脚本模块
            spec = importlib.util.spec_from_file_location("module.name", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 读取脚本头部信息
            script_info = self.parse_script_header(file_path)
            if script_info:
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

                print(f"已注册脚本: {script_name} 在 {rel_path}")
            else:
                print(f"不符合格式的脚本: {file_path}")
        except Exception as e:
            print(f"加载脚本出错 {file_path}: {str(e)}")

    def parse_script_header(self, file_path):
        """解析脚本头部信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = [s.lstrip('\ufeff') for s in file.readlines()]
                if len(lines) < 4:
                    return None
                # 确保前四行是注释
                if not all(line.strip().startswith('#') for line in lines[:4]):
                    return None
                # 提取信息
                inputs = lines[0].strip()[1:].strip()
                outputs = lines[1].strip()[1:].strip()
                description = lines[2].strip()[1:].strip()
                color = lines[3].strip()[1:].strip()

                return {
                    'inputs': [i.strip() for i in inputs.split(',')] if inputs else [],
                    'outputs': [o.strip() for o in outputs.split(',')] if outputs else [],
                    'description': description,
                    'color': color
                }
        except Exception as e:
            print(f"解析脚本头部出错 {file_path}: {str(e)}")
            return None
    def show_node_menu(self, event=None):
        """显示节点导入菜单"""
        # 创建节点菜单
        menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")

        # 递归添加菜单项
        def add_menu_items(menu, registry_dict, path=""):
            for key, value in registry_dict.items():
                if isinstance(value, dict) and not 'path' in value:
                    # 创建子菜单
                    submenu = tk.Menu(menu, tearoff=0, bg="#444444", fg="white")
                    menu.add_cascade(label=key, menu=submenu)
                    # 递归添加子菜单项
                    add_menu_items(submenu, value, path + "/" + key if path else key)
                else:
                    # 添加节点项
                    menu.add_command(
                        label=key,
                        command=lambda p=value['path'], i=value['info']: self.add_node(p, i)
                    )

        # 添加所有菜单项
        add_menu_items(menu, self.script_registry)

        # 显示菜单
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

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
            'title': os.path.splitext(os.path.basename(script_path))[0],
            'params': {},  # 将在加载模块时填充
            'inputs': {},
            'outputs': {},
            'canvas_id': None,
            'port_ids': {},
            'module': None
        }

        # 加载模块并获取默认参数
        try:
            spec = importlib.util.spec_from_file_location("module.name", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            node['module'] = module

            # 获取默认参数
            if hasattr(module, 'get_params'):
                node['params'] = module.get_params()

            # 检查子操作
            node['sub_operations'] = []
            for attr_name in dir(module):
                if attr_name.startswith('sub_') and callable(getattr(module, attr_name)):
                    op_name = attr_name[4:]  # 去掉'sub_'前缀
                    node['sub_operations'].append(op_name)

        except Exception as e:
            print(f"加载模块出错: {str(e)}")

        # 添加到节点列表
        self.nodes.append(node)
        self.next_node_id += 1

        # 绘制节点
        self.draw_node(node)

        # 如果是第一个节点，展示其设置
        if len(self.nodes) == 1:
            self.select_node(node)

        # 处理节点图并更新预览
        self.process_node_graph()

        return node

    def arrange_nodes_dense(self):
        """密集整理节点图 - 将节点紧凑排列为方阵"""
        import math  # 确保导入数学库用于计算

        if not self.nodes:
            return

        # 对节点按层级排序
        layers = self.sort_nodes_by_layer()

        # 将所有层的节点展平为一个列表，同时保持顺序
        sorted_nodes = []
        for layer in layers:
            sorted_nodes.extend(layer)

        # 计算最佳网格尺寸
        node_count = len(sorted_nodes)
        grid_cols = int(math.ceil(math.sqrt(node_count)))  # 尝试接近正方形
        grid_rows = (node_count + grid_cols - 1) // grid_cols  # 向上取整

        # 定义节点间距
        node_width = 120
        node_height = 80
        spacing_x = 20  # 减小水平间距以增加密度
        spacing_y = 40  # 垂直间距略大以留出连接线空间

        # 在网格中布置节点
        for i, node in enumerate(sorted_nodes):
            row = i // grid_cols
            col = i % grid_cols

            # 设置节点位置
            node['x'] = 50 + col * (node_width + spacing_x)
            node['y'] = 50 + row * (node_height + spacing_y)

            # 重绘节点
            self.node_canvas.delete(f"node_{node['id']}")
            self.draw_node(node)

        # 更新连接
        self.update_connections()

        # 设置滚动区域以确保所有节点可见
        scroll_width = 50 + grid_cols * (node_width + spacing_x) + 50
        scroll_height = 50 + grid_rows * (node_height + spacing_y) + 50
        self.node_canvas.config(scrollregion=(0, 0, scroll_width, scroll_height))

        # 处理节点图并更新预览
        self.process_node_graph()

    def draw_node(self, node):
        """绘制节点到Canvas上"""
        # 获取节点颜色
        color = node['script_info']['color']

        # 创建节点矩形
        x, y = node['x'], node['y']
        width, height = node['width'], node['height']

        # 绘制节点背景 - 带有渐变效果
        # 绘制底部白色部分
        bottom_height = height // 3
        node_bottom_id = self.node_canvas.create_rectangle(
            x, y + height - bottom_height, x + width, y + height,
            fill="#FFFFFF", outline="#000000",
            width=2, tags=f"node_{node['id']}"
        )

        # 绘制顶部有色部分
        node_top_id = self.node_canvas.create_rectangle(
            x, y, x + width, y + height - bottom_height,
            fill=f"#{color}", outline="#000000",
            width=2, tags=f"node_{node['id']}"
        )

        # 保存Canvas ID
        node['canvas_id'] = node_top_id

        # 绘制节点标题
        title_id = self.node_canvas.create_text(
            x + width / 2, y + height - 15,
            text=node['title'],
            fill="#000000", font=("微软雅黑", 8),
            tags=f"node_{node['id']}"
        )

        # 如果是图像节点，显示图像文件名
        if node['title'] == '图像节点' or 'image' in node['title'].lower():
            if 'params' in node and 'image_path' in node['params'] and node['params']['image_path']['value']:
                image_path = node['params']['image_path']['value']
                filename = os.path.basename(image_path)
                if len(filename) > 12:  # 如果文件名太长，截断显示
                    filename = filename[:10] + "..."

                # 创建文件名标签（在标题上方）
                filename_id = self.node_canvas.create_text(
                    x + width / 2, y + height - 35,
                    text=filename,
                    fill="#555555", font=("微软雅黑", 7),
                    tags=f"node_{node['id']}"
                )

        # 绘制输入端口
        input_types = node['script_info']['inputs']
        node['port_ids']['inputs'] = {}

        for i, input_type in enumerate(input_types):
            # 确定端口颜色
            port_color = self.get_port_color(input_type)

            # 计算位置（左侧）
            port_x = x
            port_y = y + 20 + i * 20

            # 绘制端口
            port_id = self.node_canvas.create_rectangle(
                port_x - 8, port_y - 8, port_x + 8, port_y + 8,
                fill=port_color, outline="#000000",
                tags=(f"node_{node['id']}", f"input_port_{node['id']}_{i}")
            )

            # 保存端口信息
            node['port_ids']['inputs'][i] = {
                'id': port_id,
                'type': input_type,
                'x': port_x,
                'y': port_y
            }

        # 绘制输出端口
        output_types = node['script_info']['outputs']
        node['port_ids']['outputs'] = {}

        for i, output_type in enumerate(output_types):
            # 确定端口颜色
            port_color = self.get_port_color(output_type)

            # 计算位置（右侧）
            port_x = x + width
            port_y = y + 20 + i * 20

            # 绘制端口
            port_id = self.node_canvas.create_rectangle(
                port_x - 8, port_y - 8, port_x + 8, port_y + 8,
                fill=port_color, outline="#000000",
                tags=(f"node_{node['id']}", f"output_port_{node['id']}_{i}")
            )

            # 保存端口信息
            node['port_ids']['outputs'][i] = {
                'id': port_id,
                'type': output_type,
                'x': port_x,
                'y': port_y
            }

        # 绑定事件
        self.node_canvas.tag_bind(f"node_{node['id']}", "<Button-1>",
                                  lambda event, n=node: self.select_node(n))
        self.node_canvas.tag_bind(f"node_{node['id']}", "<Button-3>",
                                  lambda event, n=node: self.show_node_context_menu(event, n))

        # 绑定端口事件 - 修复绑定问题
        for i in node['port_ids']['outputs']:
            tag = f"output_port_{node['id']}_{i}"

            # 使用函数闭包解决lambda中变量绑定问题
            def create_output_click_handler(node, port_idx):
                return lambda event: self.start_connection(event, node, port_idx, 'output')

            def create_output_right_click_handler(node, port_idx):
                return lambda event: self.show_port_context_menu(event, node, port_idx, 'output')

            self.node_canvas.tag_bind(tag, "<Button-1>", create_output_click_handler(node, i))
            self.node_canvas.tag_bind(tag, "<Button-3>", create_output_right_click_handler(node, i))

        for i in node['port_ids']['inputs']:
            tag = f"input_port_{node['id']}_{i}"

            # 使用函数闭包解决lambda中变量绑定问题
            def create_input_click_handler(node, port_idx):
                return lambda event: self.start_connection(event, node, port_idx, 'input')

            def create_input_right_click_handler(node, port_idx):
                return lambda event: self.show_port_context_menu(event, node, port_idx, 'input')

            self.node_canvas.tag_bind(tag, "<Button-1>", create_input_click_handler(node, i))
            self.node_canvas.tag_bind(tag, "<Button-3>", create_input_right_click_handler(node, i))

    def get_port_color(self, port_type):
        """获取端口颜色"""
        # 定义端口类型颜色映射
        port_colors = {
            'tif16': "#0000FF",  # 蓝色
            'tif8': "#87CEFA",  # 浅蓝色
            'img': "#8A2BE2",  # 蓝紫色
            'kernel': "#FFFF00",  # 黄色
            'spectrumf': "#FF6A6A", # 浅甜红
            'f32bmp': "#000080",  # 海军蓝色
            # 可以添加更多类型
        }

        return port_colors.get(port_type, "#CCCCCC")  # 默认灰色

    def select_node(self, node):
        """选择节点并显示其设置"""
        # 清除旧的选择状态
        if self.selected_node:
            old_id = self.selected_node['canvas_id']
            self.node_canvas.itemconfig(old_id, width=2)

        # 设置新的选择状态
        self.selected_node = node
        new_id = node['canvas_id']
        self.node_canvas.itemconfig(new_id, width=3)

        # 显示节点设置
        self.show_node_settings(node)

    def show_node_settings(self, node):
        """显示节点设置UI - 支持水平布局"""
        # 清除旧的设置UI
        for widget in self.settings_frame.winfo_children():
            widget.destroy()

        # 创建设置标题
        title_label = ttk.Label(self.settings_frame, text=f"{node['title']} 设置",
                                style="Title.TLabel", font=("微软雅黑", 11, "bold"))
        title_label.pack(side="top", pady=10, fill="x")

        # 如果没有参数，显示提示
        if not node['params']:
            no_params_label = ttk.Label(self.settings_frame,
                                        text="此节点没有可配置参数",
                                        style="Aero.TLabel")
            no_params_label.pack(side="top", pady=20)
            return

        # 创建带滚动条的设置区域
        settings_canvas = tk.Canvas(self.settings_frame, bg="#333333", highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(self.settings_frame, orient="vertical", command=settings_canvas.yview)
        h_scrollbar = ttk.Scrollbar(self.settings_frame, orient="horizontal", command=settings_canvas.xview)

        # 设置滚动区域框架 - 使用暗色背景
        content_frame = ttk.Frame(settings_canvas, style="Panel.TFrame")

        # 设置画布滚动区域
        settings_canvas.create_window((0, 0), window=content_frame, anchor="nw")

        # 配置滚动
        def on_frame_configure(event):
            settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))

        content_frame.bind("<Configure>", on_frame_configure)

        # 放置画布和滚动条
        settings_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        settings_canvas.pack(side="left", fill="both", expand=True)

        # 计算合适的列数 - 根据参数数量和窗口大小
        params_count = len(node['params'])
        settings_width = self.settings_frame.winfo_width()

        # 基于窗口宽度和参数数确定列数
        if settings_width > 600:  # 宽窗口
            max_columns = min(4, params_count)  # 最多4列
        elif settings_width > 400:  # 中等窗口
            max_columns = min(3, params_count)  # 最多3列
        else:  # 窄窗口
            max_columns = min(2, params_count)  # 最多2列

        # 确保有至少1列
        num_columns = max(1, max_columns)

        # 配置列权重
        for i in range(num_columns):
            content_frame.columnconfigure(i, weight=1)

        # 放置参数控件
        row, col = 0, 0
        for param_name, param_info in node['params'].items():
            # 创建参数框架
            param_frame = ttk.Frame(content_frame, style="Settings.TFrame")
            param_frame.grid(row=row, column=col, sticky="ew", padx=5, pady=5)

            # 参数标签
            label = ttk.Label(param_frame, text=param_info.get('label', param_name),
                              style="Aero.TLabel", font=("微软雅黑", 9))
            label.pack(side="top", anchor="w", pady=(0, 3))

            # 创建参数控件（根据类型）
            self.create_param_control(param_frame, param_name, param_info, "horizontal")

            # 更新列和行
            col += 1
            if col >= num_columns:
                col = 0
                row += 1

    def create_param_control(self, parent, param_name, param_info, layout="vertical"):
        """创建参数控件"""
        param_type = param_info.get('type', 'text')

        if param_type == 'slider':
            # 滑块控件
            min_val = param_info.get('min', 0)
            max_val = param_info.get('max', 100)
            step = param_info.get('step', 1)
            value = param_info.get('value', min_val)

            slider_frame = ttk.Frame(parent, style="Settings.TFrame")
            slider_frame.pack(fill="x", expand=True)

            # 显示当前值
            value_var = tk.StringVar(value=str(value))
            value_label = ttk.Label(slider_frame, textvariable=value_var,
                                    style="Aero.TLabel", width=5)
            value_label.pack(side="right", padx=2)

            # 滑块
            slider = ttk.Scale(slider_frame, from_=min_val, to=max_val, value=value,
                               orient="horizontal")
            slider.pack(side="left", fill="x", expand=True, padx=2)

            # 更新函数
            def update_value(event):
                val = slider.get()
                if isinstance(val, float) and step == int(step):
                    val = int(val)
                value_var.set(f"{val:.1f}" if isinstance(val, float) else str(val))
                self.update_node_param(param_name, val)

            slider.bind("<ButtonRelease-1>", update_value)

        elif param_type == 'checkbox':
            # 复选框
            value = param_info.get('value', False)
            var = tk.BooleanVar(value=value)

            checkbox = ttk.Checkbutton(parent, text="", variable=var)
            checkbox.pack(fill="x", expand=True)

            # 更新函数
            def update_value(*args):
                self.update_node_param(param_name, var.get())

            var.trace_add("write", update_value)

        elif param_type == 'dropdown':
            # 下拉框
            options = param_info.get('options', [])
            value = param_info.get('value', options[0] if options else '')

            var = tk.StringVar(value=value)
            dropdown = ttk.Combobox(parent, textvariable=var, values=options,
                                    state="readonly")
            dropdown.pack(fill="x", expand=True, padx=2)

            # 更新函数
            def update_value(*args):
                self.update_node_param(param_name, var.get())

            var.trace_add("write", update_value)

        elif param_type == 'path':
            # 路径选择
            value = param_info.get('value', '')
            var = tk.StringVar(value=value)

            path_frame = ttk.Frame(parent, style="Settings.TFrame")
            path_frame.pack(fill="x", expand=True)

            # 路径输入框
            entry = ttk.Entry(path_frame, textvariable=var)
            entry.pack(side="left", fill="x", expand=True, padx=2)

            # 浏览按钮
            browse_btn = ttk.Button(path_frame, text="...", width=3,
                                    command=lambda: self.browse_path(param_name, var))
            browse_btn.pack(side="right", padx=2)

            # 更新函数
            def update_value(*args):
                self.update_node_param(param_name, var.get())

            var.trace_add("write", update_value)

        else:
            # 默认文本输入
            value = param_info.get('value', '')
            var = tk.StringVar(value=str(value))

            entry = ttk.Entry(parent, textvariable=var)
            entry.pack(fill="x", expand=True, padx=2)

            # 更新函数
            def update_value(*args):
                self.update_node_param(param_name, var.get())

            var.trace_add("write", update_value)

    def update_node_param(self, param_name, param_value):
        """更新节点参数并触发处理"""
        if self.selected_node:
            # 更新参数值
            if param_name in self.selected_node['params']:
                self.selected_node['params'][param_name]['value'] = param_value

                # 处理节点图并更新预览
                self.process_node_graph()

    def browse_path(self, param_name, string_var):
        """浏览并选择文件路径"""
        if param_name.lower().find('export') >= 0:
            # 如果是导出路径，使用保存对话框
            file_path = filedialog.asksaveasfilename(
                initialdir=os.path.dirname(string_var.get()) if string_var.get() else self.work_folder,
                title="选择保存位置",
                filetypes=(("JPEG 文件", "*.jpg"), ("PNG 文件", "*.png"),
                           ("TIFF 文件", "*.tif"), ("所有文件", "*.*"))
            )
        else:
            # 否则使用打开对话框
            file_path = filedialog.askopenfilename(
                initialdir=os.path.dirname(string_var.get()) if string_var.get() else self.work_folder,
                title="选择文件",
                filetypes=(("图像文件", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
                           ("所有文件", "*.*"))
            )

        if file_path:
            string_var.set(file_path)

    def on_node_drag(self, event):
        """处理节点拖动"""
        if not self.selected_node:
            return

        # 获取canvas坐标（而非事件坐标）
        canvas_x = self.node_canvas.canvasx(event.x)
        canvas_y = self.node_canvas.canvasy(event.y)

        # 首次拖动时初始化位置
        if not hasattr(self, 'drag_start_x'):
            self.drag_start_x = canvas_x
            self.drag_start_y = canvas_y
            self.drag_node_start_x = self.selected_node['x']
            self.drag_node_start_y = self.selected_node['y']
            return

        # 计算相对于起始点的位移
        dx = canvas_x - self.drag_start_x
        dy = canvas_y - self.drag_start_y

        # 设置节点新位置（基于起始位置的绝对移动）
        new_x = self.drag_node_start_x + dx
        new_y = self.drag_node_start_y + dy

        # 计算需要移动的距离
        move_dx = new_x - self.selected_node['x']
        move_dy = new_y - self.selected_node['y']

        # 移动节点
        self.node_canvas.move(f"node_{self.selected_node['id']}", move_dx, move_dy)

        # 更新节点位置
        self.selected_node['x'] = new_x
        self.selected_node['y'] = new_y

        # 更新所有端口位置
        for io_type in ['inputs', 'outputs']:
            for port_idx, port_info in self.selected_node['port_ids'][io_type].items():
                port_info['x'] += move_dx
                port_info['y'] += move_dy

        # 更新连接线
        self.update_connections()

    def start_connection(self, event=None, node=None, port_idx=None, port_type=None):
        """开始创建连接线"""
        # 如果是从菜单调用而没有参数
        if event is None and self.selected_node:
            # 这里处理从菜单调用的逻辑
            # ...
            return

        # 记录拖动起点
        self.dragging = True

        if port_type == 'output':
            self.connecting_from = (node, port_idx, 'output')
            x = node['port_ids']['outputs'][port_idx]['x']
            y = node['port_ids']['outputs'][port_idx]['y']
        else:
            self.connecting_from = (node, port_idx, 'input')
            x = node['port_ids']['inputs'][port_idx]['x']
            y = node['port_ids']['inputs'][port_idx]['y']

        # 创建临时连接线 - 确保使用canvas坐标
        canvas_x = self.node_canvas.canvasx(event.x)
        canvas_y = self.node_canvas.canvasy(event.y)

        self.temp_line = self.node_canvas.create_line(
            x, y, canvas_x, canvas_y,
            fill="#ffec21", width=3, dash=(4, 2)
        )

    def on_canvas_click(self, event):
        """画布点击处理 - 改进版选择顶层节点"""
        # 获取鼠标的画布坐标
        canvas_x = self.node_canvas.canvasx(event.x)
        canvas_y = self.node_canvas.canvasy(event.y)

        # 重置拖动状态
        if hasattr(self, 'drag_start_x'):
            del self.drag_start_x
            del self.drag_start_y
            del self.drag_node_start_x
            del self.drag_node_start_y

        # 清除选择
        old_selected = self.selected_node
        self.selected_node = None

        # 检查是否点击了端口（避免端口点击触发节点选择）
        closest = self.node_canvas.find_closest(canvas_x, canvas_y)
        if closest:
            tags = self.node_canvas.gettags(closest[0])
            for tag in tags:
                if tag.startswith("input_port_") or tag.startswith("output_port_"):
                    return  # 如果点击了端口，不处理节点选择

        # 查找点击位置的所有节点，获取它们的IDs
        overlapping_items = self.node_canvas.find_overlapping(canvas_x - 5, canvas_y - 5, canvas_x + 5, canvas_y + 5)

        # 找出所有节点项
        node_items = []
        for item in overlapping_items:
            tags = self.node_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("node_"):
                    node_id = int(tag.split("_")[1])
                    node_items.append((item, node_id))

        # 如果有多个节点项，选择stacking order中最上层的节点
        # Canvas中的item ID越大，越靠上层
        if node_items:
            # 按照Canvas项目ID排序（越大越上层）
            node_items.sort(key=lambda x: x[0], reverse=True)
            top_node_id = node_items[0][1]

            # 查找并选择对应的节点
            for node in self.nodes:
                if node['id'] == top_node_id:
                    self.select_node(node)
                    return

        # 如果点击了空白区域且之前有选中节点，刷新设置面板
        if old_selected:
            # 清除设置区域
            for widget in self.settings_frame.winfo_children():
                widget.destroy()

            # 显示默认提示
            self.no_node_label = ttk.Label(self.settings_frame,
                                           text="请选择一个节点查看设置",
                                           style="Aero.TLabel")
            self.no_node_label.pack(expand=True, pady=20)

    def on_canvas_drag(self, event):
        """处理画布拖动，包括节点拖动和连接创建"""
        # 获取画布坐标
        canvas_x = self.node_canvas.canvasx(event.x)
        canvas_y = self.node_canvas.canvasy(event.y)

        # 处理连接拖动（优先）
        if self.dragging and self.temp_line:
            # 更新临时连接线的终点位置
            coords = self.node_canvas.coords(self.temp_line)
            self.node_canvas.coords(self.temp_line, coords[0], coords[1], canvas_x, canvas_y)
            return

        # 处理节点拖动
        if self.selected_node:
            # 如果是首次拖动，记录初始位置
            if not hasattr(self, 'last_drag_x'):
                self.last_drag_x = canvas_x
                self.last_drag_y = canvas_y
                return

            # 计算移动距离
            dx = canvas_x - self.last_drag_x
            dy = canvas_y - self.last_drag_y

            if dx == 0 and dy == 0:
                return

            # 更新节点位置
            self.node_canvas.move(f"node_{self.selected_node['id']}", dx, dy)

            # 将节点元素提升到顶层 - 添加这行来确保拖动的节点显示在最上层
            self.node_canvas.tag_raise(f"node_{self.selected_node['id']}")

            # 更新节点坐标
            self.selected_node['x'] += dx
            self.selected_node['y'] += dy

            # 更新所有端口位置
            for io_type in ['inputs', 'outputs']:
                for port_idx, port_info in self.selected_node['port_ids'][io_type].items():
                    port_info['x'] += dx
                    port_info['y'] += dy

            # 更新连接线
            self.update_connections()

            # 更新拖动参考点
            self.last_drag_x = canvas_x
            self.last_drag_y = canvas_y

    def on_canvas_release(self, event):
        """画布释放处理"""
        # 清除拖动参考点
        if hasattr(self, 'last_drag_x'):
            del self.last_drag_x
            del self.last_drag_y

        if hasattr(self, 'drag_start_x'):
            del self.drag_start_x
            del self.drag_start_y
            del self.drag_node_start_x
            del self.drag_node_start_y

        # 处理连接完成
        if self.dragging and self.temp_line and self.connecting_from:
            # 获取释放位置的画布坐标
            canvas_x = self.node_canvas.canvasx(event.x)
            canvas_y = self.node_canvas.canvasy(event.y)

            # 查找释放处是否有端口 - 扩大检测范围
            items = self.node_canvas.find_overlapping(canvas_x - 20, canvas_y - 20, canvas_x + 20, canvas_y + 20)

            # 找到符合条件的端口
            compatible_ports = []

            for item in items:
                tags = self.node_canvas.gettags(item)

                for tag in tags:
                    # 确保连接到正确类型的端口
                    if (self.connecting_from[2] == 'output' and tag.startswith('input_port_')) or \
                            (self.connecting_from[2] == 'input' and tag.startswith('output_port_')):

                        # 解析端口信息
                        parts = tag.split('_')
                        if len(parts) >= 4:
                            port_type, node_id, port_idx = parts[1], int(parts[2]), int(parts[3])

                            # 查找目标节点
                            for node in self.nodes:
                                if node['id'] == node_id:
                                    # 确定连接方向
                                    if self.connecting_from[2] == 'output':
                                        output_node = self.connecting_from[0]
                                        output_port = self.connecting_from[1]
                                        input_node = node
                                        input_port = port_idx
                                    else:
                                        output_node = node
                                        output_port = port_idx
                                        input_node = self.connecting_from[0]
                                        input_port = self.connecting_from[1]

                                    # 检查端口是否存在和类型兼容
                                    if (output_port in output_node['port_ids']['outputs'] and
                                            input_port in input_node['port_ids']['inputs']):
                                        output_type = output_node['script_info']['outputs'][output_port]
                                        input_type = input_node['script_info']['inputs'][input_port]

                                        #if output_type == input_type:
                                        if True:
                                            # 获取端口坐标
                                            if self.connecting_from[2] == 'output':
                                                port_coords = self.node_canvas.coords(
                                                    input_node['port_ids']['inputs'][input_port]['id'])
                                            else:
                                                port_coords = self.node_canvas.coords(
                                                    output_node['port_ids']['outputs'][output_port]['id'])

                                            # 计算端口中心点
                                            port_center_x = (port_coords[0] + port_coords[2]) / 2
                                            port_center_y = (port_coords[1] + port_coords[3]) / 2

                                            # 计算与鼠标位置的距离
                                            distance = ((port_center_x - canvas_x) ** 2 + (
                                                        port_center_y - canvas_y) ** 2) ** 0.5

                                            # 添加到兼容端口列表
                                            compatible_ports.append({
                                                'output_node': output_node,
                                                'output_port': output_port,
                                                'input_node': input_node,
                                                'input_port': input_port,
                                                'distance': distance
                                            })
                                        else:
                                            messagebox.showwarning("类型不匹配",
                                                                   f"输出类型 {output_type} 与输入类型 {input_type} 不匹配")
                                    break

            # 只有在找到兼容的端口时才创建连接
            is_connected = False
            if compatible_ports:
                # 按距离排序
                compatible_ports.sort(key=lambda x: x['distance'])

                # 选择最近的端口
                nearest_port = compatible_ports[0]

                # 创建连接
                is_connected = self.create_connection(
                    nearest_port['output_node'],
                    nearest_port['output_port'],
                    nearest_port['input_node'],
                    nearest_port['input_port']
                )

                # 如果创建了连接，处理节点图并更新预览
                if is_connected:
                    self.process_node_graph()

            # 删除临时线
            self.node_canvas.delete(self.temp_line)
            self.temp_line = None

            # 重置状态
            self.dragging = False
            self.connecting_from = None

    def create_connection(self, output_node, output_port, input_node, input_port):
        """创建节点之间的连接 - 改进版支持多输入"""
        # 检查是否已存在到此输入端口的连接
        for conn in self.connections:
            if conn['input_node'] == input_node and conn['input_port'] == input_port:
                # 删除旧连接
                self.node_canvas.delete(conn['line_id'])
                self.connections.remove(conn)
                break

        # 如果自己连自己，拒绝连接
        if output_node == input_node:
            messagebox.showwarning("无效连接", "节点不能连接到自身")
            return False

        # 检查是否会形成循环
        if self.would_form_cycle(output_node, input_node):
            messagebox.showwarning("无效连接", "此连接会形成循环")
            return False

        # 获取端口位置
        out_x = output_node['port_ids']['outputs'][output_port]['x']
        out_y = output_node['port_ids']['outputs'][output_port]['y']
        in_x = input_node['port_ids']['inputs'][input_port]['x']
        in_y = input_node['port_ids']['inputs'][input_port]['y']

        # 创建连接线
        line_id = self.node_canvas.create_line(
            out_x, out_y, in_x, in_y,
            fill="#f6f7b2", width=2, smooth=True,
            tags=(f"conn_{output_node['id']}_{output_port}_{input_node['id']}_{input_port}")
        )

        # 添加到连接列表
        connection = {
            'output_node': output_node,
            'output_port': output_port,
            'input_node': input_node,
            'input_port': input_port,
            'line_id': line_id,
            'input_type': input_node['script_info']['inputs'][input_port],  # 添加输入类型
            'output_type': output_node['script_info']['outputs'][output_port]  # 添加输出类型
        }

        self.connections.append(connection)
        return True

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

    def update_connections(self):
        """更新所有连接线"""
        for conn in self.connections:
            out_x = conn['output_node']['port_ids']['outputs'][conn['output_port']]['x']
            out_y = conn['output_node']['port_ids']['outputs'][conn['output_port']]['y']
            in_x = conn['input_node']['port_ids']['inputs'][conn['input_port']]['x']
            in_y = conn['input_node']['port_ids']['inputs'][conn['input_port']]['y']

            self.node_canvas.coords(conn['line_id'], out_x, out_y, in_x, in_y)

    def on_canvas_right_click(self, event):
        """画布右键点击处理"""
        # 获取Canvas坐标
        canvas_x = self.node_canvas.canvasx(event.x)
        canvas_y = self.node_canvas.canvasy(event.y)

        # 获取鼠标下的所有项目
        items = self.node_canvas.find_overlapping(canvas_x - 5, canvas_y - 5, canvas_x + 5, canvas_y + 5)

        if not items:
            # 如果没有项目，显示画布菜单
            self.canvas_menu.tk_popup(event.x_root, event.y_root)
            return

        # 检查是否点击了端口
        for item in items:
            tags = self.node_canvas.gettags(item)

            # 检查端口标签
            for tag in tags:
                if tag.startswith("input_port_") or tag.startswith("output_port_"):
                    parts = tag.split("_")
                    if len(parts) >= 4:  # 确保标签格式正确
                        node_id = int(parts[2])
                        port_idx = int(parts[3])
                        port_type = "input" if tag.startswith("input_port_") else "output"

                        # 找到对应的节点
                        for node in self.nodes:
                            if node['id'] == node_id:
                                self.show_port_context_menu(event, node, port_idx, port_type)
                                return

        # 检查是否点击了节点
        for item in items:
            tags = self.node_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("node_"):
                    node_id = int(tag.split("_")[1])
                    for node in self.nodes:
                        if node['id'] == node_id:
                            self.show_node_context_menu(event, node)
                            return

        # 如果都没点击到，显示画布菜单
        self.canvas_menu.tk_popup(event.x_root, event.y_root)

    def show_node_context_menu(self, event, node):
        """显示节点右键菜单"""
        # 选择节点 - 确保完全激活选择
        self.selected_node = node

        # 更新节点样式显示选中状态
        for n in self.nodes:
            if n['canvas_id']:
                self.node_canvas.itemconfig(n['canvas_id'], width=2)

        # 高亮显示选中节点
        if node['canvas_id']:
            self.node_canvas.itemconfig(node['canvas_id'], width=3)

        # 更新节点设置面板
        self.show_node_settings(node)

        # 清除旧菜单项
        self.node_menu.delete(0, tk.END)

        # 添加删除操作
        self.node_menu.add_command(label="删除节点", command=lambda: self.delete_selected_node(node))

        # 添加子操作
        if 'sub_operations' in node and node['sub_operations']:
            self.node_menu.add_separator()
            for op in node['sub_operations']:
                self.node_menu.add_command(
                    label=op,
                    command=lambda n=node, o=op: self.execute_sub_operation(n, o)
                )

        # 显示菜单
        try:
            self.node_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.node_menu.grab_release()

    def delete_selected_node(self, node=None):
        """删除选中的节点或指定节点"""
        # 确定要删除的节点 - 如果指定了node参数则使用它，否则使用selected_node
        target_node = node if node is not None else self.selected_node

        if not target_node:
            return

        # 删除相关的连接
        conn_to_remove = []
        for conn in self.connections:
            if conn['input_node'] == target_node or conn['output_node'] == target_node:
                self.node_canvas.delete(conn['line_id'])
                conn_to_remove.append(conn)

        for conn in conn_to_remove:
            self.connections.remove(conn)

        # 删除节点Canvas项
        self.node_canvas.delete(f"node_{target_node['id']}")

        # 从节点列表中移除
        self.nodes.remove(target_node)

        # 清除选择 - 只有当删除的是当前选择的节点时
        if self.selected_node == target_node:
            self.selected_node = None

            # 清除设置区域
            for widget in self.settings_frame.winfo_children():
                widget.destroy()

            # 显示默认提示
            self.no_node_label = ttk.Label(self.settings_frame,
                                           text="请选择一个节点查看设置",
                                           style="Aero.TLabel")
            self.no_node_label.pack(expand=True, pady=20)

        # 处理节点图并更新预览
        self.process_node_graph()

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
                'current_image_path': self.current_image_path,
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
                        messagebox.showinfo("操作成功", result['message'])

                    # 处理节点图并更新预览
                    self.process_node_graph()
                else:
                    # 显示错误消息
                    if 'error' in result:
                        messagebox.showerror("操作失败", result['error'])

        except Exception as e:
            messagebox.showerror("操作错误", f"执行操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def process_node_graph(self):
        """处理整个节点图并更新预览"""
        # 如果没有节点，返回
        if not self.nodes:
            return

        # 清除所有节点的中间结果
        for node in self.nodes:
            if 'processed_outputs' in node:
                del node['processed_outputs']

        # 查找没有输入的节点（起始节点）
        start_nodes = []
        for node in self.nodes:
            # 检查是否有输入
            has_inputs = False
            for conn in self.connections:
                if conn['input_node'] == node:
                    has_inputs = True
                    break

            # 如果没有输入且有输出，添加为起始节点
            if not has_inputs and node['script_info']['outputs']:
                start_nodes.append(node)

        # 处理每个起始节点
        for node in start_nodes:
            self.process_node(node)

        # 更新预览图像
        self.update_preview()

        # 自动保存节点图
        self.auto_save_node_graph()

    def auto_save_node_graph(self):
        """自动保存节点图至临时文件夹"""
        # 如果没有当前图像路径或没有节点，不保存
        if not self.current_image_path or not self.nodes:
            return

        try:
            # 获取图像文件名（不包含扩展名）
            image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]

            # 确保临时文件夹存在
            if not os.path.exists(self.temp_folder):
                os.makedirs(self.temp_folder, exist_ok=True)

            # 检查现有的自动保存文件
            existing_saves = []
            for file in os.listdir(self.temp_folder):
                if file.startswith(image_filename + "_auto_") and file.endswith(".json"):
                    existing_saves.append(file)

            # 按序号排序
            existing_saves.sort(key=lambda x: int(x.split("_auto_")[1].split(".")[0]))

            # 如果超过3个，删除最旧的
            while len(existing_saves) >= 3:
                os.remove(os.path.join(self.temp_folder, existing_saves[0]))
                existing_saves.pop(0)

            # 确定新的序号
            new_index = 1
            if existing_saves:
                try:
                    last_index = int(existing_saves[-1].split("_auto_")[1].split(".")[0])
                    new_index = last_index + 1
                except (ValueError, IndexError):
                    # 如果解析失败，使用时间戳
                    new_index = int(time.time())

            # 创建文件名
            filename = f"{image_filename}_auto_{new_index}.json"
            file_path = os.path.join(self.temp_folder, filename)

            # 创建保存数据并先保存到临时文件
            temp_path = file_path + ".tmp"
            success = self.save_node_graph_to_file(temp_path)

            # 如果临时文件保存成功，重命名为正式文件
            if success and os.path.exists(temp_path):
                if os.path.exists(file_path):
                    os.remove(file_path)  # 如果已存在同名文件，先删除
                os.rename(temp_path, file_path)
                print(f"自动保存成功: {file_path}")

            return success

        except Exception as e:
            print(f"自动保存节点图出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def process_node(self, node):
        """处理单个节点并返回输出"""
        # 如果节点已处理，直接返回结果
        if 'processed_outputs' in node:
            return node['processed_outputs']

        try:
            # 获取节点输入
            inputs = self.get_node_inputs(node)

            # 获取节点参数
            params = {name: param_info['value'] for name, param_info in node['params'].items()}

            # 执行处理
            if hasattr(node['module'], 'process'):
                outputs = node['module'].process(inputs, params)

                # 保存处理结果
                node['processed_outputs'] = outputs

                # 检查是否是预览节点，更新预览
                if node['title'] == 'preview_node':
                    self.update_preview_from_node(node)

                return outputs
            else:
                print(f"节点 {node['title']} 没有处理函数")
                return {}

        except Exception as e:
            print(f"处理节点 {node['title']} 时出错: {str(e)}")
            # 记录错误，但返回空结果以允许继续处理
            node['processed_outputs'] = {}
            return {}

    def get_node_inputs(self, node):
        """获取节点的输入数据 - 改进版支持多个同类型输入"""
        inputs = {}
        input_type_counts = {}  # 记录每种类型输入的数量

        # 初始化输入类型计数
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
            input_type = node['script_info']['inputs'][input_port]

            # 处理输出节点
            output_data = self.process_node(output_node)

            # 获取相应端口的输出数据
            if output_data:
                output_type = output_node['script_info']['outputs'][output_port]

                if output_type in output_data:
                    # 增加此类型输入的计数
                    input_type_counts[input_type] += 1
                    count = input_type_counts[input_type]

                    # 对于第一个该类型的输入，使用原始类型名
                    if count == 1:
                        inputs[input_type] = output_data[output_type]
                    else:
                        # 对于额外的同类型输入，添加序号
                        inputs[f"{input_type}_{count - 1}"] = output_data[output_type]

        #  # 特殊处理图像节点
        # if node['title'] == 'image_node' and self.current_image_path:
        #      if 'params' not in node:
        #          node['params'] = {}
        #      node['params']['image_path'] = {'value': self.current_image_path}

        return inputs

    def save_node_graph_to_file(self, file_path):
        """保存节点图到指定文件"""
        try:
            # 创建保存数据
            data = {
                'current_image_path': self.current_image_path,
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
                    'params': {k: v['value'] for k, v in node['params'].items()}
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

            return True
        except Exception as e:
            print(f"保存节点图到文件出错: {str(e)}")
            return False

    def update_preview(self):
        """更新预览图像"""
        # 查找预览节点
        preview_node = None
        for node in self.nodes:
            if node['title'] == '预览节点':
                preview_node = node
                break

        if preview_node:
            # 检查是否需要应用缩放
            if hasattr(self, 'zoom_level') and self.zoom_level != 1.0:
                self.update_preview_with_zoom()
            else:
                self.update_preview_from_node(preview_node)

    def update_preview_from_node(self, node):
        """从预览节点更新预览图像"""
        # 如果节点未处理，先处理
        if 'processed_outputs' not in node:
            self.process_node(node)

        # 获取输出图像 - 优先使用f32bmp格式，其次是tif16
        if 'processed_outputs' in node:
            img = None
            if 'f32bmp' in node['processed_outputs']:
                img = node['processed_outputs']['f32bmp']
            elif 'tif16' in node['processed_outputs']:
                img = node['processed_outputs']['tif16']

            # 转换图像用于显示
            if img is not None:
                # 根据图像类型进行适当的转换
                if img.dtype == np.float32:
                    # 将32位浮点图像转换为8位用于显示
                    # 假设浮点数据范围在0-1之间
                    img_display = (img * 255).clip(0, 255).astype(np.uint8)
                elif img.dtype == np.uint16:
                    # 将16位图像转换为8位用于显示
                    img_display = (img / 256).astype(np.uint8)
                else:
                    img_display = img

                # 创建PIL图像
                pil_img = Image.fromarray(img_display)

                # 获取原始图像尺寸
                orig_width, orig_height = pil_img.size

                # 调整大小以适应预览区域（仅当zoom_level=1.0时）
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()

                if canvas_width > 1 and canvas_height > 1:  # 确保Canvas已有尺寸
                    # 计算缩放比例 - 只有在自适应模式时使用
                    if not hasattr(self, 'zoom_level') or self.zoom_level == 1.0:
                        scale = min(canvas_width / orig_width, canvas_height / orig_height)

                        # 防止图像太小时过度放大
                        if scale > 1 and max(orig_width, orig_height) < 400:
                            scale = 1.0
                    else:
                        # 使用当前缩放级别
                        scale = self.zoom_level

                    # 计算新尺寸
                    new_width = int(orig_width * scale)
                    new_height = int(orig_height * scale)

                    # 调整大小
                    if scale < 1:
                        # 缩小时使用LANCZOS
                        pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                    elif scale > 1:
                        # 放大时使用BICUBIC
                        pil_img = pil_img.resize((new_width, new_height), Image.BICUBIC)

                    # 创建PhotoImage
                    self.preview_image = ImageTk.PhotoImage(pil_img)

                    # 清除旧的图像
                    self.preview_canvas.delete("all")

                    # 计算居中位置
                    x = max(0, (canvas_width - new_width) // 2)
                    y = max(0, (canvas_height - new_height) // 2)

                    # 显示图像
                    self.preview_canvas.create_image(x, y, anchor="nw", image=self.preview_image, tags="preview_image")

                    # 设置滚动区域
                    scroll_width = max(canvas_width, new_width)
                    scroll_height = max(canvas_height, new_height)
                    self.preview_canvas.config(scrollregion=(0, 0, scroll_width, scroll_height))

                    # 更新缩放信息
                    if hasattr(self, 'zoom_info'):
                        zoom_percent = int(scale * 100)
                        self.zoom_info.config(text=f"缩放: {zoom_percent}%")

                    # 启用图像拖动功能
                    self.enable_image_panning()
    def on_window_resize(self, event):
        """窗口大小变化事件处理"""
        # 检查事件来源是否为主窗口，避免子窗口调整触发更新
        if event.widget == self.root:
            # 重绘节点网格以适应新大小
            self.draw_node_grid()

            # 更新预览区域中的图像
            self.update_preview()

            # 调整画布滚动区域
            if hasattr(self, 'preview_canvas') and self.preview_canvas.winfo_exists():
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()
                if canvas_width > 1 and canvas_height > 1:
                    self.preview_canvas.config(scrollregion=(0, 0, canvas_width, canvas_height))

    def update_film_preview(self):
        """更新胶片预览"""
        # 清除旧的预览
        for widget in self.film_preview.winfo_children():
            widget.destroy()

        # 确保工作文件夹存在
        if not os.path.exists(self.work_folder):
            os.makedirs(self.work_folder, exist_ok=True)

        # 获取工作文件夹中的图像文件
        image_exts = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']
        images = []

        for file in os.listdir(self.work_folder):
            if os.path.splitext(file)[1].lower() in image_exts:
                images.append(file)

        # 限制显示数量
        max_display = 15
        if len(images) > max_display:
            images = images[:max_display]

        # 创建水平框架
        film_frame = ttk.Frame(self.film_preview, style="Aero.TFrame")
        film_frame.pack(fill="x", expand=True)

        # 创建每个图像的缩略图
        for image_file in images:
            try:
                # 加载图像
                image_path = os.path.join(self.work_folder, image_file)
                img = Image.open(image_path)

                # 创建缩略图
                img.thumbnail((80, 80))
                photo = ImageTk.PhotoImage(img)

                # 创建图像按钮框架（增加Glass效果）
                img_frame = ttk.Frame(film_frame, style="Glass.TFrame")
                img_frame.pack(side="left", padx=5, pady=5)

                # 创建图像按钮
                img_btn = ttk.Button(img_frame, image=photo, padding=1,
                                     command=lambda path=image_path: self.open_image_path(path))
                img_btn.image = photo  # 保持引用以防垃圾回收
                img_btn.pack()

                # 添加文件名标签
                name_label = ttk.Label(img_frame, text=image_file[:10] + "..." if len(image_file) > 10 else image_file,
                                       style="Aero.TLabel", anchor="center", width=10)
                name_label.pack()

            except Exception as e:
                print(f"加载图像 {image_file} 出错: {str(e)}")

    def zoom_in(self):
        """放大预览图像"""
        # 增加缩放级别
        self.zoom_level *= 1.25

        # 限制最大缩放级别
        if self.zoom_level > 8.0:
            self.zoom_level = 8.0

        # 更新缩放信息显示
        self.zoom_info.config(text=f"缩放: {int(self.zoom_level * 100)}%")

        # 重新绘制图像
        self.update_preview_with_zoom()

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

        # 获取输出图像 - 优先使用f32bmp格式，其次是tif16
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
                    # 假设浮点数据范围在0-1之间
                    img_display = (img * 255).clip(0, 255).astype(np.uint8)
                elif img.dtype == np.uint16:
                    # 将16位图像转换为8位用于显示
                    img_display = (img / 256).astype(np.uint8)
                else:
                    img_display = img

                # 创建PIL图像
                pil_img = Image.fromarray(img_display)

                # 获取原始图像尺寸
                orig_width, orig_height = pil_img.size

                # 应用缩放
                new_width = int(orig_width * self.zoom_level)
                new_height = int(orig_height * self.zoom_level)

                # 调整大小 - 缩小时使用LANCZOS过滤，放大时使用BICUBIC过滤
                if self.zoom_level < 1.0:
                    resized_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                else:
                    resized_img = pil_img.resize((new_width, new_height), Image.BICUBIC)

                # 创建PhotoImage
                self.preview_image = ImageTk.PhotoImage(resized_img)

                # 获取画布尺寸
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()

                # 清除旧的图像
                self.preview_canvas.delete("all")

                # 计算居中位置
                # 注意：如果图像大于画布，那么将图像放在左上角并设置滚动区域
                x = max(0, (canvas_width - new_width) // 2)
                y = max(0, (canvas_height - new_height) // 2)

                # 创建图像项
                self.preview_canvas.create_image(x, y, anchor="nw", image=self.preview_image, tags="preview_image")

                # 设置滚动区域
                scroll_width = max(canvas_width, new_width)
                scroll_height = max(canvas_height, new_height)
                self.preview_canvas.config(scrollregion=(0, 0, scroll_width, scroll_height))

                # 启用鼠标拖动图像的功能
                self.enable_image_panning()
    def enable_image_panning(self):
        """启用鼠标拖动图像的功能"""

        def start_pan(event):
            self.preview_canvas.scan_mark(event.x, event.y)

        def do_pan(event):
            self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

        # 绑定鼠标事件
        self.preview_canvas.bind("<ButtonPress-2>", start_pan)  # 中键
        self.preview_canvas.bind("<B2-Motion>", do_pan)

        # 也支持Shift+左键拖动
        self.preview_canvas.bind("<Shift-ButtonPress-1>", start_pan)
        self.preview_canvas.bind("<Shift-B1-Motion>", do_pan)

        # 添加鼠标滚轮缩放
        def on_mousewheel(event):
            # Windows 滚轮事件处理
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

        def on_mousewheel_linux(event):
            # Linux 滚轮事件处理
            if event.num == 4:
                self.zoom_in()
            elif event.num == 5:
                self.zoom_out()

        # 绑定鼠标滚轮事件
        if sys.platform == 'win32':
            self.preview_canvas.bind("<MouseWheel>", on_mousewheel)
        else:
            self.preview_canvas.bind("<Button-4>", on_mousewheel_linux)
            self.preview_canvas.bind("<Button-5>", on_mousewheel_linux)
    def zoom_out(self):
        """缩小预览图像"""
        # 减小缩放级别
        self.zoom_level *= 0.8

        # 限制最小缩放级别
        if self.zoom_level < 0.1:
            self.zoom_level = 0.1

        # 更新缩放信息显示
        self.zoom_info.config(text=f"缩放: {int(self.zoom_level * 100)}%")

        # 重新绘制图像
        self.update_preview_with_zoom()

    def zoom_fit(self):
        """适应预览图像到窗口大小"""
        # 重置缩放级别
        self.zoom_level = 1.0

        # 更新缩放信息显示
        self.zoom_info.config(text=f"缩放: 100%")

        # 更新预览
        self.update_preview()

    def open_image(self):
        """打开图像文件"""
        file_path = filedialog.askopenfilename(
            initialdir=self.work_folder,
            title="打开图像",
            filetypes=(("图像文件", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
                       ("所有文件", "*.*"))
        )

        if file_path:
            self.open_image_path(file_path)

    def open_image_path(self, file_path):
        """打开指定路径的图像 - 增强版本，支持缩放和像素查看"""
        try:
            # 如果当前有图像和节点图，自动保存当前节点图
            if self.current_image_path and self.nodes:
                self.auto_save_node_graph()

            # 复制图像到工作文件夹
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.work_folder, filename)

            # 如果不是同一个文件，则复制
            if os.path.normpath(file_path) != os.path.normpath(dest_path):
                shutil.copy2(file_path, dest_path)
                print(f"已复制图像至工作文件夹: {dest_path}")

            # 更新当前图像路径为工作文件夹中的路径
            self.current_image_path = dest_path

            # 直接加载图像用于状态栏信息显示
            try:
                self.current_image = cv2.imread(dest_path, cv2.IMREAD_UNCHANGED)
                if self.current_image is not None and len(self.current_image.shape) >= 2:
                    # 如果是BGR格式，转换为RGB
                    if len(self.current_image.shape) == 3:
                        self.current_image = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)

                    # 更新图像尺寸信息
                    height, width = self.current_image.shape[:2]
                    if hasattr(self, 'image_size_label'):
                        self.image_size_label.config(text=f"尺寸: {width} x {height}")
            except Exception as e:
                print(f"加载图像预览失败: {str(e)}")
                self.current_image = None

            # 更新工作文件夹
            self.work_folder = os.path.dirname(dest_path)

            # 更新胶片预览
            self.update_film_preview()

            # 清除旧的节点图
            self.clear_node_graph()

            # 检查是否有匹配的节点图文件
            image_filename = os.path.splitext(filename)[0]
            node_graph_path = os.path.join(self.nodegraphs_folder, image_filename + ".json")

            if os.path.exists(node_graph_path):
                # 如果有匹配的节点图，加载它
                self.load_node_graph_from_file(node_graph_path)
            else:
                # 检查是否有自动保存的节点图
                auto_save_found = False

                # 确保临时文件夹存在
                if os.path.exists(self.temp_folder):
                    # 查找匹配的自动保存文件
                    matching_files = []
                    for file in os.listdir(self.temp_folder):
                        if file.startswith(image_filename + "_auto_") and file.endswith(".json"):
                            file_path = os.path.join(self.temp_folder, file)
                            # 确认文件确实存在且可访问
                            if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                                matching_files.append(file)

                    # 如果找到匹配的文件，按序号排序并加载最新的
                    if matching_files:
                        try:
                            # 按序号排序
                            matching_files.sort(key=lambda x: int(x.split("_auto_")[1].split(".")[0]))
                            # 获取最新的文件
                            latest_file = matching_files[-1]
                            auto_file_path = os.path.join(self.temp_folder, latest_file)

                            # 加载自动保存的节点图
                            auto_save_found = self.load_node_graph_from_file(auto_file_path)

                            if auto_save_found:
                                print(f"已加载自动保存的节点图: {auto_file_path}")
                        except Exception as e:
                            print(f"加载自动保存节点图出错: {str(e)}")
                            auto_save_found = False

                # 如果没有找到自动保存的节点图或加载失败，创建默认节点图
                if not auto_save_found:
                    self.create_default_node_graph()

            # 重置缩放级别
            self.zoom_level = 1.0
            if hasattr(self, 'zoom_info'):
                self.zoom_info.config(text="缩放: 100%")

            # 处理节点图并更新预览
            self.process_node_graph()

        except Exception as e:
            messagebox.showerror("打开图像错误", f"打开图像时出错:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def undo_node_graph(self, event=None):
        """撤销操作，加载最近的自动保存节点图"""
        # 如果没有当前图像路径，返回
        if not self.current_image_path:
            messagebox.showinfo("提示", "没有打开的图像")
            return

        try:
            # 获取图像文件名（不包含扩展名）
            image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]

            # 确保临时文件夹存在
            if not os.path.exists(self.temp_folder):
                os.makedirs(self.temp_folder, exist_ok=True)
                messagebox.showinfo("提示", "没有找到可撤销的节点图")
                return

            # 查找匹配的自动保存文件
            matching_files = []
            for file in os.listdir(self.temp_folder):
                if file.startswith(image_filename + "_auto_") and file.endswith(".json"):
                    file_path = os.path.join(self.temp_folder, file)
                    # 确认文件确实存在且可访问
                    if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                        matching_files.append(file)

            # 如果没有匹配的文件，提示并返回
            if not matching_files:
                messagebox.showinfo("提示", "没有找到可撤销的节点图")
                return

            # 按序号排序
            try:
                matching_files.sort(key=lambda x: int(x.split("_auto_")[1].split(".")[0]))
            except (ValueError, IndexError):
                # 如果排序失败，按文件修改时间排序
                matching_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.temp_folder, x)))

            # 需要移除当前状态并加载前一个状态
            if len(matching_files) >= 2:
                # 使用倒数第二个文件（上一个状态）
                target_file = matching_files[-2]
            else:
                # 如果只有一个文件，使用它
                target_file = matching_files[-1]

            file_path = os.path.join(self.temp_folder, target_file)

            # 再次确认文件存在
            if not os.path.exists(file_path):
                messagebox.showerror("撤销错误", f"无法访问文件: {file_path}")
                return

            print(f"尝试加载文件: {file_path}")

            # 备份当前状态
            current_state = []
            for node in self.nodes:
                node_copy = node.copy()
                # 移除不可序列化的对象
                if 'module' in node_copy:
                    node_copy['module'] = None
                if 'processed_outputs' in node_copy:
                    node_copy['processed_outputs'] = None
                current_state.append(node_copy)

            # 清除当前节点图前先完全备份状态
            current_nodes = self.nodes.copy()
            current_connections = self.connections.copy()
            current_selected = self.selected_node
            current_next_id = self.next_node_id

            # 尝试加载节点图
            load_success = self.load_node_graph_from_file(file_path)

            if load_success:
                # 处理节点图并更新预览
                self.process_node_graph()

                # 如果删除最新的文件
                latest_file = matching_files[-1]
                latest_path = os.path.join(self.temp_folder, latest_file)
                try:
                    if os.path.exists(latest_path):
                        os.remove(latest_path)
                except Exception as e:
                    print(f"删除最新自动保存文件出错: {str(e)}")

                messagebox.showinfo("撤销成功", "已恢复到上一个状态")
            else:
                # 如果加载失败，恢复之前的状态
                self.clear_node_graph()  # 先清除失败的加载

                # 恢复状态
                self.nodes = current_nodes
                self.connections = current_connections
                self.selected_node = current_selected
                self.next_node_id = current_next_id

                # 重新绘制所有节点和连接
                for node in self.nodes:
                    self.draw_node(node)

                # 更新连接
                self.update_connections()

                # 如果有选中的节点，重新选中
                if self.selected_node:
                    self.select_node(self.selected_node)

                messagebox.showerror("撤销错误", "加载自动保存的节点图失败，已恢复原状态")

        except Exception as e:
            messagebox.showerror("撤销错误", f"撤销操作时出错:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def clear_node_graph(self):
        """清除节点图"""
        # 清除所有连接
        for conn in self.connections:
            self.node_canvas.delete(conn['line_id'])

        # 清除所有节点
        for node in self.nodes:
            self.node_canvas.delete(f"node_{node['id']}")

        # 清除列表
        self.connections = []
        self.nodes = []
        self.selected_node = None

        # 清除设置区域
        for widget in self.settings_frame.winfo_children():
            widget.destroy()

    def load_node_graph_from_file(self, file_path):
        """从文件加载节点图"""
        try:
            # 从文件加载数据
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 清除当前节点图 - 确保完全清除所有元素
            self.clear_node_graph()

            # 重置节点ID计数器以避免ID冲突
            self.next_node_id = 0

            # 加载图像路径
            if 'current_image_path' in data and data['current_image_path']:
                # 只更新如果路径存在
                if os.path.exists(data['current_image_path']):
                    self.current_image_path = data['current_image_path']

            # 创建节点映射（旧ID->新节点）
            node_map = {}

            # 记录最大节点ID用于更新next_node_id
            max_id = 0

            # 加载节点
            for node_data in data['nodes']:
                # 检查脚本是否存在
                script_path = node_data['script_path']
                if not os.path.exists(script_path):
                    continue

                # 解析脚本信息
                script_info = self.parse_script_header(script_path)
                if not script_info:
                    continue

                # 创建节点 - 使用原始ID
                original_id = node_data['id']
                if original_id > max_id:
                    max_id = original_id

                # 临时保存当前ID计数器
                temp_id = self.next_node_id
                self.next_node_id = original_id

                # 创建节点
                node = self.add_node(script_path, script_info)

                # 更新位置前先删除原来绘制的节点
                self.node_canvas.delete(f"node_{node['id']}")

                # 更新位置
                node['x'], node['y'] = node_data['x'], node_data['y']
                self.draw_node(node)

                # 更新参数
                if 'params' in node_data:
                    for param_name, param_value in node_data['params'].items():
                        if param_name in node['params']:
                            node['params'][param_name]['value'] = param_value

                # 添加到映射
                node_map[original_id] = node

            # 确保next_node_id比所有加载的节点ID都大
            self.next_node_id = max_id + 1

            # 加载连接
            for conn_data in data['connections']:
                # 查找节点
                if (conn_data['output_node_id'] in node_map and
                        conn_data['input_node_id'] in node_map):
                    output_node = node_map[conn_data['output_node_id']]
                    input_node = node_map[conn_data['input_node_id']]

                    # 创建连接
                    self.create_connection(
                        output_node, conn_data['output_port'],
                        input_node, conn_data['input_port']
                    )

            # 更新节点图
            self.update_connections()

            # 确保画布清理所有未使用的元素
            all_items = self.node_canvas.find_all()
            used_items = []

            # 收集所有有效节点和连接的画布ID
            for node in self.nodes:
                self.node_canvas.addtag_withtag(f"valid_node", f"node_{node['id']}")

            for conn in self.connections:
                self.node_canvas.addtag_withtag("valid_conn", conn['line_id'])

            # 删除所有不是有效节点或连接的元素
            for item in all_items:
                tags = self.node_canvas.gettags(item)
                if not ("valid_node" in tags or "valid_conn" in tags or "grid" in tags):
                    self.node_canvas.delete(item)

            # 重绘网格确保它在所有元素的底层
            self.draw_node_grid()

            return True
        except Exception as e:
            print(f"加载节点图出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def create_default_node_graph(self):
        """创建默认节点图 - 自动换行布局"""
        # 先清除任何现有节点
        self.clear_node_graph()

        # 重置节点ID计数器
        self.next_node_id = 0

        # 查找默认脚本
        image_script = os.path.join(self.scripts_folder, "图像节点.py")
        decode_script = os.path.join(self.scripts_folder, "解码节点.py")
        process_script = os.path.join(self.scripts_folder, "基本处理.py")
        preview_script = os.path.join(self.scripts_folder, "预览节点.py")
        export_script = os.path.join(self.scripts_folder, "导出节点.py")

        # 检查脚本是否存在
        if not all(os.path.exists(s) for s in
                   [image_script, decode_script, process_script, preview_script, export_script]):
            messagebox.showerror("缺少脚本", "缺少默认节点脚本文件")
            return

        # 解析脚本信息
        scripts_info = {}
        for script in [image_script, decode_script, process_script, preview_script, export_script]:
            info = self.parse_script_header(script)
            if info:
                scripts_info[script] = info

        # 获取可见区域宽度，用于计算节点布局
        visible_width = self.node_canvas.winfo_width()
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
            node['x'], node['y'] = x, y
            self.node_canvas.delete(f"node_{node['id']}")
            self.draw_node(node)

            nodes.append(node)

        # 创建连接 - 按照顺序连接节点
        for i in range(len(nodes) - 1):
            self.create_connection(nodes[i], 0, nodes[i + 1], 0)

        # 更新节点图
        self.update_connections()

        # 如果有当前打开的图像，为图像节点设置路径参数
        if self.current_image_path:
            nodes[0]['params']['image_path']['value'] = self.current_image_path

        # 计算所需的滚动区域
        max_row = (len(node_scripts) - 1) // nodes_per_row
        scroll_width = 50 + nodes_per_row * (node_width + node_spacing_x)
        scroll_height = 50 + (max_row + 1) * node_spacing_y + 100

        # 设置滚动区域确保所有节点可见
        self.node_canvas.config(scrollregion=(0, 0, scroll_width, scroll_height))

    def add_zoom_keyboard_shortcuts(self):
        """添加缩放相关的键盘快捷键和右键菜单项"""
        # 创建缩放快捷菜单项
        if hasattr(self, 'preview_context_menu'):
            return  # 已经添加过，避免重复添加

        self.preview_context_menu = tk.Menu(self.root, tearoff=0, bg="#444444", fg="white")
        self.preview_context_menu.add_command(label="放大 (+)", command=self.zoom_in)
        self.preview_context_menu.add_command(label="缩小 (-)", command=self.zoom_out)
        self.preview_context_menu.add_command(label="适应窗口 (□)", command=self.zoom_fit)
        self.preview_context_menu.add_separator()
        self.preview_context_menu.add_command(label="100% (1:1)", command=lambda: self.set_zoom_level(1.0))
        self.preview_context_menu.add_command(label="200% (2:1)", command=lambda: self.set_zoom_level(2.0))
        self.preview_context_menu.add_command(label="50% (1:2)", command=lambda: self.set_zoom_level(0.5))
        self.preview_context_menu.add_separator()
        self.preview_context_menu.add_command(label="复制到剪贴板", command=self.copy_image_to_clipboard)
        self.preview_context_menu.add_command(label="导出当前视图", command=self.export_current_view)

        # 绑定右键菜单到预览画布
        self.preview_canvas.bind("<Button-3>", self.show_preview_context_menu)

        # 添加缩放键盘快捷键
        self.root.bind("<Control-plus>", lambda event: self.zoom_in())
        self.root.bind("<Control-equal>", lambda event: self.zoom_in())  # Ctrl+= 也是放大
        self.root.bind("<Control-minus>", lambda event: self.zoom_out())
        self.root.bind("<Control-0>", lambda event: self.zoom_fit())  # Ctrl+0 重置缩放

        # 添加图像导航快捷键
        self.root.bind("<Up>", lambda event: self.pan_image(0, -20))
        self.root.bind("<Down>", lambda event: self.pan_image(0, 20))
        self.root.bind("<Left>", lambda event: self.pan_image(-20, 0))
        self.root.bind("<Right>", lambda event: self.pan_image(20, 0))
    def save_node_graph(self):
        """保存节点图配置"""
        # 如果没有当前图像路径或没有节点，不保存
        if not self.current_image_path or not self.nodes:
            messagebox.showinfo("提示", "没有图像或节点图可保存")
            return

        try:
            # 获取图像文件名（不包含扩展名）
            image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]

            # 创建文件名
            filename = f"{image_filename}.json"
            file_path = os.path.join(self.nodegraphs_folder, filename)

            # 保存节点图
            if self.save_node_graph_to_file(file_path):
                messagebox.showinfo("保存成功", f"节点图已保存到:\n{file_path}")
            else:
                messagebox.showerror("保存错误", "保存节点图时出错")

        except Exception as e:
            messagebox.showerror("保存错误", f"保存节点图时出错:\n{str(e)}")

    def load_node_graph(self):
        """加载节点图配置"""
        # 选择加载文件
        file_path = filedialog.askopenfilename(
            initialdir=self.nodegraphs_folder,
            title="加载节点图",
            filetypes=(("JSON文件", "*.json"), ("所有文件", "*.*"))
        )

        if not file_path:
            return

        # 加载节点图
        if self.load_node_graph_from_file(file_path):
            # 处理节点图并更新预览
            self.process_node_graph()
            messagebox.showinfo("加载成功", "节点图已加载")
        else:
            messagebox.showerror("加载错误", "加载节点图时出错")

    def export_image(self):
        """Export the current image using the export node's sub_export function"""
        # Find export node
        export_node = None
        for node in self.nodes:
            if 'export_node' in node['title'].lower():
                export_node = node
                break

        if export_node:
            try:
                # Get node parameters
                params = {name: param_info['value'] for name, param_info in export_node['params'].items()}

                # Get node inputs
                input_data = self.get_node_inputs(export_node)

                # Create context information
                context = {
                    'app': self,  # Pass application instance
                    'work_folder': self.work_folder,
                    'current_image_path': self.current_image_path,
                    'temp_folder': self.temp_folder,
                    'scripts_folder': self.scripts_folder,
                    'node_id': export_node['id'],
                    'node_title': export_node['title']
                }

                # Execute the sub_export function from the module
                if hasattr(export_node['module'], 'sub_export'):
                    result = export_node['module'].sub_export(params, input_data, context)

                    # Handle result
                    if result and isinstance(result, dict):
                        if result.get('success', False):
                            # Show success message if provided
                            if 'message' in result:
                                messagebox.showinfo("Export Successful", result['message'])
                        else:
                            # Show error message if provided
                            if 'error' in result:
                                messagebox.showerror("Export Failed", result['error'])
                else:
                    messagebox.showinfo("Notice", "The export node doesn't have a sub_export function")
            except Exception as e:
                messagebox.showerror("Export Error", f"Error exporting image: {str(e)}")
        else:
            messagebox.showinfo("Notice", "Please add an export node first")

    def on_closing(self):
        """窗口关闭时询问是否保存节点图"""
        if self.current_image_path and self.nodes:
            # 询问是否保存当前节点图
            answer = messagebox.askyesnocancel("退出", "是否保存当前节点图？")

            if answer is None:  # 取消
                return

            if answer:  # 是
                # 获取图像文件名（不包含扩展名）
                image_filename = os.path.splitext(os.path.basename(self.current_image_path))[0]

                # 创建文件名
                filename = f"{image_filename}.json"
                file_path = os.path.join(self.nodegraphs_folder, filename)

                # 保存节点图
                self.save_node_graph_to_file(file_path)

        # 销毁窗口
        self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    root.title("Tunnel NX Legacy")

    # 设置图标
    # root.iconbitmap("imgpp_icon.ico")  # 如果有图标可以取消注释

    # 创建应用
    app = TunnelNX(root)

    # 运行主循环
    root.mainloop()


if __name__ == "__main__":
    main()
