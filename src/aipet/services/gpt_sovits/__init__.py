# -*- coding: utf-8 -*-
"""
GPT-SoVITS 语音合成服务的初始化与高阶接口封装。
本文件动态调整 Python 的 sys.path，保证内部绝对导入在集成状态下能够正常解析，并管理模型实例缓存。
"""

import os
import sys
import numpy as np
import soundfile as sf

# 解决 Windows 下多 OpenMP 库冲突导致的 WinError 1114 动态链接库初始化失败问题
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 1. 在 Windows 下把 torch/lib 加入 DLL 查找路径，防止 Python 3.8+ 载入 c10.dll 报错
if sys.platform == "win32":
    import site
    # 收集所有可能的库路径以定位 torch/lib
    search_paths = []
    try:
        search_paths.extend(site.getsitepackages())
    except Exception:
        pass
    for p in sys.path:
        if p and os.path.isdir(p):
            search_paths.append(p)
            
    # 遍历路径，若包含 torch/lib 文件夹则加入 DLL 搜索目录
    for p in search_paths:
        torch_lib = os.path.join(p, "torch", "lib")
        if os.path.isdir(torch_lib):
            try:
                os.add_dll_directory(torch_lib)
            except Exception:
                pass
    try:
        import torch  # 提前导入 torch 保证 DLL 句柄完全加载并绑定
    except Exception as e:
        print(f"[GPT-SoVITS] Warning: Pre-loading torch failed: {e}")

# 2. 动态将当前目录和其子目录加入 sys.path，使得 GPT_SoVITS 的绝对导入可以正常工作
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 3. 将当前包注册为 sys.modules['GPT_SoVITS']，以向下兼容一些绝对导入 (例如 f5_tts.model)
sys.modules['GPT_SoVITS'] = sys.modules[__name__]

# 导入内部核心推理解析包
from TTS_infer_pack.TTS import TTS, TTS_Config

# 缓存已加载的 TTS 模型示例，键为：(t2s_weights_path, vits_weights_path, version, device)
_synthesizer_cache = {}

def get_synthesizer(t2s_weights_path: str, vits_weights_path: str, version: str = "v2", device: str = "cpu") -> TTS:
    """
    根据给定的模型路径与版本，获取或实例化对应的 TTS 推理器（带内存缓存）。
    
    参数:
        t2s_weights_path: GPT(T2S) 模型的绝对路径
        vits_weights_path: SoVITS 模型的绝对路径
        version: 模型版本，可选 v1, v2, v2Pro, v2ProPlus 等
        device: 推理设备，可选 "cpu", "cuda", "mps"
    返回:
        TTS 推理器实例
    """
    cache_key = (t2s_weights_path, vits_weights_path, version, device)
    if cache_key in _synthesizer_cache:
        return _synthesizer_cache[cache_key]
        
    # 计算项目绝对根路径与基础 BERT/Hubert 路径
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    base_model_dir = os.path.join(project_root, "resources", "models", "gpt_sovits_base")
    
    bert_base_path = os.path.join(base_model_dir, "chinese-roberta-wwm-ext-large")
    cnhuhbert_base_path = os.path.join(base_model_dir, "chinese-hubert-base")
    
    # 构造绝对路径配置，强制覆写以防止使用内部默认的相对路径
    config_dict = {
        "custom": {
            "device": device,
            "is_half": False, # CPU 运行默认采用 float32，不启用半精度以兼容更多设备
            "version": version,
            "t2s_weights_path": t2s_weights_path,
            "vits_weights_path": vits_weights_path,
            "cnhuhbert_base_path": cnhuhbert_base_path,
            "bert_base_path": bert_base_path,
        }
    }
    
    print(f"[GPT-SoVITS] 正在载入语音合成引擎 (版本: {version}, 设备: {device})...")
    print(f"  - GPT 权重: {t2s_weights_path}")
    print(f"  - SoVITS 权重: {vits_weights_path}")
    
    # 初始化配置与推理管线
    tts_config = TTS_Config(config_dict)
    synthesizer = TTS(tts_config)
    
    if device == "cpu":
        # CPU 运行强制把所有模型转为 float32，防止某些从 fp16 权重加载的模型在 CPU 上计算报错
        if synthesizer.cnhuhbert_model is not None:
            synthesizer.cnhuhbert_model = synthesizer.cnhuhbert_model.float()
        if synthesizer.bert_model is not None:
            synthesizer.bert_model = synthesizer.bert_model.float()
        if synthesizer.t2s_model is not None:
            synthesizer.t2s_model = synthesizer.t2s_model.float()
        if synthesizer.vits_model is not None:
            synthesizer.vits_model = synthesizer.vits_model.float()
    
    # 缓存实例
    _synthesizer_cache[cache_key] = synthesizer
    return synthesizer

def gpt_sovits_convert(
    text: str,
    text_lang: str,
    ref_wav_path: str,
    prompt_text: str,
    prompt_lang: str,
    output_wav_path: str,
    gpt_ckpt_path: str = None,
    sovits_pth_path: str = None,
    version: str = "v2",
    device: str = "cpu",
    temperature: float = 0.4 # 增加采样温度控制参数
):
    """
    调用本地 GPT-SoVITS 引擎进行文本到语音的合成，并保存为 wav 文件。
    
    参数:
        text: 待合成的目标文本
        text_lang: 目标文本语言 (zh: 中文, ja: 日文, en: 英文, auto: 自动切分)
        ref_wav_path: 参考音频路径 (通常为 3-10 秒的 wav 剪辑)
        prompt_text: 参考音频对应的文本内容
        prompt_lang: 参考音频的语言
        output_wav_path: 输出音频的绝对路径
        gpt_ckpt_path: 微调 GPT 模型 (.ckpt) 绝对路径；若为 None 则自动使用官方通用底模
        sovits_pth_path: 微调 SoVITS 模型 (.pth) 绝对路径；若为 None 则自动使用官方通用底模
        version: 模型版本 (v1, v2, v2Pro, v2ProPlus)
        device: 推理硬件平台 ("cpu", "cuda")
        temperature: 推理采样温度 (常用于降低自回归预测的电流噪声)
    """
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
    base_model_dir = os.path.join(project_root, "resources", "models", "gpt_sovits_base")
    
    # 判定并适配零样本与微调模式的权重路径
    if not gpt_ckpt_path or not os.path.exists(gpt_ckpt_path):
        # 零样本降级，使用官方默认底模
        if version == "v1":
            gpt_ckpt_path = os.path.join(base_model_dir, "s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt")
        else:
            gpt_ckpt_path = os.path.join(base_model_dir, "gsv-v2final-pretrained", "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")
            
    if not sovits_pth_path or not os.path.exists(sovits_pth_path):
        # 零样本降级，使用官方默认底模
        if version == "v1":
            sovits_pth_path = os.path.join(base_model_dir, "s2G488k.pth")
        elif version == "v2Pro":
            sovits_pth_path = os.path.join(base_model_dir, "v2Pro", "s2Gv2Pro.pth")
        elif version == "v2ProPlus":
            sovits_pth_path = os.path.join(base_model_dir, "v2Pro", "s2Gv2ProPlus.pth")
        else:
            sovits_pth_path = os.path.join(base_model_dir, "gsv-v2final-pretrained", "s2G2333k.pth")
            
    # 获取或载入 synthesizer 实例
    synthesizer = get_synthesizer(gpt_ckpt_path, sovits_pth_path, version, device)
    
    # 构造推理输入字典
    inputs = {
        "text": text,
        "text_lang": text_lang.lower(),
        "ref_audio_path": ref_wav_path,
        "prompt_text": prompt_text,
        "prompt_lang": prompt_lang.lower(),
        "top_k": 5,
        "top_p": 1.0,
        "temperature": temperature, # 动态设置采样温度以取得降噪调优效果
        "text_split_method": "cut5",  # 默认使用按标点与长度切分的 cut5 算法
        "batch_size": 1,
        "speed_factor": 1.0,
        "streaming_mode": False
    }
    
    # 执行推理，TTS.run 是一个生成器，由于关闭了流式，只会 yield 一次完整的合成音频
    results = list(synthesizer.run(inputs))
    if len(results) > 0:
        sr, audio_data = results[0]
        # 保存为 16bit PCM wav 音频
        sf.write(output_wav_path, audio_data, sr, format="wav", subtype="PCM_16")
        print(f"[GPT-SoVITS] 语音合成成功，输出至: {output_wav_path}")
    else:
        raise RuntimeError("GPT-SoVITS 推理未产生有效的音频数据输出。")
