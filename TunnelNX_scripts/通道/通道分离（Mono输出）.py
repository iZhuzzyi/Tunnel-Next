#f32bmp
#ChannelR,ChannelG,ChannelB,ChannelA
#将输入图像分离为四个独立单通道
#4682B4
import numpy as np

def process(inputs, params):
    """处理输入图像，将各个通道分离为单通道图像"""
    # 获取输入元数据
    input_metadata = inputs.get('_metadata', {})

    # 检查输入
    if 'f32bmp' not in inputs or inputs['f32bmp'] is None:
        print("通道分离器：缺少f32bmp输入")
        return {'ChannelR': None, 'ChannelG': None, 'ChannelB': None, 'ChannelA': None}

    try:
        # 获取输入图像
        img = inputs['f32bmp']
        print(f"通道分离器：输入图像形状 = {img.shape}, 类型 = {img.dtype}")

        # 获取图像尺寸
        if len(img.shape) == 3:
            h, w, c = img.shape
            has_channels = True
        else:  # 处理灰度图像
            h, w = img.shape
            has_channels = False

        # 创建四个单通道输出图像
        if has_channels:
            # 提取R通道
            if img.shape[2] > 0:
                channel_r = img[:, :, 0:1].copy()  # 保持形状为(h,w,1)
            else:
                channel_r = np.zeros((h, w, 1), dtype=np.float32)

            # 提取G通道
            if img.shape[2] > 1:
                channel_g = img[:, :, 1:2].copy()  # 保持形状为(h,w,1)
            else:
                channel_g = np.zeros((h, w, 1), dtype=np.float32)

            # 提取B通道
            if img.shape[2] > 2:
                channel_b = img[:, :, 2:3].copy()  # 保持形状为(h,w,1)
            else:
                channel_b = np.zeros((h, w, 1), dtype=np.float32)

            # 提取A通道
            if img.shape[2] > 3:
                channel_a = img[:, :, 3:4].copy()  # 保持形状为(h,w,1)
            else:
                channel_a = np.ones((h, w, 1), dtype=np.float32)  # 默认Alpha为1
        else:
            # 处理灰度图像 - 只有R通道有值，其他为0
            channel_r = img.reshape(h, w, 1).copy()
            channel_g = np.zeros((h, w, 1), dtype=np.float32)
            channel_b = np.zeros((h, w, 1), dtype=np.float32)
            channel_a = np.ones((h, w, 1), dtype=np.float32)  # 默认Alpha为1

        print(f"通道分离器：输出通道形状 R={channel_r.shape}, G={channel_g.shape}, B={channel_b.shape}, A={channel_a.shape}")

        # 创建输出元数据
        output_metadata = input_metadata.copy() if input_metadata else {}
        output_metadata.update({
            'channels': 1,
            'format': 'mono_channels',
            'width': w,
            'height': h,
            'operation': 'mono_channel_separation'
        })

        # 返回四个单通道和元数据
        return {
            'ChannelR': channel_r,
            'ChannelG': channel_g,
            'ChannelB': channel_b,
            'ChannelA': channel_a,
            '_metadata': output_metadata
        }

    except Exception as e:
        print(f"通道分离器处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        # 出错时返回空结果
        return {'ChannelR': None, 'ChannelG': None, 'ChannelB': None, 'ChannelA': None}