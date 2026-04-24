#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试长音频生成功能（超过47秒限制）
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stabilityai_stable_generate_audio import generate_long_audio, initialize_model, generate_audio

def test_long_audio():
    print("=" * 60)
    print("🔊 测试长音频生成功能")
    print("=" * 60)
    
    # 初始化模型
    print("\n🚀 初始化模型...")
    start_time = time.time()
    initialize_model()
    elapsed = time.time() - start_time
    print(f"✅ 模型初始化完成，耗时: {elapsed:.2f}秒")
    
    # 定义测试参数
    test_prompts = [
        "Ancient Chinese town at dusk, ambient music with bamboo flute and gentle wind chimes, peaceful atmosphere",
        "Quiet night with stars, soft traditional Chinese instrumental music, calming and serene",
        "Mysterious ancient forest, ambient sounds with distant bird calls and rustling leaves"
    ]
    
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_long_audio_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # 测试生成长音频
    for i, prompt in enumerate(test_prompts):
        print(f"\n📝 测试 {i+1}/{len(test_prompts)}")
        print(f"提示词: {prompt[:50]}...")
        
        output_path = os.path.join(output_dir, f"test_long_audio_{i+1}.wav")
        
        start_time = time.time()
        try:
            result_path = generate_long_audio(
                prompt=prompt,
                duration=120,  # 120秒 = 2分钟
                output_path=output_path
            )
            
            if result_path and os.path.exists(result_path):
                elapsed = time.time() - start_time
                file_size = os.path.getsize(result_path) / (1024 * 1024)  # MB
                print(f"✅ 测试成功！")
                print(f"   输出文件: {result_path}")
                print(f"   文件大小: {file_size:.2f} MB")
                print(f"   耗时: {elapsed:.2f}秒")
            else:
                print(f"❌ 测试失败：未生成文件")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ 测试失败: {e}")
            print(f"   耗时: {elapsed:.2f}秒")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_long_audio()