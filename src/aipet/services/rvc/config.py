import multiprocessing
import torch

class Config:
    def __init__(self):
        # 强制配置为 CPU 推理，确保可移植性和跨平台稳定
        self.device = "cpu"
        self.is_half = False  # CPU 必须运行在 FP32 模式下，防精度报错
        self.use_jit = False
        self.n_cpu = multiprocessing.cpu_count()
        self.gpu_name = None
        self.gpu_mem = None
        
        # 针对 FP32 / CPU 的默认推理分片参数
        self.x_pad = 1
        self.x_query = 6
        self.x_center = 38
        self.x_max = 41
