#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

# 完整剧本数据
script = {
    "project": "蜀山剑侠传有声小说自动生成",
    "chapter": "第十回 拯孤穷淑女垂青 订良缘醉仙作伐",
    "片头": {
        "novel_name": "蜀山剑侠传",
        "author": "还珠楼主",
        "speaker": "AI合成",
        "role_voice": "云健-低沉"
    },
    "roles_definition": {
        "旁白": {"role_voice": "云健-低沉", "pitch": "0Hz", "volume": "0%", "speed": "-5%"},
        "周云从": {"role_voice": "儒雅青年-磁性,性感", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
        "张老四": {"role_voice": "云风-沉稳,自然男声", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
        "张玉珍": {"role_voice": "俏皮女声-活泼,元气", "pitch": "+2Hz", "volume": "0%", "speed": "0%"},
        "醉道人": {"role_voice": "幽默大爷-沙哑,烟嗓", "pitch": "-5Hz", "volume": "0%", "speed": "+5%"},
        "邱林": {"role_voice": "儒雅君子-低沉,温暖", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
        "小三儿": {"role_voice": "明朗-阳光少年,情感", "pitch": "+5Hz", "volume": "0%", "speed": "+5%"}
    },
    "soundscape": {
        "scene_layers": [
            {
                "name": "雨夜菜园",
                "name_en": "雨夜菜园，屋檐滴水，风声呼啸，破旧茅屋",
                "start_line": 1,
                "end_line": 8,
                "prompt": "very subtle low volume cinematic background ambience, rainy night vegetable garden, distant thunder, wind howling, dripping water from eaves, tense atmosphere",
                "volume": "-26%",
                "fade_in": 2,
                "fade_out": 2,
                "target_dbfs": -32,
                "high_pass_hz": 80,
                "low_pass_hz": 3800
            },
            {
                "name": "邱林豆腐房",
                "name_en": "乡村豆腐房，炉火温暖，豆浆沸腾，木头桌椅",
                "start_line": 9,
                "end_line": 35,
                "prompt": "country tofu workshop, warm fire glow, boiling soy milk, wooden tables and chairs, cozy atmosphere",
                "volume": "-24%",
                "fade_in": 2,
                "fade_out": 2,
                "target_dbfs": -30,
                "high_pass_hz": 90,
                "low_pass_hz": 4000
            },
            {
                "name": "旅途行色",
                "name_en": "清晨赶路，马蹄声声，微风轻拂，晨光熹微",
                "start_line": 36,
                "end_line": 50,
                "prompt": "morning travel on horseback, hoofbeats on road, gentle breeze, early morning light",
                "volume": "-24%",
                "fade_in": 2,
                "fade_out": 2,
                "target_dbfs": -30,
                "high_pass_hz": 90,
                "low_pass_hz": 4000
            },
            {
                "name": "客店夜谈",
                "name_en": "乡村客店，油灯昏黄，酒香弥漫，江湖气息",
                "start_line": 51,
                "end_line": 65,
                "prompt": "country inn at night, dim oil lamp light, wine aroma, martial arts atmosphere",
                "volume": "-24%",
                "fade_in": 2,
                "fade_out": 2,
                "target_dbfs": -30,
                "high_pass_hz": 90,
                "low_pass_hz": 4000
            }
        ]
    },
    "data": [
        {
            "id": 0,
            "role": "旁白",
            "api": {
                "voice": {
                    "role": "旁白",
                    "role_voice": "云健-低沉",
                    "speed": "-5%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "第十回 拯孤穷淑女垂青 订良缘醉仙作伐",
                    "instruct": "庄重开场"
                },
                "effects": []
            },
            "mix": {"mode": "voice_only"}
        },
        {
            "id": 1,
            "role": "旁白",
            "api": {
                "voice": {
                    "role": "旁白",
                    "role_voice": "云健-低沉",
                    "speed": "-5%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "那父女二人听了，甚为动容。云从又问他父女怎样救的自己。",
                    "instruct": "平静叙述"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 2,
            "role": "张老四",
            "api": {
                "voice": {
                    "role": "张老四",
                    "role_voice": "云风-沉稳,自然男声",
                    "speed": "0%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "老汉名叫张老四，旁人因我为人本分，就给我取了一个外号，叫张老实。老伴早年去世，只剩我同我女儿玉珍度日，种这庙里的菜园，已经十多年了。想不到那些和尚这等凶恶。",
                    "instruct": "忧虑叙述"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 3,
            "role": "张老四",
            "api": {
                "voice": {
                    "role": "张老四",
                    "role_voice": "云风-沉稳,自然男声",
                    "speed": "0%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "照这等说来，公子如今虽然得逃活命，明天雨住，庙中和尚往石洞查看踪迹，定然看出公子逃到老汉家中。老汉幼年虽然也懂得一些拳棒，只是双拳难敌四手，我父女绝不是和尚们的敌手。连累老汉父女不要紧，公子性命休矣。",
                    "instruct": "担忧"
                },
                "effects": [{"trigger_delay": 8, "duration": 2, "process_mode": "overlay", "name": "叹气", "sound_cn": "张老四无奈的叹气", "sound_en": "old man sighing with worry", "volume": "-26%"}]
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 4,
            "role": "旁白",
            "api": {
                "voice": {
                    "role": "旁白",
                    "role_voice": "云健-低沉",
                    "speed": "-5%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "云从听了这一席话，又惊又怕，顾不得手脚疼痛，连忙翻身跪倒，苦苦哀求搭救性命。",
                    "instruct": "紧张描述"
                },
                "effects": [{"trigger_delay": 5, "duration": 2, "process_mode": "overlay", "name": "跪倒", "sound_cn": "周云从跪倒在地", "sound_en": "man kneeling urgently", "volume": "-24%"}]
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 5,
            "role": "周云从",
            "api": {
                "voice": {
                    "role": "周云从",
                    "role_voice": "儒雅青年-磁性,性感",
                    "speed": "0%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "老丈救命之恩，学生没齿难忘！还望老丈搭救！",
                    "instruct": "急切哀求"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 6,
            "role": "张老四",
            "api": {
                "voice": {
                    "role": "张老四",
                    "role_voice": "云风-沉稳,自然男声",
                    "speed": "0%",
                    "volume": "0%",
                    "pitch": "0Hz",
                    "text": "公子快快请起。等我同小女商量商量，再作计较。",
                    "instruct": "温和安慰"
                },
                "effects": []
            },
            "mix": {"mode": "mix"}
        },
        {
            "id": 7,
            "role": "旁白",
            "api": {
                "voice": {
                    "role": "旁白",
                    "role_voice": "云健-低沉",
                    "speed": "-5%",
                    "volume": "0%",
