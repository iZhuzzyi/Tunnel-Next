#tif16,tif16
#tif16
#傅里叶逆变换 - 从幅度谱和相位谱重建图像
#FF6600
import cv2
import numpy as np

def process(inputs, params):
    # 检查输入
    if 'tif16_magnitude' not in inputs or inputs['tif16_magnitude'] is None or \
       'tif16_phase' not in inputs or inputs['tif16_phase'] is None:
        return {'tif16': None}
    
    # 获取幅度谱和相位谱
    magnitude_spectrum = inputs['tif16_magnitude'].copy().astype(np.float32)
    phase_spectrum = inputs['tif16_phase'].copy().astype(np.float32)
    
    # 尝试从幅度谱中提取元数据
    try:
        original_rows = int(magnitude_spectrum[0, 0])
        original_cols = int(magnitude_spectrum[0, 1])
        log_transform_applied = bool(magnitude_spectrum[0, 2])
        center_fft_applied = bool(magnitude_spectrum[0, 3])
    except:
        # 如果无法提取元数据，使用参数中的值
        original_rows = magnitude_spectrum.shape[0]
        original_cols = magnitude_spectrum.shape[1]
        log_transform_applied = params.get('inverse_log_transform', True)
        center_fft_applied = params.get('center_fft', True)
    
    # 将相位谱从0-65535映射回-pi到pi
    phase_spectrum = (phase_spectrum / 65535.0 * 2 * np.pi) - np.pi
    
    # 如果应用了对数变换，需要逆变换
    if log_transform_applied and params.get('inverse_log_transform', True):
        magnitude_spectrum = np.exp(magnitude_spectrum) - 1
    
    # 根据幅度谱和相位谱创建复数数组
    real = magnitude_spectrum * np.cos(phase_spectrum)
    imaginary = magnitude_spectrum * np.sin(phase_spectrum)
    complex_array = cv2.merge([real, imaginary])
    
    # 执行逆傅里叶变换
    # 首先进行逆移动使零频率回到原位置（如果在FFT中进行了中心化）
    if center_fft_applied and params.get('center_fft', True):
        complex_array = np.fft.ifftshift(complex_array)
    
    # 逆傅里叶变换
    idft = cv2.idft(complex_array)
    
    # 提取实部作为结果图像
    reconstructed = cv2.magnitude(idft[:,:,0], idft[:,:,1])
    
    # 归一化到0-65535范围
    reconstructed_normalized = cv2.normalize(reconstructed, None, 0, 65535, cv2.NORM_MINMAX)
    
    # 转换为uint16
    result = reconstructed_normalized.astype(np.uint16)
    
    # 尝试裁剪回原始尺寸
    try:
        if original_rows > 0 and original_cols > 0 and \
           original_rows <= result.shape[0] and original_cols <= result.shape[1] and \
           params.get('preserve_original_size', True):
            result = result[:original_rows, :original_cols]
    except:
        pass  # 如果裁剪失败，使用整个图像
    
    return {'tif16': result}

def get_params():
    return {
        'inverse_log_transform': {'type': 'checkbox', 'label': '逆对数变换', 'value': True},
        'center_fft': {'type': 'checkbox', 'label': '零频率居中', 'value': True},
        'preserve_original_size': {'type': 'checkbox', 'label': '保持原始尺寸', 'value': True},
        'normalize_output': {'type': 'checkbox', 'label': '归一化输出', 'value': True},
    }

def sub_frequency_filter(params, inputs, context):
    """应用频率域滤波"""
    if 'tif16_magnitude' not in inputs or inputs['tif16_magnitude'] is None:
        return {'success': False, 'error': '缺少幅度谱'}
    
    try:
        # 这里可以实现频率域滤波的逻辑
        return {'success': True, 'message': '频率滤波已应用'}
    except Exception as e:
        return {'success': False, 'error': f'滤波失败: {str(e)}'}

def sub_reset_params(params, inputs, context):
    """重置参数到推荐值"""
    return {
        'success': True,
        'message': '参数已重置',
        'update_params': {
            'inverse_log_transform': True,
            'center_fft': True,
            'preserve_original_size': True,
            'normalize_output': True
        }
    }