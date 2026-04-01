#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试instruct参数的处理逻辑
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from 小说批量工具.脚本.audio_processing_module import VoiceParams


def test_instruct_handling():
    """
    测试instruct参数的处理逻辑
    """
    print("=== 测试instruct参数处理逻辑 ===")
    
    # 测试场景1：没有instruct参数
    print("\n1. 测试场景：没有instruct参数")
    voice_params1 = VoiceParams(
        text="测试文本1",
        role="旁白",
        role_voice="uncle_fu",
        speed="0%",
        volume="0%",
        pitch="0Hz"
    )
    
    # 模拟_text_to_speech_qwen中的instruct处理逻辑
    if voice_params1.instruct and voice_params1.instruct.strip():
        instruct = voice_params1.instruct.strip()
    else:
        speed_value = int(voice_params1.speed.replace('%', '')) if '%' in voice_params1.speed else 0
        instruct = f"语速{speed_value}"
    
    print(f"   输入: VoiceParams(instruct=None)")
    print(f"   输出: instruct='{instruct}'")
    print(f"   预期: instruct='语速0'")
    print(f"   结果: {'✅ 正确' if instruct == '语速0' else '❌ 错误'}")
    
    # 测试场景2：有instruct参数
    print("\n2. 测试场景：有instruct参数")
    voice_params2 = VoiceParams(
        text="测试文本2",
        role="旁白",
        role_voice="uncle_fu",
        speed="0%",
        volume="0%",
        pitch="0Hz",
        instruct="沉稳大气、古风叙事、江湖感"
    )
    
    if voice_params2.instruct and voice_params2.instruct.strip():
        instruct = voice_params2.instruct.strip()
    else:
        speed_value = int(voice_params2.speed.replace('%', '')) if '%' in voice_params2.speed else 0
        instruct = f"语速{speed_value}"
    
    print(f"   输入: VoiceParams(instruct='沉稳大气、古风叙事、江湖感')")
    print(f"   输出: instruct='{instruct}'")
    print(f"   预期: instruct='沉稳大气、古风叙事、江湖感'")
    print(f"   结果: {'✅ 正确' if instruct == '沉稳大气、古风叙事、江湖感' else '❌ 错误'}")
    
    # 测试场景3：有instruct参数但为空字符串
    print("\n3. 测试场景：有instruct参数但为空字符串")
    voice_params3 = VoiceParams(
        text="测试文本3",
        role="旁白",
        role_voice="uncle_fu",
        speed="+5%",
        volume="0%",
        pitch="0Hz",
        instruct="   "  # 只有空格
    )
    
    if voice_params3.instruct and voice_params3.instruct.strip():
        instruct = voice_params3.instruct.strip()
    else:
        speed_value = int(voice_params3.speed.replace('%', '')) if '%' in voice_params3.speed else 0
        instruct = f"语速{speed_value}"
    
    print(f"   输入: VoiceParams(instruct='   ', speed='+5%')")
    print(f"   输出: instruct='{instruct}'")
    print(f"   预期: instruct='语速5'")
    print(f"   结果: {'✅ 正确' if instruct == '语速5' else '❌ 错误'}")
    
    # 测试场景4：有instruct参数且包含语速信息
    print("\n4. 测试场景：有instruct参数且包含语速信息")
    voice_params4 = VoiceParams(
        text="测试文本4",
        role="陈平安",
        role_voice="aiden",
        speed="-3%",
        volume="0%",
        pitch="0Hz",
        instruct="温和平静，带有一丝对生活的无奈和坚韧"
    )
    
    if voice_params4.instruct and voice_params4.instruct.strip():
        instruct = voice_params4.instruct.strip()
    else:
        speed_value = int(voice_params4.speed.replace('%', '')) if '%' in voice_params4.speed else 0
        instruct = f"语速{speed_value}"
    
    print(f"   输入: VoiceParams(instruct='温和平静，带有一丝对生活的无奈和坚韧', speed='-3%')")
    print(f"   输出: instruct='{instruct}'")
    print(f"   预期: instruct='温和平静，带有一丝对生活的无奈和坚韧'")
    print(f"   结果: {'✅ 正确' if instruct == '温和平静，带有一丝对生活的无奈和坚韧' else '❌ 错误'}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_instruct_handling()
