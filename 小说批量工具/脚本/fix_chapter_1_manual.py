#!/usr/bin/env python3
import json

with open('/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿/剑来第1章-惊蛰.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

new_data = []
current_id = 0

for item in data['data']:
    text = item['api']['voice']['text']
    
    if text == "院门那边，有个嗓音响起，" and item['id'] == 18:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "院门那边，有个嗓音响起，“你这婢女卖不卖？”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪愣了愣，循着声音转头望去，是个眉眼含笑的锦衣少年，站在院外，一张全然陌生的面孔。" and item['id'] == 19:
        new_item = item.copy()
        new_item['id'] = current_id
        new_data.append(new_item)
        current_id += 1
        
        new_narration = {
            "id": current_id,
            "role": "旁白",
            "api": {
                "voice": {
                    "text": "锦衣少年身边站着一位身材高大的老者，面容白皙，脸色和蔼，轻轻眯眼打量着两座毗邻院落的少年少女。",
                    "role": "旁白",
                    "role_voice": "云健-中年男性磁性声音",
                    "speed": "-10%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "instruct": "平静叙述"
                },
                "bgm": {
                    "play_mode": "keep",
                    "scene": "街巷对峙",
                    "scene_cn": "轻微紧张",
                    "scene_en": "Street Confrontation",
                    "fade_in": 0,
                    "fade_out": 0,
                    "volume": "-25%",
                    "pitch": "+0Hz"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        }
        new_data.append(new_narration)
        current_id += 1
        
        new_narration2 = {
            "id": current_id,
            "role": "旁白",
            "api": {
                "voice": {
                    "text": "老者的视线在陈平安一扫而过，并无停滞，但是在宋集薪和婢女身上，多有停留，笑意渐渐浓郁。",
                    "role": "旁白",
                    "role_voice": "云健-中年男性磁性声音",
                    "speed": "-10%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "instruct": "平静叙述"
                },
                "bgm": {
                    "play_mode": "keep",
                    "scene": "街巷对峙",
                    "scene_cn": "轻微紧张",
                    "scene_en": "Street Confrontation",
                    "fade_in": 0,
                    "fade_out": 0,
                    "volume": "-25%",
                    "pitch": "+0Hz"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        }
        new_data.append(new_narration2)
        current_id += 1
        continue
        
    elif text == "宋集薪斜眼道：" and item['id'] == 22:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "宋集薪斜眼道：“卖！怎么不卖！”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "那少年微笑道：" and item['id'] == 23:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "那少年微笑道：“那你说个价。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪翻了个白眼，伸出一根手指，晃了晃，" and item['id'] == 26:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "宋集薪翻了个白眼，伸出一根手指，晃了晃，“白银一万两！”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "锦衣少年脸色如常，点头道：" and item['id'] == 28:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "锦衣少年脸色如常，点头道：“好。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪见那少年不像是开玩笑的样子，连忙改口道：" and item['id'] == 30:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "宋集薪见那少年不像是开玩笑的样子，连忙改口道：“是黄金万两！”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "锦衣少年嘴角翘起，道：" and item['id'] == 32:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "锦衣少年嘴角翘起，道：“逗你玩的。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪脸色阴沉。" and item['id'] == 34:
        new_item = item.copy()
        new_item['id'] = current_id
        new_data.append(new_item)
        current_id += 1
        
        jinyi_speech = {
            "id": current_id,
            "role": "锦衣少年",
            "api": {
                "voice": {
                    "text": "锦衣少年不再理睬宋集薪，偏移视线，望向陈平安，“今天多亏了你，我才能买到那条鲤鱼，买回去后，我越看越欢喜，想着一定要当面跟你道一声谢，于是就让吴爷爷带我连夜来找你。”",
                    "role": "锦衣少年",
                    "role_voice": "明朗-男声-阳光少年,情感",
                    "speed": "0%",
                    "volume": "+1%",
                    "pitch": "+1Hz",
                    "instruct": "感激"
                },
                "bgm": {
                    "play_mode": "keep",
                    "scene": "街巷对峙",
                    "scene_cn": "轻微紧张",
                    "scene_en": "Street Confrontation",
                    "fade_in": 0,
                    "fade_out": 0,
                    "volume": "-25%",
                    "pitch": "+0Hz"
                },
                "effects": []
            },
            "mix": {"mode": "voice_on_bgm"}
        }
        new_data.append(jinyi_speech)
        current_id += 1
        
        narration = {
            "id": current_id,
            "role": "旁白",
            "api": {
                "voice": {
                    "text": "他丢出一只沉甸甸的绣袋，抛给陈平安，笑脸灿烂道：“这是酬谢，你我就算两清了。”",
                    "role": "旁白",
                    "role_voice": "云健-中年男性磁性声音",
                    "speed": "-10%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "instruct": "生动描述"
                },
                "bgm": {
                    "play_mode": "keep",
                    "scene": "街巷对峙",
                    "scene_cn": "轻微紧张",
                    "scene_en": "Street Confrontation",
                    "fade_in": 0,
                    "fade_out": 0,
                    "volume": "-25%",
                    "pitch": "+0Hz"
                },
                "effects": [{"trigger_delay": 0, "duration": 2, "process_mode": "insert", "name": "钱袋抛掷", "sound_cn": "钱袋落地声", "sound_en": "Money Pouch Dropping", "volume": "-20%", "pitch": "+0Hz"}]
            },
            "mix": {"mode": "mix"}
        }
        new_data.append(narration)
        current_id += 1
        
        narration2 = {
            "id": current_id,
            "role": "旁白",
            "api": {
                "voice": {
                    "text": "陈平安刚想要说话，锦衣少年已经转身离去。",
                    "role": "旁白",
                    "role_voice": "云健-中年男性磁性声音",
                    "speed": "-10%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "instruct": "平静叙述"
                },
                "bgm": {
                    "play_mode": "keep",
                    "scene": "街巷对峙",
                    "scene_cn": "轻微紧张",
                    "scene_en": "Street Confrontation",
                    "fade_in": 0,
                    "fade_out": 0,
                    "volume": "-25%",
                    "pitch": "+0Hz"
                },
                "effects": [{"trigger_delay": 2, "duration": 3, "process_mode": "insert", "name": "脚步轻踏", "sound_cn": "脚步声远去", "sound_en": "Footsteps Fading Away", "volume": "-28%", "pitch": "+0Hz"}]
            },
            "mix": {"mode": "mix"}
        }
        new_data.append(narration2)
        current_id += 1
        continue
        
    elif "今天多亏了你" in text and item['role'] == "锦衣少年":
        continue
        
    elif "他丢出一只沉甸甸的绣袋" in text and item['role'] == "旁白":
        continue
        
    elif "陈平安刚想要说话" in text and item['role'] == "旁白":
        continue
        
    elif text == "死死盯住那对爷孙愈行愈远的背影，宋集薪收回恶狠狠的眼神后，跳下墙头，似乎记起什么，对陈平安说道：" and item['id'] == 39:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "死死盯住那对爷孙愈行愈远的背影，宋集薪收回恶狠狠的眼神后，跳下墙头，似乎记起什么，对陈平安说道：“你还记得正月里的那条四脚吗？”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪换了一句话说出口，" and item['id'] == 51:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "宋集薪换了一句话说出口，“我和稚圭可能下个月就要离开这里了。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "陈平安叹了口气，" and item['id'] == 53:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "陈平安叹了口气，“路上小心。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    elif text == "宋集薪半真半假道：" and item['id'] == 55:
        new_item = item.copy()
        new_item['id'] = current_id
        new_item['api']['voice']['text'] = "宋集薪半真半假道：“有些物件我肯定搬不走，你可别趁我家没人，就肆无忌惮地偷东西。”"
        new_data.append(new_item)
        current_id += 1
        continue
        
    else:
        new_item = item.copy()
        new_item['id'] = current_id
        new_data.append(new_item)
        current_id += 1

data['data'] = new_data

with open('/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来json稿/剑来第1章-惊蛰.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"修复完成！总片段数: {len(data['data'])}")