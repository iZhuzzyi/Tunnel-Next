# img,f32bmp
# f32bmp
# 生成文字图像
# 3366FF
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os


def process(inputs, params):
    # 获取参数
    text = params.get('text', '示例文字')
    font_name = params.get('font_name', 'SimSun')
    font_size = int(params.get('font_size', 32))
    text_color = params.get('text_color', '#FFFFFF')
    background_color = params.get('background_color', '#000000')
    image_width = int(params.get('image_width', 800))
    image_height = int(params.get('image_height', 600))
    position_x = int(params.get('position_x', 50))
    position_y = int(params.get('position_y', 50))

    # 解析颜色
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    text_rgb = hex_to_rgb(text_color)
    bg_rgb = hex_to_rgb(background_color)

    # 使用PIL创建图像
    try:
        # 如果输入中有图像，使用输入图像作为背景
        if ('img' in inputs and inputs['img'] is not None) or ('f32bmp' in inputs and inputs['f32bmp'] is not None):
            if 'f32bmp' in inputs and inputs['f32bmp'] is not None:
                # 使用f32bmp作为背景 - 避免不必要的复制
                bg_img = inputs['f32bmp']
                # 转换为8位用于PIL处理
                bg_img_8bit = (bg_img * 255).clip(0, 255).astype(np.uint8)
                pil_img = Image.fromarray(bg_img_8bit)
            else:
                # 使用普通图像作为背景 - 避免不必要的复制
                bg_img = inputs['img']

                # 转换为PIL图像进行处理
                if bg_img.dtype == np.uint16:
                    # 16位图像需要归一化到0-255
                    bg_img_8bit = (bg_img / 256).astype(np.uint8)
                    pil_img = Image.fromarray(bg_img_8bit)
                else:
                    pil_img = Image.fromarray(bg_img)

            # 如果是灰度图像，转换为RGB
            if pil_img.mode == 'L':
                pil_img = pil_img.convert('RGB')
        else:
            # 创建空白图像
            pil_img = Image.new('RGB', (image_width, image_height), bg_rgb)

        # 获取系统字体路径
        def get_system_font_path(font_name):
            # 常见的字体路径
            font_paths = {
                'Windows': [
                    'C:/Windows/Fonts',
                ],
                'Darwin': [  # macOS
                    '/System/Library/Fonts',
                    '/Library/Fonts',
                    os.path.expanduser('~/Library/Fonts')
                ],
                'Linux': [
                    '/usr/share/fonts',
                    '/usr/local/share/fonts',
                    os.path.expanduser('~/.fonts')
                ]
            }

            # 尝试常见的字体文件扩展名
            extensions = ['.ttf', '.ttc', '.otf', '.TIF', '.TTC', '.OTF']

            # 根据操作系统获取字体路径
            import platform
            system = platform.system()

            for path in font_paths.get(system, []):
                if os.path.exists(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_lower = file.lower()
                            name_lower = font_name.lower()

                            # 检查文件名是否匹配请求的字体名称
                            if any(file_lower == name_lower + ext.lower() for ext in extensions) or \
                                    any(name_lower in file_lower and file_lower.endswith(ext.lower()) for ext in
                                        extensions):
                                return os.path.join(root, file)

            # 如果没有找到匹配的字体，返回None
            return None

        # 尝试加载字体
        font_path = get_system_font_path(font_name)

        if font_path:
            font = ImageFont.truetype(font_path, font_size)
        else:
            # 使用默认字体
            font = ImageFont.load_default()
            print(f"警告：找不到字体 '{font_name}'，使用默认字体")

        # 创建绘图对象
        draw = ImageDraw.Draw(pil_img)

        # 绘制文字
        draw.text((position_x, position_y), text, font=font, fill=text_rgb)

        # 将PIL图像转回OpenCV格式
        cv_img = np.array(pil_img)

        # 转换为f32bmp格式 (范围[0.0, 1.0])
        f32_img = cv_img.astype(np.float32) / 255.0

        # 返回f32bmp格式
        return {'f32bmp': f32_img}

    except Exception as e:
        print(f"错误：{str(e)}")
        # 返回空图像
        empty_img = np.zeros((image_height, image_width, 3), dtype=np.float32)
        return {'f32bmp': empty_img}


def get_params():
    return {
        'text': {'type': 'text', 'label': '文字内容', 'value': '示例文字'},
        'font_name': {'type': 'dropdown', 'label': '字体', 'options': [
            'SimSun', 'SimHei', 'Microsoft YaHei', 'KaiTi', 'FangSong',  # 中文常用字体
            'Arial', 'Times New Roman', 'Courier New', 'Verdana', 'Georgia'  # 英文常用字体
        ], 'value': 'SimSun'},
        'font_size': {'type': 'slider', 'label': '字号', 'min': 8, 'max': 144, 'value': 32},
        'text_color': {'type': 'text', 'label': '文字颜色(十六进制)', 'value': '#FFFFFF'},
        'background_color': {'type': 'text', 'label': '背景颜色(十六进制)', 'value': '#000000'},
        'image_width': {'type': 'slider', 'label': '图像宽度', 'min': 100, 'max': 4096, 'value': 800},
        'image_height': {'type': 'slider', 'label': '图像高度', 'min': 100, 'max': 4096, 'value': 600},
        'position_x': {'type': 'slider', 'label': '文字X坐标', 'min': 0, 'max': 4000, 'value': 50},
        'position_y': {'type': 'slider', 'label': '文字Y坐标', 'min': 0, 'max': 4000, 'value': 50},
    }


def sub_center_text(params, inputs, context):
    """将文字居中显示在图像上"""
    try:
        # 获取图像尺寸
        if 'f32bmp' in inputs and inputs['f32bmp'] is not None:
            img = inputs['f32bmp']
        elif 'img' in inputs and inputs['img'] is not None:
            img = inputs['img']
        else:
            img_width = int(params.get('image_width', 800))
            img_height = int(params.get('image_height', 600))
            return {
                'success': True,
                'message': '已将文字居中',
                'update_params': {
                    'position_x': img_width // 2 - 50,  # 估计的文字宽度的一半
                    'position_y': img_height // 2 - 20,  # 估计的文字高度的一半
                }
            }

        img_height, img_width = img.shape[:2]

        # 估算文字宽度和高度
        font_size = int(params.get('font_size', 32))
        text_width_estimate = len(params.get('text', '示例文字')) * font_size * 0.6
        text_height_estimate = font_size * 1.2

        return {
            'success': True,
            'message': '已将文字居中',
            'update_params': {
                'position_x': int(img_width // 2 - text_width_estimate // 2),
                'position_y': int(img_height // 2 - text_height_estimate // 2),
            }
        }
    except Exception as e:
        return {'success': False, 'error': f'居中失败: {str(e)}'}


def sub_color_picker(params, inputs, context):
    """颜色选择器辅助功能"""
    # 这个子功能仅作为示例，实际实现可能需要应用程序支持弹出颜色选择器
    return {
        'success': True,
        'message': '颜色选择功能需要应用程序支持',
    }