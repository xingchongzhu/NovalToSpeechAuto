# coding=utf-8
"""VoiceDesign 同角色音色一致性测试：同一 instruct + subtalker 参数生成三句"""
import time
import torch
import soundfile as sf
import numpy as np

from qwen_tts import Qwen3TTSModel


def main():
    if torch.backends.mps.is_available():
        device = "mps"
        print(">>> 使用 MPS (Apple Silicon GPU) 加速")
    else:
        device = "cpu"
        print(">>> MPS 不可用，回退到 CPU")

    MODEL_PATH = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    print(f">>> 正在加载模型: {MODEL_PATH}")

    t0 = time.time()
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map=device,
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    print(f">>> 模型加载完成，耗时: {time.time() - t0:.1f}s")

    # 同一 instruct，三句不同文本
    instruct = "温柔清冷 25 岁女声，语速平缓，轻微气声，适合有声书旁白，语调柔和克制"

    texts = [
        "夜幕降临，整座青云山笼罩在一片寂静之中。",
        "只有远处偶尔传来几声猿啼。",
        "山间的雾气慢慢升起，月光洒在青石台阶上。",
    ]

    print(f"\n=== 同角色音色一致性测试 ===")
    print(f"  instruct: {instruct}")
    print(f"  subtalker_dosample: False")
    print(f"  subtalker_temperature: 0.5")

    results = []
    for i, text in enumerate(texts, 1):
        print(f"\n--- 测试{i}: \"{text}\" ---")
        t_start = time.time()

        wavs, sr = tts.generate_voice_design(
            text=text,
            language="Chinese",
            instruct=instruct,
            subtalker_dosample=False,
            subtalker_temperature=0.5,
        )

        audio = np.concatenate(wavs) if isinstance(wavs, list) else wavs
        elapsed = time.time() - t_start
        dur = len(audio) / sr

        pitch = _estimate_pitch_mean(audio, sr)
        energy = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))

        output_path = f"test_voice_consistency_{i}.wav"
        sf.write(output_path, audio, sr)

        results.append({"text": text, "duration": dur, "pitch_hz": pitch, "rms": energy, "path": output_path})

        print(f"    耗时: {elapsed:.1f}s | 时长: {dur:.1f}s | 基频: {pitch:.1f}Hz | 能量: {energy:.4f}")

    # 汇总对比
    print(f"\n=== 汇总对比 ===")
    print(f"{'句':<4} {'时长':<8} {'基频(Hz)':<12} {'RMS能量':<12}")
    for i, r in enumerate(results, 1):
        print(f"{i:<4} {r['duration']:<8.2f} {r['pitch_hz']:<12.1f} {r['rms']:<12.4f}")

    pitches = [r["pitch_hz"] for r in results]
    energies = [r["rms"] for r in results]
    print(f"\n基频范围: {min(pitches):.1f} ~ {max(pitches):.1f} Hz (差 {max(pitches)-min(pitches):.1f} Hz)")
    print(f"能量范围: {min(energies):.4f} ~ {max(energies):.4f}")

    if max(pitches) - min(pitches) < 15:
        print("\n✅ 基频稳定，音色一致性好")
    else:
        print("\n⚠️ 基频波动较大，音色可能存在差异（注意：不同文本的自然语调也会有影响）")

    print(f"\n生成文件: {', '.join(r['path'] for r in results)}")


def _estimate_pitch_mean(audio: np.ndarray, sr: int) -> float:
    """简易基频估计：找频谱第一个峰值"""
    n = len(audio)
    if n < sr // 40:
        return 0.0
    fft = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    # 人声基频范围 80-400Hz
    mask = (freqs >= 80) & (freqs <= 400)
    if not np.any(mask):
        return 0.0
    idx = np.argmax(fft[mask])
    return float(freqs[mask][idx])


if __name__ == "__main__":
    main()
