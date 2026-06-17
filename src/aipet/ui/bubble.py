from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF
from PyQt5.QtGui import QFont, QPainter, QColor, QPainterPath

class ChatBubble(QWidget):
    def __init__(self):
        super().__init__(None)
        self.text = ""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFont(QFont("Microsoft YaHei", 11))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

    def show_message(self, text, pos, dur=3000):
        self.text = text
        self.adjust_size()
        self.reposition(pos)
        self.show()
        self.timer.start(dur)

    def update_text(self, text, pos):
        """流式增量更新文本接口，更新文本内容并调整气泡尺寸，同时挂起定时器，防止流式期间意外关闭"""
        self.text = text
        self.adjust_size()
        self.reposition(pos)
        self.show()
        self.timer.stop()

    def reposition(self, pos):
        self.move(pos.x() - self.width() // 2, pos.y() - self.height())

    def adjust_size(self):
        fm = self.fontMetrics()
        # 增加最大宽度至 240px，让段落在大字号下更舒展
        rect = fm.boundingRect(QRect(0, 0, 240, 0), Qt.TextWordWrap, self.text)
        self.resize(rect.width() + 40, rect.height() + 50)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # 使用经典的二次元游戏暗青蓝半透明背景
        p.setBrush(QColor(25, 32, 48, 235))
        # 使用淡雅的琥珀金色边框
        p.setPen(QColor(211, 188, 142, 210))
        
        r = self.rect().adjusted(2, 2, -2, -15)
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 10, 10) # 6px - 10px 更加硬朗、有质感
        
        # 气泡尖角
        path.moveTo(r.center().x() - 10, r.bottom())
        path.lineTo(r.center().x(), r.bottom() + 15)
        path.lineTo(r.center().x() + 10, r.bottom())
        
        p.drawPath(path)
        # 使用原神特有的米黄象牙色文字
        p.setPen(QColor(236, 229, 216))
        p.drawText(r.adjusted(12, 8, -12, -8), Qt.TextWordWrap | Qt.AlignCenter, self.text)
