#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试"的"字多音字处理"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'novel_tool', 'scripts'))

from polyphone_processor import process_polyphone_text

def test_de_character():
    print("=" * 60)
    print("测试\"的\"字多音字处理")
    print("=" * 60)
    
    # 直接替换为拼音，没有方括号
    test_cases = [
        # de 轻声 - 定语标志
        ("我的名字是小明。", "我de名字是小明。"),
        ("红色的苹果。", "红色de苹果。"),
        ("他的书。", "他de书。"),
        
        # de 轻声 - 状语标志"地"
        ("高兴地说。", "高兴de说。"),
        ("慢慢地走。", "慢慢de走。"),
        ("认真地学习。", "认真de学习。"),
        
        # dí 第二声 - 确实
        ("的确是这样。", "dí确是这样。"),
        ("的当处理。", "dí当处理。"),
        
        # dì 第四声 - 目的
        ("他的目的是什么？", "他de目dì是什么？"),
        ("目的明确。", "目dì明确。"),
        ("众矢之的。", "众矢之dì。"),
        ("无的放矢。", "无dì放矢。"),
        
        # 混合场景
        ("我的目的是完成任务。", "我de目dì是完成任务。"),
        ("的确是他的错。", "dí确是他de错。"),
        ("他高兴地说的确是这样的。", "他高兴de说dí确是这样de。"),
    ]
    
    all_pass = True
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = process_polyphone_text(input_text)
        has_bracket = '[' in result or ']' in result
        status = "✅" if result == expected and not has_bracket else "❌"
        if result != expected or has_bracket:
            all_pass = False
        
        print(f"\n案例 {i}:")
        print(f"  原文: {input_text}")
        print(f"  期望: {expected}")
        print(f"  实际: {result}")
        print(f"  {status}")
        if has_bracket:
            print(f"  ⚠️ 包含方括号")
    
    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败！")
    print("=" * 60)
    
    return all_pass

if __name__ == "__main__":
    test_de_character()