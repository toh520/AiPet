import os
import sys

# 1. 编写动态元类（Metaclass）以确保任意层级属性访问返回的均是真正的 Python 类对象（type 类型）
# 这能完全解决 PyTorch/Pickle 在执行 NEWOBJ 指令时因获取不到 type 报错的问题
class MetaMock(type):
    def __getattr__(cls, name):
        # 拦截并防范私有魔术属性递归
        if name.startswith("_"):
            raise AttributeError(name)
        # 动态实例化并返回一个继承自 FairseqMock 且元类为 MetaMock 的真实 Python 类定义
        new_class = MetaMock(name, (FairseqMock,), {})
        return new_class

class FairseqMock(metaclass=MetaMock):
    """自适应 Mock 骨架类"""
    def __init__(self, *args, **kwargs):
        pass
        
    def __call__(self, *args, **kwargs):
        # 允许被实例化或像函数般调用，返回实例本身
        return self
        
    def __getitem__(self, key):
        # 允许索引操作
        return self
        
    def __setstate__(self, state):
        # 屏蔽反序列化状态注入
        pass
        
    def __getstate__(self):
        return {}

# 注册核心的 fairseq 各级子命名空间为 FairseqMock 类定义本身（而非实例）
sys.modules["fairseq"] = FairseqMock
sys.modules["fairseq.data"] = FairseqMock
sys.modules["fairseq.data.dictionary"] = FairseqMock
sys.modules["fairseq.models"] = FairseqMock
sys.modules["fairseq.tasks"] = FairseqMock
sys.modules["fairseq.modules"] = FairseqMock

import torch

def extract():
    # 动态获取项目根目录路径
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    model_path = os.path.join(base_path, "resources", "models", "hubert_base_state.pt")
    
    print(f"[*] 正在加载并反序列化 ContentVec 模型: {model_path}")
    try:
        # 显式使用 weights_only=False 以运行元类 Mock 反序列化
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    except Exception as e:
        print(f"[!] 加载模型失败: {e}")
        return
        
    # 提取核心的神经网络参数 state_dict
    if isinstance(checkpoint, dict) and "model" in checkpoint:
        print("[*] 成功识别到 'model' 参数键，正在剥离非必要字段...")
        state_dict = checkpoint["model"]
    else:
        print("[*] 未发现 'model' 键，可能已是纯 parameters 格式，将使用完整字典...")
        state_dict = checkpoint
        
    # 过滤掉一些多余的/我们网络不需要的 fairseq 冗余特征
    for k in ["mask_emb", "label_embs_concat"]:
        if k in state_dict:
            del state_dict[k]
            print(f"[*] 已过滤冗余字段: {k}")
            
    # 覆盖原文件重新保存为 100% 纯净的 PyTorch State Dict（不含任何自定义类依赖）
    print(f"[*] 正在重新保存为纯净参数文件至: {model_path}")
    torch.save(state_dict, model_path)
    print("[+] 恭喜！ContentVec 权重“脱水”提取完成，已完全剥离所有 fairseq 依赖！")

if __name__ == "__main__":
    extract()
