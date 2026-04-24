#!/usr/bin/env python3
import json
import re

txt_path = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来/剑来第1章-惊蛰.txt'
json_path = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿/剑来第1章-惊蛰.json'

with open(txt_path, 'r', encoding='utf-8') as f:
    txt_lines = f.readlines()

txt_content = ''
for line in txt_lines:
    if re.match(r'^第[\d]+章\s+.+$', line.strip()):
        continue
    if any(keyword in line for keyword in ['欢迎', '收藏', '剑来手机版', '小提示', '版权', '-------------']):
        continue
    txt_content += line

txt_clean = re.sub(r'[！。？，、；：\"\"''\n\r]+', '', txt_content)

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

json_text = ''
for item in data.get('data', []):
    text = item.get('api', {}).get('voice', {}).get('text', '')
    if text:
        json_text += text

json_clean = re.sub(r'[！。？，、；：\"\"''\n\r]+', '', json_text)

print('=== TXT原文内容 ===')
print(f'总长度: {len(txt_clean)}')
print(f'前300字符: {txt_clean[:300]}...')
print()
print('=== JSON内容 ===')
print(f'总长度: {len(json_clean)}')
print(f'前300字符: {json_clean[:300]}...')
print()
print('=== 缺失的内容片段 ===')
missing = []
for i in range(0, len(txt_clean), 30):
    chunk = txt_clean[i:i+30]
    if len(chunk) < 15:
        continue
    if chunk not in json_clean:
        missing.append(chunk)

print(f'共发现 {len(missing)} 处缺失片段:')
for i, part in enumerate(missing[:15], 1):
    print(f'{i}. {part}')