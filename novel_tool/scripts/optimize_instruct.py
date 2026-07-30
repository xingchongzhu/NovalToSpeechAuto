#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化蜀山剑侠传 JSON 剧本中的 instruct 情绪描述字段
处理第51回到第150回（共100章）
"""

import json
import os
import re
from pathlib import Path

# 基础目录
BASE_DIR = Path("/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/novel_tool/novel_scripts/蜀山剑侠转json")

# 情绪词汇库
NARRATION_STYLES = {
    # 基础叙述类 -> 复合描述
    "平静叙述": "平静叙述，语气舒缓，如画卷般展开",
    "": "平静叙述，语气舒缓，如画卷般展开",  # 空字符串默认使用
    "紧张叙述": "紧张叙述，语速加快，营造紧迫感",
    "庄重叙述": "庄重大气，掷地有声，说书人的韵味",
    "庄重宣告": "庄重大气，掷地有声，说书人的韵味",
    "悲伤叙述": "悲伤叙述，语调低沉，如泣如诉",
    "喜悦叙述": "喜悦叙述，语调轻快，充满生机",
    "神秘叙述": "神秘叙述，语调压低，营造悬疑氛围",
    "悬疑叙述": "悬疑叙述，语调压低，营造悬疑氛围",
    "急促叙述": "急促叙述，语速加快，营造紧迫感",
    "恢宏叙述": "恢宏叙述，声如洪钟，气势磅磗",
    "阴森叙述": "阴森叙述，语调阴冷，令人毛骨悚然",
    "俏皮叙述": "俏皮叙述，语调活泼，带点调侃",
    "感叹叙述": "感叹叙述，语调起伏，饱含感慨",
    "回忆叙述": "回忆叙述，语调悠远，陷入沉思",
    "温馨叙述": "温馨叙述，语调柔和，温暖人心",
    "压抑叙述": "压抑叙述，语调沉重，令人窒息",
    "轻声叙述": "轻声叙述，语调轻柔，如在耳边低语",
    "郑重叙述": "郑重叙述，语调庄严，字字千钧",
}

# 角色情绪映射（简单 -> 复合）
CHARACTER_EMOTIONS = {
    # 基础情绪 -> 复合描述
    "温和": "温和慈祥，语带关怀，令人心安",
    "温和慈祥": "温和慈祥，语带关怀，令人心安",
    "温和安排": "温和从容，条理清晰，长辈的睿智",
    "焦急": "焦急万分，语速急促，忧心忡忡",
    "焦急询问": "焦急万分，语速急促，忧心忡忡",
    "急切": "急切期待，语速加快，迫不及待",
    "急切期待": "急切期待，语速加快，迫不及待",
    "愤怒": "愤怒，咬牙切齿，怒火中烧",
    "悲伤": "悲伤，哽咽，泣不成声",
    "喜悦": "喜悦，欢欣鼓舞，眉飞色舞",
    "恐惧": "恐惧，声音颤抖，惊慌失措",
    "惊讶": "惊讶，难以置信，倒吸一口凉气",
    "疑惑": "疑惑，语气迟疑，困惑不解",
    "温柔": "温柔体贴，语带柔情，如春风拂面",
    "严厉": "严厉训斥，语气冰冷，不容置疑",
    "得意": "得意洋洋，语气轻狂，志得意满",
    "嘲讽": "嘲讽讥笑，语带轻蔑，冷嘲热讽",
    "无奈": "无奈苦笑，语气萧索，心灰意冷",
    "冷漠": "冷漠淡然，语气疏离，拒人千里",
    "爽朗": "爽朗大笑，声音洪亮，豁达开朗",
    "俏皮": "俏皮调侃，语带戏谑，古灵精怪",
    "严肃": "严肃郑重，语气庄重，一丝不苟",
    "哀求": "哀求恳请，语气卑微，声泪俱下",
    "安慰": "安慰劝导，语气温和，循循善诱",
    "鼓励": "鼓励支持，语气坚定，给人力量",
    "喝令": "喝令制止，语气威严，不容违抗",
    "逼问": "逼问追问，语气凌厉，步步紧逼",
    "质问": "质问质疑，语气尖锐，咄咄逼人",
    "激动": "激动万分，声音颤抖，情绪高涨",
    "痛苦": "痛苦挣扎，声音嘶哑，痛不欲生",
    "怨恨": "怨恨咒骂，语气阴毒，咬牙切齿",
    "担心": "担心忧虑，语气不安，心系他人",
    "好奇": "好奇询问，语气轻快，充满兴趣",
    "犹豫": "犹豫不决，语气迟疑，举棋不定",
    "坚定": "坚定不移，语气铿锵，斩钉截铁",
    "羞怯": "羞怯腼腆，声音低微，含羞带怯",
    "兴奋": "兴奋激动，语速加快，兴高采烈",
    "失望": "失望沮丧，语气低落，万念俱灰",
    "惭愧": "惭愧内疚，语气低沉，无地自容",
    "感激": "感激涕零，语带哽咽，感恩戴德",
    "悔恨": "悔恨交加，语气沉痛，追悔莫及",
    "倔强": "倔强不服，语气执拗，宁折不弯",
    "傲慢": "傲慢无礼，语气轻狂，目中无人",
    "天真": "天真烂漫，语气纯真，不谙世事",
    "神秘": "神秘莫测，语调压低，故弄玄虚",
    "紧张": "紧张不安，声音微颤，如临大敌",
    "冷静": "冷静沉着，语气平稳，处变不惊",
    "轻蔑": "轻蔑不屑，语气冷淡，嗤之以鼻",
}

# 特殊角色特质映射
CHARACTER_TRAITS = {
    "妙一夫人": "清雅从容，灵秀聪慧，一派仙家风范",
    "英琼": "阳光爽朗，迫不及待，侠女的直率",
    "李英琼": "阳光爽朗，迫不及待，侠女的直率",
    "余英男": "清冷干练，被激起斗志，外冷内热",
    "矮叟朱梅": "豪迈挥洒，声如洪钟，老当益壮的豪情",
    "朱梅": "豪迈挥洒，声如洪钟，老当益壮的豪情",
    "赤城子": "醉意微醺，举重若轻，世外高人的洒脱",
    "广慧大师": "慈悲安详，话锋一转，引出下文",
    "裘芷仙": "温柔端庄，如同长姐关怀，善解人意",
    "芷仙": "温柔端庄，如同长姐关怀，善解人意",
    "若兰": "温柔中陡然转利，深情而自信",
    "芝仙": "活泼俏皮，古灵精怪，谁也不怕",
    "袁星": "粗犷中透着狡黠，自有一套道理",
    "唐西": "朝气蓬勃，少年意气，发起挑战的兴奋",
}

# 复合情绪词汇
COMPLEX_EMOTIONS = [
    "惊喜交加", "悲愤交加", "强压怒火", "故作镇定",
    "哭笑不得", "又惊又怕", "欲言又止", "泣不成声",
    "声泪俱下", "语重心长", "意味深长"
]

def analyze_context(text, role, prev_text="", next_text=""):
    """
    根据文本内容分析情绪上下文
    """
    text = text.strip()
    
    # 旁白处理
    if role == "旁白":
        return analyze_narration(text, prev_text, next_text)
    
    # 角色对话处理
    return analyze_character_dialog(text, role, prev_text, next_text)

def analyze_narration(text, prev_text, next_text):
    """
    分析旁白叙述的情绪
    """
    # 战斗/紧张场景
    if any(kw in text for kw in ["斗", "杀", "战", "打", "伤", "死", "危急", "危险", "紧迫", "快", "急忙"]):
        if any(kw in text for kw in ["大惊", "慌忙", "急忙", "紧迫", "危急"]):
            return "紧张叙述，语速加快，营造紧迫感"
        return "紧张叙述，节奏紧凑，剑拔弩张"
    
    # 庄重/宣告场景
    if any(kw in text for kw in ["说道", "宣布", "宣告", "命令", "法旨", "天意", "天机"]):
        return "庄重大气，掷地有声，说书人的韵味"
    
    # 悲伤场景
    if any(kw in text for kw in ["哭", "泪", "悲", "哀", "伤", "惨", "痛", "死", "亡", "牺牲"]):
        if any(kw in text for kw in ["大哭", "痛哭", "泪如雨", "悲伤", "哀嚎"]):
            return "悲伤叙述，语调低沉，如泣如诉"
    
    # 喜悦场景
    if any(kw in text for kw in ["笑", "喜", "乐", "欢", "高兴", "欢喜", "欣喜"]):
        return "喜悦叙述，语调轻快，充满生机"
    
    # 神秘/悬疑场景
    if any(kw in text for kw in ["秘", "密", "诡", "异", "怪", "奇", "玄", "奥", "不知", "奇怪"]):
        return "神秘叙述，语调压低，营造悬疑氛围"
    
    # 回忆场景
    if any(kw in text for kw in ["想起", "回忆", "记得", "当年", "以前", "从前", "昔日"]):
        return "回忆叙述，语调悠远，陷入沉思"
    
    # 场景转换/过渡
    if any(kw in text for kw in ["且说", "话说", "却说", "当下", "于是", "随后", "过了"]):
        return "平静叙述，语气舒缓，如画卷般展开"
    
    # 描述环境/景色
    if any(kw in text for kw in ["山", "水", "云", "风", "雨", "雪", "花", "树", "景色", "风光", "美景"]):
        return "平静叙述，如诗如画，意境悠远"
    
    # 默认平静叙述
    return "平静叙述，语气舒缓，如画卷般展开"

def analyze_character_dialog(text, role, prev_text, next_text):
    """
    分析角色对话的情绪
    """
    text = text.strip()
    
    # 检查是否有角色特质定义
    if role in CHARACTER_TRAITS:
        base_trait = CHARACTER_TRAITS[role]
    else:
        base_trait = None
    
    # 情绪检测
    emotion = None
    
    # 愤怒/生气
    if any(kw in text for kw in ["气", "怒", "恨", "杀", "死", "混蛋", "该死", "可恶", "可恨"]):
        if any(kw in text for kw in ["大怒", "怒道", "喝道", "骂道", "气极", "怒极", "气冲冲"]):
            emotion = "愤怒，咬牙切齿，怒火中烧"
        elif any(kw in text for kw in ["强忍", "压下", "忍住"]):
            emotion = "强压怒火，语气冰冷，暗藏杀机"
        else:
            emotion = "愤怒，语气凌厉，毫不留情"
    
    # 悲伤/哭泣
    elif any(kw in text for kw in ["哭", "泪", "悲", "哀", "伤", "惨", "痛"]):
        if any(kw in text for kw in ["大哭", "痛哭", "泪如雨", "泣不成声", "泪流满面"]):
            emotion = "悲伤，泣不成声，撕心裂肺"
        else:
            emotion = "悲伤，哽咽，声音颤抖"
    
    # 焦急/担心
    elif any(kw in text for kw in ["急", "慌", "怕", "担心", "怎么办", "完了", "不好"]):
        if any(kw in text for kw in ["大惊", "大惊失色", "慌了", "着急"]):
            emotion = "焦急万分，语速急促，忧心忡忡"
        else:
            emotion = "担心忧虑，语气不安，心系他人"
    
    # 喜悦/高兴
    elif any(kw in text for kw in ["笑", "喜", "乐", "欢", "好", "妙", "哈哈", "太好了"]):
        if any(kw in text for kw in ["大笑", "笑道", "欢喜", "高兴", "欣喜"]):
            emotion = "喜悦，欢欣鼓舞，眉飞色舞"
        else:
            emotion = "喜悦，语气轻快，心情愉悦"
    
    # 惊讶
    elif any(kw in text for kw in ["啊", "呀", "咦", "哦", "咦", "什么", "怎么", "竟", "没想到", "原来"]):
        if any(kw in text for kw in ["大惊", "惊讶", "震惊", "意外"]):
            emotion = "惊讶，难以置信，倒吸一口凉气"
        else:
            emotion = "疑惑，语气迟疑，困惑不解"
    
    # 询问/疑问
    elif text.endswith(("？", "?", "吗", "呢", "么")) or any(kw in text for kw in ["问", "请问", "如何", "什么", "哪里", "为何"]):
        if any(kw in text for kw in ["请问", "敢问", "请教"]):
            emotion = "恭敬询问，语气谦逊，虚心求教"
        else:
            emotion = "疑惑询问，语气迟疑，寻求答案"
    
    # 请求/哀求
    elif any(kw in text for kw in ["求", "请", "帮", "拜托", "恳请", "望", "希望"]):
        if any(kw in text for kw in ["求求", "恳求", "哀求", "恳请"]):
            emotion = "哀求恳请，语气卑微，声泪俱下"
        else:
            emotion = "恳切请求，语气真诚，满怀期待"
    
    # 命令/喝令
    elif any(kw in text for kw in ["速", "快", "立即", "给我", "不准", "不得", "休得", "胆敢"]):
        emotion = "喝令制止，语气威严，不容违抗"
    
    # 思考/内心独白
    elif any(kw in text for kw in ["想", "寻思", "暗想", "心想", "思忖", "琢磨", "思量"]):
        emotion = "心中暗想，犹豫不决，举棋不定"
    
    # 如果检测到情绪
    if emotion:
        if base_trait:
            # 合并特质和情绪
            return f"{base_trait}，{emotion.split('，')[0]}"
        return emotion
    
    # 使用默认特质或通用描述
    if base_trait:
        return base_trait
    
    # 默认角色对话描述
    return "语气平和，神态自然，从容不迫"

def optimize_instruct(item, prev_item=None, next_item=None):
    """
    优化单个data项的instruct字段
    """
    role = item.get("role", "旁白")
    voice = item.get("api", {}).get("voice", {})
    text = voice.get("text", "")
    current_instruct = voice.get("instruct", "")
    
    # 获取前后文
    prev_text = prev_item.get("api", {}).get("voice", {}).get("text", "") if prev_item else ""
    next_text = next_item.get("api", {}).get("voice", {}).get("text", "") if next_item else ""
    
    # 分析并生成新的instruct
    new_instruct = analyze_context(text, role, prev_text, next_text)
    
    # 如果当前已有复合描述（包含逗号），且不是空字符串，保留原样
    if current_instruct and "，" in current_instruct and current_instruct not in ["", "平静叙述"]:
        return None  # 不需要修改
    
    # 如果当前简单描述在映射表中
    if current_instruct in CHARACTER_EMOTIONS:
        return CHARACTER_EMOTIONS[current_instruct]
    
    if current_instruct in NARRATION_STYLES:
        return NARRATION_STYLES[current_instruct]
    
    # 返回新的分析结果
    return new_instruct

def process_chapter(file_path):
    """
    处理单个章节文件
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified_count = 0
        data_array = data.get("data", [])
        
        for i, item in enumerate(data_array):
            prev_item = data_array[i-1] if i > 0 else None
            next_item = data_array[i+1] if i < len(data_array) - 1 else None
            
            new_instruct = optimize_instruct(item, prev_item, next_item)
            
            if new_instruct:
                old_instruct = item.get("api", {}).get("voice", {}).get("instruct", "")
                item["api"]["voice"]["instruct"] = new_instruct
                modified_count += 1
                
                # 记录修改日志（每章前3条）
                if modified_count <= 3:
                    print(f"    [{item.get('role')}] '{old_instruct}' -> '{new_instruct}'")
        
        # 保存修改后的文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return modified_count, len(data_array)
    
    except Exception as e:
        print(f"  错误: {e}")
        return 0, 0

def get_chapter_files():
    """
    获取第51-150回的文件列表
    """
    files = []
    for i in range(51, 151):
        # 尝试多种可能的文件名格式
        patterns = [
            f"蜀山剑侠传第{i}回-*.json",
            f"蜀山剑侠传第{i}回.json"
        ]
        
        found = False
        for pattern in patterns:
            matched = list(BASE_DIR.glob(pattern))
            if matched:
                files.append(matched[0])
                found = True
                break
        
        if not found:
            print(f"  警告: 未找到第{i}回的文件")
    
    return sorted(files, key=lambda x: int(re.search(r'第(\d+)回', x.name).group(1)))

def main():
    print("="*80)
    print("《蜀山剑侠传》第51-150回 instruct 字段优化")
    print("="*80)
    
    # 获取文件列表
    files = get_chapter_files()
    print(f"\n找到 {len(files)} 个章节文件")
    
    # 统计信息
    total_modified = 0
    total_fragments = 0
    batch_size = 10
    
    # 分批处理
    for batch_start in range(0, len(files), batch_size):
        batch_end = min(batch_start + batch_size, len(files))
        batch_files = files[batch_start:batch_end]
        
        print(f"\n{'='*60}")
        print(f"处理第{batch_start+1}批: 第{51+batch_start}回 - 第{51+batch_end-1}回")
        print(f"{'='*60}")
        
        batch_modified = 0
        batch_fragments = 0
        
        for file_path in batch_files:
            chapter_num = re.search(r'第(\d+)回', file_path.name).group(1)
            print(f"\n  第{chapter_num}回: {file_path.name}")
            
            modified, fragments = process_chapter(file_path)
            batch_modified += modified
            batch_fragments += fragments
            
            print(f"    片段数: {fragments}, 优化数: {modified}")
        
        total_modified += batch_modified
        total_fragments += batch_fragments
        
        print(f"\n  本批汇总: 优化 {batch_modified}/{batch_fragments} 条 instruct")
    
    # 最终汇总
    print("\n" + "="*80)
    print("优化完成汇总")
    print("="*80)
    print(f"总章节数: {len(files)}")
    print(f"总片段数: {total_fragments}")
    print(f"总优化数: {total_modified}")
    print(f"优化比例: {total_modified/total_fragments*100:.1f}%" if total_fragments > 0 else "N/A")
    print("="*80)

if __name__ == "__main__":
    main()
