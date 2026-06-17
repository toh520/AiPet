import os
import sys

# 解决 Windows 下多个 OpenMP 运行时库冲突导致的 WinError 1114 动态链接库初始化失败问题
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 将项目的 src 目录添加到 Python 的查找路径中，确保能正确导入 aipet 包
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aipet.services.gpt_sovits import gpt_sovits_convert
from aipet.services.rvc import rvc_convert

# 动态获取项目根目录路径
BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHARACTER_BASE = os.path.join(BASE_PATH, "resources", "characters", "HuTao")
REF_WAV = os.path.join(CHARACTER_BASE, "voice", "ref.wav")
PROMPT_TEXT = "这位客官，想照顾我们往生堂的生意，也不必这么心急嘛！你没什么事吧？"

GPT_CKPT = os.path.join(BASE_PATH, "resources", "models", "gpt_sovits_base", "gsv-v2final-pretrained", "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt")
SOVITS_PTH = os.path.join(BASE_PATH, "resources", "models", "gpt_sovits_base", "gsv-v2final-pretrained", "s2G2333k.pth")
HUBERT_PATH = os.path.join(BASE_PATH, "resources", "models", "hubert_base_state.pt")

RVC_PTH = os.path.join(CHARACTER_BASE, "rvc", "hutaoo.pth")
RVC_INDEX = os.path.join(CHARACTER_BASE, "rvc", "added_IVF1016_Flat_nprobe_1_hutaoo_v2.index")

# 测试合成文本及保存的音频路径
TEST_TEXT = "你好，本堂主在此恭候您多时了。"
OUT_SOVITS = os.path.join(BASE_PATH, "scratch", "out_sovits.wav")
OUT_RVC = os.path.join(BASE_PATH, "scratch", "out_rvc.wav")

def test_gpt_sovits():
    """测试 GPT-SoVITS 语音合成功能"""
    print("--- 开始测试 GPT-SoVITS 语音合成 ---")
    try:
        gpt_sovits_convert(
            text=TEST_TEXT,
            text_lang="zh",
            ref_wav_path=REF_WAV,
            prompt_text=PROMPT_TEXT,
            prompt_lang="zh",
            output_wav_path=OUT_SOVITS,
            gpt_ckpt_path=GPT_CKPT,
            sovits_pth_path=SOVITS_PTH,
            version="v2",
            device="cpu"
        )
        print(f"GPT-SoVITS 测试成功！生成的音频文件保存在: {OUT_SOVITS}")
    except Exception as e:
        print(f"GPT-SoVITS 测试失败！错误信息为: {e}")
        import traceback
        traceback.print_exc()

def test_rvc():
    """测试 RVC 音色转换功能"""
    print("--- 开始测试 RVC 音色转换 ---")
    # 这里直接使用刚刚 GPT-SoVITS 生成的普通人声音频作为输入，如果没生成则用参考音频代替
    input_wav = OUT_SOVITS if os.path.exists(OUT_SOVITS) else REF_WAV
    try:
        rvc_convert(
            model_path=RVC_PTH,
            index_path=RVC_INDEX,
            hubert_path=HUBERT_PATH,
            input_wav_path=input_wav,
            output_wav_path=OUT_RVC,
            f0_up_key=0,
            f0_method="pm",  # 使用 PM 音高提取算法
            index_rate=0.75,
            rms_mix_rate=0.25,
            protect=0.33
        )
        print(f"RVC 音色转换测试成功！转换后的音频文件保存在: {OUT_RVC}")
    except Exception as e:
        print(f"RVC 音色转换测试失败！错误信息为: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 执行两个合成模式的测试
    test_gpt_sovits()
    test_rvc()
