# coding=utf-8
"""VoiceDesign 前缀裁剪测试 — 3 段不同语速验证裁剪准确性

对比三种语速 (-15% / +0% / +15%) 下：
  1. 前缀 "话说，" 实际音频长度
  2. 动态计算的裁剪上限 safe_trim
  3. 生成音频头部是否还残留"说"或被切掉正文首字

输出：3 个 wav 文件 + 打印裁剪明细
"""
import os
import sys
import time

# 添加模块路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.abspath(os.path.join(_HERE, "..", "novel_tool", "scripts"))
sys.path.insert(0, _MODULE_DIR)

from audio_processing_module import AudioEngine, VoiceParams  # noqa: E402


TEST_TEXT = "夜幕降临，整座青云山笼罩在一片寂静之中，只有远处偶尔传来几声猿啼。"
VD_PROMPT = "温柔清冷 25 岁女声，语速平缓，轻微气声，适合有声书旁白，语调柔和克制"

# 三种语速
SPEED_CASES = [
    ("slow", "-15%"),
    ("normal", "+0%"),
    ("fast", "+15%"),
]

OUTPUT_DIR = os.path.join(_HERE, "vd_prefix_trim_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    print("=" * 60)
    print("VoiceDesign 前缀裁剪 3 段语速测试")
    print("=" * 60)

    # 初始化引擎（VoiceDesign 模式，模型加载一次复用）
    t_init = time.time()
    engine = AudioEngine(
        temp_dir=os.path.join(OUTPUT_DIR, "_temp"),
        tts_engine="qwen3-tts",
        tts_mode="voice_design",
    )
    print(f"[Init] 引擎就绪，耗时 {time.time() - t_init:.1f}s\n")

    results = []
    for tag, speed in SPEED_CASES:
        print("─" * 60)
        print(f"▶ 测试: {tag} (speed={speed})")
        print("─" * 60)

        params = VoiceParams(
            text=TEST_TEXT,
            role="旁白",
            role_voice="",
            speed=speed,
            volume="+0%",
            pitch="+0Hz",
            tts_mode="voice_design",
            voice_design_prompt=VD_PROMPT,
        )

        t0 = time.time()
        audio = engine.text_to_speech(params)
        dur = len(audio) / 1000.0
        elapsed = time.time() - t0

        out_path = os.path.join(OUTPUT_DIR, f"vd_prefix_{tag}_{speed.replace('+', 'p').replace('-', 'm').replace('%', '')}.wav")
        audio.export(out_path, format="wav")

        print(f"[✓] 生成完成: {out_path}")
        print(f"    音频时长 {dur:.2f}s，耗时 {elapsed:.1f}s")
        results.append((tag, speed, dur, out_path))
        print()

    print("=" * 60)
    print("汇总:")
    for tag, speed, dur, path in results:
        print(f"  {tag:8s} speed={speed:6s} → {dur:5.2f}s  {os.path.basename(path)}")
    print("=" * 60)
    print(f"\n输出目录: {OUTPUT_DIR}")
    print("请人工听测三段音频，重点检查：")
    print("  1. 开头是否有残留 '说' 字（裁剪不足）")
    print("  2. 开头 '夜' 字是否被切（裁剪过头）")


if __name__ == "__main__":
    main()
