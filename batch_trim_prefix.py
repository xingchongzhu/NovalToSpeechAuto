#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量检测并裁剪音频中的"话说"前缀
优化版：预加载模型，单进程处理所有文件
"""

import os
import sys
import wave
import time
import numpy as np
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent / "novel_tool" / "scripts"))

# 先预加载模型
print("=" * 80)
print("预加载 ASR 模型...")
print("=" * 80)
start_time = time.time()

from asr_prefix_detector import get_sensevoice_model, detect_and_trim_prefix
model = get_sensevoice_model()
if model is None:
    print("模型加载失败，退出")
    sys.exit(1)

print(f"模型加载完成，耗时: {time.time() - start_time:.2f}s")
print()


def process_audio_file(audio_path: Path, project_root: Path) -> tuple:
    """
    处理单个音频文件，检测并裁剪前缀

    Returns:
        (success, trimmed, message, elapsed_time)
        - success: 是否成功处理
        - trimmed: 是否裁剪了前缀
        - message: 处理结果信息
        - elapsed_time: 处理耗时（秒）
    """
    start_time = time.time()
    try:
        # 读取音频
        with wave.open(str(audio_path), 'rb') as wf:
            n_channels = wf.getnchannels()
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            audio_bytes = wf.readframes(n_frames)

        # 转换为 numpy 数组
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        if n_channels == 2:
            audio_int16 = audio_int16.reshape(-1, 2)
        audio_array = audio_int16.astype(np.float32) / 32767.0

        # 检测并裁剪前缀（使用预加载的模型）
        trimmed_audio = detect_and_trim_prefix(
            audio_array, sr, prefix_text='话说，', project_root=project_root,
            asr_model='sensevoice'  # 使用 SenseVoice
        )

        elapsed = time.time() - start_time

        # 检查是否裁剪了
        if len(trimmed_audio) < len(audio_array):
            trimmed_samples = len(audio_array) - len(trimmed_audio)
            trimmed_time = trimmed_samples / sr

            # 保存裁剪后的音频（覆盖原文件，先备份）
            backup_path = audio_path.with_suffix('.wav.backup')
            audio_path.rename(backup_path)

            # 写入裁剪后的音频
            trimmed_int16 = (np.clip(trimmed_audio, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(str(audio_path), 'wb') as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(trimmed_int16.tobytes())

            # 删除备份
            backup_path.unlink()

            return True, True, f"裁剪 {trimmed_time:.2f}s", elapsed
        else:
            return True, False, "无前缀", elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        return False, False, f"错误: {e}", elapsed


def batch_process_directory(base_dir: Path, project_root: Path):
    """批量处理目录下的所有配音音频"""

    # 查找所有配音目录
    dubbing_dirs = list(base_dir.glob("*/配音"))

    total_files = 0
    for dubbing_dir in dubbing_dirs:
        total_files += len(list(dubbing_dir.glob("*.wav")))

    print(f"找到 {len(dubbing_dirs)} 个配音目录，共 {total_files} 个音频文件")
    print(f"项目根目录: {project_root}")
    print("-" * 100)
    print(f"{'序号':<6} {'文件路径':<70} {'耗时':<10} {'结果'}")
    print("-" * 100)

    processed = 0
    trimmed = 0
    errors = 0
    total_elapsed = 0

    idx = 0
    for dubbing_dir in sorted(dubbing_dirs):
        chapter_name = dubbing_dir.parent.name

        for audio_file in sorted(dubbing_dir.glob("*.wav")):
            idx += 1
            success, was_trimmed, message, elapsed = process_audio_file(
                audio_file, project_root
            )

            # 实时打印处理信息
            rel_path = str(audio_file.relative_to(project_root))
            # 截断路径如果太长
            if len(rel_path) > 68:
                rel_path = "..." + rel_path[-65:]
            print(f"{idx:<6} {rel_path:<70} {elapsed:>6.2f}s   {message}", flush=True)

            if success:
                processed += 1
                if was_trimmed:
                    trimmed += 1
            else:
                errors += 1

            total_elapsed += elapsed

    print("-" * 100)
    print(f"处理完成:")
    print(f"  - 总文件数: {total_files}")
    print(f"  - 成功处理: {processed}")
    print(f"  - 裁剪前缀: {trimmed}")
    print(f"  - 处理失败: {errors}")
    print(f"  - 总耗时: {total_elapsed:.2f}s ({total_elapsed/60:.2f}min)")
    if total_files > 0:
        print(f"  - 平均耗时: {total_elapsed/total_files:.2f}s/文件")


if __name__ == "__main__":
    # 项目根目录
    project_root = Path(__file__).parent

    # 蜀山剑侠转json 目录
    base_dir = project_root / "output" / "蜀山剑侠转json"

    if not base_dir.exists():
        print(f"目录不存在: {base_dir}")
        sys.exit(1)

    batch_process_directory(base_dir, project_root)
