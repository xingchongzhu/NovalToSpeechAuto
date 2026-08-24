#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比 SenseVoice 和 Whisper 的识别效果
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "novel_tool" / "scripts"))
from asr_prefix_detector import transcribe_audio, detect_and_trim_prefix
import numpy as np
import wave

# 测试音频文件
test_files = [
    "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/output/蜀山剑侠转json/蜀山剑侠传第197回-第197回/配音/voice_line_2.wav",
    "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/output/蜀山剑侠转json/蜀山剑侠传第220回-第220回/配音/voice_line_1.wav",
    "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/output/蜀山剑侠转json/蜀山剑侠传第220回-第220回/配音/voice_line_2.wav",
]

project_root = Path(__file__).parent

print("=" * 80)
print("ASR 模型对比测试")
print("=" * 80)
print(f"{'文件':<50} {'模型':<12} {'耗时':<8} {'识别结果'}")
print("-" * 80)

for audio_file in test_files:
    if not Path(audio_file).exists():
        continue
    
    file_name = Path(audio_file).name
    
    # 读取音频
    with wave.open(audio_file, 'rb') as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        audio_bytes = wf.readframes(wf.getnframes())
    
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    if n_channels == 2:
        audio_int16 = audio_int16.reshape(-1, 2)
    audio_array = audio_int16.astype(np.float32) / 32767.0
    
    # 测试 SenseVoice
    start = time.time()
    result_sv = transcribe_audio(audio_file, project_root=project_root, asr_model="sensevoice")
    elapsed_sv = time.time() - start
    text_sv = result_sv["transcription"][0]["text"] if result_sv and result_sv["transcription"] else "识别失败"
    
    # 测试 Whisper
    start = time.time()
    result_wh = transcribe_audio(audio_file, project_root=project_root, asr_model="whisper")
    elapsed_wh = time.time() - start
    text_wh = result_wh["transcription"][0]["text"] if result_wh and result_wh["transcription"] else "识别失败"
    
    print(f"{file_name:<50} {'SenseVoice':<12} {elapsed_sv:>6.2f}s  {text_sv[:40]}")
    print(f"{'':<50} {'Whisper':<12} {elapsed_wh:>6.2f}s  {text_wh[:40]}")
    print("-" * 80)

print("\n检测 '话说' 前缀对比:")
print("=" * 80)
print(f"{'文件':<50} {'模型':<12} {'耗时':<8} {'裁剪时长':<10} {'检测到的文本'}")
print("-" * 80)

for audio_file in test_files[:2]:  # 只测试前2个
    if not Path(audio_file).exists():
        continue
    
    file_name = Path(audio_file).name
    
    # 读取音频
    with wave.open(audio_file, 'rb') as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        audio_bytes = wf.readframes(wf.getnframes())
    
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    if n_channels == 2:
        audio_int16 = audio_int16.reshape(-1, 2)
    audio_array = audio_int16.astype(np.float32) / 32767.0
    orig_len = len(audio_array) / sr
    
    # SenseVoice 检测
    start = time.time()
    trimmed_sv = detect_and_trim_prefix(audio_array.copy(), sr, prefix_text='话说，', 
                                        project_root=project_root, asr_model='sensevoice')
    elapsed_sv = time.time() - start
    trimmed_len_sv = (len(audio_array) - len(trimmed_sv)) / sr if len(trimmed_sv) < len(audio_array) else 0
    
    # Whisper 检测
    start = time.time()
    trimmed_wh = detect_and_trim_prefix(audio_array.copy(), sr, prefix_text='话说，', 
                                        project_root=project_root, asr_model='whisper')
    elapsed_wh = time.time() - start
    trimmed_len_wh = (len(audio_array) - len(trimmed_wh)) / sr if len(trimmed_wh) < len(audio_array) else 0
    
    print(f"{file_name:<50} {'SenseVoice':<12} {elapsed_sv:>6.2f}s  {trimmed_len_sv:>6.2f}s    {'是' if trimmed_len_sv > 0 else '否'}")
    print(f"{'':<50} {'Whisper':<12} {elapsed_wh:>6.2f}s  {trimmed_len_wh:>6.2f}s    {'是' if trimmed_len_wh > 0 else '否'}")
    print("-" * 80)

print("\n测试完成!")
