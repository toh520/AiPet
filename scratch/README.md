# 🛠️ 语音底模脱水工具 (ContentVec Model Dehydrator)

本目录包含用于本地开发、调试以及模型优化的辅助脚本。其中，`extract_contentvec.py` 是本桌宠项目能够实现 **“免安装重型 fairseq 依赖库”** 本地加载的关键工具。

---

## 📄 脚本介绍：`extract_contentvec.py`

### 1. 背景与痛点
官方原版的 ContentVec 语音特征提取底模（`hubert_base_state.pt`）在保存时，序列化了 Facebook 的 `fairseq` 框架中的各种 Python 类定义。
如果在加载该模型时本地没有安装完整的 `fairseq` 及其 C 编译依赖，PyTorch 会报错 `ModuleNotFoundError: No module named 'fairseq'` 并拒绝加载。而 `fairseq` 库体积大、在 Windows 下极难成功编译和安装。

### 2. 解决方案（脱水原理）
`extract_contentvec.py` 内部通过注册一个高度自适应的 **Mock 元类 (MetaMock)**：
* 在反序列化模型时，动态拦截并伪造 `fairseq` 的命名空间，从而在不安装 `fairseq` 的情况下顺利绕过反序列化校验。
* 成功读取模型后，剥离掉只在训练时用到的冗余梯度和权重字段，只提取纯粹的 `state_dict` 神经网络核心参数。
* 将提取后的参数以 **纯 PyTorch 权重格式** 重新保存并覆盖原文件。

通过这种“脱水”处理，新生成的 `hubert_base_state.pt` 将成为 100% 干净的参数字典，可以在任意仅安装了 `torch` 的轻量级环境下用 `torch.load` 直接秒级加载。

---

## 🚀 使用指南

当你或其他开发者克隆了本源码，并下载了基础模型后，可以按照以下步骤对模型进行脱水处理：

### 步骤 1：下载官方底模
1. 下载原始的 `hubert_base_state.pt` 模型（约 378MB）。
2. 将下载好的模型放置在项目根目录下的特定位置：
   `resources/models/hubert_base_state.pt`

### 步骤 2：运行脱水脚本
在项目根目录下打开终端，确保你的虚拟环境已激活并安装了 `torch`，然后运行：
```bash
python scratch/extract_contentvec.py
```

### 步骤 3：验证输出
控制台输出如下内容即代表成功：
```text
[*] 正在加载并反序列化 ContentVec 模型: ./resources/models/hubert_base_state.pt
[*] 成功识别到 'model' 参数键，正在剥离非必要字段...
[*] 已过滤冗余字段: mask_emb
[*] 已过滤冗余字段: label_embs_concat
[*] 正在重新保存为纯净参数文件至: ./resources/models/hubert_base_state.pt
[+] 恭喜！ContentVec 权重“脱水”提取完成，已完全剥离所有 fairseq 依赖！
```
此时，你的 `hubert_base_state.pt` 已经在原地完成了转换，项目运行时将自动兼容，且从此摆脱对 `fairseq` 依赖的束缚。

---

## ⚠️ 注意事项
* **测试生成物**：本目录下的测试运行可能会产生 `out_sovits.wav` 或 `out_rvc.wav` 等音频文件，这些临时生成物已被配置在 Git 忽略规则中，不会被提交。
