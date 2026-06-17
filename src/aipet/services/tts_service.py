import os
import re
import asyncio
import shutil
import threading
import edge_tts
from aipet.signals import WorkerSignals

class TextCleaner:
    """发音文本前端清洗与正则化器，防止自回归 TTS 在遇到非标符号/数字时喷射电音噪波"""
    
    # 匹配各类无发音意义的颜表情与特殊符号
    EMOJI_PATTERN = re.compile(
        r'(?i)(?:[pQoO0D]-?[pQoO0D]|QwQ|QAQ|OwO|orz|O\(∩_∩\)O|Qvq|OvO|QAQ|XD|=[D3]|T_T|\^_\^|\(╯°□°\)╯︵ ┻━┻|:\)|:\(|:-D)'
    )
    
    @classmethod
    def num_to_chinese(cls, num_str):
        """将数字字符串翻译成中文读音字串"""
        # 如果正好是 4 位纯数字，则按年份或者电话单字直译（如 2026 -> 二零二六）
        if len(num_str) == 4 and num_str.isdigit():
            digits = "零一二三四五六七八九"
            return "".join(digits[int(d)] for d in num_str)
            
        # 其他普通整数，按权位转换（支持最大万亿级）
        try:
            val = int(num_str)
            if val == 0:
                return "零"
            
            units = ["", "十", "百", "千"]
            sections = ["", "万", "亿", "万亿"]
            digits = "零一二三四五六七八九"
            
            def section_to_chinese(section_val):
                section_str = ""
                zero_flag = False
                unit_idx = 0
                temp = section_val
                while temp > 0:
                    d = temp % 10
                    if d == 0:
                        if not zero_flag and section_str != "":
                            zero_flag = True
                            section_str = digits[0] + section_str
                    else:
                        zero_flag = False
                        section_str = digits[d] + units[unit_idx] + section_str
                    unit_idx += 1
                    temp //= 10
                # 修正口语习惯：如“一十”直接读作“十”
                if section_str.startswith("一十"):
                    section_str = section_str[1:]
                return section_str

            ans = ""
            sec_idx = 0
            temp = val
            while temp > 0:
                sec = temp % 10000
                if sec > 0:
                    sec_str = section_to_chinese(sec)
                    ans = sec_str + sections[sec_idx] + ans
                elif temp > 10000:
                    # 补零
                    if not ans.startswith("零"):
                        ans = "零" + ans
                sec_idx += 1
                temp //= 10000
            
            return ans
        except ValueError:
            # 转换失败则退回单字直译
            digits = "零一二三四五六七八九"
            return "".join(digits[int(d)] if d.isdigit() else d for d in num_str)

    @classmethod
    def clean(cls, text):
        if not text:
            return ""
            
        # 1. 净化常见无括号的纯文本颜表情
        text = cls.EMOJI_PATTERN.sub("", text)
        
        # 2. 彻底清除各类括号/特殊包围符号及其内部的文本（防止读出动作指令、非标表情包或舞台提示）
        text = re.sub(r'\([^)]*\)', '', text)        # 英文括号 ()
        text = re.sub(r'（[^）]*）', '', text)        # 中文括号 （）
        text = re.sub(r'\[[^\]]*\]', '', text)        # 英文中括号 []
        text = re.sub(r'［[^］]*］', '', text)        # 中文中括号 ［］
        text = re.sub(r'\{[^}]*\}', '', text)        # 花括号 {}
        text = re.sub(r'【[^】]*】', '', text)        # 中文粗括号 【】
        text = re.sub(r'<[^>]*>', '', text)          # 尖括号 <>
        text = re.sub(r'\|[^|]*\|', '', text)        # 竖线括号 ||
        text = re.sub(r'\*[^*]*\*', '', text)        # 星号 * * (如 *笑* 或 *giggles*)
        
        # 3. 剥离书名号，但保留书名号内部的文字内容以确保书名正常发音
        text = re.sub(r'《([^》]*)》', r'\1', text)
        
        # 4. 规范化语气拉长符（波浪号）与分隔符（斜杠、反斜杠、竖线），转换为逗号以提供自然的停顿
        text = re.sub(r'[~～]+', '，', text)
        text = re.sub(r'[\\/|]+', '，', text)
        
        # 5. 将阿拉伯数字字符串整体正则化转译为汉字
        text = re.sub(r'\d+', lambda m: cls.num_to_chinese(m.group(0)), text)
        
        # 6. 白名单字符过滤：只保留中日文字符、英文字母、数字、标准中英文标点、空格，剔除其余乱码、特殊数学符号及修饰音标字符
        # 允许字符范围：汉字 \u4e00-\u9fa5，平假名 \u3040-\u309f，片假名 \u30a0-\u30ff
        # 标点符号：，。！？、：； (中文)  ,.!?:;- (英文)  \s (空格/换行)
        allowed_pattern = re.compile(
            r'[^\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9，。！？、：；,\.\!\?\:\;\-\s]'
        )
        text = allowed_pattern.sub('', text)
        
        # 7. 合并连续空格与重复标点
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'，+', '，', text)
        text = re.sub(r'。+', '。', text)
        text = re.sub(r'！+', '！', text)
        text = re.sub(r'？+', '？', text)
        
        # 8. 解决标点叠加冲突，强标点（。！？）覆盖弱标点（，、）
        text = re.sub(r'[，、]+([。！？])', r'\1', text)
        text = re.sub(r'([。！？])[，、]+', r'\1', text)
        
        # 9. 去除首尾的空白字符与无意义的前导/尾随弱标点
        text = text.strip(' ，、, \t\r\n')
        
        return text

class TTSWorker(threading.Thread):
    def __init__(self, text, enable_tts, temp_audio_path, signals: WorkerSignals,
                 voice_mode="gpt_sovits", ref_audio_path=None, prompt_text=None, prompt_lang="zh", text_lang="zh",
                 gpt_ckpt_path=None, sovits_pth_path=None, gpt_sovits_version="v2",
                 voice_base_path=None, rvc_pth=None, rvc_index=None, hubert_path=None,
                 f0_up_key=0, f0_method="harvest", index_rate=0.75, rms_mix_rate=0.25, protect=0.33,
                 temperature=0.4):
        """
        三引擎自适应混合语音合成工作线程。
        支持本地 GPT-SoVITS 零样本/微调合成、Edge-TTS + RVC 高阶变声、以及纯 Edge-TTS 播报。
        """
        super().__init__(daemon=True)
        self.text = text
        self.enable_tts = enable_tts
        self.temp_audio_path = temp_audio_path
        self.signals = signals
        
        # 发音模式与 GPT-SoVITS 参数
        self.voice_mode = voice_mode
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text
        self.prompt_lang = prompt_lang
        self.text_lang = text_lang
        self.gpt_ckpt_path = gpt_ckpt_path
        self.sovits_pth_path = sovits_pth_path
        self.gpt_sovits_version = gpt_sovits_version
        self.temperature = temperature # 保存自回归推理采样温度
        
        # RVC 高音质变声参数
        self.voice_base_path = voice_base_path
        self.rvc_pth = rvc_pth
        self.rvc_index = rvc_index
        self.hubert_path = hubert_path
        self.f0_up_key = f0_up_key
        self.f0_method = f0_method
        self.index_rate = index_rate
        self.rms_mix_rate = rms_mix_rate
        self.protect = protect

    def run(self):
        if not self.enable_tts:
            return
        if not self.text or not self.text.strip():
            return

        # 在发音引擎合成的最开头执行文本过滤正则化清洗
        self.text = TextCleaner.clean(self.text)
        if not self.text or not self.text.strip():
            return

        print(f"[TTSWorker] 启动语音合成 (模式: {self.voice_mode})")
        
        # 1. 尝试使用 GPT-SoVITS 本地直接合成模式
        if self.voice_mode == "gpt_sovits":
            try:
                # 检查参考音频是否存在（零样本克隆和微调模式均必需）
                if self.ref_audio_path and os.path.exists(self.ref_audio_path):
                    # 动态注入 Windows DLL 路径防止 Python 3.14 下 torch 载入异常
                    if os.name == 'nt':
                        import site
                        for p in site.getsitepackages():
                            torch_lib = os.path.join(p, "torch", "lib")
                            if os.path.exists(torch_lib):
                                try:
                                    os.add_dll_directory(torch_lib)
                                except Exception:
                                    pass
                    
                    from aipet.services.gpt_sovits import gpt_sovits_convert
                    
                    # 执行本地两阶段 CPU 推理
                    gpt_sovits_convert(
                        text=self.text,
                        text_lang=self.text_lang,
                        ref_wav_path=self.ref_audio_path,
                        prompt_text=self.prompt_text,
                        prompt_lang=self.prompt_lang,
                        output_wav_path=self.temp_audio_path,
                        gpt_ckpt_path=self.gpt_ckpt_path,
                        sovits_pth_path=self.sovits_pth_path,
                        version=self.gpt_sovits_version,
                        device="cpu",
                        temperature=self.temperature # 注入自定义的推理温度以过滤高频随机电流声
                    )
                    self.signals.tts_finished.emit(self.temp_audio_path)
                    return
                else:
                    print(f"[Warning] GPT-SoVITS 参考音频不存在或未设置: {self.ref_audio_path}。将安全降级至 Edge-TTS 模式。")
            except Exception as e:
                print(f"[Warning] GPT-SoVITS 本地直接合成失败: {e}。将安全降级至 Edge-TTS 模式。")
                import traceback
                traceback.print_exc()

        # 临时存储 edge-tts 合成的普通人声文件
        temp_raw_path = self.temp_audio_path + ".raw.wav"

        # 2. 调度普通 Edge-TTS 或是级联 RVC 变声模式
        try:
            # 执行异步 edge-tts 语音合成（默认采用微软高清女声 Xiaoxiao）
            async def run_edge_tts():
                communicate = edge_tts.Communicate(self.text, "zh-CN-XiaoxiaoNeural")
                await communicate.save(temp_raw_path)
                
            asyncio.run(run_edge_tts())
            
            # 兼容性转换：由于 edge-tts 默认仅生成 MP3 格式音频流
            # 我们通过 load_audio 读入并用 soundfile 重新以标准 PCM_16 WAV 格式保存，避免播放器由于没有 RIFF 头部标识报错
            if os.path.exists(temp_raw_path):
                from aipet.services.rvc.audio import load_audio
                import soundfile as sf
                raw_wav_data = load_audio(temp_raw_path, 24000)
                sf.write(temp_raw_path, raw_wav_data, 24000, format="wav", subtype="PCM_16")
            
            # 判断是否需要进行 RVC 胡桃音色转换（自适应模式二）
            if self.voice_mode == "rvc" and self.rvc_pth and self.voice_base_path and self.hubert_path:
                pth_abs = os.path.join(self.voice_base_path, self.rvc_pth)
                index_abs = os.path.join(self.voice_base_path, self.rvc_index) if self.rvc_index else ""
                
                if os.path.exists(pth_abs) and os.path.exists(self.hubert_path):
                    from aipet.services.rvc import rvc_convert
                    # 执行 CPU 轻量化 RVC 推理（使用 harvest 基频提取）
                    rvc_convert(
                        model_path=pth_abs,
                        index_path=index_abs,
                        hubert_path=self.hubert_path,
                        input_wav_path=temp_raw_path,
                        output_wav_path=self.temp_audio_path,
                        f0_up_key=self.f0_up_key,
                        f0_method=self.f0_method,
                        index_rate=self.index_rate,
                        rms_mix_rate=self.rms_mix_rate,
                        protect=self.protect
                    )
                    self.signals.tts_finished.emit(self.temp_audio_path)
                else:
                    print("[Warning] RVC pth 或 hubert 基础模型不存在。降级使用普通 TTS 发音。")
                    shutil.copy(temp_raw_path, self.temp_audio_path)
                    self.signals.tts_finished.emit(self.temp_audio_path)
            else:
                # 模式三：纯 Edge-TTS 发音，直接复制输出
                shutil.copy(temp_raw_path, self.temp_audio_path)
                self.signals.tts_finished.emit(self.temp_audio_path)
                
        except Exception as e:
            print(f"Edge-TTS / RVC 语音合成错误: {e}")
            if os.path.exists(temp_raw_path):
                shutil.copy(temp_raw_path, self.temp_audio_path)
                self.signals.tts_finished.emit(self.temp_audio_path)
        finally:
            if os.path.exists(temp_raw_path):
                try:
                    os.remove(temp_raw_path)
                except:
                    pass

import queue

class TTSQueueWorker(threading.Thread):
    """顺序音频流式合成队列工作线程，从队列中逐句获取文本并进行语音合成，支持安全中止打断"""
    def __init__(self, enable_tts, signals: WorkerSignals,
                 voice_mode="gpt_sovits", ref_audio_path=None, prompt_text=None, prompt_lang="zh", text_lang="zh",
                 gpt_ckpt_path=None, sovits_pth_path=None, gpt_sovits_version="v2",
                 voice_base_path=None, rvc_pth=None, rvc_index=None, hubert_path=None,
                 f0_up_key=0, f0_method="harvest", index_rate=0.75, rms_mix_rate=0.25, protect=0.33,
                 temperature=0.4):
        super().__init__(daemon=True)
        self.enable_tts = enable_tts
        self.signals = signals
        self.voice_mode = voice_mode
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text
        self.prompt_lang = prompt_lang
        self.text_lang = text_lang
        self.gpt_ckpt_path = gpt_ckpt_path
        self.sovits_pth_path = sovits_pth_path
        self.gpt_sovits_version = gpt_sovits_version
        self.voice_base_path = voice_base_path
        self.rvc_pth = rvc_pth
        self.rvc_index = rvc_index
        self.hubert_path = hubert_path
        self.f0_up_key = f0_up_key
        self.f0_method = f0_method
        self.index_rate = index_rate
        self.rms_mix_rate = rms_mix_rate
        self.protect = protect
        self.temperature = temperature
        
        self.task_queue = queue.Queue()
        self.running = True
        self._is_aborted = False

    def add_task(self, index, text):
        """向任务队列添加分句文本"""
        if not self._is_aborted:
            self.task_queue.put((index, text))

    def abort(self):
        """打断清空队列并退出"""
        self._is_aborted = True
        self.running = False
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
        self.task_queue.put((None, None)) # 毒丸唤醒

    def run(self):
        if not self.enable_tts:
            return

        while self.running:
            index, raw_text = self.task_queue.get()
            if index is None or not self.running or self._is_aborted:
                break
                
            clean_text = TextCleaner.clean(raw_text)
            if not clean_text or not clean_text.strip():
                # 空白文本直接发送完成信号以推进播放队列
                self.signals.tts_sentence_finished.emit(index, "", "")
                continue

            from aipet.config import TEMP_AUDIO_DIR
            out_wav_path = os.path.join(TEMP_AUDIO_DIR, f"temp_speech_{index}.wav")
            print(f"[TTSQueueWorker] 正在合成句段 [{index}]: {repr(clean_text)}")
            success = False
            
            # 1. 尝试使用 GPT-SoVITS 本地直接合成模式
            if self.voice_mode == "gpt_sovits":
                try:
                    if self.ref_audio_path and os.path.exists(self.ref_audio_path):
                        if os.name == 'nt':
                            import site
                            for p in site.getsitepackages():
                                torch_lib = os.path.join(p, "torch", "lib")
                                if os.path.exists(torch_lib):
                                    try:
                                        os.add_dll_directory(torch_lib)
                                    except Exception:
                                        pass
                        
                        from aipet.services.gpt_sovits import gpt_sovits_convert
                        gpt_sovits_convert(
                            text=clean_text,
                            text_lang=self.text_lang,
                            ref_wav_path=self.ref_audio_path,
                            prompt_text=self.prompt_text,
                            prompt_lang=self.prompt_lang,
                            output_wav_path=out_wav_path,
                            gpt_ckpt_path=self.gpt_ckpt_path,
                            sovits_pth_path=self.sovits_pth_path,
                            version=self.gpt_sovits_version,
                            device="cpu",
                            temperature=self.temperature
                        )
                        success = True
                    else:
                        print(f"[Warning] GPT-SoVITS 缺失参考音频. 降级使用 Edge-TTS.")
                except Exception as e:
                    print(f"[Warning] GPT-SoVITS 合成失败: {e}. 降级使用 Edge-TTS.")
            
            # 2. 调度普通 Edge-TTS 或是级联 RVC 变声模式
            if not success:
                temp_raw_path = out_wav_path + ".raw.wav"
                try:
                    async def run_edge_tts():
                        import edge_tts
                        communicate = edge_tts.Communicate(clean_text, "zh-CN-XiaoxiaoNeural")
                        await communicate.save(temp_raw_path)
                    
                    import asyncio
                    asyncio.run(run_edge_tts())
                    
                    if os.path.exists(temp_raw_path):
                        from aipet.services.rvc.audio import load_audio
                        import soundfile as sf
                        raw_wav_data = load_audio(temp_raw_path, 24000)
                        sf.write(temp_raw_path, raw_wav_data, 24000, format="wav", subtype="PCM_16")
                        
                        if self.voice_mode == "rvc" and self.rvc_pth and self.voice_base_path and self.hubert_path:
                            pth_abs = os.path.join(self.voice_base_path, self.rvc_pth)
                            index_abs = os.path.join(self.voice_base_path, self.rvc_index) if self.rvc_index else ""
                            
                            if os.path.exists(pth_abs) and os.path.exists(self.hubert_path):
                                from aipet.services.rvc import rvc_convert
                                rvc_convert(
                                    model_path=pth_abs,
                                    index_path=index_abs,
                                    hubert_path=self.hubert_path,
                                    input_wav_path=temp_raw_path,
                                    output_wav_path=out_wav_path,
                                    f0_up_key=self.f0_up_key,
                                    f0_method=self.f0_method,
                                    index_rate=self.index_rate,
                                    rms_mix_rate=self.rms_mix_rate,
                                    protect=self.protect
                                )
                                success = True
                            else:
                                print("[Warning] RVC pth 或 hubert 基础模型不存在。")
                                shutil.copy(temp_raw_path, out_wav_path)
                                success = True
                        else:
                            shutil.copy(temp_raw_path, out_wav_path)
                            success = True
                except Exception as e:
                    print(f"Edge-TTS / RVC 语音合成错误: {e}")
                finally:
                    if os.path.exists(temp_raw_path):
                        try:
                            os.remove(temp_raw_path)
                        except:
                            pass
            
            if success and os.path.exists(out_wav_path) and not self._is_aborted:
                self.signals.tts_sentence_finished.emit(index, out_wav_path, raw_text)
            else:
                self.signals.tts_sentence_finished.emit(index, "", "")


