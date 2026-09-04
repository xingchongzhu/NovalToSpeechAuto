#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时构建脚本：生成《蜀山剑侠传》第247回剧本 JSON（随后删除）"""
import json, os

SRC = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/novel_tool/novel_scripts_raw/蜀山剑侠传/蜀山剑侠传第247回-第247回.txt"
OUT = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/novel_tool/novel_scripts/蜀山剑侠转json/蜀山剑侠传第247回-第247回.json"

with open(SRC, encoding="utf-8") as f:
    content = f.read()
anchor = "古杉坪二仙盗法"
idx = content.find(anchor)
assert idx != -1
body = content[idx + len(anchor):]
body_s = body.replace("\u201c", "").replace("\u201d", "")

roles = {
    "旁白": {"role_voice": "旁白", "pitch": "0Hz", "volume": "0%", "speed": "-10%"},
    "谢山": {"role_voice": "谢山", "pitch": "0Hz", "volume": "0%", "speed": "-2%"},
    "谢璎": {"role_voice": "谢璎", "pitch": "+1Hz", "volume": "0%", "speed": "-1%"},
    "谢琳": {"role_voice": "谢琳", "pitch": "+2Hz", "volume": "0%", "speed": "+2%"},
    "叶缤": {"role_voice": "叶缤", "pitch": "0Hz", "volume": "0%", "speed": "-1%"},
    "老佛婆": {"role_voice": "老佛婆", "pitch": "-2Hz", "volume": "0%", "speed": "-4%"},
    "妖童": {"role_voice": "妖童", "pitch": "+3Hz", "volume": "+1%", "speed": "+3%"},
    "乌头婆": {"role_voice": "乌头婆", "pitch": "-3Hz", "volume": "0%", "speed": "+1%"},
    "谢璎/谢琳": {"role_voice": "谢璎_谢琳", "pitch": "+1Hz", "volume": "0%", "speed": "+1%"},
}

# (role, instruct, effects, start_marker)
SEGMENTS = [
    ("旁白", "恢宏叙述，回顾前情，铺陈背景", [
        {"trigger_keyword": "云岚倏地腾涌", "trigger_offset": 0, "duration": 3, "name": "云岚腾涌", "sound_cn": "云岚腾涌如山，朝上卷来", "sound_en": "clouds and mist surging upward like mountains rolling over", "volume": "-20%", "pitch": "+0Hz"},
    ], "上文写到"),
    ("谢琳", "急切呼唤，惊喜交加", [], "爹爹！"),
    ("旁白", "紧张叙述，描绘乃父现身", [
        {"trigger_keyword": "金光", "trigger_offset": 0, "duration": 2, "name": "金光射来", "sound_cn": "一道金光自下方射来，冲开云巷", "sound_en": "a golden light beam shooting up from below splitting the clouds", "volume": "-16%", "pitch": "+0Hz"},
    ], "忽见一道金光"),
    ("谢山", "温和慈祥，含笑叮嘱", [], "你们这次可在此住四五日"),
    ("旁白", "平静叙述，解说叶缤炼法前情", [
        {"trigger_keyword": "白光", "trigger_offset": 0, "duration": 3, "name": "白光字迹", "sound_cn": "手上现出一片白光，光中现出字迹", "sound_en": "a white light appearing with characters shining within it", "volume": "-18%", "pitch": "+0Hz"},
    ], "说罢，将手一扬"),
    ("谢璎", "疑惑询问，条理清晰", [], "爹爹设想如此周密"),
    ("旁白", "平静叙述，铺陈因果", [], "寒月大师原以叶缤此事在所必办"),
    ("谢山", "含笑解答，禅理开示", [], "佛家原以清静寂灭为宗"),
    ("旁白", "平静叙述", [], "谢琳不等说完"),
    ("谢琳", "急切争辩，志得意满", [], "爹爹说的是习了此法以后"),
    ("旁白", "平静叙述", [], "寒月大师闻言颇喜"),
    ("谢山", "眉头微皱，语带告诫", [], "琳儿今日怎地失了故态"),
    ("旁白", "平静叙述", [], "谢琳微笑不答"),
    ("谢山", "郑重叮嘱，压低声音", [], "从此你们不要再开口了"),
    ("旁白", "平静叙述，解说通灵问答", [], "说罢，仍用法力现出金字"),
    ("谢山", "含笑坦白，略带歉意", [], "你叶姑忙于炼法"),
    ("旁白", "平静叙述", [], "谢琳笑道"),
    ("谢琳", "笑着辩解，语气俏皮", [], "爹爹答话含糊"),
    ("旁白", "平静叙述", [], "谢璎笑道"),
    ("谢璎", "笑着点评，温柔了然", [], "琳妹乃是巧辩"),
    ("旁白", "平静叙述", [], "谢山道"),
    ("谢山", "感慨提及，语气平和", [], "你看绝尊者法力何等高强"),
    ("旁白", "平静叙述", [], "二女同声笑道"),
    ("谢璎/谢琳", "同声撒娇，天真依恋", [], "毕竟佛门中人情薄"),
    ("旁白", "平静叙述", [], "谢山笑道"),
    ("谢山", "慈爱笑责，宠溺", [], "痴儿，痴儿"),
    ("旁白", "平静叙述", [], "谢璎道"),
    ("谢璎", "温柔辩白，替父开解", [], "那也不然"),
    ("旁白", "平静叙述", [], "谢琳道"),
    ("谢琳", "伶牙俐齿，引经据典", [], "我佛无缘无故"),
    ("旁白", "平静叙述，过渡到启程", [], "谢山微笑不语"),
    ("谢山", "郑重叮嘱，谆谆告诫", [], "你叶姑明日申初大功告成"),
    ("旁白", "平静叙述，描写巫峡纤夫", [
        {"trigger_keyword": "江流又急", "trigger_offset": 0, "duration": 4, "name": "江流湍急", "sound_cn": "巫峡江流湍急，水面倾斜，纤夫奋力拉纤", "sound_en": "rapid river water rushing through a narrow gorge with strong current", "volume": "-22%", "pitch": "+0Hz"},
    ], "二女领命"),
    ("谢璎", "温柔劝阻，理性分析", [], "巫峡有名的浪恶滩险"),
    ("旁白", "紧张叙述，描写纤夫遇险", [], "谢琳只得罢了"),
    ("谢琳", "怒喝，急切", [], "姊姊，你快去救那些可怜人"),
    ("旁白", "紧张叙述，描写妖童作祟", [], "谢璎心急救人"),
    ("妖童", "凶恶嚣张，破口大骂", [], "狗丫头无故上门欺人"),
    ("旁白", "紧张叙述", [], "谢琳已用法宝将妖童罩住"),
    ("谢琳", "厉声叱喝，正气凛然", [], "无知妖孽"),
    ("旁白", "紧张叙述，描写妖童", [], "谢璎虽觉谢琳不应多事"),
    ("谢璎", "内心独白，暗自忖度", [], "自有护身神光"),
    ("旁白", "平静叙述", [], "便向谢琳传声示意"),
    ("谢琳", "托大自信，不以为意", [], "区区么么小丑"),
    ("旁白", "紧张叙述", [], "谢璎仍未将身现出"),
    ("妖童", "嚣张挑衅，恶语相向", [], "狗丫头，我知你还有同党"),
    ("旁白", "紧张叙述，描写妖童相貌与谢琳追凶", [], "随说随试探着斜飞而上"),
    ("妖童", "凶悍狂妄，戟指喝骂", [
        {"trigger_keyword": "金环", "trigger_offset": 0, "duration": 2, "name": "金环红光", "sound_cn": "左耳金环忽化一圈红光飞起", "sound_en": "a golden ring turning into a ring of red light and flying up", "volume": "-15%", "pitch": "+0Hz"},
    ], "何方无知鼠辈"),
    ("旁白", "紧张叙述，描写斗法", [
        {"trigger_keyword": "飞针", "trigger_offset": 0, "duration": 2, "name": "飞针破空", "sound_cn": "五色飞针暴雨般射出", "sound_en": "five-colored flying needles shooting out like a sudden storm", "volume": "-14%", "pitch": "+0Hz"},
        {"trigger_keyword": "金碧光华", "trigger_offset": 0, "duration": 2, "name": "金碧光华", "sound_cn": "谢琳指上金碧光华飞出，斩碎金环", "sound_en": "a golden-green light streaking out and shattering the ring", "volume": "-13%", "pitch": "+0Hz"},
    ], "谢氏姊妹素来行事光明"),
    ("谢琳", "厉声叱喝，怒不可遏", [], "该死妖孽"),
    ("旁白", "紧张叙述", [], "妖童连受宝光侵削"),
    ("妖童", "外强中干，强作声势", [], "我娘便在前面乌树岭"),
    ("旁白", "平静叙述", [], "谢琳冷笑道"),
    ("谢琳", "冷笑轻蔑，果断", [], "我先前因不知你巢穴"),
    ("旁白", "紧张叙述", [], "妖童原以先前连唤未应"),
    ("妖童", "凶恶咒骂，戛然而止", [], "狗丫头"),
    ("旁白", "紧张叙述，描写妖童伏诛", [
        {"trigger_keyword": "碧蜈钩", "trigger_offset": 0, "duration": 2, "name": "碧蜈钩飞", "sound_cn": "碧蜈钩化作金碧光华绞向妖童", "sound_en": "a golden-green hook light whirling and slashing through the air", "volume": "-14%", "pitch": "+0Hz"},
    ], "，底下话未出口"),
    ("谢璎", "温柔劝阻，提醒父亲嘱托", [], "妹子，你忘记爹爹的话吗"),
    ("旁白", "平静叙述", [], "谢琳本和乃姊一样天真和善"),
    ("谢璎", "理性分析，沉稳劝解", [], "这妖孽看她孽子"),
    ("旁白", "平静叙述", [], "谢琳也觉此言有理"),
    ("谢琳", "高声叱喝，正气凛然", [], "该死妖妇"),
    ("旁白", "紧张叙述，描写乌头婆追来", [], "说罢，也无回应"),
    ("乌头婆", "凄厉哭喊，悲愤怨毒", [], "何方贱婢"),
    ("旁白", "紧张叙述", [], "二女遁光何等神速"),
    ("谢琳", "急促惊呼，脱口而出", [], "姊姊！"),
    ("旁白", "紧张叙述", [], "声才出口"),
    ("乌头婆", "凄厉哭喊，摄魂夺魄", [], "仇人"),
    ("旁白", "紧张叙述，描写摄魂斗法", [], "谢琳底下话未出口"),
    ("谢璎", "内心独白，暗自警觉", [], "无论多厉害的妖人"),
    ("旁白", "紧张叙述，铺陈乌头婆来历", [], "忙用手揽住谢琳"),
    ("老佛婆", "和蔼慈祥，语调平稳", [], "芬陀大师师徒现往南海"),
    ("旁白", "平静叙述", [], "二女见这老佛婆"),
    ("老佛婆", "和蔼中带着谦逊", [], "我姓丘"),
    ("旁白", "平静叙述", [], "随说，随引二女"),
    ("老佛婆", "和蔼，带着一丝考较的意味", [], "道友理会得吗"),
    ("旁白", "平静叙述", [], "二女同声答道"),
    ("谢璎/谢琳", "恭敬有礼，略带谦逊", [], "师伯之命"),
    ("旁白", "平静叙述", [], "老佛婆道"),
    ("老佛婆", "神秘而安详，点到为止", [], "如论此时"),
    ("旁白", "平静叙述，描写双杉坪", [
        {"trigger_keyword": "双杉", "trigger_offset": 0, "duration": 3, "name": "古杉奇景", "sound_cn": "双杉铁干撑空，枝叶葱茏", "sound_en": "ancient fir trees standing tall with lush rustling branches", "volume": "-20%", "pitch": "+0Hz"},
    ], "二女知她不肯深说"),
    ("叶缤", "含笑招呼，亲切", [], "璎、琳二女来得真巧"),
    ("旁白", "神秘叙述，描写移峰开洞", [
        {"trigger_keyword": "地底殷殷雷鸣", "trigger_offset": 0, "duration": 3, "name": "地底雷鸣", "sound_cn": "地底殷殷雷鸣，小峰往前移动", "sound_en": "deep rumbling from underground as the small peak shifts forward", "volume": "-16%", "pitch": "+0Hz"},
    ], "二女一听声由圆石发出"),
    ("叶缤", "亲切唤道，喜悦", [], "峰移洞现"),
    ("旁白", "平静叙述", [], "这次话声却由地底传来"),
    ("叶缤", "含笑自嘲，喜悦", [], "今日大功告成"),
    ("旁白", "平静叙述", [], "话还未毕"),
    ("谢琳", "天真活泼，好奇欣喜", [], "叶姑，几时炼此妙法"),
    ("旁白", "平静叙述", [], "叶缤道"),
    ("叶缤", "语气淡然，随口一问", [], "这些下乘法术"),
    ("旁白", "平静叙述", [], "谢琳笑道"),
    ("谢琳", "俏皮反问，带着撒娇意味", [], "叶姑神通广大"),
    ("旁白", "平静叙述", [], "说罢，又道"),
    ("谢琳", "天真活泼，提出打赌", [], "啊！今天不许叶姑算"),
    ("旁白", "平静叙述", [], "叶缤一手一个"),
    ("叶缤", "带着笑意，语气宠溺", [], "这还有估不到的"),
    ("旁白", "平静叙述", [], "二女同笑道"),
    ("谢璎/谢琳", "同声笑语，撒娇", [], "却不许你按神光占算呢"),
    ("旁白", "平静叙述", [], "叶缤笑道"),
    ("叶缤", "温和，带着长者的慈爱", [], "我最爱你姊妹天真"),
    ("旁白", "平静叙述", [], "谢琳早已瞥见"),
    ("谢琳", "故作不知，撒娇", [], "叶姑，不收书有什要紧"),
    ("旁白", "平静叙述", [], "叶缤闻言，立被打动"),
    ("叶缤", "温和解释，语带关切", [], "此书以前乃神泥封合"),
    ("旁白", "平静叙述", [], "谢琳笑道"),
    ("谢琳", "俏皮狡黠，转移话题", [], "姊姊先不说"),
    ("旁白", "平静叙述", [], "叶缤因无坐处"),
    ("叶缤", "带着笑意，准备猜谜", [], "那么，我先猜吧"),
    ("旁白", "平静叙述", [], "二女见叶缤一昧欣喜"),
    ("叶缤", "带着宠溺的调侃", [], "没见你姊妹都不小了"),
    ("旁白", "平静叙述", [], "二女拍手笑道"),
    ("谢璎/谢琳", "拍手嬉笑，天真", [], "这头一估"),
    ("旁白", "平静叙述", [], "叶缤笑道"),
    ("叶缤", "依然带着笑意，继续猜测", [], "我答还未完呢"),
    ("旁白", "平静叙述", [], "谢璎闻言"),
    ("谢琳", "语速快，带着掩饰的兴奋", [], "全估不对"),
    ("旁白", "平静叙述", [], "叶缤也是爱怜二女太甚"),
    ("谢琳", "故作气愤，添枝加叶", [], "我二人是让一个名叫乌头婆的妖妇"),
    ("旁白", "平静叙述", [], "叶缤惊道"),
    ("叶缤", "惊讶，语带关切", [], "那老妖妇邪法厉害"),
    ("旁白", "平静叙述", [], "谢璎正要开口"),
    ("谢琳", "语速快，带着激愤与请求", [], "姊姊莫插话"),
    ("旁白", "平静叙述", [], "说罢，随即添枝加叶"),
    ("谢琳", "绘声绘色，编造经过", [], "久不见爹爹和叶姑"),
    ("旁白", "平静叙述", [], "叶缤以为忍大师欲令二女承她衣钵"),
    ("叶缤", "语气转为认真，略带探究", [], "那妖妇既与你们结下杀子之仇"),
    ("旁白", "平静叙述，描写宝箓讲解", [
        {"trigger_keyword": "白光连闪", "trigger_offset": 0, "duration": 2, "name": "白光连闪", "sound_cn": "洞顶白光连闪，叶缤入定", "sound_en": "white light flashing from the cave ceiling", "volume": "-16%", "pitch": "+0Hz"},
    ], "二女闻言，知已上套"),
    ("叶缤", "含笑叮嘱，语气温和", [], "你父亲不知有何要事与我通灵"),
    ("旁白", "平静叙述", [], "谢琳将小嘴一撇"),
    ("谢琳", "故作顽皮，实则心虚", [], "叶姑既不放心我们"),
    ("旁白", "平静叙述，描写盗书", [
        {"trigger_keyword": "金花宝焰", "trigger_offset": 0, "duration": 3, "name": "金花宝焰", "sound_cn": "金砂立化成金花宝焰笼罩宝书", "sound_en": "golden sand turning into blazing golden flowers covering the book", "volume": "-15%", "pitch": "+0Hz"},
    ], "叶缤急于和谢山问答"),
    ("谢璎", "笑着指出漏洞，语气温和", [], "你今日怎这粗心"),
    ("旁白", "平静叙述", [], "谢琳含笑点头"),
    ("叶缤", "语气带着一丝不悦，但仍有爱意", [], "我起初只当你二人孪生姊妹"),
    ("旁白", "平静叙述", [], "谢璎也忙跪下道"),
    ("谢璎", "诚恳认错，条理清晰", [], "此事休怪琳妹一人"),
    ("旁白", "平静叙述", [], "谢琳因从小便受叶缤爱怜"),
    ("叶缤", "转为语重心长，既有感慨又有剖析", [], "痴儿，我岂不知此是你师父"),
    ("旁白", "平静叙述", [], "谢琳吃叶缤一抚慰"),
    ("谢琳", "乘机笑答，剖析师意", [], "爹爹和叶姑至今还不知师父用意"),
    ("旁白", "平静叙述", [], "叶缤闻言，好似恍然"),
    ("叶缤", "感慨，声音低缓", [], "你师父对我真个故人情重呢"),
    ("旁白", "平静叙述", [], "谢璎接口问道"),
    ("谢璎", "恭敬提问，带着好奇", [], "叶姑和师父几生至交"),
    ("旁白", "平静叙述", [], "叶缤道"),
    ("叶缤", "语气转为严肃谨慎，谆谆告诫", [], "详情此时不便明言"),
    ("旁白", "平静叙述", [], "谢璎忙答"),
    ("谢璎", "恭敬回答，表示谨记", [], "叶姑如此叮嘱"),
    ("旁白", "平静叙述", [], "叶缤道"),
    ("叶缤", "语气转为自责与感慨", [], "你爹不是不知"),
    ("旁白", "平静叙述", [], "说罢，便令谢璎立向一旁"),
]

# 切分
texts = []
pos = 0
n = len(SEGMENTS)
for i, (role, instruct, effects, marker) in enumerate(SEGMENTS):
    start = body_s.find(marker, pos)
    assert start != -1, f"未找到片段起始标记: {marker!r} (第{i}段)"
    if i + 1 < n:
        end = body_s.find(SEGMENTS[i + 1][3], start + len(marker))
        assert end != -1, f"未找到下一片段起始标记: {SEGMENTS[i+1][3]!r} (第{i+1}段)"
    else:
        end = len(body_s)
    texts.append(body_s[start:end])
    pos = end

joined = "".join(texts)
if joined != body_s:
    for i in range(min(len(joined), len(body_s))):
        if joined[i] != body_s[i]:
            print("校验失败，首个差异位置", i)
            print("期望:", repr(body_s[max(0,i-25):i+25]))
            print("实际:", repr(joined[max(0,i-25):i+25]))
            raise SystemExit(1)
    print("校验失败：长度不一致", len(joined), len(body_s))
    raise SystemExit(1)
print("✅ 原文完整性校验通过：正文", len(body_s), "字")

# data
data = [{
    "id": 0, "role": "旁白",
    "api": {"voice": {"role": "旁白", "role_voice": "旁白", "speed": "-10%", "volume": "0%", "pitch": "0Hz", "text": "第247回", "instruct": "庄重大气，掷地有声，说书人的韵味"}, "effects": []},
    "mix": {"mode": "voice_only"},
}]
for i, (role, instruct, effects, _m) in enumerate(SEGMENTS):
    rv = roles[role]
    text = texts[i]
    ef_list = []
    for ef in effects:
        kw = ef["trigger_keyword"]
        p = text.find(kw)
        delay = round(p / 3.0, 1) if p >= 0 else 0
        ef_list.append({
            "trigger_delay": delay, "trigger_keyword": kw, "trigger_offset": ef["trigger_offset"],
            "duration": ef["duration"], "process_mode": "overlay", "name": ef["name"],
            "sound_cn": ef["sound_cn"], "sound_en": ef["sound_en"], "volume": ef["volume"], "pitch": ef["pitch"],
        })
    data.append({
        "id": i + 1, "role": role,
        "api": {"voice": {"role": role, "role_voice": rv["role_voice"], "speed": rv["speed"], "volume": rv["volume"], "pitch": rv["pitch"], "text": text, "instruct": instruct}, "effects": ef_list},
        "mix": {"mode": "mix"},
    })

def sc(name, name_en, s, e, prompt, vol="-22%", lp=4200):
    return {"name": name, "name_en": name_en, "start_line": s, "end_line": e,
            "prompt": prompt, "volume": vol, "fade_in": 2, "fade_out": 2,
            "target_dbfs": -30, "high_pass_hz": 90, "low_pass_hz": lp}

scene_layers = [
    sc("武夷云海", "武夷山巅云海翻涌，金光开巷，父女久别重逢，气氛温煦",
       1, 4, "very subtle low volume cinematic background ambience, misty mountain summit above a sea of clouds, soft wind over pine forest, faint golden light piercing clouds, warm and serene reunion atmosphere, deep guqin low resonance, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts"),
    sc("武夷屋内长谈", "武夷山居室内，父女密议降魔真诀，窗外梅林，静谧温馨",
       5, 31, "very subtle low volume cinematic background ambience, quiet mountain house interior, faint plum blossom fragrance in air, soft creak of wooden beams, low charcoal brazier crackle, intimate and warm family talk, soft xiao flute distant and breathy, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts"),
    sc("巫峡纤道", "巫峡江流湍急，危崖纤道，纤夫呼号拉纤，江水奔腾",
       32, 45, "very subtle low volume cinematic background ambience, deep narrow gorge with rushing river, surging water against cliffs, distant shouting of trackers echoing, wind through the gorge, tense and laborious atmosphere, warm erhu hum, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts", "-26%"),
    sc("巫峡斗妖童", "巫峡崖顶追凶，二女与妖童斗法，宝光纵横，剑拔弩张",
       46, 60, "very subtle low volume cinematic background ambience, perilous cliff tops over a gorge, rushing wind, faint demonic aura, tense confrontation, low drone of magic power, sparse pipa plucks, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts", "-24%"),
    sc("雪山倚天崖", "雪山边倚天崖，山风劲疾，龙象庵前二女驻足，肃穆清寒",
       61, 80, "very subtle low volume cinematic background ambience, snow mountain boundary with cold howling wind, sparse trees rustling, faint temple bell from afar, solemn and cold atmosphere, deep guqin low resonance, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts", "-24%"),
    sc("双杉坪仙府", "双杉坪古木奇峰，地底洞府中叶缤炼法，金光宝焰，仙家气象",
       81, 103, "very subtle low volume cinematic background ambience, hidden cave dwelling beneath twin ancient firs, faint golden magic light, subtle echo of deep stone chamber, low hum of spiritual power, serene and mystical atmosphere, soft xiao flute distant and breathy, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts"),
]

result = {
    "project": "蜀山剑侠传有声小说自动生成",
    "chapter": "第247回",
    "片头": {"novel_name": "蜀山剑侠传", "author": "还珠楼主", "speaker": "AI合成", "role_voice": "旁白"},
    "roles_definition": roles,
    "data": data,
    "soundscape": {"scene_layers": scene_layers},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("✅ 已写入:", OUT)
print("片段总数:", len(data), "（含标题）")
print("场景层数:", len(scene_layers))
