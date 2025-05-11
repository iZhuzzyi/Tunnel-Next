#f32bmp,constant
#f32bmp,constant
#加法
#FF8C00
import numpy as np

def get_params():
    """定义节点参数"""
    return {
        'enable_10bit_scaling': {
            'type': 'checkbox',
            'label': '启用10bit数值缩放(0-1023)',
            'value': False
        },
        'offset_x': {
            'type': 'slider',
            'label': 'X偏移',
            'min': -1000,
            'max': 1000,
            'value': 0,
            'step': 1
        },
        'offset_y': {
            'type': 'slider',
            'label': 'Y偏移',
            'min': -1000,
            'max': 1000,
            'value': 0,
            'step': 1
        }
    }

def process(inputs, params):
    # 检查输入
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("加法节点缺少f32bmp输入")
        return {'f32bmp': None, 'constant': None}
        
    if 'constant' not in inputs or inputs['constant'] is None:
        print("加法节点缺少constant输入，输入键：", list(inputs.keys()))
        return {'f32bmp': inputs['f32bmp'], 'constant': None}
    
    try:
        # 获取图像输入
        img = inputs['f32bmp'].copy()
        
        # 获取常量输入
        constant_input = inputs['constant']
        
        # 检查常量输入是否为常量值(1x1x4)还是图像(HxWx4)
        is_image_input = constant_input.shape[0] > 1 or constant_input.shape[1] > 1
        
        # 获取偏移值
        offset_x = params.get('offset_x', 0)
        offset_y = params.get('offset_y', 0)
        
        # 创建输出图像副本
        result = img.copy()
        
        if is_image_input:
            # 处理图像叠加（常量输入是图像）
            print(f"加法节点：检测到图像输入：形状={constant_input.shape}，应用偏移(x={offset_x}, y={offset_y})")
            
            # 确定两个图像的重叠区域
            h1, w1 = img.shape[:2]  # 第一个输入的高度和宽度
            h2, w2 = constant_input.shape[:2]  # 第二个输入的高度和宽度
            
            # 计算有效重叠区域
            x1 = max(0, offset_x)  # 第一个图像中的起始x
            y1 = max(0, offset_y)  # 第一个图像中的起始y
            x2 = max(0, -offset_x)  # 第二个图像中的起始x
            y2 = max(0, -offset_y)  # 第二个图像中的起始y
            
            # 计算重叠区域的宽度和高度
            w = min(w1 - x1, w2 - x2)
            h = min(h1 - y1, h2 - y2)
            
            # 确保重叠区域有效
            if w <= 0 or h <= 0:
                print("加法节点：警告 - 图像偏移后没有重叠区域")
                return {'f32bmp': result, 'constant': constant_input}
            
            # 为了确保不会有浮点舍入误差，转换为整数
            x1, y1, x2, y2, w, h = int(x1), int(y1), int(x2), int(y2), int(w), int(h)
            
            # 逐像素加法运算
            result[y1:y1+h, x1:x1+w, 0] = np.clip(result[y1:y1+h, x1:x1+w, 0] + constant_input[y2:y2+h, x2:x2+w, 0], 0.0, 1.0)  # R
            result[y1:y1+h, x1:x1+w, 1] = np.clip(result[y1:y1+h, x1:x1+w, 1] + constant_input[y2:y2+h, x2:x2+w, 1], 0.0, 1.0)  # G
            result[y1:y1+h, x1:x1+w, 2] = np.clip(result[y1:y1+h, x1:x1+w, 2] + constant_input[y2:y2+h, x2:x2+w, 2], 0.0, 1.0)  # B
            # Alpha通道保持不变
            
        else:
            # 处理常量值叠加（常量输入是单个像素）
            constant_value = constant_input[0, 0, 0]
            
            # 检查是否启用10bit缩放
            enable_10bit_scaling = params.get('enable_10bit_scaling', False)
            
            # 如果启用10bit缩放，将0-1023范围缩放到0-1范围
            if enable_10bit_scaling:
                # 假设输入值在0-1023范围内，除以1023将其缩放到0-1范围
                constant_value = constant_value / 1023.0
                print(f"加法节点：应用10bit缩放，原始值={constant_input[0, 0, 0]}，缩放后={constant_value}")
            
            print(f"加法节点：常量值={constant_value}，图像形状={img.shape}，10bit缩放={enable_10bit_scaling}")
            
            # 对所有像素应用加法操作
            result[:, :, 0] = np.clip(result[:, :, 0] + constant_value, 0.0, 1.0)  # R
            result[:, :, 1] = np.clip(result[:, :, 1] + constant_value, 0.0, 1.0)  # G
            result[:, :, 2] = np.clip(result[:, :, 2] + constant_value, 0.0, 1.0)  # B
        
        # 返回处理后的图像和原始常量输入
        return {
            'f32bmp': result,
            'constant': constant_input
        }
        
    except Exception as e:
        print(f"加法节点处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        # 出错时，尽可能保留输入
        outputs = {}
        if 'f32bmp' in inputs:
            outputs['f32bmp'] = inputs['f32bmp']
        if 'constant' in inputs:
            outputs['constant'] = inputs['constant']
        return outputs