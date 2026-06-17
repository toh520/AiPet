import os
import sys

# 解决 Windows 下多 OpenMP 库冲突导致的 WinError 1114 动态链接库初始化失败问题
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Windows 平台且 Python 3.8+ 下，为防止 PyTorch CPU 导入时发生 DLL 初始化失败 OSError 1114 错误
# 遍历 site.getsitepackages() 以及 sys.path 动态定位并添加 torch/lib 路径至 DLL 搜索目录中
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    import site
    search_paths = []
    try:
        search_paths.extend(site.getsitepackages())
    except Exception:
        pass
    for p in sys.path:
        if p and os.path.isdir(p):
            search_paths.append(p)
            
    for p in search_paths:
        if p:
            torch_lib = os.path.join(p, "torch", "lib")
            if os.path.isdir(torch_lib):
                try:
                    os.add_dll_directory(torch_lib)
                except Exception:
                    pass

import torch
import numpy as np
import soundfile as sf

from aipet.services.rvc.config import Config
from aipet.services.rvc.pipeline import Pipeline
from aipet.services.rvc.audio import load_audio
from aipet.services.rvc.infer_pack.models import (
    SynthesizerTrnMs256NSFsid,
    SynthesizerTrnMs256NSFsid_nono,
    SynthesizerTrnMs768NSFsid,
    SynthesizerTrnMs768NSFsid_nono,
)

_hubert_model = None

def load_hubert(hubert_path, config):
    """单例模式载入 Hubert 语义模型，避免重复加载引起内存泄露"""
    global _hubert_model
    if _hubert_model is not None:
        return _hubert_model
    
    from aipet.services.rvc.hubert import HubertModel
    model = HubertModel()
    
    # 加载已提取的纯权重 (hubert_base_state.pt / ContentVec)
    # 显式设置 weights_only=False 以兼容 PyTorch 2.6+ 默认的安全反序列化机制限制
    state_dict = torch.load(hubert_path, map_location="cpu", weights_only=False)
    # 过滤掉不需要的 mask_emb 和 label_embs_concat 字段
    for k in ["mask_emb", "label_embs_concat"]:
        if k in state_dict:
            del state_dict[k]
            
    model.load_state_dict(state_dict)
    model.to(config.device).eval()
    _hubert_model = model
    return _hubert_model

def rvc_convert(
    model_path,
    index_path,
    hubert_path,
    input_wav_path,
    output_wav_path,
    f0_up_key=0,
    f0_method="pm",
    index_rate=0.75,
    rms_mix_rate=0.25,
    protect=0.33,
):
    """
    RVC 一键式变声转换核心包装接口 (自包含推理链)
    """
    config = Config()
    
    # 1. 载入角色专属变声权重 (.pth)
    # 显式设置 weights_only=False 防止 PyTorch 2.6+ 因反序列化安全规则报错
    cpt = torch.load(model_path, map_location="cpu", weights_only=False)
    tgt_sr = cpt["config"][-1]
    cpt["config"][-3] = cpt["weight"]["emb_g.weight"].shape[0]  # n_spk
    if_f0 = cpt.get("f0", 1)
    version = cpt.get("version", "v1")
    
    # 根据模型版本和是否支持音高，选取对应的前向合成网络类
    if version == "v1":
        if if_f0 == 1:
            net_g = SynthesizerTrnMs256NSFsid(*cpt["config"], is_half=config.is_half)
        else:
            net_g = SynthesizerTrnMs256NSFsid_nono(*cpt["config"])
    else:
        if if_f0 == 1:
            net_g = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=config.is_half)
        else:
            net_g = SynthesizerTrnMs768NSFsid_nono(*cpt["config"])
            
    # 载入 state_dict 权重数据
    net_g.load_state_dict(cpt["weight"], strict=False)
    net_g.eval().to(config.device)
    
    # 2. 载入通用的 Hubert 语义编码模型
    hubert_model = load_hubert(hubert_path, config)
    
    # 3. 读取待变声的普通基础音频
    audio = load_audio(input_wav_path, 16000)
    audio_max = np.abs(audio).max() / 0.95
    if audio_max > 1:
        audio /= audio_max
        
    # 4. 执行变声 Pipeline 推理
    pipeline = Pipeline(tgt_sr, config)
    times = [0, 0, 0]
    
    audio_opt = pipeline.pipeline(
        hubert_model,
        net_g,
        0,  # Speaker ID (单说话人默认为 0)
        audio,
        input_wav_path,
        times,
        f0_up_key,
        f0_method,
        index_path if os.path.exists(index_path) else "",
        index_rate,
        if_f0,
        3,  # filter_radius 滤波器半径
        tgt_sr,
        tgt_sr,  # resample_sr 目标重采样率
        rms_mix_rate,
        version,
        protect,
    )
    
    # 5. 保存合成后的 wav 音频
    sf.write(output_wav_path, audio_opt, tgt_sr)
    print(f"RVC Convert Success -> Saved output to {output_wav_path}")
