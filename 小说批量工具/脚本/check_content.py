import os
import json
import re

json_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿"
txt_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来"

def extract_text_from_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_text = []
        for item in data.get('data', []):
            text = item.get('api', {}).get('voice', {}).get('text', '')
            if text:
                all_text.append(text)
        return '\n'.join(all_text)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return ""

def extract_text_from_txt(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        content = ""
        for line in lines:
            if re.match(r'^第[\d]+章\s+.+$', line.strip()):
                continue
            if '欢迎' in line or '收藏' in line or '剑来手机版' in line or '小提示' in line or '版权' in line:
                continue
            content += line
        
        content = re.sub(r'[！。？，、；：""''\n\r]+', '', content)
        return content.strip()
    except Exception as e:
        print(f"Error reading {txt_path}: {e}")
        return ""

def compare_files(json_path, txt_path):
    json_text = extract_text_from_json(json_path)
    txt_text = extract_text_from_txt(txt_path)
    
    json_text_clean = re.sub(r'[！。？，、；：""''\n\r]+', '', json_text)
    
    missing_parts = []
    txt_chunks = [txt_text[i:i+50] for i in range(0, len(txt_text), 50)]
    
    for chunk in txt_chunks:
        if len(chunk) > 30 and chunk not in json_text_clean:
            missing_parts.append(chunk[:60] + "..." if len(chunk) > 60 else chunk)
    
    return missing_parts

json_files = sorted([f for f in os.listdir(json_dir) if f.endswith('.json') and '第' in f])

has_missing = False
for json_file in json_files:
    chapter_num = re.search(r'第(\d+)章', json_file)
    if chapter_num:
        num = chapter_num.group(1)
        txt_files = [f for f in os.listdir(txt_dir) if f.startswith(f"剑来第{num}章-") and f.endswith('.txt')]
        
        if txt_files:
            json_path = os.path.join(json_dir, json_file)
            txt_path = os.path.join(txt_dir, txt_files[0])
            
            missing = compare_files(json_path, txt_path)
            if missing:
                has_missing = True
                print(f"\n{'='*50}")
                print(f"章节: {json_file}")
                print(f"缺失内容 ({len(missing)} 处):")
                for i, part in enumerate(missing, 1):
                    print(f"  {i}. {part}")
            else:
                print(f"章节: {json_file} - 内容完整")

if not has_missing:
    print("\n所有章节内容完整，无缺失！")
else:
    print("\n检查完成，存在缺失内容！")