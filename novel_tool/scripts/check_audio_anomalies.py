#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频异常检测脚本
================
支持检测单个音频文件或递归扫描目录下所有音频文件的异常。

检测项：
  - 文件不可读 / 损坏（解码失败、格式异常、空文件）
  - 静音 / 近乎静音（峰值、RMS、dBFS 过低）
  - 削波 / 饱和（大量样本触顶）
  - NaN/Inf 样本（数据损坏）
  - 时长异常（空音频、极短音频）
  - 截断（尾部非零结束，疑似不完整）
  - 毛刺/爆音（相邻样本间剧烈跳变）
  - 连续静音（超过 2s 无有效音频信号）
  - 持续低信号/杂音（超过 2s RMS 低于 -40dBFS）
  - 频谱异常（需 --strict，频谱质心偏离常态）

用法:
  python check_audio_anomalies.py <path>                     # 扫描文件或目录
  python check_audio_anomalies.py <path> --recursive         # 递归扫描子目录
  python check_audio_anomalies.py <path> --format mp3        # 只检查指定格式
  python check_audio_anomalies.py <path> --json report.json  # 输出 JSON 报告
  python check_audio_anomalies.py <path> --strict            # 严格模式（低响度也报异常）
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

# ============================================================
# 默认阈值配置
# ============================================================

# 静音检测
SILENCE_PEAK_THRESHOLD = 0.005
SILENCE_RMS_THRESHOLD = 0.0005
LOW_PEAK_WARN = 0.02

# dBFS
DEAD_AUDIO_DBFS = -48.0
LOW_AUDIO_DBFS = -36.0
NORMAL_AUDIO_DBFS = -24.0

# NaN/Inf
NAN_FRACTION_THRESHOLD = 0.01

# 削波检测
CLIPPING_FRACTION_THRESHOLD = 0.05

# 时长
MIN_VALID_DURATION = 0.3
VERY_SHORT_DURATION = 1.0

# 截断检测
TRUNCATION_TAIL_MS = 50
TRUNCATION_TAIL_RMS_RATIO = 2.0

# 毛刺/爆音检测
GLITCH_SAMPLE_JUMP = 0.5
GLITCH_MIN_COUNT = 3

# 连续静音检测
CONTINUOUS_SILENCE_MAX_SECONDS = 2.0   # 连续静音超过此时长 → 异常
CONTINUOUS_SILENCE_PEAK = 0.003        # 静音判定峰值阈值（低于此视为静音样本）

# 持续低信号检测（杂音/底噪/信号极弱）
CONTINUOUS_LOW_SIGNAL_MAX_SECONDS = 2.0  # 连续低信号超过此时长 → 异常
LOW_SIGNAL_RMS_THRESHOLD = 0.01          # 0.1s 窗口 RMS 低于此 → 弱信号（-40dBFS，人耳几乎听不到）

# 频谱异常检测（频谱质心偏离常态）
SPECTRAL_ANOMALY_WINDOW_SEC = 0.5       # 分析窗口大小
SPECTRAL_ANOMALY_CENTROID_HIGH_RATIO = 4.0  # 质心 > median*此值 → 高频杂音（嘶声）
SPECTRAL_ANOMALY_CENTROID_LOW_RATIO = 0.25  # 质心 < median*此值 → 低频杂音（嗡声）
SPECTRAL_ANOMALY_MIN_DURATION_SEC = 1.5     # 持续异常超过此时长才报警

# 支持的文件后缀
SUPPORTED_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".webm", ".mka"}


@dataclass
class AudioAnomalyResult:
    """单个音频文件的检测结果"""
    file_path: str
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    passed: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    error: Optional[str] = None


def _read_audio_with_pydub(file_path: str):
    """使用 pydub 读取音频，返回 (pcm_float32, sample_rate, channels) 或 None。"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        sr = audio.frame_rate
        ch = audio.channels
        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        if ch > 1:
            samples = samples.reshape(-1, ch)[:, 0]
        # 归一化到 [-1, 1]：使用位深对应的满量程值，而非文件自身峰值
        full_scale = 2 ** (8 * audio.sample_width - 1)
        samples = samples / full_scale
        return samples.astype(np.float32), sr, ch
    except Exception:
        pass

    wav = _read_wav_raw(file_path)
    if wav is not None:
        pcm, sr = wav
        return pcm, sr, 1
    return None


def _read_wav_raw(file_path: str):
    """低层 WAV PCM/FLOAT 读取，返回 (mono_pcm, sample_rate) 或 (None, 0)。"""
    import struct
    try:
        if not os.path.exists(file_path):
            return None, 0
        file_size = os.path.getsize(file_path)
        if file_size < 44:
            return None, 0
        with open(file_path, 'rb') as f:
            riff_id = f.read(4)
            if riff_id != b'RIFF':
                return None, 0
            f.read(4)
            wave_id = f.read(4)
            if wave_id != b'WAVE':
                return None, 0
            fmt_tag = 1
            channels = 1
            sample_rate = 0
            bits_per_sample = 16
            data_bytes = b''
            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                chunk_size_bytes = f.read(4)
                if len(chunk_size_bytes) < 4:
                    break
                chunk_size = struct.unpack('<I', chunk_size_bytes)[0]
                if chunk_id == b'fmt ':
                    fmt_data = f.read(chunk_size)
                    if len(fmt_data) < 16:
                        break
                    fmt_tag = struct.unpack_from('<H', fmt_data, 0)[0]
                    channels = struct.unpack_from('<H', fmt_data, 2)[0]
                    sample_rate = struct.unpack_from('<I', fmt_data, 4)[0]
                    bits_per_sample = struct.unpack_from('<H', fmt_data, 14)[0]
                    if fmt_tag == 0xFFFE:
                        fmt_tag = 3
                elif chunk_id == b'data':
                    data_bytes = f.read(chunk_size)
                    break
                else:
                    f.seek(chunk_size, 1)
        if len(data_bytes) == 0 or sample_rate == 0:
            return None, 0
        is_float = (fmt_tag == 3)
        effective_bps = 32 if is_float else bits_per_sample
        if is_float:
            pcm = np.frombuffer(data_bytes, dtype=np.float32)
        elif effective_bps == 16:
            pcm = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif effective_bps == 24:
            sample_count = len(data_bytes) // 3
            data_bytes = data_bytes[:sample_count * 3]
            padded = np.frombuffer(data_bytes + b'\x00' * sample_count, dtype='<i4')
            pcm = (padded >> 8).astype(np.float32) / 8388608.0
        elif effective_bps == 32:
            pcm = np.frombuffer(data_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif effective_bps == 8:
            pcm = (np.frombuffer(data_bytes, dtype=np.uint8).astype(np.float32) / 128.0) - 1.0
        else:
            return None, 0
        if channels > 1:
            pcm = pcm.reshape(-1, channels)[:, 0]
        return pcm, sample_rate
    except Exception:
        return None, 0


def _collect_files(path: str, recursive: bool, fmt_filter: Optional[str]) -> List[str]:
    """收集待检测的音频文件列表。"""
    files = []
    if os.path.isfile(path):
        files.append(os.path.abspath(path))
    elif os.path.isdir(path):
        for root, dirs, filenames in os.walk(path):
            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if fmt_filter and ext != f".{fmt_filter.lstrip('.')}":
                    continue
                if ext in SUPPORTED_SUFFIXES:
                    files.append(os.path.abspath(os.path.join(root, fname)))
            if not recursive:
                break
    else:
        print(f"路径不存在: {path}")
        sys.exit(1)
    return files


def _detect_truncation(pcm: np.ndarray, sr: int, overall_rms: float) -> bool:
    """检测尾部非零截断。"""
    if sr <= 0 or len(pcm) == 0:
        return False
    tail_samples = int(TRUNCATION_TAIL_MS / 1000.0 * sr)
    if tail_samples >= len(pcm):
        return False
    tail = pcm[-tail_samples:]
    tail_rms = float(np.sqrt(np.mean(tail ** 2))) if len(tail) > 0 else 0.0
    return overall_rms > 0 and tail_rms / overall_rms > TRUNCATION_TAIL_RMS_RATIO


def _detect_glitches(pcm: np.ndarray) -> int:
    """检测毛刺/爆音：相邻样本间幅度跳变超过阈值的计数。"""
    if len(pcm) < 2:
        return 0
    diff = np.abs(np.diff(pcm))
    jumps = diff > GLITCH_SAMPLE_JUMP
    glitch_count = 0
    consecutive = 0
    for j in jumps:
        if j:
            consecutive += 1
        else:
            if consecutive >= GLITCH_MIN_COUNT:
                glitch_count += consecutive
            consecutive = 0
    if consecutive >= GLITCH_MIN_COUNT:
        glitch_count += consecutive
    return glitch_count


def _detect_continuous_silence(pcm: np.ndarray, sr: int) -> float:
    """
    检测连续静音的最长时长。
    遍历样本，以 CONTINUOUS_SILENCE_PEAK 为静音判定阈值，
    统计最长的连续静音段的秒数。

    Returns:
        最长连续静音秒数
    """
    if sr <= 0 or len(pcm) == 0:
        return 0.0

    # 以 CONTINUOUS_SILENCE_PEAK 判断静音
    is_silent = np.abs(pcm) < CONTINUOUS_SILENCE_PEAK

    max_silent_samples = 0
    current_silent = 0
    for s in is_silent:
        if s:
            current_silent += 1
        else:
            if current_silent > max_silent_samples:
                max_silent_samples = current_silent
            current_silent = 0
    if current_silent > max_silent_samples:
        max_silent_samples = current_silent

    return max_silent_samples / sr


def _detect_continuous_low_signal(pcm: np.ndarray, sr: int) -> float:
    """
    检测持续低信号（杂音/底噪）的最长时长。
    以 0.1s 窗口为单位，窗口 RMS < LOW_SIGNAL_RMS_THRESHOLD 视为弱信号，
    统计最长的连续弱信号段秒数。

    Returns:
        最长连续低信号秒数
    """
    if sr <= 0 or len(pcm) == 0:
        return 0.0

    window_samples = int(sr * 0.1)
    if window_samples == 0:
        return 0.0

    max_low_seconds = 0.0
    current_low_seconds = 0.0
    for i in range(0, len(pcm), window_samples):
        window = pcm[i:i + window_samples]
        window_rms = float(np.sqrt(np.mean(window ** 2)))
        if window_rms < LOW_SIGNAL_RMS_THRESHOLD:
            current_low_seconds += len(window) / sr
        else:
            if current_low_seconds > max_low_seconds:
                max_low_seconds = current_low_seconds
            current_low_seconds = 0.0
    if current_low_seconds > max_low_seconds:
        max_low_seconds = current_low_seconds

    return max_low_seconds


def _detect_spectral_anomaly(pcm: np.ndarray, sr: int):
    """
    检测频谱质心异常（高频杂音或低频嗡声）。

    按 SPECTRAL_ANOMALY_WINDOW_SEC 窗口计算频谱质心，
    与文件中位数做比较，统计最长连续异常段的秒数。

    Returns:
        (max_anomaly_seconds: float, anomaly_type: str)
        anomaly_type 为 "high"(高频杂音)、"low"(低频嗡声) 或 ""(无异常)
    """
    if sr <= 0 or len(pcm) < int(sr * SPECTRAL_ANOMALY_WINDOW_SEC):
        return 0.0, ""

    window_samples = int(sr * SPECTRAL_ANOMALY_WINDOW_SEC)
    if window_samples == 0:
        return 0.0, ""

    centroids = []
    for i in range(0, len(pcm) - window_samples, window_samples):
        chunk = pcm[i:i + window_samples]
        spec = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / sr)
        total = np.sum(spec)
        if total > 0:
            centroids.append(np.sum(freqs * spec) / total)
        else:
            centroids.append(0.0)

    if len(centroids) < 2:
        return 0.0, ""

    median_centroid = float(np.median(centroids))
    if median_centroid == 0:
        return 0.0, ""

    high_threshold = median_centroid * SPECTRAL_ANOMALY_CENTROID_HIGH_RATIO
    low_threshold = median_centroid * SPECTRAL_ANOMALY_CENTROID_LOW_RATIO
    window_sec = SPECTRAL_ANOMALY_WINDOW_SEC

    # 分别检测高频异常和低频异常，取最长
    max_dur = 0.0
    anomaly_type = ""

    for anomaly_label, threshold, cmp_op in [
        ("high", high_threshold, lambda c, t: c > t),
        ("low", low_threshold, lambda c, t: c < t),
    ]:
        current = 0.0
        longest = 0.0
        for c in centroids:
            if cmp_op(c, threshold):
                current += window_sec
            else:
                if current > longest:
                    longest = current
                current = 0.0
        if current > longest:
            longest = current
        if longest > max_dur:
            max_dur = longest
            anomaly_type = anomaly_label

    if max_dur < SPECTRAL_ANOMALY_MIN_DURATION_SEC:
        return 0.0, ""

    return max_dur, anomaly_type


def check_audio(file_path: str, strict: bool = False) -> AudioAnomalyResult:
    """
    对单个音频文件执行全面异常检测。

    Args:
        file_path: 音频文件路径
        strict: 是否启用严格模式（低响度也报异常）

    Returns:
        AudioAnomalyResult 包含所有检测结果
    """
    result = AudioAnomalyResult(file_path=file_path)

    # ---- 文件基础信息 ----
    try:
        result.file_size_bytes = os.path.getsize(file_path)
    except OSError as e:
        result.passed = False
        result.error = f"无法获取文件信息: {e}"
        result.issues.append(result.error)
        return result

    if result.file_size_bytes == 0:
        result.passed = False
        result.error = "空文件"
        result.issues.append("空文件（文件大小为 0）")
        return result

    # ---- 读取音频数据 ----
    raw = _read_audio_with_pydub(file_path)
    if raw is None:
        result.passed = False
        result.error = "无法解码音频文件（格式损坏或不支持）"
        result.issues.append(result.error)
        return result

    pcm, sr, ch = raw
    if pcm is None or len(pcm) == 0 or sr == 0:
        result.passed = False
        result.error = "音频数据为空"
        result.issues.append(result.error)
        return result

    result.sample_rate = sr
    result.channels = ch
    result.duration_seconds = len(pcm) / sr

    # ---- 基础信号指标 ----
    peak = float(np.max(np.abs(pcm)))
    rms = float(np.sqrt(np.mean(pcm ** 2)))
    dbfs = 20.0 * np.log10(peak) if peak > 0 else float('-inf')

    result.metrics["peak"] = peak
    result.metrics["rms"] = rms
    result.metrics["dbfs"] = dbfs
    result.metrics["sample_rate"] = sr
    result.metrics["channels"] = ch
    result.metrics["duration"] = result.duration_seconds

    # ---- 1. NaN/Inf 检测 ----
    nan_count = int(np.sum(~np.isfinite(pcm)))
    nan_fraction = nan_count / len(pcm)
    result.metrics["nan_count"] = nan_count
    result.metrics["nan_fraction"] = nan_fraction
    if nan_fraction > NAN_FRACTION_THRESHOLD:
        result.passed = False
        result.issues.append(
            f"NaN/Inf 样本占比 {nan_fraction:.2%}（阈值 {NAN_FRACTION_THRESHOLD:.2%}）"
        )

    # ---- 2. 静音检测 ----
    is_silent = peak < SILENCE_PEAK_THRESHOLD and rms < SILENCE_RMS_THRESHOLD
    if is_silent and result.duration_seconds > MIN_VALID_DURATION:
        result.passed = False
        result.issues.append(
            f"音频近乎静音 (peak={peak:.6f}, rms={rms:.6f}, dBFS={dbfs:.1f})"
        )

    # ---- 3. dBFS 检测 ----
    if dbfs != float('-inf'):
        if dbfs < DEAD_AUDIO_DBFS and result.duration_seconds > MIN_VALID_DURATION:
            result.passed = False
            result.issues.append(f"dBFS={dbfs:.1f}，低于废品阈值 {DEAD_AUDIO_DBFS}（近乎静音）")
        elif dbfs < LOW_AUDIO_DBFS:
            if strict:
                result.passed = False
                result.issues.append(f"dBFS={dbfs:.1f}，低于标准阈值 {LOW_AUDIO_DBFS}（响度偏低）")
            else:
                result.warnings.append(f"dBFS={dbfs:.1f}，响度偏低（阈值 {LOW_AUDIO_DBFS}）")
        elif strict and dbfs < NORMAL_AUDIO_DBFS:
            result.warnings.append(f"dBFS={dbfs:.1f}，响度偏软（阈值 {NORMAL_AUDIO_DBFS}）")
        elif strict and peak < LOW_PEAK_WARN:
            result.warnings.append(f"峰值偏低 peak={peak:.4f}（阈值 {LOW_PEAK_WARN}）")

    # ---- 4. 削波检测 ----
    clip_count = int(np.sum(np.abs(pcm) > 0.999))
    clip_fraction = clip_count / len(pcm)
    result.metrics["clip_count"] = clip_count
    result.metrics["clip_fraction"] = clip_fraction
    if clip_fraction > CLIPPING_FRACTION_THRESHOLD:
        result.passed = False
        result.issues.append(
            f"削波样本占比 {clip_fraction:.2%}（阈值 {CLIPPING_FRACTION_THRESHOLD:.2%}）"
        )

    # ---- 5. 时长检测 ----
    if result.duration_seconds < MIN_VALID_DURATION:
        result.passed = False
        result.issues.append(f"时长过短: {result.duration_seconds:.2f}s（阈值 {MIN_VALID_DURATION}s）")
    elif result.duration_seconds < VERY_SHORT_DURATION and peak < SILENCE_PEAK_THRESHOLD * 2:
        result.passed = False
        result.issues.append(
            f"短音频且峰值低: {result.duration_seconds:.2f}s, peak={peak:.4f}（疑似生成失败）"
        )

    # ---- 6. 截断检测 ----
    if _detect_truncation(pcm, sr, rms):
        result.passed = False
        result.issues.append(
            f"尾部疑似截断：尾部 {TRUNCATION_TAIL_MS}ms RMS 明显高于整体（音频未正常淡出）"
        )

    # ---- 7. 毛刺/爆音检测 ----
    glitch_count = _detect_glitches(pcm)
    result.metrics["glitch_count"] = glitch_count
    if glitch_count > 0:
        result.passed = False
        result.issues.append(
            f"检测到 {glitch_count} 个毛刺/爆音（相邻样本间幅度跳变 > {GLITCH_SAMPLE_JUMP}）"
        )

    # ---- 8. 连续静音检测 ----
    max_silence_sec = _detect_continuous_silence(pcm, sr)
    result.metrics["max_continuous_silence_seconds"] = max_silence_sec
    if max_silence_sec > CONTINUOUS_SILENCE_MAX_SECONDS:
        result.passed = False
        result.issues.append(
            f"检测到超过 {CONTINUOUS_SILENCE_MAX_SECONDS}s 的连续静音（最长 {max_silence_sec:.1f}s）"
        )

    # ---- 9. 持续低信号检测（杂音/底噪） ----
    max_low_sec = _detect_continuous_low_signal(pcm, sr)
    result.metrics["max_continuous_low_signal_seconds"] = max_low_sec
    if max_low_sec > CONTINUOUS_LOW_SIGNAL_MAX_SECONDS:
        result.passed = False
        result.issues.append(
            f"检测到超过 {CONTINUOUS_LOW_SIGNAL_MAX_SECONDS}s 的持续低信号/杂音"
            f"（RMS<{LOW_SIGNAL_RMS_THRESHOLD}，最长 {max_low_sec:.1f}s）"
        )

    # ---- 10. 频谱异常检测（高频杂音/低频嗡声）—— 仅 strict 模式 ----
    if strict:
        spectral_dur, spectral_type = _detect_spectral_anomaly(pcm, sr)
        result.metrics["max_spectral_anomaly_seconds"] = spectral_dur
        result.metrics["spectral_anomaly_type"] = spectral_type
        if spectral_dur > 0:
            type_desc = "高频杂音/嘶声" if spectral_type == "high" else "低频嗡声/哼声"
            result.passed = False
            result.issues.append(
                f"检测到频谱异常（{type_desc}），持续 {spectral_dur:.1f}s"
            )

    return result


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    elif size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes} B"


def print_result(result: AudioAnomalyResult, idx: int = 0, total: int = 0):
    """格式化打印单个文件的检测结果。"""
    prefix = f"[{idx}/{total}]" if total > 1 else ""
    fname = os.path.basename(result.file_path)
    status = "[FAIL]" if not result.passed else "[PASS]"

    if result.error and "无法解码" in result.error:
        print(f"  {status} {prefix} {fname}  — 文件损坏/无法解码")
    elif result.error:
        print(f"  {status} {prefix} {fname}  — {result.error}")
    else:
        dur_str = (
            f"{result.duration_seconds:.1f}s"
            if result.duration_seconds < 60
            else f"{result.duration_seconds / 60:.1f}min"
        )
        meta = (
            f"peak={result.metrics.get('peak', 0):.4f} "
            f"dBFs={result.metrics.get('dbfs', float('-inf')):.1f} "
            f"dur={dur_str} "
            f"{result.channels}ch@{int(result.sample_rate / 1000)}kHz"
        )
        print(f"  {status} {prefix} {fname}  {format_size(result.file_size_bytes)}  {meta}")

    for issue in result.issues:
        print(f"       !  {issue}")
    for warn in result.warnings:
        print(f"       i  {warn}")


def main():
    parser = argparse.ArgumentParser(
        description="音频异常检测脚本 - 检测音频文件的静音、损坏、削波、截断、毛刺等问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python check_audio_anomalies.py output/蜀山剑侠传                     # 扫描目录
  python check_audio_anomalies.py output/ --r                         # 递归扫描子目录
  python check_audio_anomalies.py output/ --format mp3                 # 只检查 mp3
  python check_audio_anomalies.py single.wav --json report.json        # 输出 JSON 报告
  python check_audio_anomalies.py output/ --strict --json result.json  # 严格模式
        """,
    )
    parser.add_argument("path", help="音频文件路径或目录路径")
    parser.add_argument("-r", "--r", action="store_true", help="递归扫描子目录")
    parser.add_argument("--format", "-f", dest="fmt_filter", help="仅检查指定格式（如 mp3、wav）")
    parser.add_argument("--json", "-j", dest="json_output", help="输出 JSON 报告到指定文件")
    parser.add_argument("--strict", "-s", action="store_true", help="严格模式（低响度也标记为异常）")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式，仅输出异常文件")
    args = parser.parse_args()

    # ---- 收集文件 ----
    files = _collect_files(args.path, args.r, args.fmt_filter)
    if not files:
        print(f"未找到音频文件。支持的格式: {', '.join(sorted(SUPPORTED_SUFFIXES))}")
        sys.exit(0)

    print(f"找到 {len(files)} 个音频文件，开始检测...\n")

    # ---- 逐文件检测 ----
    results: List[AudioAnomalyResult] = []
    for i, fpath in enumerate(files, 1):
        r = check_audio(fpath, strict=args.strict)
        results.append(r)
        if not args.quiet or not r.passed:
            print_result(r, idx=i, total=len(files))

    # ---- 汇总 ----
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print(f"\n{'=' * 55}")
    print(f"检测完成: {passed}/{total} 通过, {failed}/{total} 异常")
    if failed > 0:
        print(f"\n异常文件列表:")
        for r in results:
            if not r.passed:
                fname = os.path.basename(r.file_path)
                if r.error:
                    print(f"  FAIL  {fname} [{r.error}]")
                else:
                    print(f"  FAIL  {fname}")
                    for issue in r.issues:
                        print(f"      └ {issue}")
    print(f"{'=' * 55}")

    # ---- JSON 输出 ----
    if args.json_output:
        report = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": []
        }
        for r in results:
            entry = {
                "file": r.file_path,
                "size_bytes": r.file_size_bytes,
                "passed": r.passed,
            }
            if r.error:
                entry["error"] = r.error
            else:
                entry["duration_seconds"] = r.duration_seconds
                entry["sample_rate"] = r.sample_rate
                entry["channels"] = r.channels
                entry["metrics"] = {
                    k: (v if not isinstance(v, (np.floating, np.integer)) else v.item())
                    for k, v in r.metrics.items()
                }
            entry["issues"] = r.issues
            entry["warnings"] = r.warnings
            report["results"].append(entry)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nJSON 报告已保存到: {args.json_output}")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
