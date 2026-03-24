#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试音量调整逻辑修复效果
"""

import os
from pydub import AudioSegment

# 测试音量调整函数
def test_volume_adjustment():
    # 模拟 AudioEngine 类中的 _adjust_audio_params 方法
    def adjust_volume(audio, volume_str):
        """
        调整音频音量
        :param audio: AudioSegment 对象
        :param volume_str: 音量百分比字符串（如 "-18%"）
        :return: 调整后的 AudioSegment 对象
        """
        # 解析音量百分比
        vol_value = float(volume_str.replace("%", ""))
        
        # 音量过低时返回静音
        if vol_value < -50:
            return AudioSegment.silent(duration=len(audio), frame_rate=audio.frame_rate)
        
        # 改进的音量转换逻辑
        if vol_value >= 0:
            gain_db = vol_value
        else:
            # 使用对数转换，让负数音量降低更自然
            # 公式：gain_db = vol_value / 3.333
            # 这样-18% → 约-5.4dB，而不是之前的-18dB
            gain_db = vol_value / 3.333
        
        print(f"音量百分比: {volume_str}")
        print(f"计算的dB增益: {gain_db}")
        
        return audio + gain_db
    
    # 创建一个有声音的测试音频（使用pydub生成正弦波）
    print("创建测试音频...")
    from pydub.generators import Sine
    
    # 创建一个2秒的440Hz正弦波
    sine_wave = Sine(440, sample_rate=44100)
    test_audio = sine_wave.to_audio_segment(duration=2000).apply_gain(-10)  # -10dB 基础音量
    
    # 测试不同音量值
    test_volumes = ["-50%", "-18%", "-10%", "0%", "+10%"]
    
    for volume in test_volumes:
        print(f"\n=== 测试音量: {volume} ===")
        
        # 调整音量
        adjusted_audio = adjust_volume(test_audio, volume)
        
        # 保存调整后的音频
        output_file = f"test_audio_{volume.replace('%', '').replace('+', '').replace('-', 'minus')}.wav"
        adjusted_audio.export(output_file, format="wav")
        
        print(f"✅ 已保存调整后音频: {output_file}")
        print(f"   文件大小: {os.path.getsize(output_file)} 字节")
    
    print(f"\n🎉 测试完成！")
    print("生成的测试文件可以用音频播放器验证音量差异")
    
    # 清理测试文件
    print("\n清理测试文件...")
    for volume in test_volumes:
        output_file = f"test_audio_{volume.replace('%', '').replace('+', '').replace('-', 'minus')}.wav"
        if os.path.exists(output_file):
            os.remove(output_file)
            print(f"✅ 已删除: {output_file}")

if __name__ == "__main__":
    test_volume_adjustment()
