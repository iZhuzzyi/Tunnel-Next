#tif16
#tif16,tif16
#傅里叶变换 - 生成幅度谱和相位谱
#3399FF
import cv2
import numpy as np

def process(inputs, params):
    # 检查输入
    if 'tif16' not in inputs or inputs['tif16'] is None:
        return {'tif16_magnitude': None, 'tif16_phase': None}
    
    # 获取图像
    img = inputs['tif16'].copy()
    
    # 如果图像是彩色的，转换为灰度图
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # 确保图像尺寸适合FFT（加速计算）
    rows, cols = img.shape
    optimal_rows = cv2.getOptimalDFTSize(rows)
    optimal_cols = cv2.getOptimalDFTSize(cols)
    
    # 如果需要，填充图像到最佳尺寸
    padded = cv2.copyMakeBorder(img, 0, optimal_rows - rows, 0, optimal_cols - cols, 
                                cv2.BORDER_CONSTANT, value=0)
    
    # 应用窗函数减少频谱泄漏（如果启用）
    if params.get('apply_window', False):
        window = cv2.createHanningWindow((padded.shape[1], padded.shape[0]), cv2.CV_32F)
        padded = padded * window
    
    # 执行傅里叶变换
    dft = cv2.dft(np.float32(padded), flags=cv2.DFT_COMPLEX_OUTPUT)
    
    # 移动零频率到中心（如果需要）
    if params.get('center_fft', True):
        dft_shift = np.fft.fftshift(dft)
    else:
        dft_shift = dft
    
    # 计算幅度谱和相位谱
    magnitude_spectrum = cv2.magnitude(dft_shift[:,:,0], dft_shift[:,:,1])
    phase_spectrum = cv2.phase(dft_shift[:,:,0], dft_shift[:,:,1])
    
    # 对幅度谱应用对数变换以增强可视化效果（如果需要）
    if params.get('apply_log_transform', True):
        # 这里我们在进行log变换前加1，避免log(0)的问题
        magnitude_spectrum = np.log(1 + magnitude_spectrum)
    
    # 归一化到0-65535范围以适应uint16存储
    magnitude_output = cv2.normalize(magnitude_spectrum, None, 0, 65535, cv2.NORM_MINMAX).astype(np.uint16)
    
    # 相位谱已经在-pi到pi范围内，需要映射到0-65535
    phase_normalized = (phase_spectrum + np.pi) / (2 * np.pi) * 65535
    phase_output = phase_normalized.astype(np.uint16)
    
    # 将原始尺寸信息存储在幅度谱的前几个像素中
    if params.get('store_metadata', True):
        # 使用前4个像素存储原始尺寸和其他元数据
        # 实际应用中可能需要更好的方式存储元数据
        magnitude_output[0, 0] = rows
        magnitude_output[0, 1] = cols
        magnitude_output[0, 2] = 1 if params.get('apply_log_transform', True) else 0
        magnitude_output[0, 3] = 1 if params.get('center_fft', True) else 0
    
    # 返回两个输出，使用tif16类型
    return {
        'tif16_magnitude': magnitude_output,
        'tif16_phase': phase_output
    }

def get_params():
    return {
        'apply_log_transform': {'type': 'checkbox', 'label': '应用对数变换', 'value': True},
        'center_fft': {'type': 'checkbox', 'label': '零频率居中', 'value': True},
        'store_metadata': {'type': 'checkbox', 'label': '存储元数据', 'value': True},
        'apply_window': {'type': 'checkbox', 'label': '应用汉宁窗', 'value': False},
        'enhance_preview': {'type': 'checkbox', 'label': '增强预览效果', 'value': True},
    }

def sub_enhance_magnitude_preview(params, inputs, context):
    """增强幅度谱的预览效果"""
    if 'tif16' not in inputs or inputs['tif16'] is None:
        return {'success': False, 'error': '没有输入图像'}
    
    try:
        # 应用预览增强
        return {
            'success': True, 
            'message': '幅度谱预览已增强',
            'update_params': {
                'apply_log_transform': True,
                'center_fft': True
            }
        }
    except Exception as e:
        return {'success': False, 'error': f'增强失败: {str(e)}'}