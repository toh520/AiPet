# AiPet 🐾 - 基于 PyQt5 与多模态 AI 驱动的智能桌面宠物

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-windows-lightgrey.svg)]()

**AiPet** 是一款基于 **PyQt5** 架构开发的轻量级、高度可定制的智能桌面陪伴宠物。项目摆脱了传统桌宠“预设脚本与机械反馈”的局限，通过集成大语言模型（LLM）与本地化级联语音合成克隆（Edge-TTS + RVC）等技术，赋予了虚拟角色以独特的“灵魂”与俏皮的声音。

---

## 🌟 项目特色 (Core Features)

*   **🔊 自适应三模式混合语音引擎**：
    *   **Edge-TTS + RVC 级联变声 (`rvc`) [最推荐]**：由微软 Edge-TTS 云端合成高清女声底音，配合本地纯 PyTorch 实现的 RVC 变声模块。升级采用 `pyworld/harvest` 高阶基频算法，音高变换丝滑自然，告别机械棒读。
    *   **GPT-SoVITS 本地直接推理 (`gpt_sovits`)**：无需运行繁重的外部 API 程序，本地纯 PyTorch 快速推理。支持零样本（Zero-shot）仅凭参考音频克隆，以及加载专属角色 `.ckpt` 与 `.pth` 微调模型的高品质拟真发音。
    *   **纯 Edge-TTS 播报 (`edge_tts`)**：免去加载任何本地大模型的超轻量化运行模式，极低 CPU 和内存占用。
*   **⚙️ 免 fairseq 重型二进制依赖**：
    *   重构并手写了原生的 Hubert 神经网络算子，彻底移除了 `fairseq`、`PyAV (av)` 等在 Windows 环境下极难安装与打包的 C 编译依赖包，确保所有人均可顺利运行并一键使用 PyInstaller 打包。
*   **🎨 控制台与“资产工坊”可视化管理**：
    *   **交互联动**：控制台配置角色时，“发音模式”下拉框与表单输入行实现动态联动隐藏，只展示所需字段。
    *   **一键分发**：保存时自动执行文件拷贝并生成 `profile.json`。只需将整个角色目录复制到 `resources/characters/` 下即可完美热插拔导入新音色和 Live2D 形象。
*   **🧠 大脑 (LLM) 接入**：支持流式大语言模型 API，提供自定义人设 Prompt，让桌宠拥有独特的性格设定。
*   **💻 完美 Windows 兼容**：对 Windows 平台做了深度透明窗体渲染与点击穿透优化，CPU 占用率极低。

---

## 🛠️ 安装与部署指南 (Installation & Setup)

### 环境要求
*   **操作系统**：Windows 10/11
*   **Python 版本**：Python 3.8 ~ Python 3.14

---

### 步骤 1：克隆项目与安装依赖
1. 打开终端并克隆本仓库：
   ```bash
   git clone https://github.com/your-username/AiPet.git
   cd AiPet
   ```
2. 激活你的 Python 虚拟环境（例如使用 `.venv`），并安装所需依赖：
   ```bash
   pip install -r requirements.txt
   ```

---

### 步骤 2：配置本地设置
为了保护你的隐私，真实的配置文件已被 Git 忽略。你需要将模板文件复制并更名：
1. 复制配置模板：
   在 `config/` 目录下，将 `settings.json.example` 复制一份并重命名为 `settings.json`。
2. 填入你的大语言模型 API 密钥（例如 SiliconFlow 或 OpenAI 密钥）：
   打开 `config/settings.json`，在第 35 行将 `"api_key": "your_api_key_here"` 替换为你真实的 API 密钥。

---

### 步骤 3：配置大模型依赖（双方案可选）
由于语音合成与变声（RVC 和 GPT-SoVITS）所依赖的官方基础模型体积较大（单文件已超 GitHub 100MB 限制），项目已通过 `.gitignore` 自动忽略这些大文件。你可以在以下两种模型部署方案中任选其一：

#### 💡 方案 A：懒人一键包安装（推荐，最省心 ⭐⭐⭐⭐⭐）
我们已将所有底模完整打包并配置好了层级结构（名为 **`models.zip`**）。你无需一个个下载并新建文件夹，只需通过以下任意一个通道下载：
*   **通道 1（国内极速云盘）**：暂无（请优先使用下方通道 2）
*   **通道 2（GitHub Release）**：[GitHub Releases 官方发布页下载](https://github.com/toh520/AiPet/releases/download/v1.0/models.zip)

**安装步骤**：将下载的一键包解压，把解压得到的整个 **`models` 文件夹** 拖入本项目的 **`resources/`** 目录下。

---

#### 🛠️ 方案 B：去官网自主下载并手动配置（适合高级用户 ⚙️）
如果你不想使用打包好的一键包，也可以直接去 RVC 官方和 GPT-SoVITS 官方下载预训练权重，并按照以下规则进行手动重命名和目录摆放：

1. **RVC 特征提取底模**：
   *   下载官方的 [hubert_base.pt](https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt)（约 378MB）。
   *   将文件重命名为 **`hubert_base_state.pt`**，放置在 `resources/models/hubert_base_state.pt`。
2. **GPT-SoVITS 官方共享底模**：
   *   前往 GPT-SoVITS 官方 HuggingFace 仓库 [lj1995/GPT-SoVITS](https://huggingface.co/lj1995/GPT-SoVITS/tree/main) 下载对应模型：
       *   下载 `chinese-hubert-base/pytorch_model.bin` 并放入项目 `resources/models/gpt_sovits_base/chinese-hubert-base/` 目录下。
       *   下载 `chinese-roberta-wwm-ext-large/pytorch_model.bin` 并放入项目 `resources/models/gpt_sovits_base/chinese-roberta-wwm-ext-large/` 目录下。
       *   下载 V2 版本的 GPT 权重 `gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt` 和 SoVITS 权重 `s2G2333k.pth`，保持目录结构放入项目 `resources/models/gpt_sovits_base/gsv-v2final-pretrained/` 下。
       *   下载中文声纹检索权重 `sv/pretrained_eres2netv2w24s4ep4.ckpt` 放入 `resources/models/gpt_sovits_base/sv/` 目录下。

---

#### ⚡ 运行模型“脱水”处理（两种方案完成后均需运行）
无论是方案 A 还是方案 B，下载完底模后，为摆脱 Windows 下极难安装的 C 语言 `fairseq` 编译依赖库，请在项目根目录下激活你的环境并运行脱水提取脚本，将 Hubert 底模原地转换成纯 PyTorch 参数格式：
```bash
python scratch/extract_contentvec.py
```

#### 📦 一键包内的完整目录结构参考（解压后自动对齐）：
```text
resources/models/
├── hubert_base_state.pt                  # RVC 变声引擎底模（脱水前为 hubert_base.pt）
└── gpt_sovits_base/                       # GPT-SoVITS 引擎预训练底模目录
    ├── chinese-hubert-base/
    │   └── pytorch_model.bin
    ├── chinese-roberta-wwm-ext-large/
    │   └── pytorch_model.bin
    ├── gsv-v2final-pretrained/
    │   ├── s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt
    │   └── s2G2333k.pth
    └── sv/
        └── pretrained_eres2netv2w24s4ep4.ckpt
```

---

### 步骤 4：启动与运行
完成上述配置后，在项目根目录下运行：
```bash
python src/main.py
```
*   **提示**：在桌宠身上右键点击可呼出“控制台”，进入“资产工坊”可以自由切换发音模式、微调发音参数或导入新的 Live2D 材质与音色权重。

---

## 🎨 角色形象与音色自定义教程 (Customization Guide)

本项目具有极佳的扩展性。无论是普通用户还是开发者，都可以极其轻松地创建或导入一个全新的桌宠角色。自定义分为**可视化导入**与**手动配置文件导入**两种方式。

### 方式一：使用控制台“资产工坊”导入（推荐 ⭐⭐⭐⭐⭐）

这是最直观的方式，你无需修改任何代码或 JSON 配置文件：

1. **进入资产工坊**：
   运行桌宠后，在桌宠身上**右键点击**选择 **"⚙️ 控制台"**，然后点击 **"🎨 资产工坊"** 标签页。
2. **配置基本信息**：
   *   **角色名称**：输入角色的英文或拼音标识（如 `Furina`）。
   *   **系统人设 (System Prompt)**：填入赋予该角色的 AI 提示词（例如：“你现在是芙宁娜，性格傲娇，说话喜欢用戏剧腔调……”），这决定了桌宠的大脑和聊天风格。
3. **导入形象资源**：
   *   **渲染模式 (Renderer)**：选择 `live2d`（Live2D 模型）或 `sprite`（2D 图片帧/序列帧）。
   *   **导入路径**：点击浏览按钮，选择你本地的 `.model3.json` 物理文件，资产工坊会**自动**将整个 Live2D 文件夹复制并重构至该角色目录下。
4. **导入音色模型与配置发音模式**：
   *   **发音模式 (Voice Mode)**：下拉框选择你需要的发音引擎，表单将动态刷新显示对应的选项。
   *   **RVC 变声模式**：选择你为该角色训练好的变声权重（`.pth`）与检索索引（`.index`，可选）。
   *   **GPT-SoVITS 模式**：选择你的微调模型权重（`.ckpt` 和 `.pth`），并填入对应的参考音频（`.wav`）与参考文本。
   *   **纯 Edge-TTS 模式**：无需导入任何模型，只需选择云端的微软高清发音人（如 `zh-CN-XiaoxiaoNeural`）。
5. **保存并载入**：
   *   点击表单下方的 **“💾 保存角色资产”** 按钮。系统会把选中的模型和素材复制到该角色文件夹下，自动生成 `profile.json` 配置文件。
   - 切换到 **“角色选择”**，你就能在桌面上即刻与你创造的新角色进行音色和视觉的双重互动了！

---

### 方式二：手动编写配置文件导入（适合开发者）

如果你习惯于文件配置，可以直接在 `resources/characters/` 目录下手动构建角色。

#### 1. 角色目录结构规范
在 `resources/characters/` 下为你的角色新建一个文件夹（例如 `HuTao`），并保持以下目录层级结构：
```text
resources/characters/HuTao/
├── live2d_model/           # 存放角色的 Live2D 模型文件夹
│   └── 胡桃001.model3.json # 主配置文件
├── idle/                   # 存放静态图片帧或序列帧素材（非Live2D模式使用）
├── rvc/                    # 存放该角色的 RVC 变声模型
│   ├── hutaoo.pth          # RVC 权重
│   └── added_IVF_...index  # 索引文件
├── voice/                  # 存放合成所需的参考音频
│   └── ref.wav             # 参考音频
├── profile.json            # 核心人设立绘及语音配置文件（必须）
```

#### 2. `profile.json` 配置字段详解
在角色文件夹根目录下新建 `profile.json` 文件，标准的格式示例如下：
```json
{
    "name": "HuTao",
    "system_prompt": "你现在是《原神》中的胡桃，往生堂第七十七代堂主。你的性格古灵精怪、俏皮可爱。...",
    "renderer": "live2d",
    "live2d_model": "live2d_model/胡桃001.model3.json",
    "live2d_scale": 1.0,
    "live2d_offset_y": 0.0,
    "voice_mode": "rvc",  // 语音引擎模式选择，支持: "rvc" | "gpt_sovits" | "edge_tts"
    "tts": {
        "ref_audio": "voice/ref.wav",                         // 参考音频相对路径
        "prompt_text": "这位客官，想照顾我们往生堂的生意，也不必这么心急嘛！", // 参考音频对应的文本
        "text_lang": "zh",                                    // 目标生成语言
        "prompt_lang": "zh"                                   // 参考音频语言
    },
    "gpt_sovits": {
        "ckpt": "gpt_sovits/hutao-e25.ckpt",                  // GPT 权重路径（不填则自动使用共享底模）
        "pth": "gpt_sovits/hutao_s100.pth"                     // SoVITS 权重路径
    },
    "rvc": {
        "enable": true,                                       // 是否启用 RVC
        "pth": "rvc/hutaoo.pth",                              // RVC 权重路径
        "index": "rvc/added_IVF1016_Flat_nprobe_1_hutaoo_v2.index" // 索引文件路径
    }
}
```
*   **注**：`profile.json` 中所有的资源路径，均应填写相对于该角色文件夹根目录的**相对路径**（例如 `"voice/ref.wav"` 而非完整的绝对路径），以确保该角色文件夹被整体打包分享给其他人时依然能直接运行。

---

## 📂 项目目录结构说明

```text
PetProject/
├── config/                 # 配置文件目录
│   ├── settings.json       # 本地运行配置文件（本地特有，被 Git 忽略）
│   └── settings.json.example # 配置模板（无私钥，用于 GitHub 共享）
├── resources/              # 静态与模型共享资源
│   ├── characters/         # 角色配置目录（包含 live2d、image、voice 等）
│   └── models/             # 共享基础模型权重目录
├── scratch/                # 本地测试与脚本工具目录
│   ├── README.md           # 脱水工具使用说明书
│   ├── extract_contentvec.py # 核心模型脱水工具
│   └── test_tts.py         # TTS 与变声效果本地单元测试脚本
├── src/                    # 源码目录
│   ├── aipet/              # 核心业务逻辑
│   │   ├── services/       # 语音合成、RVC变声及大模型推理服务
│   │   ├── ui/             # PyQt5 桌宠窗体、控制台与聊天气泡 UI 
│   │   └── utils.py        # 通用 IO 辅助工具
│   └── main.py             # 统一启动入口
└── requirements.txt        # Python 依赖项清单
```

---

## 📢 开源免责与版权保护声明 (Disclaimer & Credits)

### 1. 项目定位与无资产声明
*   **纯代码框架**：本项目是一个完全开源、免费的桌面宠物**自适应交互框架**。为了彻底防范版权纠纷，**本开源仓库内不包含、亦不分发任何受版权保护的美术资源、Live2D 原始模型（Moc3 材质文件）、或游戏原声配音音频**。
*   **资产解耦**：项目在设计上实现了代码与资产的完全解耦。仓库中自带的仅为用于程序运行演示的极简测试图，不具备商业和侵权性质。

### 2. 演示素材版权归属与商用禁止（针对胡桃/Furina等角色）
*   **版权声明**：本项目在文档或界面中所演示和提及的角色形象（如《原神》胡桃/Hu Tao、芙宁娜/Furina）及对应的原声音色，其美术形象著作权及原始音频版权均归游戏制作方 **miHoYo (米哈游)** 所有。演示用 Live2D 模型文件的二创制作版权归原模型制作者（如 B站 UP 主 [孤言omo](https://space.bilibili.com/12554228)）所有。
*   **严禁商用**：本项目的代码及上述任何美术与语音素材，**严禁用于任何形式的商业盈利活动（包括但不限于付费分发、商业直播、打赏盈利、付费定制软件等）**。
*   **二创合规**：使用者在使用该框架进行任何二次开发或发布内容时，必须严格遵守原版权方的二创规定（如米哈游官方二创管理规定）以及模型制作者的授权声明。
*   **免责条款**：任何使用者因违规使用本框架、非法二次分发模型文件、或违规用于商业用途而导致的任何版权争议、侵权纠纷或法律诉讼，**均由使用者个人完全承担责任，与本项目及项目原作者无关**。

### 3. 开源技术致谢
*   [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)：感谢 RVC-Boss 团队的开源零样本 TTS 框架贡献。
*   [Retrieval-based-Voice-Conversion](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)：感谢 RVC 团队在声音克隆技术上的贡献。
*   [PyWorld](https://github.com/JeremyRuten/pyworld)：提供基频拟合计算支持。

---

## 📝 许可证 (License)

本项目的**代码部分**遵循 **[MIT 许可证](LICENSE)**。
这意味着你可以自由修改、分发与使用本项目的源代码，但须保留原作者的版权声明。上述许可不包含任何受版权保护的美术与声音资产。

---
**Enjoy your AI Pet! 🐾**