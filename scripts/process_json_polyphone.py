#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""处理JSON小说剧本中的多音字"""

import os
import json
import sys

# 添加多音字处理模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'novel_tool', 'scripts'))

from polyphone_processor import process_polyphone_text

def process_json_file(json_path: str) -> bool:
    """处理单个JSON文件中的多音字"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        
        # 处理data中的所有文本
        for item in data.get('data', []):
            voice = item.get('api', {}).get('voice', {})
            if 'text' in voice:
                original_text = voice['text']
                processed_text = process_polyphone_text(original_text)
                if processed_text != original_text:
                    voice['text'] = processed_text
                    modified = True
        
        # 如果有修改，保存文件
        if modified:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ 已处理: {json_path}")
            return True
        else:
            print(f"ℹ️ 无需修改: {json_path}")
            return False
            
    except Exception as e:
        print(f"❌ 处理失败 {json_path}: {e}")
        return False

def batch_process_json_files(directory: str):
    """批量处理目录中的所有JSON文件"""
    json_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    print(f"找到 {len(json_files)} 个JSON文件")
    
    processed_count = 0
    for json_file in json_files:
        if process_json_file(json_file):
            processed_count += 1
    
    print(f"\n处理完成，共处理 {processed_count} 个文件")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="处理JSON小说剧本中的多音字")
    parser.add_argument("path", help="JSON文件路径或目录路径")
    
    args = parser.parse_args()
    
    if os.path.isfile(args.path):
        process_json_file(args.path)
    elif os.path.isdir(args.path):
        batch_process_json_files(args.path)
    else:
        print(f"错误：路径不存在: {args.path}")
