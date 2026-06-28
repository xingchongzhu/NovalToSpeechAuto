#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Quality Checker — 基础信号级质量检测
=========================================
在音频生成后、混入最终产物前，对生成物做快速的质量检查。
纯信号处理，无需 GPU，几毫秒内完成。

检测项：
- 静音/近乎静音
- NaN/Inf 值
- 过度削波/饱和
- 时长异常（过短/过长）
- 有效响度过低

仅用于拦截「完全不合格」的音频，不做语义级别判断。
"""

import os
import numpy as np
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class AudioQualityResult:
    """单次检测结果"""
    file_path: str
    passed: bool = False
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


# ============================================================
# 默认阈值配置
# ============================================================

# 静音检测
SILENCE_PEAK_THRESHOLD = 0.005          # 峰值低于此 → 静音
SILENCE_RMS_THRESHOLD = 0.0005          # RMS 低于此 → 静音

# dBFS
DEAD_AUDIO_DBFS = -48.0                 # dBFS 低于此 → 废品
LOW_AUDIO_DBFS = -36.0                  # dBFS 低于此 → 不合格（报警但不丢弃）

# NaN/Inf
NAN_FRACTION_THRESHOLD = 0.01           # 超过 1% 样本是 NaN/Inf → 不合格

# 削波检测
CLIPPING_FRACTION_THRESHOLD = 0.05      # 超过 5% 样本在 0dB 削波 → 不合格

# 时长检测（相对于预期时长的偏差）
DURATION_MIN_RATIO = 0.5                # 实际时长 < 预期 * 0.5 → 过短
DURATION_MAX_RATIO = 2.0                # 实际时长 > 预期 * 2.0 → 过长

# 最小有效时长（秒），低于此值即使无声也不报警（如极短砰声）
MIN_VALID_DURATION = 0.3


def _read_wav_pcm(file_path: str) -> Tuple[Optional[np.ndarray], int]:
    """
    读取 WAV 文件的原始 PCM / FLOAT 数据，通过遍历 RIFF 子块定位 fmt/data。
    返回 (mono_abs_pcm, sample_rate) 或 (None, 0)。
    """
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
            f.read(4)  # 跳过文件大小
            wave_id = f.read(4)
            if wave_id != b'WAVE':
                return None, 0

            fmt_tag = 1          # 默认 PCM
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
                    # WAVE_FORMAT_EXTENSIBLE: real fmt_tag is in the extension
                    if fmt_tag == 0xFFFE:
                        fmt_tag = 3  # treat EXTENSIBLE as FLOAT for safety
                elif chunk_id == b'data':
                    data_bytes = f.read(chunk_size)
                    break
                else:
                    # 跳过未知 / fact / LIST 等子块
                    f.seek(chunk_size, 1)

        if len(data_bytes) == 0 or sample_rate == 0:
            return None, 0

        is_float = (fmt_tag == 3)  # IEEE_FLOAT
        effective_bps = 32 if is_float else bits_per_sample

        # ---------- 转换为 float32 ----------
        if is_float:
            pcm = np.frombuffer(data_bytes, dtype=np.float32)
        elif effective_bps == 16:
            pcm = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32)
            pcm /= 32768.0
        elif effective_bps == 24:
            sample_count = len(data_bytes) // 3
            data_bytes = data_bytes[:sample_count * 3]
            padded = np.frombuffer(data_bytes + b'\x00' * sample_count, dtype='<i4')
            padded = padded >> 8
            pcm = padded.astype(np.float32) / 8388608.0
        elif effective_bps == 32:
            pcm = np.frombuffer(data_bytes, dtype=np.int32).astype(np.float32)
            pcm /= 2147483648.0
        elif effective_bps == 8:
            pcm = np.frombuffer(data_bytes, dtype=np.uint8).astype(np.float32)
            pcm = (pcm / 128.0) - 1.0
        else:
            return None, 0

        # 多声道 → 取第一声道用于质量检测
        if channels > 1:
            pcm = pcm.reshape(-1, channels)[:, 0]

        return pcm, sample_rate

    except Exception:
        return None, 0


def check_audio_quality(
    file_path: str,
    expected_duration: Optional[float] = None,
    silence_peak_threshold: float = SILENCE_PEAK_THRESHOLD,
    silence_rms_threshold: float = SILENCE_RMS_THRESHOLD,
    dead_db: float = DEAD_AUDIO_DBFS,
    low_db: float = LOW_AUDIO_DBFS,
) -> AudioQualityResult:
    """
    对单个音频文件执行基础质量检测。

    Args:
        file_path: WAV 文件路径
        expected_duration: 预期时长（秒），用于检测生成时长是否异常
        silence_peak_threshold: 静音峰值阈值
        silence_rms_threshold: 静音 RMS 阈值
        dead_db: 低于此 dBFS 视为废品
        low_db: 低于此 dBFS 报警

    Returns:
        AudioQualityResult 包含检测结果
    """
    result = AudioQualityResult(file_path=file_path)

    pcm, sr = _read_wav_pcm(file_path)

    if pcm is None or sr == 0:
        result.passed = False
        result.issues.append("文件读取失败或格式异常")
        result.checks_failed.append("file_read")
        return result

    actual_duration = len(pcm) / sr

    # ============================================================
    # 1. NaN/Inf 检测
    # ============================================================
    nan_count = int(np.sum(~np.isfinite(pcm)))
    nan_fraction = nan_count / len(pcm) if len(pcm) > 0 else 0

    if nan_fraction > NAN_FRACTION_THRESHOLD:
        result.passed = False
        result.issues.append(f"NaN/Inf 样本占 {nan_fraction:.2%}，超过阈值 {NAN_FRACTION_THRESHOLD:.2%}")
        result.checks_failed.append("nan_inf")
    else:
        result.checks_passed.append("nan_inf")

    result.metrics["nan_count"] = nan_count
    result.metrics["nan_fraction"] = nan_fraction

    # ============================================================
    # 2. 静音检测
    # ============================================================
    peak = float(np.max(np.abs(pcm))) if len(pcm) > 0 else 0.0
    rms = float(np.sqrt(np.mean(pcm ** 2))) if len(pcm) > 0 else 0.0

    is_silent = peak < silence_peak_threshold and rms < silence_rms_threshold

    if is_silent and actual_duration > MIN_VALID_DURATION:
        result.passed = False
        result.issues.append(
            f"音频近乎静音 peak={peak:.6f} (阈值 {silence_peak_threshold}), "
            f"rms={rms:.6f} (阈值 {silence_rms_threshold})"
        )
        result.checks_failed.append("silence")
    else:
        result.checks_passed.append("silence")

    result.metrics["peak"] = peak
    result.metrics["rms"] = rms

    # ============================================================
    # 3. dBFS 检测
    # ============================================================
    if peak > 0:
        dbfs = 20.0 * np.log10(peak)
    else:
        dbfs = float('-inf')

    if dbfs != float('-inf') and dbfs < dead_db and actual_duration > MIN_VALID_DURATION:
        result.passed = False
        result.issues.append(f"dBFS={dbfs:.1f} 低于废品阈值 {dead_db}")
        result.checks_failed.append("dead_audio")
    elif dbfs != float('-inf') and dbfs < low_db:
        # 不直接标记失败，但记录为警告
        result.issues.append(f"dBFS={dbfs:.1f} 低于警告阈值 {low_db}")
        result.checks_passed.append("dbfs_low")
    else:
        result.checks_passed.append("dbfs")

    result.metrics["dbfs"] = dbfs

    # ============================================================
    # 4. 削波检测
    # ============================================================
    clip_count = int(np.sum(np.abs(pcm) > 0.999))
    clip_fraction = clip_count / len(pcm) if len(pcm) > 0 else 0

    if clip_fraction > CLIPPING_FRACTION_THRESHOLD:
        result.passed = False
        result.issues.append(f"削波样本占 {clip_fraction:.2%}，超过阈值 {CLIPPING_FRACTION_THRESHOLD:.2%}")
        result.checks_failed.append("clipping")
    else:
        result.checks_passed.append("clipping")

    result.metrics["clip_count"] = clip_count
    result.metrics["clip_fraction"] = clip_fraction

    # ============================================================
    # 5. 时长检测（仅当提供 expected_duration 时）
    # ============================================================
    if expected_duration is not None and expected_duration > 0:
        duration_ratio = actual_duration / expected_duration
        result.metrics["expected_duration"] = expected_duration
        result.metrics["actual_duration"] = actual_duration
        result.metrics["duration_ratio"] = duration_ratio

        if duration_ratio < DURATION_MIN_RATIO and actual_duration < 0.5:
            # 极短音频，可能是生成失败
            result.passed = False
            result.issues.append(
                f"时长过短: 实际 {actual_duration:.1f}s, 预期 {expected_duration:.1f}s "
                f"(ratio {duration_ratio:.2f} < {DURATION_MIN_RATIO})"
            )
            result.checks_failed.append("duration_too_short")
        else:
            result.checks_passed.append("duration")

    result.metrics["actual_duration"] = actual_duration

    # 如果没有失败的检查项且 passed 仍为 True
    if not result.checks_failed:
        result.passed = True

    return result


def check_audio_batch(
    file_paths: List[str],
    expected_durations: Optional[List[Optional[float]]] = None,
    descriptions: Optional[List[str]] = None,
) -> List[AudioQualityResult]:
    """
    批量检测多个音频文件。

    Args:
        file_paths: WAV 文件路径列表
        expected_durations: 各文件预期时长列表（可选）
        descriptions: 各文件描述（可选，用于日志）

    Returns:
        AudioQualityResult 列表
    """
    results = []
    for i, path in enumerate(file_paths):
        exp_dur = expected_durations[i] if expected_durations else None
        desc = descriptions[i] if descriptions else os.path.basename(path)

        r = check_audio_quality(path, expected_duration=exp_dur)
        results.append(r)

        status = "✅" if r.passed else "❌"
        issues_str = "; ".join(r.issues) if r.issues else "无问题"
        print(f"  {status} [{desc}] "
              f"peak={r.metrics.get('peak', '?'):.4f} "
              f"rms={r.metrics.get('rms', '?'):.6f} "
              f"dBFs={r.metrics.get('dbfs', '?'):.1f} "
              f"dur={r.metrics.get('actual_duration', '?'):.1f}s "
              f"— {issues_str}")

    return results


def summary(results: List[AudioQualityResult]) -> Tuple[int, int]:
    """
    打印汇总并返回 (通过数, 失败数)。
    """
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print(f"\n{'='*50}")
    print(f"音频质量检测汇总: {passed}/{total} 通过, {failed}/{total} 失败")
    if failed > 0:
        print(f"\n失败项详情:")
        for r in results:
            if not r.passed:
                print(f"  ❌ {os.path.basename(r.file_path)}")
                for issue in r.issues:
                    print(f"     └ {issue}")
    print(f"{'='*50}")

    return passed, failed


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python audio_quality_checker.py <wav_file> [expected_duration]")
        sys.exit(1)

    path = sys.argv[1]
    expected = float(sys.argv[2]) if len(sys.argv) > 2 else None

    result = check_audio_quality(path, expected_duration=expected)
    summary([result])
