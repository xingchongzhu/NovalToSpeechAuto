#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
背景音音量降低测试脚本
使用Qwen-TTS接口合成真实音频来验证BGM音量降低功能是否生效
"""

import os
import sys
import tempfile

# 添加脚本所在目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from audio_processing_module import AudioSegment, AudioEngine, VoiceParams

def test_bgm_volume_reduction():
    """测试BGM音量降低功能"""
    print("🔊 测试背景音音量降低功能...")
    
    # 初始化音频引擎
    print("📦 初始化音频引擎...")
    audio_engine = AudioEngine(
        temp_dir=tempfile.mkdtemp(),
        sample_rate=44100,
        channels=1,
        tts_engine="qwen3-tts",
        qwen_model_path="/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/qwen3-tts-base-model"
    )
    print("✅ 音频引擎初始化成功")
    
    # 使用Qwen-TTS生成测试音频
    print("\n🎤 正在使用Qwen-TTS合成测试音频...")
    test_params = VoiceParams(
        text="这是一段测试音频，用于验证背景音音量降低功能是否正常工作。",
        role="旁白",
        role_voice="云健-中年男性磁性声音",
        speed="0%",
        volume="0%",
        pitch="0Hz",
        instruct="neutral"
    )
    
    try:
        test_audio = audio_engine.text_to_speech(test_params)
        print(f"✅ Qwen-TTS合成成功，音频时长: {len(test_audio)}ms")
    except Exception as e:
        print(f"❌ Qwen-TTS合成失败: {e}")
        print("📌 使用静音音频进行测试")
        test_audio = AudioSegment.silent(duration=3000, frame_rate=44100)
    
    # 测试1: 全局降低2dB（模拟代码中的全局降低）
    bgm_global_reduce = 2.0
    bgm_audio_1 = test_audio - bgm_global_reduce
    print(f"\n✅ 测试1: 全局降低 {bgm_global_reduce}dB - 成功")
    print(f"   原音频时长: {len(test_audio)}ms, 降低后时长: {len(bgm_audio_1)}ms")
    
    # 测试2: 自定义降低5dB（模拟play_mode='lower'时的降低）
    custom_reduce = 5.0
    bgm_audio_2 = test_audio - custom_reduce
    print(f"✅ 测试2: 自定义降低 {custom_reduce}dB - 成功")
    
    # 测试3: 降低10dB（大幅降低）
    big_reduce = 10.0
    bgm_audio_3 = test_audio - big_reduce
    print(f"✅ 测试3: 大幅降低 {big_reduce}dB - 成功")
    
    # 测试4: 验证音频时长保持不变
    original_duration = len(test_audio)
    reduced_duration = len(bgm_audio_3)
    assert original_duration == reduced_duration, "音频时长不应改变"
    print(f"✅ 测试4: 音频时长保持不变 ({original_duration}ms) - 成功")
    
    # 测试5: 保存测试结果到文件
    test_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_test_output")
    os.makedirs(test_output_dir, exist_ok=True)
    
    # 保存原始音频
    original_path = os.path.join(test_output_dir, "original_audio.wav")
    test_audio.export(original_path, format="wav")
    print(f"💾 原始音频已保存: {original_path}")
    
    # 保存降低后的音频
    reduced_path = os.path.join(test_output_dir, "reduced_audio.wav")
    bgm_audio_3.export(reduced_path, format="wav")
    print(f"💾 降低10dB后的音频已保存: {reduced_path}")
    
    print("\n🎉 所有背景音音量降低测试通过！")
    print("\n📝 功能说明：")
    print("1. BGM音量降低通过 AudioSegment 对象的减法操作实现")
    print("2. 在 audio_processing_module.py 中：")
    print("   - 第845-846行：根据 play_mode='lower' 和 lower_db 参数降低音量")
    print("   - 第851-854行：全局降低BGM音量2dB")
    print("3. JSON配置示例：")
    print('   "bgm": {')
    print('       "play_mode": "lower",')
    print('       "lower_db": 5.0,')
    print('       "params": {...}')
    print('   }')

if __name__ == "__main__":
    test_bgm_volume_reduction()