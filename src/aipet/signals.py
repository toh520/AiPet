from PyQt5.QtCore import QObject, pyqtSignal

class WorkerSignals(QObject):
    chat_finished = pyqtSignal(str)
    tts_finished = pyqtSignal(str)
    
    # --- 流式交互与分句音频队列新增信号 ---
    chat_chunk = pyqtSignal(str)                     # 流式文字块增量信号
    sentence_ready = pyqtSignal(int, str)             # 分句就绪信号 (index, sentence_text)
    tts_sentence_finished = pyqtSignal(int, str, str) # 单句 TTS 合成完成信号 (index, wav_path, sentence_text)

