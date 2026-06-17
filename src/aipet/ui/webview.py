from PyQt5.QtCore import Qt, QTimer, QEvent
from aipet.config import WEB_ENGINE_AVAILABLE

if WEB_ENGINE_AVAILABLE:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    from typing import TYPE_CHECKING
    
    if TYPE_CHECKING:
        from aipet.ui.pet_window import DesktopPet

    class DraggableWebView(QWebEngineView):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.parent_window = parent
            self.page().setBackgroundColor(Qt.transparent)
            self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            self.setContextMenuPolicy(Qt.NoContextMenu)
            self.drag_pos = None
            self.filter_installed = False
            
            # 初始尝试
            QTimer.singleShot(100, self.install_filter)

        def install_filter(self):
            if self.filter_installed:
                return

            # 遍历子控件，找到那个处理输入的 RenderWidgetHostView
            target = self.focusProxy()
            if not target and self.children():
                for child in self.children():
                    if child.metaObject().className() == "QtWebEngineCore::RenderWidgetHostViewQtDelegateWidget":
                        target = child
                        break
            
            if not target and self.children():
                target = self.children()[0]

            if target:
                target.removeEventFilter(self)  # 防止重复
                target.installEventFilter(self)
                self.filter_installed = True
                print("Event filter installed on WebEngine child.")
            else:
                # 如果还没加载好，稍微延时重试
                QTimer.singleShot(500, self.install_filter)

        def ensure_filter_installed(self):
            # 外部强制重新检查
            self.filter_installed = False
            self.install_filter()

        def eventFilter(self, source, event):
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    if self.parent_window:
                        self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
                        # 检查聊天框是否开启，避免冲突
                        if hasattr(self.parent_window, 'chat_input') and not self.parent_window.chat_input.isVisible():
                            if hasattr(self.parent_window, 'is_thinking_state') and self.parent_window.is_thinking_state:
                                if hasattr(self.parent_window, 'talk_thinking'):
                                    self.parent_window.talk_thinking()
                            elif hasattr(self.parent_window, 'talk_random'):
                                self.parent_window.talk_random()
                    return True
                elif event.button() == Qt.RightButton:
                    if self.parent_window:
                        self.parent_window.show_menu(event.globalPos())
                    return True  # 拦截右键，防止弹出浏览器上下文菜单

            elif event.type() == QEvent.MouseMove:
                if event.buttons() == Qt.LeftButton and self.drag_pos:
                    if self.parent_window:
                        self.parent_window.move(event.globalPos() - self.drag_pos)
                    return True  # 拖拽时拦截
                # 非拖拽时的移动，返回 False (不拦截)，让 Live2D 收到视线跟随信号
                return False

            elif event.type() == QEvent.MouseButtonRelease:
                self.drag_pos = None
                return False

            return super().eventFilter(source, event)
else:
    class DraggableWebView:
        pass
