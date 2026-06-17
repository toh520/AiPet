# 必须在最前面导入 torch，以防在 Windows 系统下与 PyQt5 的初始化发生冲突
# 导致 [WinError 1114] 动态链接库(DLL)初始化例程失败 (c10.dll)
import torch
import sys
from PyQt5.QtWidgets import QApplication
from aipet.ui.pet_window import DesktopPet

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 保证关闭所有窗口时程序依然运行（驻留托盘/后台模式，通常桌宠右键退出才是真正退出）
    app.setQuitOnLastWindowClosed(False)
    
    pet = DesktopPet()
    sys.exit(app.exec_())
