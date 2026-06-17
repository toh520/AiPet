import threading
import requests
import json
from aipet.signals import WorkerSignals

class SentenceSplitter:
    """实时文本分句器，在接收流式文本时动态按句尾标点切分出完整的句子"""
    def __init__(self):
        self.buffer = ""
        # 常见的中英文句尾结束符，包含换行
        self.delimiters = {'。', '！', '？', '；', '\n', '!', '?', ';'}

    def feed(self, text):
        """输入新增的文本片段，返回切分出的完整句子列表"""
        sentences = []
        self.buffer += text
        start = 0
        for i, char in enumerate(self.buffer):
            if char in self.delimiters:
                sentence = self.buffer[start:i+1].strip()
                if sentence:
                    sentences.append(sentence)
                start = i + 1
        self.buffer = self.buffer[start:]
        return sentences

    def flush(self):
        """流结束时，强制输出 buffer 中剩余的所有文本"""
        sentence = self.buffer.strip()
        self.buffer = ""
        if sentence:
            return [sentence]
        return []

class LLMWorker(threading.Thread):
    def __init__(self, text, prompt, chat_history, key, url, model, signals: WorkerSignals):
        super().__init__(daemon=True)
        self.text = text
        self.prompt = prompt
        self.chat_history = chat_history.copy() if chat_history else []
        self.key = key
        self.url = url
        self.model = model
        self.signals = signals
        self._is_aborted = False # 支持在运行中途打断

    def abort(self):
        """打断标志位设置"""
        self._is_aborted = True

    def run(self):
        print(f"[DEBUG] Starting streaming chat thread with input: {repr(self.text)}")
        print(f"[DEBUG] Config - Key: {'Set' if self.key else 'None'}, URL: {self.url}, Model: {self.model}")
        
        if not self.key:
            self.signals.chat_finished.emit("大脑配置错误，请在控制台设置 API Key")
            return
            
        try:
            # 构建消息上下文
            messages = [{"role": "system", "content": self.prompt}]
            messages.extend(self.chat_history)
            messages.append({"role": "user", "content": self.text})
            
            print(f"[DEBUG] Sending streaming request to LLM...")

            r = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.key}"},
                json={"model": self.model, "messages": messages, "stream": True},
                timeout=60, 
                proxies={"http": None, "https": None},
                stream=True
            )
            print(f"[DEBUG] Response Status Code: {r.status_code}")
            
            if r.status_code != 200:
                self.signals.chat_finished.emit(f"大脑出错啦，状态码: {r.status_code}")
                return

            splitter = SentenceSplitter()
            sentence_index = 0
            accumulated_text = ""
            emitted_text = ""
            
            # 按行解析 SSE (Server-Sent Events) 流数据
            for line in r.iter_lines():
                if self._is_aborted:
                    print("[DEBUG] LLMWorker aborted mid-stream.")
                    return
                    
                if not line:
                    continue
                decoded_line = line.decode('utf-8').strip()
                if not decoded_line.startswith("data: "):
                    continue
                
                data_str = decoded_line[6:]
                if data_str == "[DONE]":
                    break
                
                try:
                    data_json = json.loads(data_str)
                    delta = data_json['choices'][0]['delta']
                    if 'content' in delta:
                        chunk = delta['content']
                        accumulated_text += chunk
                        
                        # 过滤 DeepSeek R1 的 <think> 思考内容
                        clean_text = accumulated_text.lstrip()
                        if clean_text.startswith("<think>"):
                            if "</think>" in clean_text:
                                # 提取思维链结束后的实际回答部分
                                actual_content = clean_text.split("</think>", 1)[1]
                                # 获取最新增量并流式发送
                                new_chars = actual_content[len(emitted_text):]
                                if new_chars:
                                    emitted_text += new_chars
                                    self.signals.chat_chunk.emit(new_chars)
                                    sentences = splitter.feed(new_chars)
                                    for sentence in sentences:
                                        self.signals.sentence_ready.emit(sentence_index, sentence)
                                        sentence_index += 1
                        else:
                            # 正常非推理模型直接输出
                            new_chars = accumulated_text[len(emitted_text):]
                            if new_chars:
                                emitted_text += new_chars
                                self.signals.chat_chunk.emit(new_chars)
                                sentences = splitter.feed(new_chars)
                                for sentence in sentences:
                                    self.signals.sentence_ready.emit(sentence_index, sentence)
                                    sentence_index += 1
                except Exception:
                    pass

            # 流式结束，清洗分句器缓存
            remaining = splitter.flush()
            for sentence in remaining:
                if self._is_aborted:
                    return
                self.signals.sentence_ready.emit(sentence_index, sentence)
                sentence_index += 1
                
            final_resp = emitted_text.strip()
            if not final_resp:
                final_resp = "刚刚在发呆，请重新尝试"
                self.signals.chat_chunk.emit(final_resp)
                self.signals.sentence_ready.emit(sentence_index, final_resp)
                
            print(f"[DEBUG] Streaming LLM finished. Final response: {repr(final_resp)}")
            self.signals.chat_finished.emit(final_resp)

        except Exception as e:
            print(f"LLM Stream Error: {e}")
            self.signals.chat_finished.emit(f"大脑出错啦: {e}")

