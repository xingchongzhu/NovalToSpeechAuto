import os
import json
import re

novel_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来"
output_dir = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿"
voice_table_path = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/剧本生成skill/剑来角色配配音表.md"

role_voice_map = {}

def load_voice_table():
    with open(voice_table_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    in_table = False
    for line in lines:
        if line.startswith('| 角色名 |'):
            in_table = True
            continue
        if in_table and line.startswith('|') and not line.startswith('|---'):
            parts = line.split('|')
            if len(parts) >= 3:
                role_name = parts[1].strip()
                voice_name = parts[2].strip()
                if role_name and voice_name and role_name != '角色名':
                    role_voice_map[role_name] = voice_name

load_voice_table()

def get_voice_for_role(role_name):
    if role_name in role_voice_map