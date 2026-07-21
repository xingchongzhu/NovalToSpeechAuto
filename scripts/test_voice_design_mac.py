# coding=utf-8
"""Qwen3-TTS VoiceDesign 测试脚本 — 适配 Apple Silicon Mac (MPS)"""
import time
import torch
import soundfile as sf

from qwen_tts import Qwen3TTSModel


def main():
    # 自动检测可用设备
    if torch.backends.mps.is_available():
        device = "mps"
        print(">>> 使用 MPS (Apple Silicon GPU) 加速")
    else:
        device = "cpu"
        print(">>> MPS 不可用，回退到 CPU")

    MODEL_PATH = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

    print(f">>> 正在加载模型: {MODEL_PATH}")
    print(">>> 首次运行会从 HuggingFace 下载模型（约 3-5 GB），请耐心等待...")

    t0 = time.time()

    tts = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map=device,
        dtype=torch.float16,
        attn_implementation="sdpa",
    )

    t1 = time.time()
    print(f">>> 模型加载完成，耗时: {t1 - t0:.1f}s")

    # 测试1: 中文旁白音色
    print("\n=== 测试1: 温柔旁白女声 ===")
    print("    描述: 温柔清冷 25 岁女声，语速平缓，轻微气声，适合有声书旁白，语调柔和克制")
    print("    文本: 夜幕降临，整座青云山笼罩在一片寂静之中，只有远处偶尔传来几声猿啼。")

    t2 = time.time()

    wavs, sr = tts.generate_voice_design(
        text="夜幕降临，整座青云山笼罩在一片寂静之中，只有远处偶尔传来几声猿啼。",
        language="Chinese",
        instruct="温柔清冷 25 岁女声，语速平缓，轻微气声，适合有声书旁白，语调柔和克制",
    )

    t3 = time.time()
    print(f"    生成耗时: {t3 - t2:.1f}s, 采样率: {sr}Hz, 时长: {len(wavs[0])/sr:.1f}s")
    sf.write("test_voice_design_narrator.wav", wavs[0], sr)
    print("    已保存: test_voice_design_narrator.wav")

    # 测试2: 不同角色音色
    print("\n=== 测试2: 威严中年男声 ===")
    print("    描述: 低沉威严的中年男声，说话沉稳有力，带有不容置疑的气场")
    print("    文本: 尔等小辈，也敢在本座面前放肆！")

    t2 = time.time()

    wavs, sr = tts.generate_voice_design(
        text="尔等小辈，也敢在本座面前放肆！",
        language="Chinese",
        instruct="低沉威严的中年男声，说话沉稳有力，带有不容置疑的气场和威压感",
    )

    t3 = time.time()
    print(f"    生成耗时: {t3 - t2:.1f}s, 时长: {len(wavs[0])/sr:.1f}s")
    sf.write("test_voice_design_elder.wav", wavs[0], sr)
    print("    已保存: test_voice_design_elder.wav")

    # 测试3: 年轻活泼音色
    print("\n=== 测试3: 活泼少女声 ===")
    print("    描述: 17 岁活泼少女，声音清脆明亮，语速稍快，充满青春活力")
    print("    文本: 师兄师兄，你快来看！那边的花开得好漂亮啊！")

    t2 = time.time()

    wavs, sr = tts.generate_voice_design(
        text="师兄师兄，你快来看！那边的花开得好漂亮啊！",
        language="Chinese",
        instruct="17 岁活泼少女，声音清脆明亮，语速稍快，充满青春活力和好奇心",
    )

    t3 = time.time()
    print(f"    生成耗时: {t3 - t2:.1f}s, 时长: {len(wavs[0])/sr:.1f}s")
    sf.write("test_voice_design_girl.wav", wavs[0], sr)
    print("    已保存: test_voice_design_girl.wav")

    print("\n=== 全部测试完成 ===")
    print("生成文件:")
    print("  - test_voice_design_narrator.wav (温柔旁白女声)")
    print("  - test_voice_design_elder.wav (威严中年男声)")
    print("  - test_voice_design_girl.wav (活泼少女声)")


if __name__ == "__main__":
    main()
