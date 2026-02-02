import sys
import os
import math
import json
import random
import glob
import winsound
import requests
import threading
import shutil
import time
import wave
import contextlib

# 尝试导入 WebEngine，如果失败则降级运行
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False
    print("Warning: PyQtWebEngine not found. Live2D features will be disabled.")

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QAction, 
                             QLineEdit, QMessageBox, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QPushButton, QGroupBox, QFileDialog, 
                             QTextEdit, QTabWidget, QComboBox, QRadioButton, QButtonGroup, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QRectF, pyqtSignal, QObject, QUrl, QSize
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QBrush, QColor, QFont, QPen, QPainterPath

# 路径配置
if getattr(sys, 'frozen', False):
    # 打包后的运行环境 (exe同级目录)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境 (src的上一级)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(BASE_DIR, "config", "settings.json")
CHAR_DIR = os.path.join(BASE_DIR, "resources", "characters")
TEMP_AUDIO_PATH = os.path.join(BASE_DIR, "temp_speech.wav")
WEB_TEMPLATE_PATH = os.path.join(BASE_DIR, "src", "web", "viewer.html")

def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
    return None

def save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {path}: {e}")

class WorkerSignals(QObject):
    chat_finished = pyqtSignal(str)
    tts_finished = pyqtSignal(str)

# --- 自定义 WebView 以支持拖拽 ---
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QRectF, pyqtSignal, QObject, QUrl, QSize, QEvent

# ... (Previous imports remain, ensure QEvent is imported)

if WEB_ENGINE_AVAILABLE:
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
            if self.filter_installed: return

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
                target.removeEventFilter(self) # 防止重复
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
                    self.drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
                    
                    # 触发点击互动 (Random Talk)
                    if self.parent_window:
                        # 检查聊天框是否开启，避免冲突
                        if hasattr(self.parent_window, 'chat_input') and not self.parent_window.chat_input.isVisible():
                            if hasattr(self.parent_window, 'talk_random'):
                                self.parent_window.talk_random()
                                
                    return True 
                elif event.button() == Qt.RightButton:
                    if self.parent_window:
                        self.parent_window.show_menu(event.globalPos())
                    return True # 拦截右键，防止出浏览器菜单

            elif event.type() == QEvent.MouseMove:
                if event.buttons() == Qt.LeftButton and self.drag_pos:
                    if self.parent_window:
                        self.parent_window.move(event.globalPos() - self.drag_pos)
                    return True # 拖拽时拦截
                # 非拖拽时的移动，返回 False (不拦截)，让 Live2D 收到视线跟随信号
                return False

            elif event.type() == QEvent.MouseButtonRelease:
                self.drag_pos = None
                return False

            return super().eventFilter(source, event)

        # 移除之前的 mousePressEvent 等重写，全靠 eventFilter
    
class SettingsWindow(QWidget):
    """可视化设置窗口 - V1.0 Live2D 增强版"""
    def __init__(self, parent_pet):
        super().__init__()
        self.pet = parent_pet
        self.setWindowTitle("AiPet 控制台 (Admin)")
        self.resize(650, 800)
        self.apply_stylesheet()
        self.init_ui()

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #ffffff; font-family: "Microsoft YaHei"; font-size: 14px; }
            QGroupBox { border: 1px solid #555; border-radius: 8px; margin-top: 12px; font-weight: bold; padding-top: 20px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: #bbb; }
            QLineEdit, QTextEdit, QComboBox { background-color: #3e3e3e; border: 1px solid #555; padding: 6px; border-radius: 4px; color: #fff; selection-background-color: #007acc; }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #007acc; }
            QPushButton { background-color: #007acc; border: none; padding: 8px 15px; border-radius: 6px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #0098ff; }
            QPushButton:pressed { background-color: #005c99; }
            QTabWidget::pane { border: 1px solid #555; top: -1px; }
            QTabBar::tab { background: #3e3e3e; color: #aaa; padding: 10px 15px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #555; color: #fff; border-bottom: 2px solid #007acc; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QScrollBar:vertical { background: #2b2b2b; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #555; min-height: 20px; border-radius: 6px; }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        self.tabs = QTabWidget()
        
        self.tab_run = QWidget()
        self.init_run_tab()
        self.tabs.addTab(self.tab_run, "🎮 运行配置")

        self.tab_creator = QWidget()
        self.init_creator_tab()
        self.tabs.addTab(self.tab_creator, "🎨 资产工坊")

        self.tab_system = QWidget()
        self.init_system_tab()
        self.tabs.addTab(self.tab_system, "⚙️ 系统设置")

        main_layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭窗口")
        close_btn.setStyleSheet("background-color: #555;")
        close_btn.clicked.connect(self.hide)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def init_run_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        group = QGroupBox("🎭 形象与声音搭配")
        form = QFormLayout()
        form.setVerticalSpacing(15)

        self.avatar_selector = QComboBox()
        self.avatar_selector.setToolTip("决定桌宠长什么样 (Live2D/图片)")
        form.addRow("👀 显示形象:", self.avatar_selector)

        self.voice_selector = QComboBox()
        self.voice_selector.setToolTip("决定桌宠用谁的声音说话")
        form.addRow("🎤 说话声音:", self.voice_selector)

        group.setLayout(form)
        layout.addWidget(group)

        apply_btn = QPushButton("✅ 应用搭配")
        apply_btn.setStyleSheet("background-color: #673AB7; color: white; padding: 12px; font-weight: bold; font-size: 15px;")
        apply_btn.clicked.connect(self.apply_mix_match)
        layout.addWidget(apply_btn)
        layout.addStretch()
        self.tab_run.setLayout(layout)

    def init_system_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # --- LLM 设置 ---
        llm_group = QGroupBox("🧠 大脑 (LLM) 设置")
        llm_form = QFormLayout()
        llm_form.setVerticalSpacing(10)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        
        self.model_input = QLineEdit()
        
        llm_form.addRow("API Key:", self.api_key_input)
        llm_form.addRow("Base URL:", self.base_url_input)
        llm_form.addRow("模型名称:", self.model_input)
        llm_group.setLayout(llm_form)
        layout.addWidget(llm_group)

        # --- 语音设置 ---
        tts_group = QGroupBox("🔌 语音 (TTS) 设置")
        tts_layout = QVBoxLayout()
        
        # 启用开关
        self.tts_enable_check = QCheckBox("启用 TTS 语音合成")
        self.tts_enable_check.setToolTip("关闭后只显示气泡，不播放声音")
        tts_layout.addWidget(self.tts_enable_check)
        
        tts_form = QFormLayout()
        self.tts_url_input = QLineEdit()
        self.tts_url_input.setPlaceholderText("http://127.0.0.1:9880")
        tts_form.addRow("API 地址:", self.tts_url_input)
        tts_layout.addLayout(tts_form)
        
        tts_group.setLayout(tts_layout)
        layout.addWidget(tts_group)

        # --- 互动设置 ---
        interact_group = QGroupBox("💬 互动设置")
        interact_layout = QVBoxLayout()
        interact_layout.addWidget(QLabel("点击互动的随机语录 (每行一句):"))
        self.random_talk_input = QTextEdit()
        self.random_talk_input.setMaximumHeight(80)
        self.random_talk_input.setPlaceholderText("Hi~\n你好呀！\n今天天气真好")
        interact_layout.addWidget(self.random_talk_input)
        interact_group.setLayout(interact_layout)
        layout.addWidget(interact_group)

        # --- 显示设置 ---
        app_group = QGroupBox("🖥️ 显示设置")
        app_form = QFormLayout()
        self.scale_input = QLineEdit()
        self.refresh_rate_input = QLineEdit()
        app_form.addRow("缩放 (0.5-2.0):", self.scale_input)
        app_form.addRow("刷新 (ms):", self.refresh_rate_input)
        app_group.setLayout(app_form)
        layout.addWidget(app_group)

        save_btn = QPushButton("💾 保存系统设置")
        save_btn.setStyleSheet("background-color: #28a745; padding: 10px;")
        save_btn.clicked.connect(self.save_system_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        self.tab_system.setLayout(layout)

    def init_creator_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("编辑目标:"))
        self.editor_char_selector = QComboBox()
        self.editor_char_selector.currentIndexChanged.connect(self.load_char_to_editor)
        top_layout.addWidget(self.editor_char_selector)
        
        new_btn = QPushButton("➕ 新建")
        new_btn.clicked.connect(self.prepare_new_char)
        top_layout.addWidget(new_btn)
        
        del_btn = QPushButton("🗑️ 删除")
        del_btn.setStyleSheet("background-color: #d32f2f; color: white;")
        del_btn.clicked.connect(self.delete_character)
        top_layout.addWidget(del_btn)
        
        layout.addLayout(top_layout)

        editor_group = QGroupBox("📝 资产编辑")
        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.char_name_input = QLineEdit()
        form.addRow("ID (文件夹名):", self.char_name_input)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMaximumHeight(60)
        form.addRow("人设 Prompt:", self.system_prompt_input)

        # --- 渲染模式选择 ---
        mode_layout = QHBoxLayout()
        self.rb_image = QRadioButton("图片模式")
        self.rb_live2d = QRadioButton("Live2D 模式")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_image, 0)
        self.mode_group.addButton(self.rb_live2d, 1)
        self.rb_image.setChecked(True)
        self.mode_group.buttonClicked.connect(self.toggle_asset_input)
        mode_layout.addWidget(self.rb_image)
        mode_layout.addWidget(self.rb_live2d)
        if not WEB_ENGINE_AVAILABLE:
            self.rb_live2d.setEnabled(False)
            self.rb_live2d.setText("Live2D (未安装库)")
        form.addRow("渲染模式:", mode_layout)

        # 图片源
        self.img_path_display = QLineEdit()
        self.img_btn = QPushButton("📂")
        self.img_btn.setFixedSize(30, 30)
        self.img_btn.clicked.connect(self.browse_images)
        self.img_row_layout = QHBoxLayout()
        self.img_row_layout.addWidget(self.img_path_display)
        self.img_row_layout.addWidget(self.img_btn)
        self.lbl_img = QLabel("图片源:")
        form.addRow(self.lbl_img, self.img_row_layout)

        # Live2D 源
        self.l2d_path_display = QLineEdit()
        self.l2d_btn = QPushButton("📂")
        self.l2d_btn.setFixedSize(30, 30)
        self.l2d_btn.clicked.connect(self.browse_live2d)
        self.l2d_row_layout = QHBoxLayout()
        self.l2d_row_layout.addWidget(self.l2d_path_display)
        self.l2d_row_layout.addWidget(self.l2d_btn)
        self.lbl_l2d = QLabel("模型文件:")
        form.addRow(self.lbl_l2d, self.l2d_row_layout)
        
        # Live2D 参数
        self.l2d_scale_input = QLineEdit("1.0")
        self.l2d_offset_input = QLineEdit("0.0")
        l2d_params = QHBoxLayout()
        l2d_params.addWidget(QLabel("缩放:"))
        l2d_params.addWidget(self.l2d_scale_input)
        l2d_params.addWidget(QLabel("垂直偏移:"))
        l2d_params.addWidget(self.l2d_offset_input)
        self.l2d_param_row = l2d_params
        # 默认隐藏 Live2D 相关
        self.toggle_asset_input()
        form.addRow(self.l2d_param_row)

        # 语音
        self.audio_path_display = QLineEdit()
        audio_btn = QPushButton("🎵")
        audio_btn.setFixedSize(30, 30)
        audio_btn.clicked.connect(self.browse_audio)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self.audio_path_display)
        audio_row.addWidget(audio_btn)
        form.addRow("参考音频:", audio_row)

        self.ref_text_input = QTextEdit()
        self.ref_text_input.setMaximumHeight(50)
        form.addRow("音频文本:", self.ref_text_input)

        editor_group.setLayout(form)
        layout.addWidget(editor_group)

        save_char_btn = QPushButton("💾 保存资产配置")
        save_char_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        save_char_btn.clicked.connect(self.save_character_asset)
        layout.addWidget(save_char_btn)

        self.tab_creator.setLayout(layout)

    def toggle_asset_input(self):
        is_live2d = self.rb_live2d.isChecked()
        # 显隐控制
        self.lbl_img.setVisible(not is_live2d)
        self.img_path_display.setVisible(not is_live2d)
        self.img_btn.setVisible(not is_live2d)
        
        self.lbl_l2d.setVisible(is_live2d)
        self.l2d_path_display.setVisible(is_live2d)
        self.l2d_btn.setVisible(is_live2d)
        
        # 参数行控制 (QLayoutItem 比较麻烦，这里简单显隐内容)
        for i in range(self.l2d_param_row.count()):
            widget = self.l2d_param_row.itemAt(i).widget()
            if widget: widget.setVisible(is_live2d)

    def showEvent(self, event):
        self.refresh_all_lists()
        self.load_system_values()
        self.load_run_values()
        if self.editor_char_selector.count() > 0:
            self.load_char_to_editor()

    def refresh_all_lists(self):
        if os.path.exists(CHAR_DIR):
            chars = sorted([d for d in os.listdir(CHAR_DIR) if os.path.isdir(os.path.join(CHAR_DIR, d))])
            
            curr_avatar = self.avatar_selector.currentText()
            curr_voice = self.voice_selector.currentText()
            curr_editor = self.editor_char_selector.currentText()
            
            self.avatar_selector.clear()
            self.avatar_selector.addItems(chars)
            self.voice_selector.clear()
            self.voice_selector.addItems(chars)
            self.editor_char_selector.clear()
            self.editor_char_selector.addItems(chars)
            
            if curr_avatar in chars: self.avatar_selector.setCurrentText(curr_avatar)
            if curr_voice in chars: self.voice_selector.setCurrentText(curr_voice)
            if curr_editor in chars: self.editor_char_selector.setCurrentText(curr_editor)

    def load_run_values(self):
        cfg = self.pet.config
        self.avatar_selector.setCurrentText(cfg.get('active_avatar', 'HuTao'))
        self.voice_selector.setCurrentText(cfg.get('active_voice', 'HuTao'))

    def apply_mix_match(self):
        self.pet.update_mix_match(self.avatar_selector.currentText(), self.voice_selector.currentText())

    def load_system_values(self):
        cfg = self.pet.config
        self.api_key_input.setText(cfg['llm'].get('api_key', ""))
        self.base_url_input.setText(cfg['llm'].get('base_url', ""))
        self.model_input.setText(cfg['llm'].get('model', ""))
        self.tts_url_input.setText(cfg['app'].get('tts_api_url', ""))
        self.tts_enable_check.setChecked(cfg['app'].get('enable_tts', True))
        
        # 随机语录
        talks = cfg.get('interaction', {}).get('random_talk', ["Hi~"])
        self.random_talk_input.setText("\n".join(talks))
        
        self.scale_input.setText(str(cfg['app'].get('scale', 1.0)))
        self.refresh_rate_input.setText(str(cfg['app'].get('refresh_rate', 100)))

    def save_system_settings(self):
        try:
            self.pet.config['llm']['api_key'] = self.api_key_input.text()
            self.pet.config['llm']['base_url'] = self.base_url_input.text()
            self.pet.config['llm']['model'] = self.model_input.text()
            self.pet.config['app']['tts_api_url'] = self.tts_url_input.text()
            self.pet.config['app']['enable_tts'] = self.tts_enable_check.isChecked()
            self.pet.config['app']['scale'] = float(self.scale_input.text())
            self.pet.config['app']['refresh_rate'] = int(self.refresh_rate_input.text())
            
            # 保存随机语录
            lines = [l.strip() for l in self.random_talk_input.toPlainText().split('\n') if l.strip()]
            if 'interaction' not in self.pet.config:
                self.pet.config['interaction'] = {}
            self.pet.config['interaction']['random_talk'] = lines
            
            save_json(CONFIG_PATH, self.pet.config)
            self.pet.apply_config_system()
            QMessageBox.information(self, "成功", "系统设置已保存！")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def prepare_new_char(self):
        self.char_name_input.setText("")
        self.char_name_input.setReadOnly(False)
        self.system_prompt_input.setText("")
        self.img_path_display.setText("")
        self.l2d_path_display.setText("")
        self.audio_path_display.setText("")
        self.ref_text_input.setText("")

    def load_char_to_editor(self):
        char_name = self.editor_char_selector.currentText()
        if not char_name: return
        self.char_name_input.setText(char_name)
        self.char_name_input.setReadOnly(True)
        
        path = os.path.join(CHAR_DIR, char_name, "profile.json")
        data = load_json(path)
        if data:
            self.system_prompt_input.setText(data.get("system_prompt", ""))
            
            # 渲染模式
            renderer = data.get("renderer", "image")
            if renderer == "live2d" and WEB_ENGINE_AVAILABLE:
                self.rb_live2d.setChecked(True)
                self.l2d_path_display.setText(data.get("live2d_model", ""))
                self.l2d_scale_input.setText(str(data.get("live2d_scale", 1.0)))
                self.l2d_offset_input.setText(str(data.get("live2d_offset_y", 0.0)))
            else:
                self.rb_image.setChecked(True)
                # 检查是否真的有图片
                img_dir = os.path.join(CHAR_DIR, char_name, "idle")
                if not os.path.exists(img_dir): # 兼容旧版，旧版可能是 images? 
                    img_dir = os.path.join(CHAR_DIR, char_name, "images")
                
                has_images = False
                if os.path.exists(img_dir):
                    if glob.glob(os.path.join(img_dir, "*.png")):
                        has_images = True
                
                if has_images:
                    self.img_path_display.setText("(已有图片)")
                else:
                    self.img_path_display.setText("") # 空，提示用户需要上传
                    
            self.toggle_asset_input()
            
            # TTS
            tts = data.get("tts", {})
            self.audio_path_display.setText(tts.get("ref_audio", ""))
            self.ref_text_input.setText(tts.get("prompt_text", ""))

    def browse_images(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if d: self.img_path_display.setText(d)
    
    def browse_live2d(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 .model3.json", "c:\\", "Live2D Model (*.model3.json)")
        if f: self.l2d_path_display.setText(f)

    def browse_audio(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择音频", "c:\\", "Audio (*.wav)")
        if f: self.audio_path_display.setText(f)

    def delete_character(self):
        char_name = self.editor_char_selector.currentText()
        if not char_name: return
        if self.editor_char_selector.count() <= 1:
            QMessageBox.warning(self, "禁止", "这是最后一个角色！")
            return
        if char_name == self.pet.active_avatar or char_name == self.pet.active_voice:
             QMessageBox.warning(self, "占用中", f"角色 [{char_name}] 正在使用中，请先切换。")
             return
        if QMessageBox.question(self, "确认", f"删除 {char_name}？") == QMessageBox.Yes:
            try:
                shutil.rmtree(os.path.join(CHAR_DIR, char_name))
                self.refresh_all_lists()
            except Exception as e: QMessageBox.critical(self, "错误", str(e))

    def save_character_asset(self):
        name = self.char_name_input.text().strip()
        if not name: return
        target_dir = os.path.join(CHAR_DIR, name)
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        
        # 读取旧配置
        old_prof = load_json(os.path.join(target_dir, "profile.json")) or {}
        
        # 1. 渲染配置
        is_live2d = self.rb_live2d.isChecked()
        renderer = "live2d" if is_live2d else "image"
        live2d_model_rel = old_prof.get("live2d_model", "")
        
        if is_live2d:
            # 处理 Live2D 文件复制
            src_l2d = self.l2d_path_display.text()
            # 如果选择了新文件
            if src_l2d and os.path.exists(src_l2d) and not src_l2d.startswith("voice/"):
                # 这里我们假设用户选择的是外部文件
                # 复制整个 Live2D 文件夹比较稳妥，因为有很多关联文件
                # 简单起见，我们建议用户把文件夹准备好，或者我们只复制 .model3.json 和相关?
                # Live2D 结构复杂，只复制 json 是不行的。
                # 策略：如果用户选的是外部文件，提示用户“请手动将模型文件夹放入 characters/{name}/live2d” 
                # 或者：我们尝试复制整个父文件夹
                
                # 简化方案：只保存相对路径，假设用户已经把东西放好了，或者我们做一个简易复制
                # 为了支持用户的 `genshin胡桃live2dex`，我们把该文件夹整个复制进去
                if not os.path.abspath(src_l2d).startswith(os.path.abspath(target_dir)):
                     src_dir = os.path.dirname(src_l2d) # 模型所在文件夹
                     dest_l2d_dir = os.path.join(target_dir, "live2d_model")
                     if os.path.exists(dest_l2d_dir): shutil.rmtree(dest_l2d_dir)
                     shutil.copytree(src_dir, dest_l2d_dir)
                     live2d_model_rel = f"live2d_model/{os.path.basename(src_l2d)}"
                else:
                    live2d_model_rel = os.path.relpath(src_l2d, target_dir).replace("\\", "/")
        else:
            # 图片模式
            src_img = self.img_path_display.text()
            dest_img = os.path.join(target_dir, "idle")
            if src_img and os.path.isdir(src_img):
                if not os.path.exists(dest_img): os.makedirs(dest_img)
                for p in glob.glob(os.path.join(src_img, "*.png")):
                    shutil.copy(p, dest_img)

        # 2. TTS 音频处理
        src_audio = self.audio_path_display.text()
        ref_audio_rel = old_prof.get("tts", {}).get("ref_audio", "")
        if src_audio and os.path.exists(src_audio):
             if not os.path.abspath(src_audio).startswith(os.path.abspath(target_dir)):
                 voice_dir = os.path.join(target_dir, "voice")
                 if not os.path.exists(voice_dir): os.makedirs(voice_dir)
                 fname = f"ref_{int(time.time())}.wav"
                 shutil.copy(src_audio, os.path.join(voice_dir, fname))
                 ref_audio_rel = f"voice/{fname}"
             else:
                 ref_audio_rel = os.path.relpath(src_audio, target_dir).replace("\\", "/")

        # 3. 生成 Profile
        prof = {
            "name": name,
            "system_prompt": self.system_prompt_input.toPlainText(),
            "renderer": renderer,
            "live2d_model": live2d_model_rel,
            "live2d_scale": float(self.l2d_scale_input.text() or 1.0),
            "live2d_offset_y": float(self.l2d_offset_input.text() or 0.0),
            "tts": {
                "ref_audio": ref_audio_rel,
                "prompt_text": self.ref_text_input.toPlainText(),
                "text_lang": "zh",
                "prompt_lang": "zh"
            }
        }
        save_json(os.path.join(target_dir, "profile.json"), prof)
        QMessageBox.information(self, "成功", "配置已保存")
        self.refresh_all_lists()

class ChatInput(QLineEdit):
    def __init__(self, parent_pet):
        super().__init__(None)
        self.pet = parent_pet
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 增大尺寸
        self.resize(400, 60)
        self.setFont(QFont("Microsoft YaHei", 12))
        self.setStyleSheet("background:rgba(255,255,255,230);border:2px solid #a52a2a;border-radius:15px;padding:0 15px;")
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
        t=self.text().strip()
        if t: self.pet.process_chat(t)
        self.hide()
        self.clear()
    def focusOutEvent(self, e): self.hide(); super().focusOutEvent(e)

class ChatBubble(QWidget):
    def __init__(self):
        super().__init__(None)
        self.text=""; self.setWindowFlags(Qt.FramelessWindowHint|Qt.Tool|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setFont(QFont("Microsoft YaHei", 10))
        self.timer=QTimer(self); self.timer.timeout.connect(self.hide)
    def show_message(self, text, pos, dur=3000):
        self.text=text; self.adjust_size(); self.reposition(pos); self.show(); self.timer.start(dur)
    def reposition(self, pos): self.move(pos.x()-self.width()//2, pos.y()-self.height())
    def adjust_size(self):
        fm=self.fontMetrics(); rect=fm.boundingRect(QRect(0,0,200,0), Qt.TextWordWrap, self.text)
        self.resize(rect.width()+40, rect.height()+50); self.update()
    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255,255,255,240)); p.setPen(QColor(100,100,100,150))
        r=self.rect().adjusted(2,2,-2,-15); path=QPainterPath()
        path.addRoundedRect(QRectF(r),10,10)
        path.moveTo(r.center().x()-10, r.bottom()); path.lineTo(r.center().x(), r.bottom()+15); path.lineTo(r.center().x()+10, r.bottom())
        p.drawPath(path); p.setPen(Qt.black)
        p.drawText(r.adjusted(10,5,-10,-5), Qt.TextWordWrap|Qt.AlignCenter, self.text)

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_json(CONFIG_PATH)
        self.visual_profile = {}
        self.voice_profile = {}
        self.active_avatar = self.config.get('active_avatar', 'HuTao')
        self.active_voice = self.config.get('active_voice', 'HuTao')
        
        # 动画状态初始化
        self.current_frame = 0
        self.frames = []
        self.angle = 0

        # 拖拽相关
        self.is_dragging = False; self.drag_pos = QPoint()
        
        self.signals = WorkerSignals()
        self.signals.chat_finished.connect(self.on_chat)
        self.signals.tts_finished.connect(self.on_tts)

        self.initUI() # 先初始化UI容器
        
        # 必须先创建 WebView (如果支持)
        if WEB_ENGINE_AVAILABLE:
            self.webview = DraggableWebView(self)
            self.webview.resize(300, 400) # 默认大小
            self.webview.hide()

        self.update_mix_match(self.active_avatar, self.active_voice) # 加载资源
        
        self.timer = QTimer(self); self.timer.timeout.connect(self.on_timer)
        self.apply_config_system()
        
        self.load_audio_pool()
        self.settings_window = SettingsWindow(self)
        
        # --- 聊天记忆 ---
        self.chat_history = [] 
        self.max_history_len = 5
        self.current_response_text = ""

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.image_label = QLabel(self)
        self.bubble = ChatBubble()
        self.chat_input = ChatInput(self)
        
        # 屏幕居中逻辑
        screen_geo = QApplication.primaryScreen().geometry()
        # 默认先给个大小，加载资源后会调整
        self.resize(300, 400)
        # 移动到中心
        self.move((screen_geo.width() - 300) // 2, (screen_geo.height() - 400) // 2)
        
        self.show()

    def update_mix_match(self, av, vo):
        self.active_avatar = av; self.active_voice = vo
        self.config['active_avatar']=av; self.config['active_voice']=vo
        save_json(CONFIG_PATH, self.config)
        
        self.chat_history = [] # 核心：切换搭配时清空对话记忆
        
        # 加载视觉
        char_path = os.path.join(CHAR_DIR, av)
        prof = load_json(os.path.join(char_path, "profile.json")) or {}
        self.visual_profile = prof
        
        renderer = prof.get('renderer', 'image')
        
        if renderer == 'live2d' and WEB_ENGINE_AVAILABLE:
            self.image_label.hide()
            self.webview.show()
            self.load_live2d(char_path, prof)
        else:
            if hasattr(self, 'webview'): self.webview.hide()
            self.image_label.show()
            self.load_images(char_path)

        # 加载语音
        v_path = os.path.join(CHAR_DIR, vo)
        v_prof = load_json(os.path.join(v_path, "profile.json")) or {}
        self.voice_profile = v_prof.get('tts', {})
        self.voice_profile['_base_path'] = v_path

    def load_images(self, path):
        # 原有的图片加载逻辑
        self.frames = []
        d = os.path.join(path, "idle")
        scale = self.config['app'].get('scale', 1.0)
        for p in sorted(glob.glob(os.path.join(d, "*.png"))):
            pix = QPixmap(p)
            if not pix.isNull():
                pix = pix.scaled(int(pix.width()*scale), int(pix.height()*scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.frames.append(pix)
        if self.frames:
            self.image_label.setPixmap(self.frames[0])
            self.resize(self.frames[0].size())
            self.image_label.resize(self.frames[0].size())
        else:
            # 容错：如果找不到图片，显示占位符
            fallback = QPixmap(200, 100)
            fallback.fill(Qt.transparent)
            painter = QPainter(fallback)
            painter.setPen(Qt.red)
            painter.setFont(QFont("Arial", 16, QFont.Bold))
            painter.drawText(fallback.rect(), Qt.AlignCenter, "No Image")
            painter.end()
            self.image_label.setPixmap(fallback)
            self.resize(200, 100)
            self.image_label.resize(200, 100)
        
    def load_live2d(self, base_path, prof):
        # 1. 尝试动态补全 model3.json (内存级别)
        model_rel = prof.get('live2d_model', '')
        model_abs = os.path.join(base_path, model_rel)
        
        # 容错：如果配置的文件不存在，尝试找目录下随便一个 model3.json
        if not os.path.exists(model_abs):
            search_dir = os.path.dirname(model_abs)
            if not os.path.exists(search_dir): search_dir = base_path
            candidates = glob.glob(os.path.join(search_dir, "*.model3.json"))
            candidates = [c for c in candidates if "_temp_" not in c] # 排除临时文件
            if candidates:
                model_abs = candidates[0]
                # 更新相对路径，以便后续逻辑正确
                model_rel = os.path.relpath(model_abs, base_path).replace("\\", "/")
                print(f"Configured model not found, falling back to: {model_rel}")

        # 读取原始数据
        m3_data = load_json(model_abs)
        if m3_data:
            # 扫描 motions 文件夹
            m_dir = os.path.join(os.path.dirname(model_abs), "motions")
            if not os.path.exists(m_dir):
                # 兼容改名后的文件夹
                m_dir = os.path.join(os.path.dirname(model_abs), "motions_extra")

            if os.path.exists(m_dir):
                m_refs = m3_data.get("FileReferences", {})
                if "Motions" not in m_refs: m_refs["Motions"] = {}
                
                found_files = glob.glob(os.path.join(m_dir, "*.motion3.json"))
                for f in found_files:
                    m_name = os.path.basename(f).replace(".motion3.json", "")
                    if m_name not in m_refs["Motions"]:
                        # 强行登记！
                        rel_f = os.path.relpath(f, os.path.dirname(model_abs)).replace("\\", "/")
                        m_refs["Motions"][m_name] = [{"File": rel_f}]
                m3_data["FileReferences"] = m_refs
            
            temp_m3_path = os.path.join(os.path.dirname(model_abs), "_temp_model.json")
            save_json(temp_m3_path, m3_data)
            model_rel = os.path.relpath(temp_m3_path, base_path).replace("\\", "/")

        # 2. 读取模板
        with open(WEB_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            html = f.read()
        
        web_dir = os.path.dirname(WEB_TEMPLATE_PATH).replace("\\", "/")
        html = html.replace('src="js/', f'src="{web_dir}/js/')
        
        scale = prof.get('live2d_scale', 1.0) * self.config['app'].get('scale', 1.0)
        offset = prof.get('live2d_offset_y', 0.0)
        
        # 3. URL 编码处理 (解决中文路径问题)
        from urllib.parse import quote
        # model_rel 是相对于 base_path 的。因为我们 setHtml 设了 baseUrl，所以这里只需要相对路径并编码
        # 注意：quote 应该只编码文件名部分，不应该编码路径分隔符 '/'
        # 简单起见，我们对每一段进行编码
        encoded_rel = "/".join([quote(part) for part in model_rel.split("/")])

        html = html.replace('[[MODEL_PATH]]', encoded_rel)
        html = html.replace('[[MODEL_SCALE]]', str(scale))
        html = html.replace('[[MODEL_Y_OFFSET]]', str(offset))
        model_rel = prof.get('live2d_model', '')
        # HTML需要的是相对于 baseURL 的路径，或者绝对路径
        # 这里我们用绝对路径更稳
        model_abs = os.path.join(base_path, model_rel).replace("\\", "/")
        # 由于浏览器安全性，本地文件通常需要 file:/// 协议，但 QWebEngine 的 setHtml(baseUrl) 可以解决
        
        # 必须确保路径是 file:/// 格式或者相对路径
        # PixiLive2D 在加载本地文件时比较挑剔。
        # 最稳妥的方式：将 baseUrl 设为 base_path，然后 model_rel 作为相对路径
        
        scale = prof.get('live2d_scale', 1.0) * self.config['app'].get('scale', 1.0) # 叠加全局缩放
        offset = prof.get('live2d_offset_y', 0.0)
        
        html = html.replace('[[MODEL_PATH]]', model_rel)
        html = html.replace('[[MODEL_SCALE]]', str(scale))
        html = html.replace('[[MODEL_Y_OFFSET]]', str(offset))
        
        # 3. 加载
        # 修改策略：将 baseUrl 直接指向模型文件所在的目录 (live2d_model/)
        # 这样 json 内部的相对路径 (如 motions_extra/xxx) 就能直接匹配，无需考虑上层目录
        model_dir = os.path.dirname(model_abs)
        base_url = QUrl.fromLocalFile(model_dir + "/")
        
        # 此时 HTML 里只需要加载文件名即可
        model_filename = os.path.basename(model_rel) # 例如 _temp_model.json
        encoded_filename = quote(model_filename)
        
        # 重新替换 HTML 中的路径 (覆盖掉上面的逻辑，因为 base 变了)
        html = html.replace(encoded_rel, encoded_filename)
        
        self.webview.setHtml(html, baseUrl=base_url)
        
        # 调整窗口大小以适应 Live2D (给一个较大的透明区域)
        # Live2D 往往比较大，默认给 300x500 * scale
        base_w, base_h = 300, 500
        g_scale = self.config['app'].get('scale', 1.0)
        self.resize(int(base_w * g_scale), int(base_h * g_scale))
        self.webview.resize(self.size())
        
        # 确保事件过滤器已安装 (修复切换导致无法拖拽的问题)
        self.webview.ensure_filter_installed()

    def apply_config_system(self):
        self.timer.start(self.config['app'].get('refresh_rate', 100))
        # 刷新当前显示以应用缩放
        self.update_mix_match(self.active_avatar, self.active_voice)

    def on_timer(self):
        if self.image_label.isVisible() and self.frames:
            self.current_frame = (self.current_frame+1)%len(self.frames)
            self.image_label.setPixmap(self.frames[self.current_frame])
        
        if self.bubble.isVisible(): self.bubble.reposition(self.get_head_pos())

    def get_head_pos(self):
        return self.mapToGlobal(QPoint(self.width()//2, 0))

    # --- 拖拽逻辑 ---
    def handle_mouse_press(self, e): 
        if e.button()==Qt.LeftButton: 
            self.is_dragging=True; self.drag_pos=e.globalPos()-self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            if not self.chat_input.isVisible(): self.talk_random()
    def handle_mouse_move(self, e):
        if self.is_dragging: self.move(e.globalPos()-self.drag_pos)
    def handle_mouse_release(self, e): self.is_dragging=False; self.setCursor(Qt.ArrowCursor)

    def moveEvent(self, e):
        super().moveEvent(e)
        if hasattr(self, 'bubble') and self.bubble.isVisible():
            self.bubble.reposition(self.get_head_pos())

    # 兼容 QLabel 的拖拽 (当 WebView 隐藏时)
    def mousePressEvent(self, e): self.handle_mouse_press(e)
    def mouseMoveEvent(self, e): self.handle_mouse_move(e)
    def mouseReleaseEvent(self, e): self.handle_mouse_release(e)
    
    # --- 交互 ---
    def mousePressEvent(self, e):
        if e.button()==Qt.RightButton: self.show_menu(e.globalPos())
        else: self.handle_mouse_press(e)

    def show_menu(self, global_pos):
        m=QMenu(self)
        m.addAction("🗣 对话").triggered.connect(self.chat_input.show_input)
        
        # --- 动态加载动作子菜单 ---
        if self.visual_profile.get('renderer') == 'live2d':
            motion_menu = m.addMenu("🎬 动作表演")
            motions = self.get_available_motions()
            if motions:
                for group in motions:
                    # 创建闭包以正确捕获动作名称
                    action = motion_menu.addAction(group)
                    action.triggered.connect(lambda checked, g=group: self.play_l2d_motion(g))
            else:
                motion_menu.addAction("无可用动作").setEnabled(False)

        m.addAction("⚙️ 控制台").triggered.connect(self.settings_window.show)
        m.addAction("退出").triggered.connect(QApplication.instance().quit)
        m.exec_(global_pos)

    def get_available_motions(self):
        """解析 model3.json 获取所有动作组名称"""
        try:
            char_path = os.path.join(CHAR_DIR, self.active_avatar)
            prof = self.visual_profile
            model_rel = prof.get('live2d_model', '')
            model_path = os.path.join(char_path, model_rel)
            
            if os.path.exists(model_path):
                data = load_json(model_path)
                motions_data = data.get("FileReferences", {}).get("Motions", {})
                # 如果 model3.json 里没写，我们尝试直接扫描 motions 文件夹 (针对用户的情况)
                if not motions_data:
                    motions_dir = os.path.join(os.path.dirname(model_path), "motions")
                    if os.path.exists(motions_dir):
                        # 把文件名当作组名
                        files = glob.glob(os.path.join(motions_dir, "*.motion3.json"))
                        return [os.path.basename(f).replace(".motion3.json", "") for f in files]
                return list(motions_data.keys())
        except Exception as e:
            print(f"Error scanning motions: {e}")
        return []

    def play_l2d_motion(self, group):
        """调用 JS 接口播放动作"""
        if hasattr(self, 'webview') and self.webview.isVisible():
            # 这里有个细节：如果动作是通过扫描文件夹得到的，JS 的 model.motion 可能找不到
            # 我们直接运行 js 代码来触发。如果是扫描文件夹得来的，可能需要特殊处理
            # 这里我们假设 JS 端能通过 group 名触发
            js_code = f"window.playMotion('{group}');"
            self.webview.page().runJavaScript(js_code)

    def process_chat(self, t):
        # 显示"Thinking..."气泡，给予一个较长的持续时间，确保在 LLM 回复前不消失
        self.bubble.show_message("Thinking...", self.get_head_pos(), 60000)
        threading.Thread(target=self._chat_thread, args=(t,)).start()

    def _chat_thread(self, t):
        prompt = self.visual_profile.get('system_prompt', '')
        key = self.config['llm'].get('api_key','')
        resp = "..."
        if key:
            try:
                # 构建消息上下文
                messages = [{"role":"system","content":prompt}]
                messages.extend(self.chat_history)
                messages.append({"role":"user","content":t})

                r = requests.post(
                    self.config['llm']['base_url'],
                    headers={"Authorization":f"Bearer {key}"},
                    json={"model":self.config['llm']['model'], "messages":messages},
                    timeout=60, proxies={"http":None,"https":None}
                )
                if r.status_code==200:
                    c=r.json()['choices'][0]['message']['content']
                    resp=c.split("</think>")[-1].strip() if "</think>" in c else c
                    
                    # 更新并修剪记忆
                    self.chat_history.append({"role":"user","content":t})
                    self.chat_history.append({"role":"assistant","content":resp})
                    if len(self.chat_history) > self.max_history_len:
                        self.chat_history = self.chat_history[-self.max_history_len:]
            except Exception as e: print(e)
        self.signals.chat_finished.emit(resp)

    def on_chat(self, t):
        self.current_response_text = t
        enable_tts = self.config['app'].get('enable_tts', True)
        
        if not enable_tts:
            # 纯文本模式：立即显示
            duration = max(3000, len(t) * 200)
            self.bubble.show_message(t, self.get_head_pos(), duration)
        else:
            # TTS 模式：保持 "Thinking..." 或者显示 "Generating Voice..."
            # 这里的策略是：不更新气泡，保持 process_chat 设置的 "Thinking..."
            # 或者更新状态提示
            self.bubble.show_message("Thinking...", self.get_head_pos(), 60000)
            threading.Thread(target=self._tts_thread, args=(t,)).start()

    def _tts_thread(self, t):
        if not self.config['app'].get('enable_tts', True):
            return

        # 简单的 TTS 调用逻辑，复用之前的参数
        url = self.config['app'].get('tts_api_url')
        if not url: return
        ref = self.voice_profile.get('ref_audio'); base = self.voice_profile.get('_base_path')
        if not ref or not base: return
        abs_ref = os.path.join(base, ref)
        
        try:
            r = requests.post(url.rstrip('/')+'/tts', json={
                "text": t.replace('\n',' '),'text_lang':'all_zh',
                "ref_audio_path": abs_ref, "prompt_text": self.voice_profile.get('prompt_text',''), "prompt_lang":"all_zh"
            }, timeout=30)
            if r.status_code==200:
                with open(TEMP_AUDIO_PATH,'wb') as f: f.write(r.content)
                self.signals.tts_finished.emit(TEMP_AUDIO_PATH)
        except: pass

    def on_tts(self, p): 
        # 计算音频时长
        duration = 5000 # 默认兜底
        try:
            with contextlib.closing(wave.open(p, 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                duration = int((frames / float(rate)) * 1000)
                # 稍微加一点余量 (e.g. 500ms) 确保气泡不会在语音结束前立刻消失
                duration += 500
        except Exception as e:
            print(f"Error getting wav duration: {e}")

        # 播放声音
        winsound.PlaySound(p, winsound.SND_FILENAME|winsound.SND_ASYNC)
        
        # 同步显示气泡
        text = self.current_response_text if self.current_response_text else "..."
        self.bubble.show_message(text, self.get_head_pos(), duration)
    
    def load_audio_pool(self): self.audio_files=[]
    def talk_random(self):
        d=self.config.get('interaction',{}).get('random_talk',["Hi~"])
        self.bubble.show_message(random.choice(d), self.get_head_pos())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet()
    sys.exit(app.exec_())
