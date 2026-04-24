#!/usr/bin/env python3
import os
import json
import re

def generate_chapter_json(txt_path, json_path, chapter_name):
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    data = []
    id_counter = 1
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if '欢迎' in line or '收藏' in line or '剑来手机版' in line or '小提示' in line or '版权' in line:
            continue
        if re.match(r'^第[\d]+章\s+.+$', line):
            continue
        
        data.append({
            'id': id_counter,
            'role': '旁白',
            'api': {
                'voice': {
                    'text': line,
                    'role': '旁白',
                    'role_voice': '云健-中年男性磁性声音',
                    'speed': '-10%',
                    'volume': '0%',
                    'pitch': '0Hz',
                    'instruct': '平静叙述'
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
        'roles_definition': {
            '旁白': {
                'role_voice': '云健-中年男性磁性声音',
                'pitch': '0Hz',
                'volume': '0%',
                'speed': '-10%'
            }
        },
        'data': data
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f'Generated {json_path} with {len(data)} entries')

txt_dir = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来'
json_dir = '/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿'

chapters = [
    ('剑来第1章-惊蛰.txt', '剑来第1章-惊蛰.json', '剑来第1章-惊蛰'),
    ('剑来第2章-开门.txt', '剑来第2章-开门.json', '剑来第2章-开门'),
    ('剑来第3章-日出.txt', '剑来第3章-日出.json', '剑来第3章-日出'),
    ('剑来第4章-黄鸟.txt', '剑来第4章-黄鸟.json', '剑来第4章-黄鸟'),
    ('剑来第5章-道破.txt', '剑来第5章-道破.json', '剑来第5章-道破'),
    ('剑来第6章-下签.txt', '剑来第6章-下签.json', '剑来第6章-下签')
]

for txt_file, json_file, chapter_name in chapters:
    txt_path = os.path.join(txt_dir, txt_file)
    json_path = os.path.join(json_dir, json_file)
    if os.path.exists(txt_path):
        generate_chapter_json(txt_path, json_path, chapter_name)
    else:
        print(f'File not found: {txt_path}')

print('\nAll chapters generated!')