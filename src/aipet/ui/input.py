from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aipet.ui.pet_window import DesktopPet

class ChatInput(QLineEdit):
    def __init__(self, parent_pet: 'DesktopPet'):
        super().__init__(None)
        self.pet = parent_pet
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(450, 52)  # 稍微加宽，使得打字时看得更清楚；略微减小高度，显得更精致
        self.setFont(QFont("Microsoft YaHei", 12))
        self.setStyleSheet("""
            QLineEdit {
                background-color: rgba(25, 32, 48, 235);
                border: 2px solid #d3bc8e;
                border-radius: 6px;  /* 换用更加硬朗、工业感强的二次元 UI 边缘 */
                padding: 0 18px;
                color: #ece5d8;
                selection-background-color: #d3bc8e;
                selection-color: #12151e;
                placeholder-text-color: #8b94a8;
            }
        """)
        self.setPlaceholderText("和她说点什么... (Enter发送)")
        self.returnPressed.connect(self.submit)

    def show_input(self):
        # 智能定位：在桌宠正下方
        geo = self.pet.frameGeometry()
        x = geo.center().x() - self.width() // 2
        y = geo.bottom() + 10
        self.move(x, y)
        self.show()
        self.setFocus()

    def submit(self):
        t = self.text().strip()
        if t:
            self.pet.process_chat(t)
        self.hide()
        self.clear()

    def focusOutEvent(self, e):
        self.hide()
        super().focusOutEvent(e)
