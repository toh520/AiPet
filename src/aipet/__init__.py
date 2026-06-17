import os
import sys

# Windows 平台且 Python 3.8+ 下，为防止 PyTorch CPU 在 Python 3.14 导入时发生 DLL 初始化失败 OSError 1114 错误
# 遍历 sys.path 动态定位并添加 torch/lib 路径至 DLL 搜索目录中
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    for p in sys.path:
        if p:
            torch_lib = os.path.join(p, "torch", "lib")
            if os.path.isdir(torch_lib):
                try:
                    os.add_dll_directory(torch_lib)
                except Exception:
                    pass

from aipet.ui.pet_window import DesktopPet

__all__ = [
    "DesktopPet",
]

__version__ = "1.0.0"
