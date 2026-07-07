#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻转音频工具
调用 audio_processing_module 中的 AudioEngine 进行语音合成
"""

import os
import sys
import json
import time
import argparse
import tempfile
from datetime import datetime
from pathlib import Path

def sanitize_filename(title):
    """清理文件名中的非法字符"""
    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r']
    for char in invalid_chars:
        title = title.replace(char, '_')
    return title[:100]

def news_to_audio(news_json_path, output_dir, voice_name="阿辉-官方新闻,资讯"):
    """将新闻JSON转换为音频文件"""
    
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "novel_tool", "scripts"))
    
    from audio_processing_module import AudioEngine, VoiceParams
    
    with open(news_json_path, "r", encoding="utf-8") as f:
        news_data = json.load(f)
    
    news_list = news_data.get("news", [])
    timestamp = news_data.get("timestamp", datetime.now().isoformat())
    
    date_str = timestamp.split('T')[0]
    date_dir = os.path.join(output_dir, date_str)
    os.makedirs(date_dir, exist_ok=True)
    
    audio_dir = os.path.join(date_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    json_dest_path = os.path.join(date_dir, os.path.basename(news_json_path))
    with open(json_dest_path, "w", encoding="utf-8") as f:
        json.dump(news_data, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON文件已保存到: {json_dest_path}")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_engine = AudioEngine(
            temp_dir=tmp_dir,
            sample_rate=44100,
            channels=1,
            tts_engine="qwen3-tts",
            target_voice_dbfs=-18.0
        )
        
        success_count = 0
        fail_count = 0
        
        print(f"\n🎤 开始生成音频，共 {len(news_list)} 条新闻...")
        print(f"   使用语音: {voice_name}")
        
        for i, news in enumerate(news_list, 1):
            title = news.get("title", "")
            simplified_content = news.get("simplified_content", news.get("summary", ""))
            
            if not title:
                print(f"⚠️ 跳过第{i}条：标题为空")
                fail_count += 1
                continue
            
            safe_title = sanitize_filename(title)
            audio_path = os.path.join(audio_dir, f"{safe_title}.wav")
            
            if os.path.exists(audio_path):
                print(f"⏭️  第{i}/{len(news_list)}条已存在，跳过: {title[:30]}...")
                success_count += 1
                continue
            
            full_text = f"{title}。{simplified_content}"
            
            print(f"\n📝 正在处理第{i}/{len(news_list)}条: {title[:30]}...")
            sys.stdout.flush()
            
            try:
                voice_params = VoiceParams(
                    text=full_text,
                    role="新闻播报",
                    role_voice=voice_name,
                    speed="+0%",
                    volume="+0%",
                    pitch="+0Hz",
                    instruct="news"
                )
                
                audio = audio_engine.text_to_speech(voice_params)
                audio.export(audio_path, format="wav")
                
                print(f"✅ 音频已生成: {os.path.basename(audio_path)}")
                sys.stdout.flush()
                success_count += 1
                
            except Exception as e:
                print(f"❌ 生成失败: {e}")
                sys.stdout.flush()
                fail_count += 1
            
            time.sleep(0.3)
    
    print(f"\n🎧 音频生成完成！")
    print(f"   成功: {success_count} 条")
    print(f"   失败: {fail_count} 条")
    print(f"   输出目录: {date_dir}")
    
    return date_dir

def main():
    parser = argparse.ArgumentParser(description='新闻转音频工具')
    parser.add_argument('json_path', help='新闻JSON文件路径')
    parser.add_argument('-o', '--output', default='news', help='输出目录')
    parser.add_argument('-v', '--voice', default='阿辉-官方新闻,资讯', help='配音角色名称')
    
    args = parser.parse_args()
    
    news_to_audio(
        news_json_path=args.json_path,
        output_dir=args.output,
        voice_name=args.voice
    )

if __name__ == "__main__":
    main()