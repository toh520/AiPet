import os
import glob
import shutil
import time
from PyQt5.QtWidgets import (QWidget, QLabel, QGroupBox, QFormLayout, QLineEdit, 
                             QTextEdit, QComboBox, QRadioButton, QButtonGroup, 
                             QCheckBox, QPushButton, QHBoxLayout, QVBoxLayout, 
                             QTabWidget, QFileDialog, QMessageBox, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QTimer
from aipet.config import CONFIG_PATH, CHAR_DIR, WEB_ENGINE_AVAILABLE
from aipet.utils import load_json, save_json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aipet.ui.pet_window import DesktopPet

class NoWheelComboBox(QComboBox):
    """自定义下拉框，屏蔽鼠标滚轮滚动修改选项的默认行为，防止用户滑动页面时意外误触。
    忽略此事件后，滚轮事件会冒泡传给父级 QScrollArea 容器，从而实现正常的页面滚动。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def wheelEvent(self, event):
        event.ignore()

class SettingsWindow(QWidget):
    """可视化设置窗口 - V2.2 Genshin/StarRail ACG 风格美化版"""
    def __init__(self, parent_pet: 'DesktopPet'):
        super().__init__()
        self.pet = parent_pet
        self.setWindowTitle("AiPet 智能控制台 (Admin)")
        self.resize(780, 720)  # 稍微放宽窗口以配合分行分块后的文字描述
        self.setMinimumSize(760, 680)  # 限制窗口最小尺寸，防止窗口收缩过小导致“资产工坊”内容溢出并被滚动条遮挡
        self.apply_stylesheet()
        self.init_ui()

    def apply_stylesheet(self):
        # 换用经典的二次元游戏（如原神/星铁）风格暗青蓝/琥珀金配色，配合清晰的描述字体与淡金悬停高亮，极具质感
        self.setStyleSheet("""
            /* 全局基础样式 */
            QWidget { 
                background-color: #12151e; 
                color: #ece5d8; 
                font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif; 
                font-size: 15px; 
            }
            
            /* 选项卡窗口样式 */
            QTabWidget::pane { 
                border: 1px solid #2f364a; 
                background-color: #192030;
                border-radius: 6px;
                top: -1px; 
            }
            QTabBar::tab { 
                background: #0c0f17; 
                color: #8b94a8; 
                padding: 14px 28px; 
                border-top-left-radius: 6px; 
                border-top-right-radius: 6px; 
                margin-right: 6px;
                font-weight: bold;
                border: 1px solid #2f364a;
                border-bottom: none;
                font-size: 15px;
            }
            QTabBar::tab:hover {
                background: #22293b;
                color: #ece5d8;
            }
            QTabBar::tab:selected { 
                background: #192030; 
                color: #d3bc8e; 
                border-bottom: 3px solid #d3bc8e;
                border-top: 1px solid #2f364a;
            }
            
            /* 分组框样式 */
            QGroupBox { 
                border: 1px solid #3c4866; 
                border-radius: 6px; 
                margin-top: 20px; 
                font-weight: bold; 
                font-size: 17px;
                padding: 24px 18px 18px 18px; 
                background-color: #1c2333;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                padding: 0 10px; 
                left: 15px; 
                color: #d3bc8e; 
            }
            
            /* 输入框、文本框、下拉列表样式 */
            QLineEdit, QTextEdit, QComboBox { 
                background-color: #1e2536; 
                border: 1px solid #3c4866; 
                padding: 10px 14px; 
                border-radius: 6px; 
                color: #ece5d8; 
                selection-background-color: #d3bc8e; 
                selection-color: #12151e;
                font-size: 14px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus { 
                border: 1px solid #d3bc8e; 
                background-color: #242c3f;
            }
            QComboBox::drop-down {
                border: none;
                width: 34px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e2536;
                border: 1px solid #3c4866;
                selection-background-color: #d3bc8e;
                selection-color: #12151e;
            }
            
            /* 单选框与复选框 */
            QRadioButton {
                spacing: 10px;
                color: #ece5d8;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid #3c4866;
                background-color: #1e2536;
            }
            QRadioButton::indicator:checked {
                background-color: #d3bc8e;
                border: 2px solid #d3bc8e;
            }
            QCheckBox { 
                spacing: 10px; 
                color: #ece5d8;
            }
            QCheckBox::indicator { 
                width: 20px; 
                height: 20px; 
                border-radius: 4px;
                border: 2px solid #3c4866;
                background-color: #1e2536;
            }
            QCheckBox::indicator:checked { 
                background-color: #d3bc8e; 
                border: 2px solid #d3bc8e;
            }
            
            /* 按钮基本样式 (默认为深暗青蓝二次元卡片按钮样式) */
            QPushButton { 
                background-color: #22293a;
                border: 1px solid #485474;
                padding: 12px 24px; 
                border-radius: 6px; 
                color: #ece5d8; 
                font-weight: bold; 
                font-size: 15px;
            }
            QPushButton:hover { 
                background-color: #2f3850;
                border: 1px solid #d3bc8e;
            }
            QPushButton:pressed { 
                background-color: #1a1e2b; 
            }
            
            /* 成功/保存/应用按钮 (使用明亮原神琥珀金拉丝渐变，深咖啡色文字) */
            QPushButton#save_btn, QPushButton#save_char_btn, QPushButton#apply_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ebdcb9, stop:1 #c19f6a);
                color: #2a2010;
                border: none;
            }
            QPushButton#save_btn:hover, QPushButton#save_char_btn:hover, QPushButton#apply_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f5edd5, stop:1 #cca974);
            }
            
            /* 危险操作按钮（如删除，采用深红渐变） */
            QPushButton#del_btn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b54747, stop:1 #8e2b2b);
                color: #ffffff;
                border: none;
            }
            QPushButton#del_btn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #c95c5c, stop:1 #a63535);
            }
            
            /* 文件浏览小按钮 (统一使用“浏览”文本，使其大小合适，居中显示) */
            QPushButton#browse_btn {
                padding: 0px;
                margin: 0px;
                font-size: 13px;
                border-radius: 4px;
                background-color: #22293a;
                border: 1px solid #485474;
                color: #ece5d8;
                font-weight: normal;
            }
            QPushButton#browse_btn:hover {
                background-color: #2f3850;
                border: 1px solid #d3bc8e;
            }
            QPushButton#browse_btn:pressed {
                background-color: #1a1e2b;
            }
            
            /* 标签样式 */
            QLabel {
                color: #ccd2e0;
                font-weight: 500;
            }
            
            /* 滚动区域与容器 */
            QScrollArea#system_scroll, QScrollArea#creator_scroll {
                background-color: transparent;
                border: none;
            }
            QWidget#system_scroll_container, QWidget#creator_scroll_container {
                background-color: transparent;
            }
            
            /* 极简精致二次元游戏滚动条 */
            QScrollBar:vertical { 
                background: #0f121d; 
                width: 10px; 
                margin: 0px; 
                border-radius: 5px;
            }
            QScrollBar::handle:vertical { 
                background-color: #3c4866; 
                min-height: 40px; 
                border-radius: 5px; 
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #d3bc8e;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #bfa473;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
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
        close_btn.setProperty("styleClass", "secondary")
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

        self.avatar_selector = NoWheelComboBox()
        self.avatar_selector.setToolTip("决定桌宠显示哪一个 Live2D 或图片形象")
        form.addRow("👀 显示形象:", self.avatar_selector)

        self.voice_selector = NoWheelComboBox()
        self.voice_selector.setToolTip("决定桌宠使用哪一个角色的音色说话 (基于 RVC 变声)")
        form.addRow("🎤 说话声音:", self.voice_selector)

        group.setLayout(form)
        layout.addWidget(group)

        # 增加好看的提示信息
        tip_group = QGroupBox("💡 运行贴士")
        tip_layout = QVBoxLayout()
        tip_text = QLabel("您可以通过控制台自由组合“形象”与“说话声音”。例如：可以让胡桃的形象套用芙宁娜的声线说话，尽情混搭吧！")
        tip_text.setWordWrap(True)
        tip_text.setStyleSheet("color: #8f8fa3; line-height: 1.4;")
        tip_layout.addWidget(tip_text)
        tip_group.setLayout(tip_layout)
        layout.addWidget(tip_group)

        apply_btn = QPushButton("✅ 应用搭配")
        apply_btn.setObjectName("apply_btn")  # 明确指定 ObjectName 供二次元 QSS 定位，杜绝背景渲染失败问题
        apply_btn.clicked.connect(self.apply_mix_match)
        layout.addWidget(apply_btn)
        layout.addStretch()
        self.tab_run.setLayout(layout)

    def init_system_tab(self):
        tab_layout = QVBoxLayout(self.tab_system)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 建立滚动区域并设定 objectName 以支持 QSS 样式表
        scroll = QScrollArea()
        scroll.setObjectName("system_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 内部容器设定 objectName，防止 background 样式继承污染子控件
        container = QWidget()
        container.setObjectName("system_scroll_container")
        layout = QVBoxLayout(container)
        # 右侧预留 28px 间距，确保轻盈纤细的二次元滚动条不会遮挡或重叠任何分组框内容
        layout.setContentsMargins(15, 15, 28, 15)
        layout.setSpacing(15)
        
        # --- LLM 设置 ---
        llm_group = QGroupBox("🧠 大脑 (LLM) 设置")
        llm_form = QFormLayout()
        llm_form.setVerticalSpacing(10)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("请输入 API Key (如 sk-...)")
        
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("如 https://api.openai.com/v1")
        
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("如 gpt-4o-mini")
        
        llm_form.addRow("API Key:", self.api_key_input)
        llm_form.addRow("Base URL:", self.base_url_input)
        llm_form.addRow("模型名称:", self.model_input)
        llm_group.setLayout(llm_form)
        layout.addWidget(llm_group)

        # --- 语音设置 (已针对新版 Edge-TTS 与 RVC 进行精简和重定义) ---
        tts_group = QGroupBox("🔌 语音 (TTS) 设置")
        tts_layout = QVBoxLayout()
        
        self.tts_enable_check = QCheckBox("启用 TTS 语音合成")
        self.tts_enable_check.setToolTip("关闭后桌宠将进入静音模式，只显示文字气泡")
        tts_layout.addWidget(self.tts_enable_check)
        
        # 增加对 Edge-TTS 云端合成和 RVC 变声的友好解释
        tts_desc = QLabel(
            "💡 语音系统说明：采用微软 Edge-TTS 云端无损语音合成，无需本地启动任何 heavy 的语音服务器。\n"
            "若需启用特定角色（如胡桃）的克隆声线，只需在【资产工坊】为该角色配置 RVC 变声模型即可。"
        )
        tts_desc.setWordWrap(True)
        tts_desc.setStyleSheet("color: #8f8fa3; font-size: 13px; line-height: 1.4; margin-top: 5px;")
        tts_layout.addWidget(tts_desc)
        
        tts_group.setLayout(tts_layout)
        layout.addWidget(tts_group)

        # --- 互动设置 ---
        interact_group = QGroupBox("💬 互动语录设置")
        interact_layout = QVBoxLayout()
        
        interact_layout.addWidget(QLabel("点击桌宠触发的随机语录 (每行一句):"))
        self.random_talk_input = QTextEdit()
        self.random_talk_input.setMaximumHeight(80)
        self.random_talk_input.setPlaceholderText("Hi~\n你好呀！\n今天天气真好")
        interact_layout.addWidget(self.random_talk_input)
        
        interact_layout.addWidget(QLabel("思考中点击触发的吐槽语录 (每行一句):"))
        self.thinking_talk_input = QTextEdit()
        self.thinking_talk_input.setMaximumHeight(80)
        self.thinking_talk_input.setPlaceholderText("哎呀，脑细胞在飞速燃烧啦，等我一下下嘛~\n别催啦别催啦，大脑要过载啦~")
        interact_layout.addWidget(self.thinking_talk_input)
        
        interact_group.setLayout(interact_layout)
        layout.addWidget(interact_group)

        # --- 显示设置 ---
        app_group = QGroupBox("🖥️ 桌面显示设置")
        app_form = QFormLayout()
        self.scale_input = QLineEdit()
        self.refresh_rate_input = QLineEdit()
        self.chat_mode_combo = NoWheelComboBox()
        self.chat_mode_combo.addItems(["打字机模式 (流式文字)", "字幕同步模式 (音字同步)"])
        app_form.addRow("缩放比例 (0.5 - 2.0):", self.scale_input)
        app_form.addRow("刷新频率 (ms):", self.refresh_rate_input)
        app_form.addRow("对话气泡模式:", self.chat_mode_combo)
        app_group.setLayout(app_form)
        layout.addWidget(app_group)

        save_btn = QPushButton("💾 保存系统设置")
        save_btn.setObjectName("save_btn")  # 明确指定 ObjectName 供二次元 QSS 定位，杜绝背景渲染失败问题
        save_btn.setProperty("styleClass", "success")
        save_btn.clicked.connect(self.save_system_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        scroll.setWidget(container)
        tab_layout.addWidget(scroll)

    def init_creator_tab(self):
        tab_layout = QVBoxLayout(self.tab_creator)
        tab_layout.setContentsMargins(15, 15, 15, 15)
        tab_layout.setSpacing(15)
        
        # 顶部目标编辑器选择 (固定在顶部不随滚动条移动)
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("编辑目标角色:"))
        self.editor_char_selector = NoWheelComboBox()
        self.editor_char_selector.currentIndexChanged.connect(self.load_char_to_editor)
        top_layout.addWidget(self.editor_char_selector)
        
        new_btn = QPushButton("➕ 新建")
        new_btn.setObjectName("new_btn")
        new_btn.setProperty("styleClass", "secondary")
        new_btn.clicked.connect(self.prepare_new_char)
        top_layout.addWidget(new_btn)
        
        del_btn = QPushButton("🗑️ 删除")
        del_btn.setObjectName("del_btn")
        del_btn.setProperty("styleClass", "danger")
        del_btn.clicked.connect(self.delete_character)
        top_layout.addWidget(del_btn)
        
        tab_layout.addLayout(top_layout)
        
        # 建立滚动区域并设定 objectName 以支持 QSS 样式表
        scroll = QScrollArea()
        scroll.setObjectName("creator_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 内部容器设定 objectName，防止 background 样式继承污染子控件
        container = QWidget()
        container.setObjectName("creator_scroll_container")
        layout = QVBoxLayout(container)
        # 右侧同样预留 28px 间距，确保滚动条不会遮挡到后面的表单输入框
        layout.setContentsMargins(0, 0, 28, 0)
        layout.setSpacing(15)

        # 基础图像与 Live2D 材质编辑分组
        editor_group = QGroupBox("📝 形象材质编辑")
        form = QFormLayout()
        form.setVerticalSpacing(8)

        self.char_name_input = QLineEdit()
        form.addRow("ID (英文文件夹名):", self.char_name_input)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMaximumHeight(60)
        form.addRow("人设 Prompt 语录:", self.system_prompt_input)

        # 渲染模式选择
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

        # 图片源文件路径
        self.img_path_display = QLineEdit()
        self.img_btn = QPushButton("浏览")
        self.img_btn.setObjectName("browse_btn")
        self.img_btn.setProperty("styleClass", "secondary")
        self.img_btn.setFixedSize(60, 30)
        self.img_btn.clicked.connect(self.browse_images)
        self.img_row_layout = QHBoxLayout()
        self.img_row_layout.addWidget(self.img_path_display)
        self.img_row_layout.addWidget(self.img_btn)
        self.lbl_img = QLabel("图片源目录:")
        form.addRow(self.lbl_img, self.img_row_layout)

        # Live2D 模型文件路径
        self.l2d_path_display = QLineEdit()
        self.l2d_btn = QPushButton("浏览")
        self.l2d_btn.setObjectName("browse_btn")
        self.l2d_btn.setProperty("styleClass", "secondary")
        self.l2d_btn.setFixedSize(60, 30)
        self.l2d_btn.clicked.connect(self.browse_live2d)
        self.l2d_row_layout = QHBoxLayout()
        self.l2d_row_layout.addWidget(self.l2d_path_display)
        self.l2d_row_layout.addWidget(self.l2d_btn)
        self.lbl_l2d = QLabel("Live2D 模型文件:")
        form.addRow(self.lbl_l2d, self.l2d_row_layout)
        
        # Live2D 微调参数
        self.l2d_scale_input = QLineEdit("1.0")
        self.l2d_offset_input = QLineEdit("0.0")
        l2d_params = QHBoxLayout()
        l2d_params.addWidget(QLabel("缩放:"))
        l2d_params.addWidget(self.l2d_scale_input)
        l2d_params.addWidget(QLabel("偏移:"))
        l2d_params.addWidget(self.l2d_offset_input)
        self.l2d_param_row = l2d_params
        
        self.toggle_asset_input()
        form.addRow(self.l2d_param_row)

        editor_group.setLayout(form)
        layout.addWidget(editor_group)

        # 🔊 语音引擎配置分组框（支持 GPT-SoVITS, RVC 变声, 纯 Edge-TTS）
        voice_group = QGroupBox("🔊 语音发音配置")
        voice_form = QFormLayout()
        voice_form.setVerticalSpacing(8)

        # 发音模式下拉框
        self.voice_mode_combo = NoWheelComboBox()
        self.voice_mode_combo.addItems([
            "gpt_sovits (本地直接合成)",
            "rvc (云端TTS + RVC变声)",
            "edge_tts (纯云端语音)"
        ])
        self.voice_mode_combo.currentIndexChanged.connect(self.on_voice_mode_changed)
        voice_form.addRow("发音模式:", self.voice_mode_combo)

        # --- GPT-SoVITS 专属表单项 ---
        # 1. 参考音频
        self.lbl_gsv_ref = QLabel("🎤 参考音频 (.wav):")
        self.gsv_ref_audio_display = QLineEdit()
        self.gsv_ref_audio_btn = QPushButton("浏览")
        self.gsv_ref_audio_btn.setObjectName("browse_btn")
        self.gsv_ref_audio_btn.setProperty("styleClass", "secondary")
        self.gsv_ref_audio_btn.setFixedSize(60, 30)
        self.gsv_ref_audio_btn.clicked.connect(self.browse_gsv_ref_audio)
        gsv_ref_row = QHBoxLayout()
        gsv_ref_row.addWidget(self.gsv_ref_audio_display)
        gsv_ref_row.addWidget(self.gsv_ref_audio_btn)
        voice_form.addRow(self.lbl_gsv_ref, gsv_ref_row)
        
        self.lbl_gsv_ref_desc = QLabel("💡 提示：作为声线克隆的音色样本（建议 3~10 秒，需清晰无背景噪音）")
        self.lbl_gsv_ref_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_gsv_ref_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_gsv_ref_desc)

        # 2. 参考音频文本
        self.lbl_gsv_text = QLabel("📝 参考音频文本:")
        self.gsv_prompt_text_display = QLineEdit()
        voice_form.addRow(self.lbl_gsv_text, self.gsv_prompt_text_display)
        
        self.lbl_gsv_text_desc = QLabel("💡 提示：输入上方参考音频中说话的实际文本，字面内容必须完全一致")
        self.lbl_gsv_text_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_gsv_text_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_gsv_text_desc)

        # 3. GPT 模型 (.ckpt)
        self.lbl_gsv_ckpt = QLabel("🧠 GPT 模型 (.ckpt):")
        self.gsv_ckpt_display = QLineEdit()
        self.gsv_ckpt_btn = QPushButton("浏览")
        self.gsv_ckpt_btn.setObjectName("browse_btn")
        self.gsv_ckpt_btn.setProperty("styleClass", "secondary")
        self.gsv_ckpt_btn.setFixedSize(60, 30)
        self.gsv_ckpt_btn.clicked.connect(self.browse_gsv_ckpt)
        gsv_ckpt_row = QHBoxLayout()
        gsv_ckpt_row.addWidget(self.gsv_ckpt_display)
        gsv_ckpt_row.addWidget(self.gsv_ckpt_btn)
        voice_form.addRow(self.lbl_gsv_ckpt, gsv_ckpt_row)
        
        self.lbl_gsv_ckpt_desc = QLabel("💡 提示：自回归微调模型权重文件（若仅使用零样本克隆模式可留空）")
        self.lbl_gsv_ckpt_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_gsv_ckpt_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_gsv_ckpt_desc)

        # 4. SoVITS 模型 (.pth)
        self.lbl_gsv_pth = QLabel("🎵 SoVITS 模型 (.pth):")
        self.gsv_pth_display = QLineEdit()
        self.gsv_pth_btn = QPushButton("浏览")
        self.gsv_pth_btn.setObjectName("browse_btn")
        self.gsv_pth_btn.setProperty("styleClass", "secondary")
        self.gsv_pth_btn.setFixedSize(60, 30)
        self.gsv_pth_btn.clicked.connect(self.browse_gsv_pth)
        gsv_pth_row = QHBoxLayout()
        gsv_pth_row.addWidget(self.gsv_pth_display)
        gsv_pth_row.addWidget(self.gsv_pth_btn)
        voice_form.addRow(self.lbl_gsv_pth, gsv_pth_row)
        
        self.lbl_gsv_pth_desc = QLabel("💡 提示：音色生成微调模型文件（若仅使用零样本克隆模式可留空）")
        self.lbl_gsv_pth_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_gsv_pth_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_gsv_pth_desc)

        # 5. 推理温度 (GPT-SoVITS 专属)
        self.lbl_gsv_temp = QLabel("🔥 推理采样温度:")
        self.gsv_temp_display = QLineEdit("0.4")
        voice_form.addRow(self.lbl_gsv_temp, self.gsv_temp_display)
        
        self.lbl_gsv_temp_desc = QLabel("💡 提示：采样温度（0.1~1.0），越小发音越稳定，可用于降低随机电流声，推荐 0.4")
        self.lbl_gsv_temp_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_gsv_temp_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_gsv_temp_desc)

        # --- RVC 专属表单项 ---
        # 1. RVC 模型权重 (.pth)
        self.lbl_rvc_pth = QLabel("💎 RVC 变声权重 (.pth):")
        self.rvc_pth_display = QLineEdit()
        self.rvc_pth_btn = QPushButton("浏览")
        self.rvc_pth_btn.setObjectName("browse_btn")
        self.rvc_pth_btn.setProperty("styleClass", "secondary")
        self.rvc_pth_btn.setFixedSize(60, 30)
        self.rvc_pth_btn.clicked.connect(self.browse_rvc_pth)
        rvc_pth_row = QHBoxLayout()
        rvc_pth_row.addWidget(self.rvc_pth_display)
        rvc_pth_row.addWidget(self.rvc_pth_btn)
        voice_form.addRow(self.lbl_rvc_pth, rvc_pth_row)
        
        self.lbl_rvc_pth_desc = QLabel("💡 提示：用于将普通人声转换成目标角色声线的变声模型文件")
        self.lbl_rvc_pth_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_rvc_pth_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_rvc_pth_desc)

        # 2. 特征检索索引 (.index)
        self.lbl_rvc_index = QLabel("📊 特征检索索引 (.index):")
        self.rvc_index_display = QLineEdit()
        self.rvc_index_btn = QPushButton("浏览")
        self.rvc_index_btn.setObjectName("browse_btn")
        self.rvc_index_btn.setProperty("styleClass", "secondary")
        self.rvc_index_btn.setFixedSize(60, 30)
        self.rvc_index_btn.clicked.connect(self.browse_rvc_index)
        rvc_index_row = QHBoxLayout()
        rvc_index_row.addWidget(self.rvc_index_display)
        rvc_index_row.addWidget(self.rvc_index_btn)
        voice_form.addRow(self.lbl_rvc_index, rvc_index_row)
        
        self.lbl_rvc_index_desc = QLabel("💡 提示：可选索引文件，用于强化角色特征细节以防止音调跑偏（非必须）")
        self.lbl_rvc_index_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_rvc_index_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_rvc_index_desc)

        # 3. 音高提取算法 (RVC 专属)
        self.lbl_rvc_f0_method = QLabel("🎯 基频音高提取算法:")
        self.rvc_f0_method_combo = NoWheelComboBox()
        self.rvc_f0_method_combo.addItems(["crepe", "harvest", "pm"])
        voice_form.addRow(self.lbl_rvc_f0_method, self.rvc_f0_method_combo)
        
        self.lbl_rvc_f0_method_desc = QLabel("💡 提示：推荐使用 crepe 算法，能够获得最清澈、最少杂音的变声效果")
        self.lbl_rvc_f0_method_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_rvc_f0_method_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_rvc_f0_method_desc)

        # 4. 特征检索强度 (RVC 专属)
        self.lbl_rvc_index_rate = QLabel("⚡ 特征检索强度:")
        self.rvc_index_rate_display = QLineEdit("0.75")
        voice_form.addRow(self.lbl_rvc_index_rate, self.rvc_index_rate_display)
        
        self.lbl_rvc_index_rate_desc = QLabel("💡 提示：特征检索率（0.0~1.0），数值越大越像角色，但过高可能引发沙哑")
        self.lbl_rvc_index_rate_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_rvc_index_rate_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_rvc_index_rate_desc)

        # 5. 清辅音/呼吸占比保护 (RVC 专属)
        self.lbl_rvc_protect = QLabel("🛡️ 清辅音保护比率:")
        self.rvc_protect_display = QLineEdit("0.33")
        voice_form.addRow(self.lbl_rvc_protect, self.rvc_protect_display)
        
        self.lbl_rvc_protect_desc = QLabel("💡 提示：辅音保护率（0.0~0.5），保护气音呼吸声不被强行改写，推荐 0.33")
        self.lbl_rvc_protect_desc.setWordWrap(True)  # 开启自动换行，防止长文本撑宽容器导致滚动条重叠
        self.lbl_rvc_protect_desc.setStyleSheet("color: #8b94a8; font-size: 13px; margin-bottom: 8px;")
        voice_form.addRow("", self.lbl_rvc_protect_desc)

        # 提示语标签
        self.lbl_voice_tip = QLabel("💡 提示：发音模式支持按需配置。")
        self.lbl_voice_tip.setWordWrap(True)
        self.lbl_voice_tip.setStyleSheet("color: #8f8fa3; font-size: 13px; line-height: 1.4; margin-top: 5px;")
        voice_form.addRow(self.lbl_voice_tip)

        voice_group.setLayout(voice_form)
        layout.addWidget(voice_group)

        # 保存角色资产按钮
        save_char_btn = QPushButton("💾 保存资产配置")
        save_char_btn.setObjectName("save_char_btn")  # 明确指定 ObjectName 供二次元 QSS 定位，杜绝背景渲染失败问题
        save_char_btn.setProperty("styleClass", "success")
        save_char_btn.clicked.connect(self.save_character_asset)
        layout.addWidget(save_char_btn)

        scroll.setWidget(container)
        tab_layout.addWidget(scroll)

    def toggle_asset_input(self):
        is_live2d = self.rb_live2d.isChecked()
        self.lbl_img.setVisible(not is_live2d)
        self.img_path_display.setVisible(not is_live2d)
        self.img_btn.setVisible(not is_live2d)
        
        self.lbl_l2d.setVisible(is_live2d)
        self.l2d_path_display.setVisible(is_live2d)
        self.l2d_btn.setVisible(is_live2d)
        
        for i in range(self.l2d_param_row.count()):
            widget = self.l2d_param_row.itemAt(i).widget()
            if widget:
                widget.setVisible(is_live2d)

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
            
            if curr_avatar in chars:
                self.avatar_selector.setCurrentText(curr_avatar)
            if curr_voice in chars:
                self.voice_selector.setCurrentText(curr_voice)
            if curr_editor in chars:
                self.editor_char_selector.setCurrentText(curr_editor)

    def load_run_values(self):
        cfg = self.pet.config
        # 若配置中无形象或声音信息，降级默认使用 default_hutao
        self.avatar_selector.setCurrentText(cfg.get('active_avatar', 'default_hutao'))
        self.voice_selector.setCurrentText(cfg.get('active_voice', 'default_hutao'))

    def apply_mix_match(self):
        self.pet.update_mix_match(self.avatar_selector.currentText(), self.voice_selector.currentText())

    def load_system_values(self):
        cfg = self.pet.config
        self.api_key_input.setText(cfg['llm'].get('api_key', ""))
        self.base_url_input.setText(cfg['llm'].get('base_url', ""))
        self.model_input.setText(cfg['llm'].get('model', ""))
        self.tts_enable_check.setChecked(cfg['app'].get('enable_tts', True))
        
        talks = cfg.get('interaction', {}).get('random_talk', ["Hi~"])
        self.random_talk_input.setText("\n".join(talks))
        
        default_thinking = [
            "哎呀，脑细胞在飞速燃烧啦，等我一下下嘛~",
            "让我想想……再想两秒钟嘛！",
            "别催啦别催啦，大脑要过载啦~",
            "唔……脑筋正在飞速运转中，等我一下嘛！",
            "哎呀，别急别急，正在努力思考中……",
            "让我想想……正在拼命组织语言呢！",
            "嘘——正在和脑海里的小精灵对话，等我几秒钟哦~",
            "正在为您加载最完美的回答，马上就好啦！"
        ]
        thinking_talks = cfg.get('interaction', {}).get('thinking_talk', default_thinking)
        self.thinking_talk_input.setText("\n".join(thinking_talks))
        
        self.scale_input.setText(str(cfg['app'].get('scale', 1.0)))
        self.refresh_rate_input.setText(str(cfg['app'].get('refresh_rate', 100)))
        
        chat_mode = cfg['app'].get('chat_mode', 'subtitle')
        self.chat_mode_combo.setCurrentIndex(1 if chat_mode == 'subtitle' else 0)

    def save_system_settings(self):
        try:
            self.pet.config['llm']['api_key'] = self.api_key_input.text()
            self.pet.config['llm']['base_url'] = self.base_url_input.text()
            self.pet.config['llm']['model'] = self.model_input.text()
            self.pet.config['app']['enable_tts'] = self.tts_enable_check.isChecked()
            self.pet.config['app']['scale'] = float(self.scale_input.text())
            self.pet.config['app']['refresh_rate'] = int(self.refresh_rate_input.text())
            self.pet.config['app']['chat_mode'] = 'subtitle' if self.chat_mode_combo.currentIndex() == 1 else 'typewriter'
            
            lines = [l.strip() for l in self.random_talk_input.toPlainText().split('\n') if l.strip()]
            thinking_lines = [l.strip() for l in self.thinking_talk_input.toPlainText().split('\n') if l.strip()]
            
            if 'interaction' not in self.pet.config:
                self.pet.config['interaction'] = {}
            self.pet.config['interaction']['random_talk'] = lines
            self.pet.config['interaction']['thinking_talk'] = thinking_lines
            
            save_json(CONFIG_PATH, self.pet.config)
            self.pet.apply_config_system()
            QMessageBox.information(self, "成功", "系统设置已保存！")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def prepare_new_char(self):
        # 临时阻止信号，避免在向下拉框添加或选中临时选项时意外触发 load_char_to_editor 逻辑
        self.editor_char_selector.blockSignals(True)
        idx = self.editor_char_selector.findText("(新建角色)")
        if idx == -1:
            self.editor_char_selector.addItem("(新建角色)")
            idx = self.editor_char_selector.count() - 1
        self.editor_char_selector.setCurrentIndex(idx)
        self.editor_char_selector.blockSignals(False)

        self.char_name_input.setText("")
        self.char_name_input.setReadOnly(False)
        self.system_prompt_input.setText("")
        self.img_path_display.setText("")
        self.l2d_path_display.setText("")
        # 清空所有的语音输入框，并恢复默认配置
        self.set_current_voice_mode("edge_tts")
        self.gsv_ref_audio_display.setText("")
        self.gsv_prompt_text_display.setText("")
        self.gsv_ckpt_display.setText("")
        self.gsv_pth_display.setText("")
        self.rvc_pth_display.setText("")
        self.rvc_index_display.setText("")
        self.on_voice_mode_changed()

    def load_char_to_editor(self):
        char_name = self.editor_char_selector.currentText()
        
        # 如果用户切换到了其他有效角色，则清除临时的 "(新建角色)" 选项
        idx = self.editor_char_selector.findText("(新建角色)")
        if idx != -1 and char_name != "(新建角色)":
            self.editor_char_selector.blockSignals(True)
            self.editor_char_selector.removeItem(idx)
            self.editor_char_selector.blockSignals(False)
            
        if not char_name or char_name == "(新建角色)":
            return
        self.char_name_input.setText(char_name)
        self.char_name_input.setReadOnly(True)
        
        path = os.path.join(CHAR_DIR, char_name, "profile.json")
        data = load_json(path)
        if data:
            self.system_prompt_input.setText(data.get("system_prompt", ""))
            
            renderer = data.get("renderer", "image")
            if renderer == "live2d" and WEB_ENGINE_AVAILABLE:
                self.rb_live2d.setChecked(True)
                self.l2d_path_display.setText(data.get("live2d_model", ""))
                self.l2d_scale_input.setText(str(data.get("live2d_scale", 1.0)))
                self.l2d_offset_input.setText(str(data.get("live2d_offset_y", 0.0)))
            else:
                self.rb_image.setChecked(True)
                img_dir = os.path.join(CHAR_DIR, char_name, "idle")
                if not os.path.exists(img_dir):
                    img_dir = os.path.join(CHAR_DIR, char_name, "images")
                
                has_images = False
                if os.path.exists(img_dir):
                    if glob.glob(os.path.join(img_dir, "*.png")):
                        has_images = True
                
                if has_images:
                    self.img_path_display.setText("(已有图片)")
                else:
                    self.img_path_display.setText("")
                    
            self.toggle_asset_input()
            
            # --- 载入语音配置 ---
            voice_mode = data.get("voice_mode", "edge_tts")
            self.set_current_voice_mode(voice_mode)
            
            # GPT-SoVITS / TTS 基础配置
            tts_cfg = data.get("tts", {})
            ref_rel = tts_cfg.get("ref_audio", "")
            self.gsv_ref_audio_display.setText(os.path.join(CHAR_DIR, char_name, ref_rel) if ref_rel else "")
            self.gsv_prompt_text_display.setText(tts_cfg.get("prompt_text", ""))
            
            gsv_cfg = data.get("gpt_sovits", {})
            ckpt_rel = gsv_cfg.get("ckpt", "")
            gsv_pth_rel = gsv_cfg.get("pth", "")
            self.gsv_ckpt_display.setText(os.path.join(CHAR_DIR, char_name, ckpt_rel) if ckpt_rel else "")
            self.gsv_pth_display.setText(os.path.join(CHAR_DIR, char_name, gsv_pth_rel) if gsv_pth_rel else "")
            
            # 加载采样温度参数，默认缺省值为 0.4
            self.gsv_temp_display.setText(str(gsv_cfg.get("temperature", 0.4)))
            
            # RVC 配置
            rvc_cfg = data.get("rvc", {})
            rvc_pth_rel = rvc_cfg.get("pth", "")
            rvc_index_rel = rvc_cfg.get("index", "")
            self.rvc_pth_display.setText(os.path.join(CHAR_DIR, char_name, rvc_pth_rel) if rvc_pth_rel else "")
            self.rvc_index_display.setText(os.path.join(CHAR_DIR, char_name, rvc_index_rel) if rvc_index_rel else "")
            
            # 载入 RVC 专属高级参数，如果为空则采用预设的最佳推荐值
            f0_method = rvc_cfg.get("f0_method", "harvest")
            modes = ["crepe", "harvest", "pm"]
            if f0_method in modes:
                self.rvc_f0_method_combo.setCurrentIndex(modes.index(f0_method))
            else:
                self.rvc_f0_method_combo.setCurrentIndex(1) # 默认 harvest
                
            self.rvc_index_rate_display.setText(str(rvc_cfg.get("index_rate", 0.75)))
            self.rvc_protect_display.setText(str(rvc_cfg.get("protect", 0.33)))
            
            # 动态触发切换显示
            self.on_voice_mode_changed()

    def browse_images(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if d:
            self.img_path_display.setText(d)
    
    def browse_live2d(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 .model3.json", "c:\\", "Live2D Model (*.model3.json)")
        if f:
            self.l2d_path_display.setText(f)

    def browse_gsv_ref_audio(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择参考音频 (.wav)", "c:\\", "Wav Audio (*.wav)")
        if f:
            self.gsv_ref_audio_display.setText(f)

    def browse_gsv_ckpt(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 GPT 权重模型 (.ckpt)", "c:\\", "GPT Model (*.ckpt)")
        if f:
            self.gsv_ckpt_display.setText(f)

    def browse_gsv_pth(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 SoVITS 权重模型 (.pth)", "c:\\", "SoVITS Model (*.pth)")
        if f:
            self.gsv_pth_display.setText(f)

    def browse_rvc_pth(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 RVC 权重模型", "c:\\", "RVC Model (*.pth)")
        if f:
            self.rvc_pth_display.setText(f)

    def browse_rvc_index(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择特征检索索引", "c:\\", "RVC Index (*.index)")
        if f:
            self.rvc_index_display.setText(f)

    def on_voice_mode_changed(self):
        # 根据选择的发音模式，动态隐藏/显示对应的参数输入行与提示语
        mode = self.get_current_voice_mode()
        
        # GPT-SoVITS 元素与描述显示状态
        is_gsv = (mode == "gpt_sovits")
        self.lbl_gsv_ref.setVisible(is_gsv)
        self.gsv_ref_audio_display.setVisible(is_gsv)
        self.gsv_ref_audio_btn.setVisible(is_gsv)
        self.lbl_gsv_ref_desc.setVisible(is_gsv)
        
        self.lbl_gsv_text.setVisible(is_gsv)
        self.gsv_prompt_text_display.setVisible(is_gsv)
        self.lbl_gsv_text_desc.setVisible(is_gsv)
        
        self.lbl_gsv_ckpt.setVisible(is_gsv)
        self.gsv_ckpt_display.setVisible(is_gsv)
        self.gsv_ckpt_btn.setVisible(is_gsv)
        self.lbl_gsv_ckpt_desc.setVisible(is_gsv)
        
        self.lbl_gsv_pth.setVisible(is_gsv)
        self.gsv_pth_display.setVisible(is_gsv)
        self.gsv_pth_btn.setVisible(is_gsv)
        self.lbl_gsv_pth_desc.setVisible(is_gsv)
        
        self.lbl_gsv_temp.setVisible(is_gsv)
        self.gsv_temp_display.setVisible(is_gsv)
        self.lbl_gsv_temp_desc.setVisible(is_gsv)
        
        # RVC 元素与描述显示状态
        is_rvc = (mode == "rvc")
        self.lbl_rvc_pth.setVisible(is_rvc)
        self.rvc_pth_display.setVisible(is_rvc)
        self.rvc_pth_btn.setVisible(is_rvc)
        self.lbl_rvc_pth_desc.setVisible(is_rvc)
        
        self.lbl_rvc_index.setVisible(is_rvc)
        self.rvc_index_display.setVisible(is_rvc)
        self.rvc_index_btn.setVisible(is_rvc)
        self.lbl_rvc_index_desc.setVisible(is_rvc)
        
        self.lbl_rvc_f0_method.setVisible(is_rvc)
        self.rvc_f0_method_combo.setVisible(is_rvc)
        self.lbl_rvc_f0_method_desc.setVisible(is_rvc)
        
        self.lbl_rvc_index_rate.setVisible(is_rvc)
        self.rvc_index_rate_display.setVisible(is_rvc)
        self.lbl_rvc_index_rate_desc.setVisible(is_rvc)
        
        self.lbl_rvc_protect.setVisible(is_rvc)
        self.rvc_protect_display.setVisible(is_rvc)
        self.lbl_rvc_protect_desc.setVisible(is_rvc)
        
        # 动态更新提示语
        if mode == "gpt_sovits":
            self.lbl_voice_tip.setText(
                "💡 提示：GPT-SoVITS 模式支持零样本克隆和微调模型合成。\n"
                "• 零样本克隆：只需上传参考音频和参考文本即可。\n"
                "• 微调模型：上传对应的 GPT(.ckpt) 和 SoVITS(.pth) 微调模型以获得更好的音质和相似度。"
            )
        elif mode == "rvc":
            self.lbl_voice_tip.setText(
                "💡 提示：RVC 模式采用 Edge-TTS 生成基础音频，然后使用本地 RVC 模型进行高音质变声。\n"
                "• 请导入该角色的 RVC (.pth) 模型和可选的特征检索 (.index) 文件。"
            )
        else:
            self.lbl_voice_tip.setText(
                "💡 提示：Edge-TTS 模式为纯云端发音模式。不使用任何本地大模型，最节省本地 CPU 和内存资源。"
            )

    def get_current_voice_mode(self):
        # 获取当前选择的语音模式标识符
        idx = self.voice_mode_combo.currentIndex()
        modes = ["gpt_sovits", "rvc", "edge_tts"]
        if 0 <= idx < len(modes):
            return modes[idx]
        return "edge_tts"

    def set_current_voice_mode(self, mode):
        # 设置语音模式下拉框的选项
        modes = ["gpt_sovits", "rvc", "edge_tts"]
        if mode in modes:
            self.voice_mode_combo.setCurrentIndex(modes.index(mode))
        else:
            self.voice_mode_combo.setCurrentIndex(2) # 默认使用 edge_tts

    def delete_character(self):
        char_name = self.editor_char_selector.currentText()
        if not char_name:
            return
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
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))

    def save_character_asset(self):
        name = self.char_name_input.text().strip()
        if not name:
            return
        target_dir = os.path.join(CHAR_DIR, name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        old_prof = load_json(os.path.join(target_dir, "profile.json")) or {}
        
        is_live2d = self.rb_live2d.isChecked()
        renderer = "live2d" if is_live2d else "image"
        live2d_model_rel = old_prof.get("live2d_model", "")
        
        if is_live2d:
            src_l2d = self.l2d_path_display.text()
            if src_l2d and os.path.exists(src_l2d) and not src_l2d.startswith("voice/"):
                if not os.path.abspath(src_l2d).startswith(os.path.abspath(target_dir)):
                    src_dir = os.path.dirname(src_l2d)
                    dest_l2d_dir = os.path.join(target_dir, "live2d_model")
                    if os.path.exists(dest_l2d_dir):
                        shutil.rmtree(dest_l2d_dir)
                    shutil.copytree(src_dir, dest_l2d_dir)
                    live2d_model_rel = f"live2d_model/{os.path.basename(src_l2d)}"
                else:
                    live2d_model_rel = os.path.relpath(src_l2d, target_dir).replace("\\", "/")
        else:
            src_img = self.img_path_display.text()
            dest_img = os.path.join(target_dir, "idle")
            if src_img and os.path.isdir(src_img):
                if not os.path.exists(dest_img):
                    os.makedirs(dest_img)
                for p in glob.glob(os.path.join(src_img, "*.png")):
                    shutil.copy(p, dest_img)

        # --- 语音引擎文件拷贝与保存逻辑 ---
        mode = self.get_current_voice_mode()
        
        # 1. GPT-SoVITS 零样本 / 微调资源拷贝
        src_ref = self.gsv_ref_audio_display.text().strip()
        ref_rel = ""
        if src_ref and os.path.exists(src_ref):
            ref_dir = os.path.join(target_dir, "voice")
            if not os.path.exists(ref_dir):
                os.makedirs(ref_dir)
            if not os.path.abspath(src_ref).startswith(os.path.abspath(target_dir)):
                fname = "ref.wav"  # 统一命名为 ref.wav 方便管理
                shutil.copy(src_ref, os.path.join(ref_dir, fname))
                ref_rel = f"voice/{fname}"
            else:
                ref_rel = os.path.relpath(src_ref, target_dir).replace("\\", "/")
        else:
            ref_rel = old_prof.get("tts", {}).get("ref_audio", "")

        src_ckpt = self.gsv_ckpt_display.text().strip()
        ckpt_rel = ""
        if src_ckpt and os.path.exists(src_ckpt):
            gsv_dir = os.path.join(target_dir, "gpt_sovits")
            if not os.path.exists(gsv_dir):
                os.makedirs(gsv_dir)
            if not os.path.abspath(src_ckpt).startswith(os.path.abspath(target_dir)):
                fname = os.path.basename(src_ckpt)
                shutil.copy(src_ckpt, os.path.join(gsv_dir, fname))
                ckpt_rel = f"gpt_sovits/{fname}"
            else:
                ckpt_rel = os.path.relpath(src_ckpt, target_dir).replace("\\", "/")
        else:
            ckpt_rel = old_prof.get("gpt_sovits", {}).get("ckpt", "")

        src_gsv_pth = self.gsv_pth_display.text().strip()
        gsv_pth_rel = ""
        if src_gsv_pth and os.path.exists(src_gsv_pth):
            gsv_dir = os.path.join(target_dir, "gpt_sovits")
            if not os.path.exists(gsv_dir):
                os.makedirs(gsv_dir)
            if not os.path.abspath(src_gsv_pth).startswith(os.path.abspath(target_dir)):
                fname = os.path.basename(src_gsv_pth)
                shutil.copy(src_gsv_pth, os.path.join(gsv_dir, fname))
                gsv_pth_rel = f"gpt_sovits/{fname}"
            else:
                gsv_pth_rel = os.path.relpath(src_gsv_pth, target_dir).replace("\\", "/")
        else:
            gsv_pth_rel = old_prof.get("gpt_sovits", {}).get("pth", "")

        # 2. RVC 资源拷贝
        src_pth = self.rvc_pth_display.text().strip()
        src_index = self.rvc_index_display.text().strip()
        rvc_dir = os.path.join(target_dir, "rvc")
        
        pth_rel = ""
        index_rel = ""
        
        if src_pth and os.path.exists(src_pth):
            if not os.path.exists(rvc_dir):
                os.makedirs(rvc_dir)
            if not os.path.abspath(src_pth).startswith(os.path.abspath(target_dir)):
                fname = os.path.basename(src_pth)
                shutil.copy(src_pth, os.path.join(rvc_dir, fname))
                pth_rel = f"rvc/{fname}"
            else:
                pth_rel = os.path.relpath(src_pth, target_dir).replace("\\", "/")
        else:
            pth_rel = old_prof.get("rvc", {}).get("pth", "")

        if src_index and os.path.exists(src_index):
            if not os.path.exists(rvc_dir):
                os.makedirs(rvc_dir)
            if not os.path.abspath(src_index).startswith(os.path.abspath(target_dir)):
                fname = os.path.basename(src_index)
                shutil.copy(src_index, os.path.join(rvc_dir, fname))
                index_rel = f"rvc/{fname}"
            else:
                index_rel = os.path.relpath(src_index, target_dir).replace("\\", "/")
        else:
            index_rel = old_prof.get("rvc", {}).get("index", "")

        # 获取表单输入的微调参数并安全转换为浮点数，若报错则回退至默认值
        try:
            gsv_temp = float(self.gsv_temp_display.text().strip())
        except ValueError:
            gsv_temp = 0.4
            
        try:
            rvc_index_rate = float(self.rvc_index_rate_display.text().strip())
        except ValueError:
            rvc_index_rate = 0.75
            
        try:
            rvc_protect = float(self.rvc_protect_display.text().strip())
        except ValueError:
            rvc_protect = 0.33
            
        rvc_f0_method = self.rvc_f0_method_combo.currentText().strip()

        prof = {
            "name": name,
            "system_prompt": self.system_prompt_input.toPlainText(),
            "renderer": renderer,
            "live2d_model": live2d_model_rel,
            "live2d_scale": float(self.l2d_scale_input.text() or 1.0),
            "live2d_offset_y": float(self.l2d_offset_input.text() or 0.0),
            "voice_mode": mode,
            "tts": {
                "ref_audio": ref_rel,
                "prompt_text": self.gsv_prompt_text_display.text().strip(),
                "text_lang": "zh",
                "prompt_lang": "zh"
            },
            "gpt_sovits": {
                "ckpt": ckpt_rel,
                "pth": gsv_pth_rel,
                "temperature": gsv_temp
            },
            "rvc": {
                "enable": bool(pth_rel),
                "pth": pth_rel,
                "index": index_rel,
                "f0_method": rvc_f0_method,
                "index_rate": rvc_index_rate,
                "protect": rvc_protect
            }
        }
        save_json(os.path.join(target_dir, "profile.json"), prof)
        
        # 自动应用搭配：如果刚才修改保存的角色正是桌宠当前活跃的形象或音色角色，则自动重新加载最新配置
        if name == self.pet.active_avatar or name == self.pet.active_voice:
            self.pet.update_mix_match(self.pet.active_avatar, self.pet.active_voice)
            self.load_run_values()
            QMessageBox.information(self, "成功", "配置已保存，且已自动应用到当前桌宠！")
        else:
            QMessageBox.information(self, "成功", "配置已保存")
            
        self.refresh_all_lists()
