#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import argparse
import sys

def extract_text_from_json(json_path):
    """从JSON文件中提取所有文本内容"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_text = []
        all_items = []
        for item in data.get('data', []):
            text = item.get('api', {}).get('voice', {}).get('text', '')
            role = item.get('api', {}).get('voice', {}).get('role', '')
            if text:
                all_text.append(text)
                all_items.append((role, text))
        return ''.join(all_text), all_items
    except Exception as e:
        print(f"❌ 读取JSON文件失败 {json_path}: {e}", file=sys.stderr)
        return "", []

def extract_text_from_txt(txt_path):
    """从TXT文件中提取纯文本内容（去除章节标题和广告）"""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = re.sub(r'^第[\d]+章\s+.+$\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r'.*(欢迎|收藏|剑来手机版|小提示|版权).*', '', content)
        content = re.sub(r'[-]{10,}', '', content)
        
        return content.strip()
    except Exception as e:
        print(f"❌ 读取TXT文件失败 {txt_path}: {e}", file=sys.stderr)
        return ""

def is_text_present(txt_chunk, json_items):
    """检查文本片段是否在JSON条目中存在（允许跨条目匹配）"""
    txt_clean = re.sub(r'[！。？，、；：""''\s]+', '', txt_chunk)
    if len(txt_clean) < 8:
        return True
    
    all_json_text = ''.join([re.sub(r'[！。？，、；：""''\s]+', '', text) for _, text in json_items])
    
    if txt_clean in all_json_text:
        return True
    
    parts = re.split(r'[！。？，、；：]', txt_chunk)
    for part in parts:
        part_clean = re.sub(r'\s+', '', part).strip()
        if len(part_clean) > 5:
            found = False
            for _, text in json_items:
                text_clean = re.sub(r'\s+', '', text)
                if part_clean in text_clean:
                    found = True
                    break
            if not found:
                return False
    return True

def compare_content(json_items, txt_text):
    """比较JSON内容与原文的匹配度"""
    if not txt_text:
        return False, "原文为空", []
    
    sentences = re.split(r'[！。？]+', txt_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    
    match_count = 0
    total_sentences = len(sentences)
    missing = []
    
    for sentence in sentences:
        if is_text_present(sentence, json_items):
            match_count += 1
        else:
            missing.append(sentence[:80] + "..." if len(sentence) > 80 else sentence)
    
    if total_sentences == 0:
        return False, "无法分割原文", []
    
    ratio = match_count / total_sentences
    return ratio >= 0.95, f"匹配度: {ratio:.2%} ({match_count}/{total_sentences})", missing

def detect_chapter_number(filename):
    """从文件名中提取章节号"""
    match = re.search(r'第(\d+)章', filename)
    return match.group(1) if match else None

def main():
    parser = argparse.ArgumentParser(description='批量检测JSON文稿与原文是否完整')
    parser.add_argument('--json_dir', default='/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿',
                        help='JSON文稿目录')
    parser.add_argument('--txt_dir', default='/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来',
                        help='TXT原文目录')
    args = parser.parse_args()
    
    print("=" * 70)
    print("          批量检测JSON文稿与原文完整性工具")
    print("=" * 70)
    print(f"JSON目录: {args.json_dir}")
    print(f"TXT目录: {args.txt_dir}")
    print("-" * 70)
    
    json_files = sorted([f for f in os.listdir(args.json_dir) if f.endswith('.json') and '第' in f])
    txt_files = {detect_chapter_number(f): f for f in os.listdir(args.txt_dir) if f.endswith('.txt') and '第' in f}
    
    results = []
    total = 0
    complete = 0
    incomplete = 0
    
    for json_file in json_files:
        chapter_num = detect_chapter_number(json_file)
        if not chapter_num:
            continue
        
        total += 1
        json_path = os.path.join(args.json_dir, json_file)
        
        if chapter_num in txt_files:
            txt_path = os.path.join(args.txt_dir, txt_files[chapter_num])
        else:
            print(f"⚠️  {json_file} - 未找到对应的TXT原文")
            results.append((json_file, '⚠️', '未找到原文', []))
            incomplete += 1
            continue
        
        json_text, json_items = extract_text_from_json(json_path)
        txt_text = extract_text_from_txt(txt_path)
        
        is_complete, message, missing = compare_content(json_items, txt_text)
        
        if is_complete:
            print(f"✅ {json_file} - 内容完整 ({message})")
            results.append((json_file, '✅', '内容完整', []))
            complete += 1
        else:
            print(f"❌ {json_file} - {message}")
            if missing:
                print(f"   缺失内容片段 ({len(missing)}处):")
                for i, part in enumerate(missing[:5], 1):
                    print(f"      {i}. {part}")
            results.append((json_file, '❌', message, missing))
            incomplete += 1
    
    print("-" * 70)
    print(f"检测完成！总计: {total} 章")
    print(f"✅ 内容完整: {complete} 章")
    print(f"❌ 内容缺失: {incomplete} 章")
    print("=" * 70)
    
    report_path = os.path.join(args.json_dir, '检测报告.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("          JSON文稿完整性检测报告\n")
        f.write("=" * 70 + "\n")
        f.write(f"检测时间: {os.popen('date').read().strip()}\n")
        f.write(f"JSON目录: {args.json_dir}\n")
        f.write(f"TXT目录: {args.txt_dir}\n")
        f.write("-" * 70 + "\n")
        for json_file, status, message, missing in results:
            f.write(f"\n【章节】{json_file}\n")
            f.write(f"【状态】{status} {message}\n")
            if missing:
                f.write(f"【缺失片段】共 {len(missing)} 处\n")
                for i, part in enumerate(missing, 1):
                    f.write(f"  {i}. {part}\n")
        f.write("\n" + "-" * 70 + "\n")
        f.write(f"总计: {total} 章 | 完整: {complete} 章 | 缺失: {incomplete} 章\n")
    
    print(f"📝 检测报告已保存到: {report_path}")

if __name__ == '__main__':
    main()