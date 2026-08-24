#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 SenseVoice (FunASR) 识别效果
"""

import sys
from pathlib import Path

# 测试音频文件
test_audio = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/output/蜀山剑侠转json/蜀山剑侠传第197回-第197回/配音/voice_line_2.wav"

print("=" * 60)
print("测试 SenseVoice (FunASR) 识别")
print("=" * 60)
print(f"音频: {test_audio}")
print()

try:
    from funasr import AutoModel
    from pathlib import Path
    
    print("正在加载 SenseVoice 模型...")
    # 使用本地 SenseVoiceSmall 模型
    model_path = Path(__file__).parent / "models" / "SenseVoiceSmall"
    model = AutoModel(
        model=str(model_path),
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",  # 可以使用 "cuda" 如果有GPU
    )
    
    print("开始识别...")
    result = model.generate(
        input=test_audio,
        language="auto",  # 自动检测语言
        use_itn=True,
    )
    
    print("\n识别结果:")
    for res in result:
        text = res.get("text", "")
        print(f"  {text}")
        
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
