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
import wave

def get_audio_duration(file_path):
    try:
        with wave.open(file_path, 'r') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        print(f"⚠️ 无法读取音频文件 {file_path}: {e}")
        return -1

def organize_audio_files():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 计算项目根目录（脚本目录的上两级）
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))
    
    # 定义目录路径
    output_dir = os.path.join(project_root, "output")
    audio_output_dir = os.path.join(project_root, "小说音频")
    
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
            
            # 查找完整音频文件（_full.wav）
            for file_name in os.listdir(chapter_path):
                if file_name.endswith("_full.wav"):
                    # 提取章节名称
                    # 文件名格式: 章节名称_full.wav
                    chapter_name = file_name.replace("_full.wav", "")
                    
                    # 清理章节名称中的特殊字符
                    chapter_name = chapter_name.replace("_", " ")
                    
                    # 尝试提取章节序号
                    # 匹配"第X章"格式
                    match = re.match(r"第(\d+)章", chapter_name)
                    if match:
                        chapter_num = int(match.group(1))
                        chapters_found.append((chapter_num, chapter_name, file_name, chapter_path))
                    else:
                        # 如果没有找到章节号，使用原名称
                        chapters_found.append((999, chapter_name, file_name, chapter_path))
        
        # 按章节号排序
        chapters_found.sort(key=lambda x: x[0])
        
        # 复制文件
        for chapter_num, chapter_name, file_name, chapter_path in chapters_found:
            source_file = os.path.join(chapter_path, file_name)
            # 使用清理后的章节名称作为目标文件名
            target_file = os.path.join(novel_audio_dir, f"{chapter_name}.wav")
            
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
                print(f"✅ 复制: {file_name} -> {novel_name}/{chapter_name}.wav")
            except Exception as e:
                print(f"❌ 复制失败: {file_name} - {e}")
    
    print("\n🎉 音频文件整理完成！")
    print(f"📁 所有音频已整理到: {audio_output_dir}")

if __name__ == "__main__":
    organize_audio_files()