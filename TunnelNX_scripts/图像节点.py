#
# img
# 打开图像并输出
# FFFFFF
import cv2
import numpy as np


def process(inputs, params):
    # 输入为空，输出图像
    if 'image_path' in params:
        image_path = params['image_path']
        # --- 打印接收到的路径 --- 
        print(f"[图像节点 DEBUG] Received image_path: {image_path}") 
        # ---------------------------
        # 读取图像 - 使用 imdecode 解决中文路径问题
        try:
            with open(image_path, 'rb') as f:
                # 读取文件内容到字节缓冲区
                file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            # 从内存缓冲区解码图像
            image = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        except Exception as e:
            print(f"[错误] 使用 imdecode 加载图像时出错: {image_path} - {e}")
            image = None
            
        # image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED) # 旧方法

        # 检查图像是否成功加载
        if image is None:
            print(f"[警告] 图像节点无法加载图像: {image_path}") # 添加警告
            return {'img': None, 'format': ''}

        # 如果是彩色图像（3通道BGR），转换颜色空间从BGR到RGB
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # 注意：对于4通道BGRA图像，此处不进行转换，解码节点将处理

        # 返回图像和文件格式
        file_format = image_path.split('.')[-1].lower()

        return {'img': image, 'format': file_format}
    return {'img': None, 'format': ''}


def get_params():
    return {
        'image_path': {'type': 'path', 'label': '图像路径', 'value': ''}
    }