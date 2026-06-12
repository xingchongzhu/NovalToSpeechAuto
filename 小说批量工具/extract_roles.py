#!/usr/bin/env python3
"""Extract and consolidate role definitions from all JSON chapter files."""

import json
import os
import re
import glob

# ============================================================
# PART 1: Parse the markdown file to extract all available voice names
# ============================================================
md_path = os.path.expanduser("~/Documents/trae_projects/NovelToSpeechAutoTool/.comate/skills/novel-to-script/references/克隆音频角色列表说明.md")

voice_names = set()

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all unique voice names from markdown tables
# Pattern: lines like | 角色名 | ... | ... | ... |
# The first column in each table row is the voice name
lines = content.split('\n')
for line in lines:
    stripped = line.strip()
    if stripped.startswith('| ') and not stripped.startswith('| --') and not stripped.startswith('| 角色名'):
        # Split by | and get first non-empty column
        parts = [p.strip() for p in stripped.split('|')]
        if len(parts) >= 2 and parts[1]:
            # Filter out header-like rows
            name = parts[1]
            if name not in ('角色名', '角色分类总览', '角色名         ', '总计'):
                voice_names.add(name)

# Also try to extract voice names that might be embedded in role_voice fields later
print(f"\n{'='*60}")
print(f"从 Markdown 文件中提取到 {len(voice_names)} 个可用语音名称")
print(f"{'='*60}")

# ============================================================
# PART 2: Extract roles_definition from all JSON files
# ============================================================
dir1 = os.path.expanduser("~/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿/")
dir2 = os.path.expanduser("~/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本/剑来/")

# Collect all JSON files with their chapter numbers
json_files = []

for d in [dir1, dir2]:
    for fpath in glob.glob(os.path.join(d, "*.json")):
        fname = os.path.basename(fpath)
        # Extract chapter number from filename like "剑来第11章-少女和飞剑.json"
        match = re.search(r'剑来第(\d+)章', fname)
        if match:
            chapter_num = int(match.group(1))
            json_files.append((chapter_num, fpath, d))

# Sort by chapter number
json_files.sort(key=lambda x: x[0])

print(f"\n找到 {len(json_files)} 个JSON文件:")
for ch, fp, d in json_files:
    src = "原稿" if "原稿" in d else "剧本"
    print(f"  [第{ch:02d}章] [{src}] {os.path.basename(fp)}")

# ============================================================
# PART 3: Extract and merge role definitions
# ============================================================
# role_name -> {role_voice, pitch, volume, speed, source_chapter, source_file}
all_roles = {}

for chapter_num, fpath, src_dir in json_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    roles_def = data.get("roles_definition", {})
    
    for role_name, role_data in roles_def.items():
        entry = {
            "role_voice": role_data.get("role_voice", ""),
            "pitch": role_data.get("pitch", ""),
            "volume": role_data.get("volume", ""),
            "speed": role_data.get("speed", ""),
            "source_chapter": chapter_num,
            "source_file": os.path.basename(fpath),
        }
        
        if role_name in all_roles:
            existing = all_roles[role_name]
            if existing["role_voice"] != entry["role_voice"] or \
               existing["pitch"] != entry["pitch"] or \
               existing["volume"] != entry["volume"] or \
               existing["speed"] != entry["speed"]:
                # Higher chapter wins (since we iterate in order, later = higher chapter)
                print(f"\n  [覆盖] '{role_name}': 第{existing['source_chapter']}章 -> 第{chapter_num}章")
                print(f"    旧: voice={existing['role_voice']}, pitch={existing['pitch']}, volume={existing['volume']}, speed={existing['speed']}")
                print(f"    新: voice={entry['role_voice']}, pitch={entry['pitch']}, volume={entry['volume']}, speed={entry['speed']}")
                all_roles[role_name] = entry
        else:
            all_roles[role_name] = entry

# ============================================================
# PART 4: Output consolidated Python dictionary
# ============================================================
print(f"\n{'='*60}")
print(f"合并后共 {len(all_roles)} 个唯一角色")
print(f"{'='*60}")

# Build final dict
consolidated = {}
for role_name in sorted(all_roles.keys()):
    entry = all_roles[role_name]
    consolidated[role_name] = {
        "role_voice": entry["role_voice"],
        "pitch": entry["pitch"],
        "volume": entry["volume"],
        "speed": entry["speed"],
    }

print("\n各角色详情:")
print("-" * 60)
for role_name in sorted(all_roles.keys()):
    entry = all_roles[role_name]
    print(f"  {role_name:12s} | voice: {entry['role_voice'][:35]:35s} | pitch: {entry['pitch']:>5s} | vol: {entry['volume']:>4s} | speed: {entry['speed']:>5s} | 第{entry['source_chapter']:02d}章")

# ============================================================
# PART 5: Check which role_voice values are NOT in the available voice list
# ============================================================
print(f"\n{'='*60}")
print("检查 role_voice 是否在可用语音列表中:")
print(f"{'='*60}")

missing_voices = set()
for role_name, info in consolidated.items():
    voice = info["role_voice"]
    if voice not in voice_names:
        missing_voices.add(voice)
        # Find closest match
        closest = []
        for v in voice_names:
            if any(part in v or v in part for part in voice.split('-')):
                closest.append(v)
        if closest:
            print(f"  ✗ '{voice}' (角色'{role_name}') - 未找到，相似: {closest[:3]}")
        else:
            print(f"  ✗ '{voice}' (角色'{role_name}') - 未找到匹配")

if not missing_voices:
    print("  所有 role_voice 都在可用语音列表中！")

# ============================================================
# PART 6: Output final Python code snippet
# ============================================================
print(f"\n{'='*60}")
print("最终 Python 代码片段:")
print(f"{'='*60}\n")

print("# -----------------------------------------------------------")
print("# 剑来 第1-11章 合并角色定义 (higher chapter wins on conflict)")
print("# -----------------------------------------------------------")
print("ALL_ROLES_DEFINITION = {")
for role_name in sorted(consolidated.keys()):
    info = consolidated[role_name]
    print(f'    "{role_name}": {{')
    print(f'        "role_voice": "{info["role_voice"]}",')
    print(f'        "pitch": "{info["pitch"]}",')
    print(f'        "volume": "{info["volume"]}",')
    print(f'        "speed": "{info["speed"]}",')
    print(f'    }},')
print("}")
print()

# Also output available_voices list
print("# -----------------------------------------------------------")
print(f"# 可用语音名称列表 (共 {len(voice_names)} 个)")
print("# -----------------------------------------------------------")
print("AVAILABLE_VOICES = [")
for v in sorted(voice_names):
    print(f'    "{v}",')
print("]")