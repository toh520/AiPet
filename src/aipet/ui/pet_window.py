import os
import sys
import glob
import random
import winsound
import contextlib
import wave
import threading
from urllib.parse import quote

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QUrl
from PyQt5.QtGui import QPixmap, QCursor, QFont

from aipet.config import (CONFIG_PATH, CHAR_DIR, TEMP_AUDIO_PATH, 
                          WEB_TEMPLATE_PATH, WEB_ENGINE_AVAILABLE)
from aipet.utils import load_json, save_json
from aipet.signals import WorkerSignals
from aipet.services.llm_service import LLMWorker
from aipet.services.tts_service import TTSWorker, TTSQueueWorker

from aipet.ui.webview import DraggableWebView
from aipet.ui.bubble import ChatBubble
from aipet.ui.input import ChatInput
from aipet.ui.settings_window import SettingsWindow

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        # 加载本地配置文件，如果不存在则尝试从 settings.json.example 复制
        self.config = load_json(CONFIG_PATH)
        if not self.config:
            example_path = CONFIG_PATH + ".example"
            if os.path.exists(example_path):
                print(f"config/settings.json 不存在，正在从 settings.json.example 复制默认配置...")
                self.config = load_json(example_path)
                if self.config:
                    save_json(CONFIG_PATH, self.config)
            
            # 如果依然加载失败，使用硬编码默认值
            if not self.config:
                print("警告: 无法加载 settings.json 和 settings.json.example，使用硬编码默认配置。")
                self.config = {
                    "active_character": "default_hutao",
                    "active_avatar": "default_hutao",
                    "active_voice": "default_hutao",
                    "app": {
                        "width": 200,
                        "height": 200,
                        "scale": 1.1,
                        "refresh_rate": 100,
                        "tts_api_url": "http://127.0.0.1:9880",
                        "enable_tts": True,
                        "chat_mode": "typewriter"
                    },
                    "interaction": {
                        "random_talk": ["呜哇！吓你一跳！", "找本堂主有何贵干？"],
                        "thinking_talk": ["脑筋飞速运转中……", "等我一下下嘛……"]
                    },
                    "llm": {
                        "enable": True,
                        "provider": "siliconflow",
                        "api_key": "your_api_key_here",
                        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
                        "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
                    }
                }
                save_json(CONFIG_PATH, self.config)

        self.visual_profile = {}
        self.voice_profile = {}
        self.voice_full_profile = {}
        
        # 获取当前选中的形象和声音，若配置中没有则默认使用 default_hutao
        self.active_avatar = self.config.get('active_avatar', 'default_hutao')
        self.active_voice = self.config.get('active_voice', 'default_hutao')
        
        # 校验形象和声音目录是否存在，若不存在，则自动降级到存在的角色（优先 default_hutao -> furina）
        if not os.path.exists(os.path.join(CHAR_DIR, self.active_avatar)):
            print(f"警告: 形象目录 {self.active_avatar} 不存在，尝试降级。")
            if os.path.exists(os.path.join(CHAR_DIR, "default_hutao")):
                self.active_avatar = "default_hutao"
            elif os.path.exists(os.path.join(CHAR_DIR, "furina")):
                self.active_avatar = "furina"
            else:
                dirs = [d for d in os.listdir(CHAR_DIR) if os.path.isdir(os.path.join(CHAR_DIR, d))]
                if dirs:
                    self.active_avatar = dirs[0]
            self.config['active_avatar'] = self.active_avatar
            save_json(CONFIG_PATH, self.config)

        if not os.path.exists(os.path.join(CHAR_DIR, self.active_voice)):
            print(f"警告: 声音目录 {self.active_voice} 不存在，尝试降级。")
            if os.path.exists(os.path.join(CHAR_DIR, "default_hutao")):
                self.active_voice = "default_hutao"
            elif os.path.exists(os.path.join(CHAR_DIR, "furina")):
                self.active_voice = "furina"
            else:
                dirs = [d for d in os.listdir(CHAR_DIR) if os.path.isdir(os.path.join(CHAR_DIR, d))]
                if dirs:
                    self.active_voice = dirs[0]
            self.config['active_voice'] = self.active_voice
            save_json(CONFIG_PATH, self.config)
        
        # 动画状态初始化
        self.current_frame = 0
        self.frames = []
        self.angle = 0

        # 拖拽相关
        self.is_dragging = False
        self.drag_pos = QPoint()
        
        self.signals = WorkerSignals()
        self.signals.chat_finished.connect(self.on_chat)
        self.signals.tts_finished.connect(self.on_tts)
        
        # --- 连接流式交互与分句放音队列信号 ---
        self.signals.chat_chunk.connect(self.on_chat_chunk)
        self.signals.sentence_ready.connect(self.on_sentence_ready)
        self.signals.tts_sentence_finished.connect(self.on_tts_sentence_finished)

        self.initUI()
        
        # 必须先创建 WebView
        if WEB_ENGINE_AVAILABLE:
            self.webview = DraggableWebView(self)
            self.webview.resize(300, 400)
            self.webview.hide()

        self.update_mix_match(self.active_avatar, self.active_voice)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.apply_config_system()
        
        self.load_audio_pool()
        self.settings_window = SettingsWindow(self)
        
        # --- 聊天记忆与放音队列初始化 ---
        self.chat_history = [] 
        self.max_history_len = 5
        self.current_response_text = ""
        
        self.synthesized_audio = {}      # 缓存已合成的单句 {index: (wav_path, text)}
        self.next_play_index = 0         # 顺序放音索引
        self.is_playing_audio = False    # 当前句播放状态
        self.accumulated_chat_text = ""  # 流式累计文字
        
        self.llm_worker = None
        self.tts_queue_worker = None
        
        # 单句播放计时器
        self.audio_timer = QTimer(self)
        self.audio_timer.setSingleShot(True)
        self.audio_timer.timeout.connect(self.on_audio_finished)
        
        # --- 新增打字机状态与定时器 ---
        self.typewriter_timer = QTimer(self)
        self.typewriter_timer.timeout.connect(self.on_typewriter_step)
        self.typewriter_text = ""
        self.typewriter_current_len = 0
        self.displayed_history_text = ""
        
        # --- 思考专属互动语录与恢复定时器 ---
        self.is_thinking_state = False
        self.restore_thinking_timer = QTimer(self)
        self.restore_thinking_timer.setSingleShot(True)
        self.restore_thinking_timer.timeout.connect(self.restore_thinking_bubble)

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.image_label = QLabel(self)
        self.bubble = ChatBubble()
        self.chat_input = ChatInput(self)
        
        screen_geo = QApplication.primaryScreen().geometry()
        self.resize(300, 400)
        self.move((screen_geo.width() - 300) // 2, (screen_geo.height() - 400) // 2)
        self.show()

    def update_mix_match(self, av, vo):
        self.active_avatar = av
        self.active_voice = vo
        self.config['active_avatar'] = av
        self.config['active_voice'] = vo
        save_json(CONFIG_PATH, self.config)
        
        self.chat_history = []  # 切换角色搭配时清空对话记忆
        
        char_path = os.path.join(CHAR_DIR, av)
        prof = load_json(os.path.join(char_path, "profile.json")) or {}
        self.visual_profile = prof
        
        renderer = prof.get('renderer', 'image')
        
        if renderer == 'live2d' and WEB_ENGINE_AVAILABLE:
            self.image_label.hide()
            self.webview.show()
            self.load_live2d(char_path, prof)
        else:
            if hasattr(self, 'webview'):
                self.webview.hide()
            self.image_label.show()
            self.load_images(char_path)

        v_path = os.path.join(CHAR_DIR, vo)
        v_prof = load_json(os.path.join(v_path, "profile.json")) or {}
        self.voice_profile = v_prof.get('tts', {})
        self.voice_profile['_base_path'] = v_path
        self.voice_full_profile = v_prof

    def load_images(self, path):
        self.frames = []
        d = os.path.join(path, "idle")
        scale = self.config['app'].get('scale', 1.0)
        for p in sorted(glob.glob(os.path.join(d, "*.png"))):
            pix = QPixmap(p)
            if not pix.isNull():
                pix = pix.scaled(int(pix.width() * scale), int(pix.height() * scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.frames.append(pix)
        if self.frames:
            self.image_label.setPixmap(self.frames[0])
            self.resize(self.frames[0].size())
            self.image_label.resize(self.frames[0].size())
        else:
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
        model_rel = prof.get('live2d_model', '')
        model_abs = os.path.join(base_path, model_rel)
        
        if not os.path.exists(model_abs):
            search_dir = os.path.dirname(model_abs)
            if not os.path.exists(search_dir):
                search_dir = base_path
            candidates = glob.glob(os.path.join(search_dir, "*.model3.json"))
            candidates = [c for c in candidates if "_temp_" not in c]
            if candidates:
                model_abs = candidates[0]
                model_rel = os.path.relpath(model_abs, base_path).replace("\\", "/")
                print(f"Configured model not found, falling back to: {model_rel}")

        m3_data = load_json(model_abs)
        if m3_data:
            m_dir = os.path.join(os.path.dirname(model_abs), "motions")
            if not os.path.exists(m_dir):
                m_dir = os.path.join(os.path.dirname(model_abs), "motions_extra")

            if os.path.exists(m_dir):
                m_refs = m3_data.get("FileReferences", {})
                if "Motions" not in m_refs:
                    m_refs["Motions"] = {}
                
                found_files = glob.glob(os.path.join(m_dir, "*.motion3.json"))
                for f in found_files:
                    m_name = os.path.basename(f).replace(".motion3.json", "")
                    if m_name not in m_refs["Motions"]:
                        rel_f = os.path.relpath(f, os.path.dirname(model_abs)).replace("\\", "/")
                        m_refs["Motions"][m_name] = [{"File": rel_f}]
                m3_data["FileReferences"] = m_refs
            
            temp_m3_path = os.path.join(os.path.dirname(model_abs), "_temp_model.json")
            save_json(temp_m3_path, m3_data)
            model_rel = os.path.relpath(temp_m3_path, base_path).replace("\\", "/")

        with open(WEB_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            html = f.read()
        
        web_dir = os.path.dirname(WEB_TEMPLATE_PATH).replace("\\", "/")
        html = html.replace('src="js/', f'src="{web_dir}/js/')
        
        scale = prof.get('live2d_scale', 1.0) * self.config['app'].get('scale', 1.0)
        offset = prof.get('live2d_offset_y', 0.0)
        
        encoded_rel = "/".join([quote(part) for part in model_rel.split("/")])

        html = html.replace('[[MODEL_PATH]]', encoded_rel)
        html = html.replace('[[MODEL_SCALE]]', str(scale))
        html = html.replace('[[MODEL_Y_OFFSET]]', str(offset))
        
        model_rel = prof.get('live2d_model', '')
        model_abs = os.path.join(base_path, model_rel).replace("\\", "/")
        
        scale = prof.get('live2d_scale', 1.0) * self.config['app'].get('scale', 1.0)
        offset = prof.get('live2d_offset_y', 0.0)
        
        html = html.replace('[[MODEL_PATH]]', model_rel)
        html = html.replace('[[MODEL_SCALE]]', str(scale))
        html = html.replace('[[MODEL_Y_OFFSET]]', str(offset))
        
        model_dir = os.path.dirname(model_abs)
        base_url = QUrl.fromLocalFile(model_dir + "/")
        
        model_filename = os.path.basename(model_rel)
        encoded_filename = quote(model_filename)
        
        html = html.replace(encoded_rel, encoded_filename)
        
        self.webview.setHtml(html, baseUrl=base_url)
        
        base_w, base_h = 300, 500
        g_scale = self.config['app'].get('scale', 1.0)
        self.resize(int(base_w * g_scale), int(base_h * g_scale))
        self.webview.resize(self.size())
        
        self.webview.ensure_filter_installed()

    def apply_config_system(self):
        self.timer.start(self.config['app'].get('refresh_rate', 100))
        self.update_mix_match(self.active_avatar, self.active_voice)

    def on_timer(self):
        if self.image_label.isVisible() and self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.image_label.setPixmap(self.frames[self.current_frame])
        
        if self.bubble.isVisible():
            self.bubble.reposition(self.get_head_pos())

    def get_head_pos(self):
        return self.mapToGlobal(QPoint(self.width() // 2, 0))

    def handle_mouse_press(self, e): 
        if e.button() == Qt.LeftButton: 
            self.is_dragging = True
            self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            if not self.chat_input.isVisible():
                if self.is_thinking_state:
                    self.talk_thinking()
                else:
                    self.talk_random()

    def talk_thinking(self):
        """在 LLM 思考时点击桌宠触发的趣味吐槽/抱怨互动，可适应所有角色"""
        self.restore_thinking_timer.stop()
        
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
        thinking_talks = self.config.get('interaction', {}).get('thinking_talk', default_thinking)
        
        # 显示 2.5 秒的可爱思考抱怨语录
        self.bubble.show_message(random.choice(thinking_talks), self.get_head_pos(), 2500)
        self.restore_thinking_timer.start(2500)

    def restore_thinking_bubble(self):
        """恢复 Thinking... 气泡显示"""
        if self.is_thinking_state:
            self.bubble.show_message("Thinking...", self.get_head_pos(), 60000)

    def handle_mouse_move(self, e):
        if self.is_dragging:
            self.move(e.globalPos() - self.drag_pos)

    def handle_mouse_release(self, e):
        self.is_dragging = False
        self.setCursor(Qt.ArrowCursor)

    def moveEvent(self, e):
        super().moveEvent(e)
        if hasattr(self, 'bubble') and self.bubble.isVisible():
            self.bubble.reposition(self.get_head_pos())

    def closeEvent(self, event):
        """主窗口关闭事件，安全释放所有后台工作线程与资源，防止程序退出挂死"""
        winsound.PlaySound(None, 0)
        self.audio_timer.stop()
        self.typewriter_timer.stop()
        
        if hasattr(self, 'llm_worker') and self.llm_worker and self.llm_worker.is_alive():
            self.llm_worker.abort()
        if hasattr(self, 'tts_queue_worker') and self.tts_queue_worker and self.tts_queue_worker.is_alive():
            self.tts_queue_worker.abort()
            
        self.cleanup_temp_audios()
        event.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.show_menu(e.globalPos())
        else:
            self.handle_mouse_press(e)

    def mouseMoveEvent(self, e):
        self.handle_mouse_move(e)

    def mouseReleaseEvent(self, e):
        self.handle_mouse_release(e)

    def show_menu(self, global_pos):
        m = QMenu(self)
        m.addAction("🗣 对话").triggered.connect(self.chat_input.show_input)
        
        if self.visual_profile.get('renderer') == 'live2d':
            motion_menu = m.addMenu("🎬 动作表演")
            motions = self.get_available_motions()
            if motions:
                for group in motions:
                    action = motion_menu.addAction(group)
                    action.triggered.connect(lambda checked, g=group: self.play_l2d_motion(g))
            else:
                motion_menu.addAction("无可用动作").setEnabled(False)

        m.addAction("⚙️ 控制台").triggered.connect(self.settings_window.show)
        m.addAction("退出").triggered.connect(QApplication.instance().quit)
        m.exec_(global_pos)

    def get_available_motions(self):
        try:
            char_path = os.path.join(CHAR_DIR, self.active_avatar)
            prof = self.visual_profile
            model_rel = prof.get('live2d_model', '')
            model_path = os.path.join(char_path, model_rel)
            
            if os.path.exists(model_path):
                data = load_json(model_path)
                motions_data = data.get("FileReferences", {}).get("Motions", {})
                if not motions_data:
                    motions_dir = os.path.join(os.path.dirname(model_path), "motions")
                    if os.path.exists(motions_dir):
                        files = glob.glob(os.path.join(motions_dir, "*.motion3.json"))
                        return [os.path.basename(f).replace(".motion3.json", "") for f in files]
                return list(motions_data.keys())
        except Exception as e:
            print(f"Error scanning motions: {e}")
        return []

    def play_l2d_motion(self, group):
        if hasattr(self, 'webview') and self.webview.isVisible():
            js_code = f"window.playMotion('{group}');"
            self.webview.page().runJavaScript(js_code)

    def cleanup_temp_audios(self):
        """清理本次对话产生的临时语音缓存文件，避免硬盘膨胀"""
        import glob
        from aipet.config import TEMP_AUDIO_DIR
        pattern = os.path.join(TEMP_AUDIO_DIR, "temp_speech_*.wav")
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except Exception:
                pass

    def process_chat(self, t):
        """用户提交对话主入口，支持中断上一次未完成的会话与音频"""
        # 1. 强行中止当前正在播放的音频、Live2D 口型动作以及所有定时器
        winsound.PlaySound(None, 0)
        self.audio_timer.stop()
        self.typewriter_timer.stop()
        self.restore_thinking_timer.stop()
        if self.visual_profile.get('renderer') == 'live2d' and hasattr(self, 'webview') and self.webview.isVisible():
            self.webview.page().runJavaScript("window.stopSpeaking();")

        # 2. 安全中止并销毁仍在运行的流式 LLM 或 TTS 工作线程
        if hasattr(self, 'llm_worker') and self.llm_worker and self.llm_worker.is_alive():
            self.llm_worker.abort()
        if hasattr(self, 'tts_queue_worker') and self.tts_queue_worker and self.tts_queue_worker.is_alive():
            self.tts_queue_worker.abort()

        # 3. 清理上一轮生成的临时音频
        self.cleanup_temp_audios()

        # 4. 初始化本轮放音队列状态、打字机变量与流式累计缓存
        self.synthesized_audio.clear()
        self.next_play_index = 0
        self.is_playing_audio = False
        self.accumulated_chat_text = ""
        self.displayed_history_text = ""
        self.typewriter_text = ""
        self.typewriter_current_len = 0
        self.is_thinking_state = True
        
        # 气泡显示 Thinking 状态
        self.bubble.show_message("Thinking...", self.get_head_pos(), 60000)

        # 5. 追加用户提问至记忆上下文
        self.chat_history.append({"role": "user", "content": t})
        if len(self.chat_history) > self.max_history_len * 2:
            self.chat_history = self.chat_history[-self.max_history_len * 2:]

        prompt = self.visual_profile.get('system_prompt', '')
        key = self.config['llm'].get('api_key', '')
        url = self.config['llm'].get('base_url', '')
        model = self.config['llm'].get('model', '')

        # 6. 启动流式大语言模型 Worker
        self.llm_worker = LLMWorker(t, prompt, self.chat_history, key, url, model, self.signals)
        self.llm_worker.start()

        # 7. 如果开启了 TTS 语音合成，则并行拉起顺序 TTS 队列合成器
        enable_tts = self.config['app'].get('enable_tts', True)
        if enable_tts:
            ref_audio = self.voice_profile.get('ref_audio')
            voice_base_path = self.voice_profile.get('_base_path')
            prompt_text = self.voice_profile.get('prompt_text', '')
            prompt_lang = self.voice_profile.get('prompt_lang', 'zh')
            text_lang = self.voice_profile.get('text_lang', 'zh')
            
            # 读取发音配置文件参数，保持平滑向后兼容
            voice_mode = self.voice_full_profile.get('voice_mode')
            rvc_cfg = self.voice_full_profile.get('rvc', {})
            rvc_enable = rvc_cfg.get('enable', False)
            if not voice_mode:
                voice_mode = 'rvc' if rvc_enable else 'gpt_sovits'
                
            # 加载 GPT-SoVITS 专属推理模型与参数
            gsv_cfg = self.voice_full_profile.get('gpt_sovits', {})
            gpt_ckpt = gsv_cfg.get('ckpt', '')
            sovits_pth = gsv_cfg.get('pth', '')
            gpt_version = gsv_cfg.get('version', 'v2')
            temperature = gsv_cfg.get('temperature', 0.4)
            
            gpt_ckpt_abs = os.path.join(voice_base_path, gpt_ckpt) if gpt_ckpt else ""
            sovits_pth_abs = os.path.join(voice_base_path, sovits_pth) if sovits_pth else ""
            ref_audio_abs = os.path.join(voice_base_path, ref_audio) if ref_audio else ""
            
            # 提取 RVC 参数与 Hubert 基础特征模型文件绝对路径
            rvc_pth = rvc_cfg.get('pth', '')
            rvc_index = rvc_cfg.get('index', '')
            f0_up_key = rvc_cfg.get('f0_up_key', 0)
            f0_method = rvc_cfg.get('f0_method', 'harvest')
            index_rate = rvc_cfg.get('index_rate', 0.75)
            rms_mix_rate = rvc_cfg.get('rms_mix_rate', 0.25)
            protect = rvc_cfg.get('protect', 0.33)
            
            from aipet.config import BASE_DIR
            hubert_path = os.path.join(BASE_DIR, "resources", "models", "hubert_base_state.pt")
            
            self.tts_queue_worker = TTSQueueWorker(
                enable_tts=enable_tts,
                signals=self.signals,
                voice_mode=voice_mode,
                ref_audio_path=ref_audio_abs,
                prompt_text=prompt_text,
                prompt_lang=prompt_lang,
                text_lang=text_lang,
                gpt_ckpt_path=gpt_ckpt_abs,
                sovits_pth_path=sovits_pth_abs,
                gpt_sovits_version=gpt_version,
                voice_base_path=voice_base_path,
                rvc_pth=rvc_pth,
                rvc_index=rvc_index,
                hubert_path=hubert_path,
                f0_up_key=f0_up_key,
                f0_method=f0_method,
                index_rate=index_rate,
                rms_mix_rate=rms_mix_rate,
                protect=protect,
                temperature=temperature
            )
            self.tts_queue_worker.start()

    def on_chat_chunk(self, chunk):
        """流式字符片段接收槽"""
        self.accumulated_chat_text += chunk
        
        # 仅在未开启 TTS (静音模式) 时才在 LLM 流式返回时实时更新气泡，因为有声模式由播放驱动打字
        enable_tts = self.config['app'].get('enable_tts', True)
        if not enable_tts:
            self.is_thinking_state = False
            self.restore_thinking_timer.stop()
            self.bubble.update_text(self.accumulated_chat_text, self.get_head_pos())

    def on_sentence_ready(self, index, text):
        """分句就绪后推送给后台 TTS 队列合成线程"""
        if hasattr(self, 'tts_queue_worker') and self.tts_queue_worker and self.tts_queue_worker.is_alive():
            self.tts_queue_worker.add_task(index, text)

    def on_tts_sentence_finished(self, index, wav_path, text):
        """单句音频合成完毕回调，载入缓存并触发队列放音"""
        if wav_path and os.path.exists(wav_path):
            self.synthesized_audio[index] = (wav_path, text)
        else:
            # 兼容处理：若合成出错则存空占位，防止索引缺失卡死播放链
            self.synthesized_audio[index] = ("", text)
        self.check_playback_queue()

    def check_playback_queue(self):
        """核心播放队列调度逻辑：严格按 index 顺序同步放音与打字机效果"""
        if self.is_playing_audio:
            return

        if self.next_play_index in self.synthesized_audio:
            wav_path, text = self.synthesized_audio[self.next_play_index]
            self.next_play_index += 1

            # 若此句音频为空（合成失败），则跳过放音直接递归播放下一句
            if not wav_path or not os.path.exists(wav_path):
                self.check_playback_queue()
                return

            self.is_playing_audio = True
            
            # 进入放音阶段，解除思考状态并停止恢复定时器
            self.is_thinking_state = False
            self.restore_thinking_timer.stop()
            
            # 1. 计算本句音频的精确时长
            duration = 3000
            try:
                import contextlib
                import wave
                with contextlib.closing(wave.open(wav_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = int((frames / float(rate)) * 1000)
            except Exception as e:
                print(f"Error calculating wav duration: {e}")

            # 2. 初始化打字机状态，并启动打字机定时器
            self.typewriter_text = text
            self.typewriter_current_len = 0
            
            # 动态计算打字间隔：根据音频时长除以文字长度，使打字速率与说话速率完美吻合
            char_count = len(text) if len(text) > 0 else 1
            # 限制打字间隔在 50ms 到 250ms 之间，防止过快或过慢，确保文字打印清晰好读
            char_delay = max(50, min(250, int(duration / char_count)))
            self.typewriter_timer.start(char_delay)

            # 3. 触发 Live2D 口型动画
            if self.visual_profile.get('renderer') == 'live2d' and hasattr(self, 'webview') and self.webview.isVisible():
                self.webview.page().runJavaScript("window.startSpeaking();")

            # 4. 异步播放音频并设定单句结束计时器 (添加 300ms 停顿缓冲)
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.audio_timer.start(duration + 300)

    def on_typewriter_step(self):
        """打字机步进回调，逐字打印当前正在播放音频的文本"""
        if self.typewriter_current_len < len(self.typewriter_text):
            self.typewriter_current_len += 1
            current_chunk = self.typewriter_text[:self.typewriter_current_len]
            
            chat_mode = self.config['app'].get('chat_mode', 'subtitle')
            if chat_mode == 'typewriter':
                # 打字机追加模式：展现已播放完的文本历史 + 当前句的打印增量
                text_to_show = self.displayed_history_text + current_chunk
            else:
                # 字幕同步模式：仅展现当前句的打印增量
                text_to_show = current_chunk
                
            self.bubble.update_text(text_to_show, self.get_head_pos())
        else:
            self.typewriter_timer.stop()

    def on_audio_finished(self):
        """单句音频播放定时完毕回调"""
        self.is_playing_audio = False
        self.typewriter_timer.stop()
        
        # 将当前句全文字并入已播放历史
        self.displayed_history_text += self.typewriter_text
        
        # 1. 停止 Live2D 说话动画
        if self.visual_profile.get('renderer') == 'live2d' and hasattr(self, 'webview') and self.webview.isVisible():
            self.webview.page().runJavaScript("window.stopSpeaking();")

        # 2. 检查是否为最后一讲，若已无待合成/待播放项，重置气泡自动隐藏倒计时
        if self.next_play_index not in self.synthesized_audio:
            self.bubble.timer.start(3000) # 3秒后隐去气泡
            
        # 3. 递归读取下一句放音
        self.check_playback_queue()

    def on_chat(self, t):
        """流式大模型生成全文本结束回调，用于保存对话历史"""
        self.current_response_text = t
        
        self.chat_history.append({"role": "assistant", "content": t})
        if len(self.chat_history) > self.max_history_len * 2:
            self.chat_history = self.chat_history[-self.max_history_len * 2:]
            
        # 静音模式下，由于无法触发 check_playback_queue 放音驱动，在这里执行最终隐退倒计时
        enable_tts = self.config['app'].get('enable_tts', True)
        if not enable_tts:
            duration = max(3000, len(t) * 200)
            self.bubble.show_message(t, self.get_head_pos(), duration)

    def on_tts(self, p):
        # 兼容旧单音合成回调，当前已被流式分句播放队列接管
        pass
    
    def load_audio_pool(self): 
        self.audio_files = []

    def talk_random(self):
        d = self.config.get('interaction', {}).get('random_talk', ["Hi~"])
        self.bubble.show_message(random.choice(d), self.get_head_pos())
