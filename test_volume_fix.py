#!/usr/bin/env python3
"""
测试音量修复脚本
"""

import sys
import os
from pydub import AudioSegment

# 添加项目路径
sys.path.append('/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/脚本')

from audio_processing_module import AudioEngine

def test_volume_adjustment():
    """测试音量调整逻辑"""
    print("=== 测试音量修复 ===")
    
    # 1. 使用之前生成的测试BGM
    test_file = '/tmp/test_bgm.wav'
    if not os.path.exists(test_file):
        print("错误：测试文件不存在")
        return False
    
    # 2. 创建AudioEngine实例
    audio_engine = AudioEngine()
    
    # 3. 读取原始音频
    original_audio = AudioSegment.from_wav(test_file)
    print(f"原始音频时长: {len(original_audio)}ms")
    print(f"原始音频音量范围: {original_audio.dBFS:.2f} dBFS")
    
    # 4. 测试修复后的音量调整（使用-18%音量，这是配置文件中常用的设置）
    test_volume = "-18%"
    adjusted_audio = audio_engine._adjust_audio_params(original_audio, "+0%", test_volume, "+0Hz")
    
    print(f"调整后音频音量范围: {adjusted_audio.dBFS:.2f} dBFS")
    print(f"应用的音量参数: {test_volume}")
    
    # 5. 保存调整后的音频用于听测
    output_file = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/test_bgm_adjusted.wav'
    adjusted_audio.export(output_file, format='wav')
    print(f"调整后的音频已保存到: {output_file}")
    
    # 6. 验证音频不是静音
    if adjusted_audio.rms < 1:
        print("❌ 错误：调整后的音频接近静音")
        return False
    else:
        print("✅ 成功：调整后的音频有正常音量")
        return True

if __name__ == "__main__":
    test_volume_adjustment()
