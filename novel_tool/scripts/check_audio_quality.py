#!/usr/bin/env python3
"""TTS 音频质量检查工具

用法:
    python3 check_audio_quality.py <文件路径>              # 检查单个文件
    python3 check_audio_quality.py <目录路径>              # 检查目录下所有 .wav
    python3 check_audio_quality.py <文件1> <文件2> ...     # 检查多个文件

检查项:
    1. 完全静音
    2. 连续静音 ≥2s
    3. 疑似纯噪声（连续 ≥5s RMS 几乎不变）
    4. 时长异常（过短/过长）
"""

import numpy as np
import os
import sys

try:
    from pydub import AudioSegment
except ImportError:
    print("请先安装 pydub: pip install pydub")
    sys.exit(1)


def check_audio_segment(audio: 'AudioSegment', text_len: int = 0):
    """检查 pydub AudioSegment 的音频质量。
    
    Args:
        audio: pydub AudioSegment 对象
        text_len: 对应文本长度（字符数），用于时长异常判断，0 则跳过时长检查
    
    Returns:
        list[str]: 问题描述列表，空列表表示无问题
    """
    issues = []
    mono = audio.set_channels(1)
    samples = np.array(mono.get_array_of_samples(), dtype=np.float32)
    sr = mono.frame_rate
    dur = len(samples) / sr

    # 4. 时长异常（需提供 text_len 才检查，放在前面以覆盖极短音频无 RMS 窗口的情况）
    if text_len > 0:
        expected_dur_min = max(0.3, text_len / 8.0)
        expected_dur_max = max(5.0, text_len / 1.0)
        if dur < expected_dur_min:
            issues.append(f"音频异常短 ({dur:.1f}s, 预期≥{expected_dur_min:.1f}s)")
        elif dur > expected_dur_max:
            issues.append(f"音频异常长 ({dur:.1f}s, 预期≤{expected_dur_max:.1f}s)")

    seg_samples = int(sr * 0.5)
    rms_vals = [float(np.sqrt(np.mean(samples[i:i+seg_samples].astype(np.float64)**2)))
                for i in range(0, len(samples), seg_samples)
                if len(samples[i:i+seg_samples]) >= seg_samples // 2]
    if not rms_vals:
        return issues

    avg_rms = np.mean(rms_vals)

    # 1. 完全静音
    if avg_rms < 1:
        issues.append("完全静音")
        return issues

    # 2. 连续静音 ≥2s
    thresh = avg_rms * 0.12
    max_silent = cur = 0
    for r in rms_vals:
        if r < thresh:
            cur += 1
            max_silent = max(max_silent, cur)
        else:
            cur = 0
    if max_silent >= 4:
        issues.append(f"连续静音 {max_silent*0.5:.1f}s")

    # 3. 疑似纯噪声（连续 ≥5s RMS 变化 <3%）
    max_stable = cur_stable = 1
    for k in range(1, len(rms_vals)):
        change = abs(rms_vals[k] - rms_vals[k-1]) / (rms_vals[k-1] + 0.001)
        if change < 0.03:
            cur_stable += 1
            max_stable = max(max_stable, cur_stable)
        else:
            cur_stable = 1
    if max_stable >= 10:
        issues.append(f"疑似纯噪声 (连续稳定{max_stable*0.5:.1f}s)")

    return issues


def check_audio(path):
    """检查音频文件的质量（文件路径版本）。
    
    Args:
        path: wav 文件路径
    
    Returns:
        list[str]: 问题描述列表
    """
    audio = AudioSegment.from_file(path)
    return check_audio_segment(audio)


def scan_path(path, verbose=True):
    """扫描路径，返回 [(filepath, issues), ...]"""
    results = []
    if os.path.isfile(path):
        if path.endswith('.wav'):
            issues = check_audio(path)
            results.append((path, issues))
            if verbose:
                _print_result(path, issues)
        else:
            print(f"跳过非 wav 文件: {path}")
    elif os.path.isdir(path):
        files = sorted(
            [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.wav')],
            key=lambda x: os.path.getsize(x),
        )
        total = len(files)
        for i, f in enumerate(files):
            issues = check_audio(f)
            results.append((f, issues))
            if verbose:
                prefix = f"[{i+1}/{total}]"
                _print_result(f, issues, prefix)
    return results


def _print_result(path, issues, prefix=""):
    fname = os.path.basename(path)
    if issues:
        print(f"  {prefix} ⚠️  {fname}: {'; '.join(issues)}")
    else:
        print(f"  {prefix} ✅ {fname}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    all_results = []
    for arg in sys.argv[1:]:
        all_results.extend(scan_path(arg))

    if not all_results:
        print("未找到可检查的 wav 文件")
        return

    ok = sum(1 for _, issues in all_results if not issues)
    warn = sum(1 for _, issues in all_results if issues)
    total = ok + warn
    print(f"\n{'='*50}")
    print(f"总计 {total} 个文件: {ok} 正常, {warn} 异常")
    sys.exit(1 if warn > 0 else 0)


if __name__ == '__main__':
    main()
