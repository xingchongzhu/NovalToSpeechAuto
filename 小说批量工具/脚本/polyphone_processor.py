#!/usr/bin/env python3
"""多音字处理模块 - 支持中文后拼音标注格式"""

import re


def process_polyphone_text(text: str) -> str:
    """处理多音字标注文本
    
    输入格式: "他在银行[háng]工作，行[xíng]事低调。"
    输出格式: "他在银háng工作，xíng事低调。"
    
    处理逻辑:
    1. 识别 "汉字[pinyin]" 模式
    2. 将汉字替换为拼音（删除方括号）
    3. 保持其他文本不变
    
    Args:
        text: 原始文本，可能包含多音字标注
        
    Returns:
        处理后的文本，拼音替换汉字
    """
    # 正则模式: 匹配 "汉字[拼音]" 格式
    # [\u4e00-\u9fa5] 匹配单个汉字
    # \[([a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z]+)\] 匹配方括号内的拼音
    pattern = r'[\u4e00-\u9fa5]\[([a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z]+)\]'
    
    # 替换为拼音（只保留拼音，删除汉字和方括号）
    processed_text = re.sub(pattern, r'\1', text)
    
    return processed_text


def extract_polyphone_hints(text: str) -> tuple[str, dict]:
    """提取多音字标注并生成提示信息（用于日志）
    
    Args:
        text: 包含多音字标注的文本
        
    Returns:
        (处理后的文本, 多音字映射字典)
    """
    pattern = r'([\u4e00-\u9fa5])\[([a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z]+)\]'
    
    polyphone_map = {}
    matches = re.finditer(pattern, text)
    for match in matches:
        char = match.group(1)
        pinyin = match.group(2)
        polyphone_map[char] = pinyin
    
    processed_text = re.sub(pattern, r'\2\1', text)
    
    return processed_text, polyphone_map


# 测试代码
if __name__ == "__main__":
    test_cases = [
        "他在银行[háng]工作，行[xíng]事低调。",
        "这件事情很重[zhòng]要，不要重[chóng]复。",
        "长[cháng]城很长[cháng]，他慢慢长[zhǎng]大了。",
        "普通文本没有标注",
        "混合文本：去银行[háng]存钱，然后去商场[chǎng]购物。"
    ]
    
    print("=" * 60)
    print("多音字处理测试")
    print("=" * 60)
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n案例 {i}:")
        print(f"  原文: {text}")
        
        processed, hints = extract_polyphone_hints(text)
        print(f"  处理: {processed}")
        
        if hints:
            print(f"  标注: {hints}")
