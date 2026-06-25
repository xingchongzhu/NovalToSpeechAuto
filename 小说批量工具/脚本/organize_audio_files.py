#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小说音频整理脚本
将output目录下的完整音频文件整理到项目根目录的"小说音频"目录下
按小说名称分类，同一小说的音频放在同一个目录下
"""

import os
import sys
import shutil
import re

def get_audio_duration(file_path):
    """获取音频时长（秒），失败返回 -1"""
    try:
        # 使用 pydub 支持多种格式（mp3/wav/m4a 等）
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception:
        # fallback: wave 模块读 WAV
        try:
            import wave
            with wave.open(file_path, 'r') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except Exception as e:
            print(f"⚠️ 无法读取音频文件 {file_path}: {e}")
            return -1

# 中文数字字符 → 数值
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}
_CN_SECTION_UNITS = {"万": 10000, "亿": 100000000}

def _chinese_num_to_int(cn_str):
    """将纯中文数字字符串转为 int，支持 个/十/百/千/万/亿，如 '一百二十三'→123, '五万零三十'→50030"""
    if not cn_str:
        return 0

    # 亿分段处理
    if "亿" in cn_str:
        idx = cn_str.index("亿")
        left = cn_str[:idx]
        right = cn_str[idx + 1:]
        return _chinese_num_to_int(left) * _CN_SECTION_UNITS["亿"] + _chinese_num_to_int(right)

    # 万分段处理
    if "万" in cn_str:
        idx = cn_str.index("万")
        left = cn_str[:idx]
        right = cn_str[idx + 1:]
        return _chinese_num_to_int(left) * _CN_SECTION_UNITS["万"] + _chinese_num_to_int(right)

    # 万字以下：逐位解析 千百十个
    result = 0
    section_val = 0  # 当前节中积累的数字
    for ch in cn_str:
        if ch in _CN_DIGITS:
            section_val = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if section_val == 0:
                # 如 "十" → 10，"十五" → 15
                section_val = 1
            result += section_val * unit
            section_val = 0
    result += section_val  # 加个位
    return result

def convert_chinese_to_arabic(text):
    """将文本中的中文数字替换为阿拉伯数字，如'第十六回_散家财'→'第16回_散家财'，'第一百二十三章'→'第123章'"""
    # 如果已经是阿拉伯数字，直接返回
    if re.match(r"第(\d+)(回|章)(.*)", text):
        return text

    # 匹配 "第" + 中文数字 + "回/章" 的模式
    match = re.match(r"(第)(.+?)(回|章)(.*)", text)
    if not match:
        return text

    prefix = match.group(1)
    num_str = match.group(2).strip()
    unit = match.group(3)
    suffix = match.group(4) if match.lastindex >= 4 else ""

    try:
        result = _chinese_num_to_int(num_str)
    except (ValueError, KeyError):
        return text

    return f"{prefix}{result}{unit}{suffix}"

def organize_audio_files():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 计算项目根目录（脚本目录的上两级）
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))
    
    # 定义目录路径
    output_dir = os.path.join(project_root, "output")
    audio_output_dir = os.path.join(project_root, "小说音频")
    
    # 清空目标目录
    if os.path.exists(audio_output_dir):
        print(f"🗑️ 清空目标目录: {audio_output_dir}")
        for item in os.listdir(audio_output_dir):
            item_path = os.path.join(audio_output_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    
    # 创建目标目录
    os.makedirs(audio_output_dir, exist_ok=True)
    
    # 检查output目录是否存在
    if not os.path.exists(output_dir):
        print(f"❌ 输出目录不存在: {output_dir}")
        return
    
    print(f"📁 开始整理音频文件...")
    print(f"📁 源目录: {output_dir}")
    print(f"📁 目标目录: {audio_output_dir}")
    
    # 遍历output目录下的所有小说目录
    for novel_name in os.listdir(output_dir):
        novel_dir = os.path.join(output_dir, novel_name)
        
        if not os.path.isdir(novel_dir):
            continue
        
        print(f"\n📖 处理小说: {novel_name}")
        
        # 创建小说目标目录
        novel_audio_dir = os.path.join(audio_output_dir, novel_name)
        os.makedirs(novel_audio_dir, exist_ok=True)
        
        # 遍历小说目录下的章节目录
        chapters_found = []
        for chapter_dir in os.listdir(novel_dir):
            chapter_path = os.path.join(novel_dir, chapter_dir)
            
            if not os.path.isdir(chapter_path):
                continue
            
            # 查找完整音频文件（优先 mp3，其次 wav）
            for file_name in os.listdir(chapter_path):
                # 匹配 _full.wav 或章节名.mp3 或章节名.wav
                is_full = file_name.endswith("_full.wav")
                is_mp3 = file_name.endswith(".mp3")
                is_wav = file_name.endswith(".wav") and not file_name.startswith("mixed_") and not file_name.startswith("voice_")
                
                if is_full or is_mp3 or is_wav:
                    chapter_name = file_name.replace("_full.wav", "").replace(".mp3", "").replace(".wav", "")
                    
                    # 清理章节名称中的特殊字符
                    chapter_name = chapter_name.replace("_", " ")
                    
                    # 尝试提取章节序号
                    # 匹配"第X回"或"第X章"格式
                    match = re.match(r"第(.+?)回", chapter_name)
                    if not match:
                        match = re.match(r"第(\d+)章", chapter_name)
                    if match:
                        num_str = match.group(1)
                        try:
                            chapter_num = _chinese_num_to_int(num_str)
                        except (ValueError, KeyError):
                            try:
                                chapter_num = int(num_str)
                            except ValueError:
                                chapter_num = 999
                        chapters_found.append((chapter_num, chapter_name, file_name, chapter_path))
        
        # 按章节号排序
        chapters_found.sort(key=lambda x: x[0])
        
        # 复制文件
        for chapter_num, chapter_name, file_name, chapter_path in chapters_found:
            source_file = os.path.join(chapter_path, file_name)
            # 保持原文件扩展名
            _, ext = os.path.splitext(file_name)
            
            # 转换章节名中的中文数字为阿拉伯数字
            chapter_name_converted = convert_chinese_to_arabic(chapter_name)
            
            # 在结尾添加"_整书免费"
            target_file = os.path.join(novel_audio_dir, f"{chapter_name_converted}_整书免费{ext}")
            
            # 检查音频时长
            duration = get_audio_duration(source_file)
            if duration == 0:
                print(f"❌ 无效音频文件（时长为0），已删除: {file_name}")
                os.remove(source_file)
                continue
            elif duration < 0:
                print(f"⚠️ 无法读取音频时长，跳过: {file_name}")
                continue
            
            # 复制文件
            try:
                shutil.copy2(source_file, target_file)
                print(f"✅ 复制: {file_name} -> {novel_name}/{chapter_name_converted}_整书免费{ext}")
            except Exception as e:
                print(f"❌ 复制失败: {file_name} - {e}")
    
    print("\n🎉 音频文件整理完成！")
    print(f"📁 所有音频已整理到: {audio_output_dir}")

if __name__ == "__main__":
    organize_audio_files()