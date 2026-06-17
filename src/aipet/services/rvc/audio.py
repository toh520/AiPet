import os
import traceback
import librosa
import numpy as np
import soundfile as sf

# 彻底移除 PyAV (import av) 依赖，改用 soundfile 和 librosa 加载音频
# 这样可以极大简化 Windows 环境依赖并缩小打包体积。

def load_audio(file, sr):
    """
    加载音频文件并重采样到指定的采样率（通常为 16000Hz）
    
    参数:
        file: 音频文件路径，或者 (sampling_rate, audio_data) 元组
        sr: 目标采样率
    返回:
        float32 格式的一维 numpy 数组
    """
    # 如果传入的是元组 (sampling_rate, audio_data)，通常来自于前端/Gradio的直接音频输入
    if isinstance(file, tuple) or isinstance(file, list):
        try:
            orig_sr = file[0]
            audio = file[1]
            # 转换为 float32 归一化格式
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32) / 32768.0
            # 如果是双声道，取均值转换为单声道
            if len(audio.shape) == 2:
                audio = np.mean(audio, -1)
            # 重采样到指定目标采样率
            if orig_sr != sr:
                return librosa.resample(audio, orig_sr=orig_sr, target_sr=sr)
            return audio
        except Exception as e:
            raise RuntimeError(f"处理音频元组时出错: {traceback.format_exc()}")

    # 处理字符串文件路径
    file = (
        file.strip(" ").strip('"').strip("\n").strip('"').strip(" ")
    )
    if not os.path.exists(file):
        raise RuntimeError(f"输入的音频文件路径不存在: {file}")

    try:
        # 优先使用 librosa.load，它可以自动重采样并转换为单声道
        audio, orig_sr = librosa.load(file, sr=sr, mono=True)
        return audio
    except Exception as e:
        # 如果 librosa 载入失败，则尝试用 soundfile 读取并手动重采样
        try:
            audio, orig_sr = sf.read(file)
            # 如果是双声道，取均值转换为单声道
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=-1)
            audio = audio.astype(np.float32)
            if orig_sr != sr:
                audio = librosa.resample(audio, orig_sr=orig_sr, target_sr=sr)
            return audio
        except Exception as e2:
            raise RuntimeError(f"无法加载音频文件 {file}。Librosa 报错: {e}，Soundfile 报错: {e2}\n{traceback.format_exc()}")

