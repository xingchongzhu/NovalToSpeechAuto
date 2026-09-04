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
import argparse

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

    # 匹配 "第" + 中文数字 + "回/章" 的模式（use search to find it anywhere in filename）
    match = re.search(r"(第)(.+?)(回|章)(.*)", text)
    if not match:
        return text

    prefix = match.group(1)
    num_str = match.group(2).strip()
    unit = match.group(3)
    suffix = match.group(4) if match.lastindex >= 4 else ""

    try:
        # 如果已经是阿拉伯数字，直接使用
        if num_str.isdigit():
            result = int(num_str)
        else:
            result = _chinese_num_to_int(num_str)
    except (ValueError, KeyError):
        return text

    return f"{prefix}{result}{unit}{suffix}"

def _natural_sort_key(name):
    """自然排序键：数字按数值比较，避免 '2' 排在 '10' 后面"""
    return [((1, int(p)) if p.isdigit() else (0, p)) for p in re.split(r"(\d+)", name)]

def _build_display_name(file_name):
    """从完整音频文件名提取展示名。

    例如 '蜀山剑侠传第201回-第201回_1.mp3' -> '第201回 1'
        '蜀山剑侠传第225回-第235回_1.mp3' -> '第225回-第235回 1'
        '蜀山剑侠传第201回-第201回_full.wav' -> '第201回'
    """
    base = re.sub(r"\.(mp3|wav)$", "", file_name)
    base = re.sub(r"_full$", "", base)

    # 匹配 "...第X回[-第Y回][_S]" 结尾
    m = re.search(r"第(\d+)回(?:-第(\d+)回)?(?:_(\d+))?$", base)
    if m:
        start, end, section = m.group(1), m.group(2), m.group(3)
        if end is None or end == start:
            chapter = f"第{start}回"
        else:
            chapter = f"第{start}回-第{end}回"
        return f"{chapter} {section}" if section else chapter

    # 兜底：下划线转空格
    return base.replace("_", " ")

def organize_audio_files(output_dir=None, audio_output_dir=None):
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 计算项目根目录（脚本目录的上两级）
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))
    
    # 定义目录路径（可通过命令行参数覆盖）
    output_dir = os.path.abspath(output_dir) if output_dir else os.path.join(project_root, "output")
    audio_output_dir = os.path.abspath(audio_output_dir) if audio_output_dir else os.path.join(project_root, "小说音频")
    
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
    
    # 收集所有完整章节音频：源目录下每个章节目录内直接存放的 .mp3（分节）/_full.wav（整章）
    # 跳过 配音/音效 等子目录，以及 chunk_title 等分段 wav
    audio_files = []
    for chapter_dir_name in sorted(os.listdir(output_dir)):
        chapter_path = os.path.join(output_dir, chapter_dir_name)
        if not os.path.isdir(chapter_path):
            continue

        print(f"\n📖 处理章节: {chapter_dir_name}")

        for file_name in os.listdir(chapter_path):
            file_path = os.path.join(chapter_path, file_name)
            if os.path.isdir(file_path):
                continue
            # 跳过 macOS 隐藏文件（.DS_Store、._* AppleDouble 资源叉等）
            if file_name.startswith("."):
                continue
            # 只取完整音频：章节分节 mp3 或整章 _full.wav
            if not (file_name.endswith(".mp3") or file_name.endswith("_full.wav")):
                continue

            # 提取展示名：'蜀山剑侠传第201回-第201回_1.mp3' -> '第201回 1'
            display_name = _build_display_name(file_name)
            audio_files.append((_natural_sort_key(display_name), display_name, file_path))

    # 按章节号/节号自然排序
    audio_files.sort(key=lambda x: x[0])

    # 复制文件（全部平铺到目标目录，不建子目录）
    for _, display_name, source_file in audio_files:
        display_name_converted = convert_chinese_to_arabic(display_name)
        _, ext = os.path.splitext(source_file)

        # 检查音频时长
        duration = get_audio_duration(source_file)
        if duration == 0:
            print(f"❌ 无效音频文件（时长为0），已删除: {os.path.basename(source_file)}")
            os.remove(source_file)
            continue
        elif duration < 0:
            print(f"⚠️ 无法读取音频时长，跳过: {os.path.basename(source_file)}")
            continue

        target_file = os.path.join(audio_output_dir, f"{display_name_converted}{ext}")
        try:
            shutil.copy2(source_file, target_file)
            print(f"✅ 复制: {os.path.basename(source_file)} -> {display_name_converted}{ext}")
        except Exception as e:
            print(f"❌ 复制失败: {os.path.basename(source_file)} - {e}")
    
    print("\n🎉 音频文件整理完成！")
    print(f"📁 所有音频已整理到: {audio_output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="小说音频整理脚本：将合成音频按小说整理到目标目录")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="源目录（合成音频所在目录），默认 <项目根>/output")
    parser.add_argument("--audio-dir", type=str, default=None,
                        help="目标目录（整理后音频输出目录），默认 <项目根>/小说音频")
    args = parser.parse_args()
    organize_audio_files(output_dir=args.output_dir, audio_output_dir=args.audio_dir)