#!/usr/bin/env python3
import os
import json
import re

KNOWN_ROLES = {'陈平安', '宋集薪', '齐先生', '稚圭', '汉子', '道人', '刘羡阳', '姚老头', '赵繇', '青衫少年', '中年儒士', '教书先生', '年轻道人', '高大少年', '先生'}

def parse_line(line):
    line = line.strip()
    if not line:
        return None, None, None
    
    if re.match(r'^[\-—]{3,}$', line):
        return None, None, None
    
    if re.match(r'^[！。？，、；：""''\s]+$', line):
        return None, None, None
    
    colon_idx = line.find('：')
    if colon_idx == -1:
        colon_idx = line.find(':')
        if colon_idx == -1:
            return '旁白', line, 'narration'
    
    before_colon = line[:colon_idx]
    after_colon = line[colon_idx+1:].strip()
    
    if after_colon.startswith('“') or after_colon.startswith('"'):
        text = after_colon[1:-1] if (after_colon.endswith('”') or after_colon.endswith('"')) else after_colon[1:]
    else:
        text = after_colon
    
    if not text or re.match(r'^[！。？，、；：""''\s]+$', text):
        return '旁白', line, 'narration'
    
    comma_parts = before_colon.split('，')
    for part in reversed(comma_parts):
        for role in KNOWN_ROLES:
            if role in part:
                return role, line, 'dialogue'
    
    return '旁白', line, 'narration'

def generate_chapter_json(txt_path, json_path, chapter_name):
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    data = []
    id_counter = 1
    roles = {'旁白': {'role_voice': '云健-中年男性磁性声音', 'speed': '-10%'}}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if '欢迎' in line or '收藏' in line or '剑来手机版' in line or '小提示' in line or '版权' in line:
            continue
        
        if re.match(r'^第[\d一二三四五六七八九十]+章', line):
            continue
        
        role, text, type_ = parse_line(line)
        if role is None:
            continue
        
        if role not in roles:
            roles[role] = {'role_voice': '云健-中年男性磁性声音', 'speed': '-10%'}
        
        data.append({
            'id': id_counter,
            'role': role,
            'api': {
                'voice': {
                    'text': text,
                    'role': role,
                    'role_voice': roles[role]['role_voice'],
                    'speed': roles[role]['speed'],
                    'volume': '0%',
                    'pitch': '0Hz',
                    'instruct': '平静叙述' if type_ == 'narration' else '角色对话'
                },
                'bgm': {
                    'play_mode': 'keep',
                    'scene': '古风小镇',
                    'scene_cn': '古风小镇',
                    'scene_en': 'Ancient Town',
                    'fade_in': 0,
                    'fade_out': 0,
                    'volume': '-18%',
                    'pitch': '+0Hz'
                },
                'effects': []
            },
            'mix': {
                'mode': 'mix'
            }
        })
        id_counter += 1
    
    result = {
        'project': '剑来有声小说自动生成',
        'chapter': chapter_name,
        'global': {
            'pitch': '+0Hz',
            'channels': 1,
            'voice_volume': '+0%',
            'bgm_volume': '-18%',
            'effect_volume': '-10%'
        },
        'roles_definition': roles,
        'data': data
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f'Generated {json_path} with {len(data)} entries, {len(roles)} roles')
    return roles

txt_dir = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来'
json_dir = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿'

chapter_files = [
    ('剑来第6章-下签.txt', '剑来第6章-下签.json', '剑来第6章-下签')
]

for txt_file, json_file, chapter_name in chapter_files:
    txt_path = os.path.join(txt_dir, txt_file)
    json_path = os.path.join(json_dir, json_file)
    if os.path.exists(txt_path):
        roles = generate_chapter_json(txt_path, json_path, chapter_name)
        print(f'识别到的角色: {list(roles.keys())}')
    else:
        print(f'File not found: {txt_path}')

print('\nDone!')