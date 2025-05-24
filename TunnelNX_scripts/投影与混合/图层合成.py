# f32bmp:
# f32bmp
# 图层合成: 将多个图层按指定模式合成为单个图像。支持多种混合模式。
# 4CAF50
# Type:NeoScript

import numpy as np
from PIL import Image, ImageChops
import concurrent.futures
import multiprocessing

# 支持的混合模式列表
SUPPORTED_BLEND_MODES = [
    "正常", "变暗", "正片叠底", "颜色加深", "线性加深",
    "变亮", "滤色", "颜色减淡", "线性减淡(添加)",
    "叠加", "柔光", "强光", "亮光", "线性光", "点光",
    "实色混合", "差值", "排除", "减去", "划分",
    "色相", "饱和度", "颜色", "明度"
]

def get_params():
    """定义节点的参数"""
    return {
        "default_blend_mode": {
            "label": "默认混合模式",
            "type": "dropdown",
            "options": SUPPORTED_BLEND_MODES,
            "value": "正常"
        },
        "default_opacity": {
            "label": "默认不透明度 (%)",
            "type": "slider",
            "min": 0,
            "max": 100,
            "step": 1,
            "value": 100
        }
        # 未来可以为每个图层添加单独的混合模式和不透明度控制
        # 这可能需要自定义设置UI
    }

def blend_normal(base_img_np, blend_img_np, opacity=1.0):
    """正常混合模式"""
    # opacity 应用于 blend_img_np
    # Formula: result = blend_img * opacity + base_img * (1 - opacity)
    # 但是由于blend_img是直接叠加在base_img上，opacity应该只调整blend_img的强度
    # 然后再用标准的alpha混合公式，但这里简单处理为：
    # result = base * (1 - alpha_blend) + top * alpha_blend
    # alpha_blend 是 top 图层的不透明度。
    # 如果顶层图像有alpha通道，则应使用该alpha，乘以opacity。
    # 此处简化：opacity 直接调整顶层图像的贡献。

    if base_img_np.shape != blend_img_np.shape:
        # 尝试将单通道灰度图扩展以匹配多通道图层
        if base_img_np.ndim == 2 and blend_img_np.ndim == 3:
            base_img_np = np.stack([base_img_np]*blend_img_np.shape[2], axis=-1)
        elif blend_img_np.ndim == 2 and base_img_np.ndim == 3:
            blend_img_np = np.stack([blend_img_np]*base_img_np.shape[2], axis=-1)
        
        if base_img_np.shape[:2] != blend_img_np.shape[:2]: # 检查高宽是否一致
             raise ValueError(f"基础图层和混合图层的尺寸不匹配: {base_img_np.shape} vs {blend_img_np.shape}")


    # 确保图像是浮点型，范围 0-1
    base = np.clip(base_img_np.astype(np.float32) / 255.0 if base_img_np.max() > 1.0 else base_img_np.astype(np.float32), 0, 1)
    blend = np.clip(blend_img_np.astype(np.float32) / 255.0 if blend_img_np.max() > 1.0 else blend_img_np.astype(np.float32), 0, 1)
    
    # 处理alpha通道（如果存在）
    base_alpha = base[..., 3:4] if base.shape[-1] == 4 else np.ones_like(base[..., 0:1])
    blend_alpha = blend[..., 3:4] if blend.shape[-1] == 4 else np.ones_like(blend[..., 0:1])
    
    # 应用不透明度
    effective_blend_alpha = blend_alpha * opacity
    
    # 混合RGB
    # result_rgb = base_rgb * (1 - blend_alpha_effective) + blend_rgb * blend_alpha_effective
    # out_alpha = base_alpha + effective_blend_alpha * (1 - base_alpha) # Porter-Duff 'source over'
    
    # 标准 Alpha 合成 (Over operator)
    # Co = Cs * As + Cb * Ab * (1 - As)
    # Ao = As + Ab * (1 - As)
    # 其中 Cs,As 是前景(blend_img), Cb,Ab 是背景(base_img)
    # 这里 Cs 是 blend * opacity, As 是 effective_blend_alpha

    # 输出的alpha通道
    out_alpha = effective_blend_alpha + base_alpha * (1.0 - effective_blend_alpha)
    out_alpha = np.clip(out_alpha, 0, 1) # 确保alpha在0-1之间
    
    # 防止除以零
    out_alpha_safe = np.where(out_alpha == 0, 1e-6, out_alpha)

    result_rgb = (blend[..., :3] * effective_blend_alpha + base[..., :3] * base_alpha * (1.0 - effective_blend_alpha)) / out_alpha_safe
    result_rgb = np.clip(result_rgb, 0, 1)

    if base.shape[-1] == 4 or blend.shape[-1] == 4 : # 如果任一输入有alpha，输出也带alpha
        final_result_np = np.concatenate((result_rgb, out_alpha), axis=-1)
    else:
        final_result_np = result_rgb

    return (final_result_np * 255).astype(base_img_np.dtype)


def pil_to_np(pil_image):
    """将Pillow图像转换为NumPy数组，确保为RGB或RGBA"""
    if pil_image.mode not in ['RGB', 'RGBA']:
        pil_image = pil_image.convert('RGBA') # 转换为 RGBA 以获得一致性
    return np.array(pil_image)

def np_to_pil(np_array):
    """将NumPy数组转换为Pillow图像"""
    if np_array.dtype != np.uint8:
        if np_array.max() <= 1.0 and np_array.min() >=0.0:
            np_array = (np_array * 255).astype(np.uint8)
        else:
            np_array = np_array.astype(np.uint8)
    
    # 如果是 HxWx1 (单通道灰度图但有通道维度)，则压缩为 HxW
    if np_array.ndim == 3 and np_array.shape[2] == 1:
        np_array = np_array.squeeze(axis=-1)

    if np_array.ndim == 3 and np_array.shape[2] == 3:
        return Image.fromarray(np_array, 'RGB')
    elif np_array.ndim == 3 and np_array.shape[2] == 4:
        return Image.fromarray(np_array, 'RGBA')
    elif np_array.ndim == 2: # 灰度图
        return Image.fromarray(np_array, 'L')
    else:
        raise ValueError(f"不受支持的 NumPy 数组形状用于转换为Pillow图像: {np_array.shape}")


# Pillow的混合模式名称与此脚本中定义的可能不同，需要映射
# Pillow ImageChops functions work on single channel or RGB.
# For RGBA, they often ignore alpha or behave unexpectedly.
# We need to handle alpha blending carefully.

def blend_pil_compatible(base_pil, blend_pil, mode_str, opacity=1.0):
    """使用Pillow的混合模式，注意处理透明度"""
    
    if base_pil.size != blend_pil.size:
        blend_pil = blend_pil.resize(base_pil.size, Image.LANCZOS)

    base_np = pil_to_np(base_pil.convert("RGBA")) / 255.0
    blend_np = pil_to_np(blend_pil.convert("RGBA")) / 255.0

    base_rgb = base_np[..., :3]
    base_alpha = base_np[..., 3:4]
    blend_rgb = blend_np[..., :3] # 这是原始混合图层的RGB颜色 (0-1 float)
    blend_alpha = blend_np[..., 3:4]

    # 应用图层不透明度到混合图层的Alpha通道 (此为 As)
    # blend_rgb_opac 在这里没有太大意义，因为opacity主要影响alpha
    # Cs_rgb (混合后的源颜色) 会根据mode_str决定
    As = blend_alpha * opacity 
    As = np.clip(As, 0, 1) # 确保 As 在0-1

    # 为了Pillow操作，准备RGB图像 (uint8)
    base_pil_rgb = Image.fromarray((base_rgb * 255).astype(np.uint8), 'RGB')
    # blend_pil_for_ops 用于 Pillow 混合操作，它应该是原始混合图层的 RGB
    blend_pil_for_ops = Image.fromarray((blend_rgb * 255).astype(np.uint8), 'RGB')

    # --- 确定 Cs_rgb (混合后的源RGB颜色，float 0-1) ---
    # Cs_pil 是 Pillow Image 对象，表示混合模式应用后的RGB结果
    if mode_str == "正常":
        Cs_pil = blend_pil_for_ops 
    elif mode_str == "变暗":
        Cs_pil = ImageChops.darker(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "正片叠底":
        Cs_pil = ImageChops.multiply(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "颜色加深":
        # NumPy 实现: 1.0 - (1.0 - base_rgb) / blend_rgb_safe
        blend_rgb_safe = np.where(blend_rgb == 0, 1e-6, blend_rgb)
        result_rgb_f = 1.0 - (1.0 - base_rgb) / blend_rgb_safe
        result_rgb_f = np.clip(result_rgb_f, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "线性加深":
        result_rgb_f = np.clip(base_rgb + blend_rgb - 1.0, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "变亮":
        Cs_pil = ImageChops.lighter(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "滤色":
        Cs_pil = ImageChops.screen(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "颜色减淡":
        # NumPy 实现: base_rgb / (1.0 - blend_rgb_safe)
        blend_rgb_safe = np.where(blend_rgb >= 1.0, 1.0 - 1e-6, blend_rgb)
        result_rgb_f = base_rgb / (1.0 - blend_rgb_safe)
        result_rgb_f = np.clip(result_rgb_f, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "线性减淡(添加)":
        # ImageChops.add clamps to 255. For float (0-1) this is clip(base+blend,0,1)
        result_rgb_f = np.clip(base_rgb + blend_rgb, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "叠加":
        Cs_pil = ImageChops.overlay(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "柔光":
        Cs_pil = ImageChops.soft_light(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "强光":
        Cs_pil = ImageChops.hard_light(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "差值":
        Cs_pil = ImageChops.difference(base_pil_rgb, blend_pil_for_ops)
    elif mode_str == "排除":
        result_rgb_f = base_rgb + blend_rgb - 2 * base_rgb * blend_rgb
        result_rgb_f = np.clip(result_rgb_f, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "减去":
        result_rgb_f = np.clip(base_rgb - blend_rgb, 0, 1)
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    elif mode_str == "划分":
        result_rgb_f = np.zeros_like(base_rgb)
        non_zero_blend_mask = blend_rgb > 1e-6
        zero_blend_mask = ~non_zero_blend_mask
        result_rgb_f[non_zero_blend_mask] = np.clip(base_rgb[non_zero_blend_mask] / blend_rgb[non_zero_blend_mask], 0, 1)
        result_rgb_f[zero_blend_mask & (base_rgb[zero_blend_mask] > 1e-6)] = 1.0
        result_rgb_f[zero_blend_mask & (base_rgb[zero_blend_mask] <= 1e-6)] = 0.0
        Cs_pil = Image.fromarray((result_rgb_f * 255).astype(np.uint8), 'RGB')
    # HSL modes (色相, 饱和度, 颜色, 明度) and others like (亮光, 线性光, 点光, 实色混合) are not yet implemented.
    # They will fall into the else case.
    else: 
        print(f"警告: 混合模式 '{mode_str}' 未完全实现或未知，RGB通道将按'正常'模式处理（即直接使用顶层颜色）。")
        Cs_pil = blend_pil_for_ops # Default to Normal mode behavior for RGB part

    Cs_rgb_np = np.array(Cs_pil.convert('RGB')).astype(np.float32) / 255.0 # Shape (H,W,3)

    # --- Alpha Compositing (Porter-Duff: Source Over Background) ---
    # Formula: Co = (Cs*As + Cb*Ab*(1-As)) / Ao if Ao > 0 else 0
    #          Ao = As + Ab*(1-As)
    # Where: Cs = Cs_rgb_np (source color), As = As (source alpha, already has opacity)
    #        Cb = base_rgb (background color), Ab = base_alpha (background alpha)

    Ab = base_alpha # Shape (H,W,1)

    # Output Alpha (Ao)
    final_alpha = As + Ab * (1.0 - As)
    final_alpha = np.clip(final_alpha, 0, 1) # Shape (H,W,1)

    # Numerator for Output Color (Co_num = Cs*As + Cb*Ab*(1-As))
    numerator_rgb = Cs_rgb_np * As + base_rgb * Ab * (1.0 - As) # Shape (H,W,3)

    # Output RGB (Co)
    output_rgb = np.zeros_like(base_rgb) # Initialize with zeros, shape (H,W,3)
    
    # Condition for safe division: final_alpha > epsilon
    condition_mask = final_alpha > 1e-6 # Shape (H,W,1), boolean

    # Calculate Co where Ao > 0
    # np.where broadcasts condition_mask (H,W,1) to match numerator_rgb (H,W,3) and final_alpha (H,W,1)
    # For division, final_alpha (H,W,1) broadcasts with numerator_rgb (H,W,3)
    calculated_rgb_values = numerator_rgb / final_alpha 
    
    output_rgb = np.where(condition_mask, calculated_rgb_values, 0.0) # if final_alpha is ~0, output_rgb is 0
    output_rgb = np.clip(output_rgb, 0, 1)

    # Combine final RGB and Alpha
    final_output_np = np.concatenate((output_rgb, final_alpha), axis=-1) # Shape (H,W,4)
    
    return (final_output_np * 255).astype(np.uint8)


def process_chunk(chunk_data):
    """处理图像分块的函数，用于并行处理"""
    base_chunk, blend_chunk, mode_str, opacity = chunk_data
    base_pil = np_to_pil(base_chunk)
    blend_pil = np_to_pil(blend_chunk)
    return blend_pil_compatible(base_pil, blend_pil, mode_str, opacity)

def split_image(img_np, num_chunks):
    """将图像分割成若干块，用于并行处理"""
    h, w = img_np.shape[:2]
    chunk_height = h // num_chunks
    chunks = []
    
    for i in range(num_chunks):
        start_h = i * chunk_height
        end_h = (i+1) * chunk_height if i < num_chunks-1 else h
        chunk = img_np[start_h:end_h, :]
        chunks.append((chunk, start_h, end_h))
    
    return chunks

def merge_chunks(chunks, original_shape):
    """合并处理后的图像块"""
    h, w = original_shape[:2]
    channels = original_shape[2] if len(original_shape) > 2 else 1
    result = np.zeros((h, w, channels), dtype=np.uint8)
    
    for chunk_data, start_h, end_h in chunks:
        result[start_h:end_h, :] = chunk_data
    
    return result

def parallel_blend(base_img_np, blend_img_np, mode_str, opacity, num_workers=None):
    """并行处理图像混合"""
    if num_workers is None:
        # 由于使用ThreadPoolExecutor，可以使用更多线程
        # 对于IO密集型操作，线程数可以适当高于CPU核心数
        num_workers = min(32, multiprocessing.cpu_count() * 2)
    
    # 如果图像太小，不值得并行处理
    h, w = base_img_np.shape[:2]
    if h * w < 250000:  # 小于250K像素的图像不进行并行处理
        base_pil = np_to_pil(base_img_np)
        blend_pil = np_to_pil(blend_img_np)
        return blend_pil_compatible(base_pil, blend_pil, mode_str, opacity)
    
    # 将图像分成与工作线程数量相同的块
    base_chunks = split_image(base_img_np, num_workers)
    blend_chunks = split_image(blend_img_np, num_workers)
    
    # 准备工作数据
    work_data = []
    for i in range(len(base_chunks)):
        base_chunk, _, _ = base_chunks[i]
        blend_chunk, _, _ = blend_chunks[i]
        work_data.append((base_chunk, blend_chunk, mode_str, opacity))
    
    # 使用线程池并行处理（避免进程池的pickle问题）
    processed_chunks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        chunk_results = list(executor.map(process_chunk, work_data))
        
        for i, result in enumerate(chunk_results):
            _, start_h, end_h = base_chunks[i]
            processed_chunks.append((result, start_h, end_h))
    
    # 合并结果
    return merge_chunks(processed_chunks, base_img_np.shape)

def process(inputs, params, context):
    """核心处理函数"""
    layers_data = []
    # 按照 TunnelNext 灵活输入的命名规则 f32bmp, f32bmp_1, f32bmp_2 ... 获取输入
    base_input_name = 'f32bmp' 
    i = 0
    while True:
        key = base_input_name if i == 0 else f'{base_input_name}_{i}'
        if key in inputs and inputs[key] is not None:
            layer_img_np = inputs[key]
            if not isinstance(layer_img_np, np.ndarray):
                print(f"警告: 输入 {key} 不是 NumPy 数组，已跳过。类型: {type(layer_img_np)}")
                i += 1
                continue
            if layer_img_np.ndim == 2:
                layer_img_np = layer_img_np[..., np.newaxis]
            if layer_img_np.dtype != np.uint8:
                if layer_img_np.max() <= 1.0 and layer_img_np.min() >= 0.0:
                    layer_img_np = (layer_img_np * 255).astype(np.uint8)
                else:
                    layer_img_np = layer_img_np.astype(np.uint8)
            
            layers_data.append(layer_img_np)
            i += 1
        else:
            # 尝试检查没有后缀的下一个序号，例如 f32bmp_2 之后可能是 f32bmp_3 而不是 f32bmp_2_1
            # 不过通常灵活端口是 _idx 形式，所以当前逻辑应该能覆盖大部分情况
            # 如果 inputs 中完全没有更多 f32bmp 或 f32bmp_i 格式的key，则中断
            if not any(k.startswith(base_input_name) for k in inputs if k not in [base_input_name if j == 0 else f'{base_input_name}_{j}' for j in range(i)]):
                break
            # 为了避免无限循环（如果输入字典的key不按预期排列），加一个最大尝试次数
            if i > 50: # 假设不会有超过50个图层输入
                print("警告：检测到过多图层输入尝试，已中断获取图层。")
                break
            break

    if not layers_data:
        print("图层合成：没有输入图层。")
        return {}

    if len(layers_data) == 1:
        return {'f32bmp': layers_data[0]} # 确保输出键名与头部一致

    # 获取参数
    blend_mode_str = params.get('default_blend_mode', '正常')
    opacity_percent = params.get('default_opacity', 100)
    opacity = float(opacity_percent) / 100.0
    
    # 对于线程池，使用更多线程可以提高性能
    num_workers = min(32, multiprocessing.cpu_count() * 2)

    try:
        current_result_np = layers_data[0]
        if current_result_np.ndim == 3 and current_result_np.shape[2] == 1:
            current_result_np = np.concatenate([current_result_np]*3, axis=-1)

        for i in range(1, len(layers_data)):
            blend_layer_np = layers_data[i]
            if blend_layer_np.ndim == 3 and blend_layer_np.shape[2] == 1:
                blend_layer_np = np.concatenate([blend_layer_np]*3, axis=-1)
            
            if current_result_np.shape[:2] != blend_layer_np.shape[:2]:
                print(f"警告: 图层 {i} 的尺寸 {blend_layer_np.shape[:2]} 与基础图层 {current_result_np.shape[:2]} 不匹配。将尝试调整尺寸。")
                h, w = current_result_np.shape[:2]
                pil_blend_temp = np_to_pil(blend_layer_np)
                pil_blend_temp_resized = pil_blend_temp.resize((w,h), Image.LANCZOS)
                blend_layer_np = pil_to_np(pil_blend_temp_resized)

            # 使用并行处理来混合图层
            current_result_np = parallel_blend(current_result_np, blend_layer_np, blend_mode_str, opacity, num_workers)

            if not isinstance(current_result_np, np.ndarray):
                print(f"错误: 并行混合返回的不是 NumPy 数组，类型: {type(current_result_np)}")
                if isinstance(current_result_np, Image.Image):
                    current_result_np = pil_to_np(current_result_np)
                else: 
                    current_result_np = layers_data[i-1] if i > 0 else layers_data[0]
                    # 返回上一个有效状态，或者第一个图层，如果这是第一次迭代出错
                    return {'f32bmp': current_result_np } 

        final_output = current_result_np

    except ValueError as e:
        print(f"图层合成处理错误: {e}")
        import traceback
        traceback.print_exc()
        return {}
    except Exception as e:
        print(f"图层合成发生未知错误: {e}")
        import traceback
        traceback.print_exc()
        return {}

    return {'f32bmp': final_output} # 确保输出键名与头部一致

# 可以在这里添加更多具体的混合模式实现函数 (如果不用Pillow的或者Pillow没有提供)
# 例如:
# def blend_difference_np(base_np, blend_np, opacity=1.0):
#     # base_np, blend_np should be float [0,1]
#     # Apply opacity to blend_np's color contribution
#     # For difference, opacity is tricky. Usually applied before mode.
#     # For now, assume blend_np is already opacity-adjusted if needed, or apply simply
#     blend_adj = blend_np * opacity + base_np * (1-opacity) # simple alpha blend before difference
#     return np.abs(base_np - blend_adj)

# def blend_screen_np(base_np, blend_np, opacity=1.0):
#     # base_np, blend_np should be float [0,1]
#     # screen: 1 - (1-base) * (1-blend)
#     # Apply opacity: conceptually, blend layer at certain opacity over base.
#     # C = Cb * (1-alpha_eff) + (1-(1-Cb)*(1-Cs)) * alpha_eff
#     # where Cs is blend_np, Cb is base_np, alpha_eff is opacity
#     # This is complex. A simpler approach is to blend the result of screen(base,blend) with base.
#     # screened_color = 1 - (1 - base_np) * (1 - blend_np)
#     # return base_np * (1 - opacity) + screened_color * opacity

# ... 更多混合模式的 Numpy 实现 ...
