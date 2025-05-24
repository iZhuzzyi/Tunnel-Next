#f32bmp,f32bmp
#f32bmp
#逐像素比较两张图像，RGB通道独立比较
#9370DB
import numpy as np

def get_params():
    """定义节点参数"""
    return {
        'comparison_type': {
            'type': 'dropdown',
            'label': '比较类型',
            'value': '大于',
            'options': ['大于', '等于', '小于', '大于等于', '小于等于', '不等于']
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
        },
        'threshold': {
            'type': 'slider',
            'label': '容差阈值',
            'min': 0.0,
            'max': 0.1,
            'value': 0.001,
            'step': 0.001
        }
    }

def process(inputs, params):
    """处理两个输入图像，进行逐像素比较并输出结果"""
    # 检查第一个输入
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("比较节点缺少第一个f32bmp输入")
        return {'f32bmp': None}
    
    # 寻找第二个输入
    second_input_key = None
    for key in inputs:
        if key != 'f32bmp' and key.startswith('f32bmp'):
            second_input_key = key
            break
    
    if second_input_key is None or inputs[second_input_key] is None:
        print(f"比较节点缺少第二个f32bmp输入，可用输入键：{list(inputs.keys())}")
        return {'f32bmp': inputs['f32bmp']}
    
    try:
        # 获取两个输入图像
        img1 = inputs['f32bmp'].copy()
        img2 = inputs[second_input_key].copy()
        
        print(f"逐像素比较：图像1形状={img1.shape}，图像2形状={img2.shape}")
        
        # 获取参数
        comparison_type = params.get('comparison_type', '大于')
        offset_x = int(params.get('offset_x', 0))
        offset_y = int(params.get('offset_y', 0))
        threshold = float(params.get('threshold', 0.001))
        
        print(f"比较类型：{comparison_type}，偏移=({offset_x},{offset_y})，阈值={threshold}")
        
        # 获取图像尺寸
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        # 创建输出图像（四通道浮点图像）
        output = np.zeros((h1, w1, 4), dtype=np.float32)
        
        # 计算有效重叠区域
        x1 = max(0, offset_x)  # 第一个图像中的起始x
        y1 = max(0, offset_y)  # 第一个图像中的起始y
        x2 = max(0, -offset_x)  # 第二个图像中的起始x
        y2 = max(0, -offset_y)  # 第二个图像中的起始y
        
        # 计算重叠区域的宽度和高度
        w = min(w1 - x1, w2 - x2)
        h = min(h1 - y1, h2 - y2)
        
        print(f"重叠区域：起点1=({x1},{y1})，起点2=({x2},{y2})，宽度={w}，高度={h}")
        
        # 确保重叠区域有效
        if w <= 0 or h <= 0:
            print("比较节点：警告 - 图像偏移后没有重叠区域")
            # 返回全黑图像，但Alpha通道为1.0
            output[:, :, 3] = 1.0
            return {'f32bmp': output}
        
        # 确定两个图像的通道数（仅比较RGB通道，最多3个通道）
        channels1 = min(img1.shape[2], 3) if len(img1.shape) > 2 else 1
        channels2 = min(img2.shape[2], 3) if len(img2.shape) > 2 else 1
        channels = min(channels1, channels2)
        
        print(f"处理通道数：图像1={channels1}，图像2={channels2}，实际处理={channels}")
        
        # 对RGB通道分别进行比较
        for i in range(channels):
            # 提取当前通道
            if len(img1.shape) > 2:
                img1_channel = img1[y1:y1+h, x1:x1+w, i]
            else:
                img1_channel = img1[y1:y1+h, x1:x1+w]
                
            if len(img2.shape) > 2:
                img2_channel = img2[y2:y2+h, x2:x2+w, i]
            else:
                img2_channel = img2[y2:y2+h, x2:x2+w]
            
            # 根据比较类型执行比较操作
            if comparison_type == '大于':
                result = img1_channel > (img2_channel + threshold)
            elif comparison_type == '等于':
                result = np.abs(img1_channel - img2_channel) <= threshold
            elif comparison_type == '小于':
                result = img1_channel < (img2_channel - threshold)
            elif comparison_type == '大于等于':
                result = img1_channel >= (img2_channel - threshold)
            elif comparison_type == '小于等于':
                result = img1_channel <= (img2_channel + threshold)
            elif comparison_type == '不等于':
                result = np.abs(img1_channel - img2_channel) > threshold
            else:
                # 默认使用大于比较
                result = img1_channel > img2_channel
            
            # 将布尔结果转换为浮点值（True=1.0, False=0.0）
            result_float = result.astype(np.float32)
            
            # 将结果填充到输出图像的对应通道
            output[y1:y1+h, x1:x1+w, i] = result_float
            
            # 打印通道比较的基本统计信息
            true_count = np.sum(result)
            total_pixels = result.size
            print(f"通道{i}比较结果：True像素数={true_count}/{total_pixels} ({true_count/total_pixels*100:.2f}%)")
        
        # 如果通道数小于3，将剩余通道填充为0.0
        for i in range(channels, 3):
            output[:, :, i] = 0.0
            print(f"通道{i}设置为全0.0（未比较）")
            
        # 始终将Alpha通道设置为1.0（完全不透明）
        output[:, :, 3] = 1.0
        print("Alpha通道设置为全1.0（不进行比较）")
            
        # 返回比较结果图像
        return {'f32bmp': output}
        
    except Exception as e:
        print(f"比较节点处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        # 出错时返回空结果，但确保Alpha通道为1.0
        if 'f32bmp' in inputs and inputs['f32bmp'] is not None:
            output = np.zeros_like(inputs['f32bmp'])
            if output.shape[2] >= 4:
                output[:, :, 3] = 1.0
            return {'f32bmp': output}
        return {'f32bmp': None}