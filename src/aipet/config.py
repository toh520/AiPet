import os
import sys

# --- 解决中文路径和控制台编码的关键补丁 ---
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform.startswith('win'):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

# 尝试导入 WebEngine，如果失败则降级运行
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False
    print("Warning: PyQtWebEngine not found. Live2D features will be disabled.")

# 路径配置
if getattr(sys, 'frozen', False):
    # 打包后的运行环境 (exe同级目录)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境: __file__ 为 src/aipet/config.py，需要向上三级
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")
CHAR_DIR = os.path.join(BASE_DIR, "resources", "characters")
WEB_TEMPLATE_PATH = os.path.join(BASE_DIR, "src", "web", "viewer.html")

# 专用的临时音频输出/缓存文件夹配置
TEMP_AUDIO_DIR = os.path.join(BASE_DIR, "temp_audio")
if not os.path.exists(TEMP_AUDIO_DIR):
    try:
        os.makedirs(TEMP_AUDIO_DIR)
    except Exception:
        pass

TEMP_AUDIO_PATH = os.path.join(TEMP_AUDIO_DIR, "temp_speech.wav")
