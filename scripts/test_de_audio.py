#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试"的"字多音字音频合成效果"""

import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'novel_tool', 'scripts'))

from audio_processing_module import AudioEngine, VoiceParams

OUTPUT_DIR = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/temp_audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_audio(audio, filename):
    """保存音频到指定目录"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    audio.export(filepath, format="wav")
    print(f"💾 音频已保存: {filepath}")
    return filepath

def test_de_audio():
    print("=" * 60)
    print("测试\"的\"字多音字音频合成")
    print("=" * 60)
    
    audio_engine = AudioEngine()
    
    test_cases = [
        ("de_test_1.wav", "我的名字是小明。", "定语标志 de"),
        ("de_test_2.wav", "红色的苹果很好吃。", "定语标志 de"),
        ("de_test_3.wav", "他高兴地说。", "状语标志 地 de"),
        ("de_test_4.wav", "慢慢地走过去。", "状语标志 地 de"),
        ("de_test_5.wav", "的确是这样的。", "的确 dí"),
        ("de_test_6.wav", "他的目的是什么？", "目的 dì"),
        ("de_test_7.wav", "众矢之的。", "众矢之的 dì"),
        ("de_test_8.wav", "无的放矢。", "无的放矢 dì"),
        ("de_test_9.wav", "我的目的是完成任务。", "混合: de + dì"),
        ("de_test_10.wav", "他高兴地说的确是这样的。", "混合: 地de + dí + 的de"),
    ]
    
    for filename, text, description in test_cases:
        print(f"\n📝 测试: {description}")
        print(f"   文本: {text}")
        
        params = VoiceParams(
            text=text,
            role="旁白",
            role_voice="温润学者-磁性,浑厚",
            speed="+0%",
            volume="+0%",
            pitch="+0Hz"
        )
        
        try:
            start_time = time.time()
            audio = audio_engine.text_to_speech(params)
            elapsed = time.time() - start_time
            
            save_audio(audio, filename)
            print(f"   ⏱️ 耗时: {elapsed:.2f} 秒")
            print(f"   ✅ 成功")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试完成！音频已保存到: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    test_de_audio()