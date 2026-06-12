#!/usr/bin/env python3
"""Build Chapter 2 JSON script for 剑来第2章-鱼龙变"""
import json
import os

OUTPUT = "小说批量工具/小说剧本原稿/剑来后续json稿/剑来第2章-鱼龙变.json"

roles_definition = {
    "旁白": {"role_voice": "云健-中年男性磁性声音", "pitch": "0Hz", "volume": "0%", "speed": "-10%"},
    "陈平安": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "-2%"},
    "宋集薪": {"role_voice": "元气少年-男声-磁性,性感", "pitch": "+3Hz", "volume": "+2%", "speed": "+2%"},
    "容鱼": {"role_voice": "清冷女神-女声-低沉女声,情感", "pitch": "+1Hz", "volume": "0%", "speed": "-2%"},
    "洪霁": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "秦骠": {"role_voice": "爽朗少年-男声-低沉,稳重", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "司徒殿武": {"role_voice": "热血少年-男声-明亮,成熟", "pitch": "0Hz", "volume": "0%", "speed": "+1%"},
    "王涌金": {"role_voice": "王几-儒雅男声", "pitch": "0Hz", "volume": "0%", "speed": "-3%"},
    "陈溪": {"role_voice": "傲娇女友-女声-甜美,优雅", "pitch": "+4Hz", "volume": "-1%", "speed": "-1%"},
    "韩祎": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "韦赹": {"role_voice": "干净少年-男声-明亮,稳重", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "洪崇本": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "-2Hz", "volume": "0%", "speed": "-3%"},
    "许谧": {"role_voice": "干净少年-男声-明亮,稳重", "pitch": "+1Hz", "volume": "0%", "speed": "0%"},
    "卢钧": {"role_voice": "干净少年-男声-明亮,稳重", "pitch": "+2Hz", "volume": "+1%", "speed": "+1%"},
    "杨后觉": {"role_voice": "王几-儒雅男声", "pitch": "0Hz", "volume": "0%", "speed": "-3%"},
    "曹焽": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "高弑": {"role_voice": "热血少年-男声-明亮,成熟", "pitch": "0Hz", "volume": "0%", "speed": "+1%"},
    "柳䢦": {"role_voice": "油腻大叔-男声-油桑,低沉", "pitch": "-2Hz", "volume": "+1%", "speed": "+2%"},
    "宋连": {"role_voice": "温顺少年-男声-温暖,亲和", "pitch": "0Hz", "volume": "+1%", "speed": "+2%"},
    "巡城司官员": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
    "李拔": {"role_voice": "风发少年-男声-潇洒,磁性", "pitch": "0Hz", "volume": "0%", "speed": "0%"},
}

def seg(role, text, instruct="", effects=None):
    """Create a data segment"""
    rdef = roles_definition[role]
    voice = {
        "role": role,
        "role_voice": rdef["role_voice"],
        "speed": rdef["speed"],
        "volume": rdef["volume"],
        "pitch": rdef["pitch"],
        "text": text,
    }
    if instruct:
        voice["instruct"] = instruct
    entry = {
        "role": role,
        "api": {"voice": voice, "effects": effects or []},
        "mix": {"mode": "voice_only" if role == "旁白" else "mix"},
    }
    return entry

data = []
idx = 0

# id=0: title
data.append({**seg("旁白", "第2章 鱼龙变", instruct="庄重开场"), "id": idx, "mix": {"mode": "voice_only"}})
idx += 1

# ===== Segment 1: Opening narration (lines 3-9) =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {
            "role": "旁白", "role_voice": "云健-中年男性磁性声音",
            "speed": "-10%", "volume": "0%", "pitch": "0Hz",
            "text": "大骊京城的外城，注定会被后世史家浓墨重彩书写一笔的老莺湖。",
            "instruct": "沉稳开场"
        },
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {
            "role": "旁白", "role_voice": "云健-中年男性磁性声音",
            "speed": "-10%", "volume": "0%", "pitch": "0Hz",
            "text": "地支一脉率先返回此地，宋续去了趟御书房，跟皇帝大致说了这场天地通的缘由。只不过宋续也说自己境界低，只算略知皮毛。真相到底如何，只能是问陈国师本人了。皇帝陛下却是摇头笑言一句，我当然好奇那些山巅甚至是天上的奇奇怪怪，不过我更在意大骊朝廷明天的走向。当陈平安重新现身的那一刻，园内众人心情各异，有些终于松了口气，有人将心提到嗓子眼，有人如丧考妣，有人笑颜如花。",
            "instruct": "平实叙述"
        },
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 容鱼说话 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "甲字号院子门口，容鱼轻声说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“洛王等久了，就先去院子里边坐着休息。”", "instruct": "轻声汇报"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安笑道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“他从小就这德行，能躺着绝不坐着，能坐着绝不站着。”", "instruct": "调侃戏谑"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "容鱼说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“陈溪还在水榭那边，韩祎和韦赹都在，不会有任何问题。”", "instruct": "从容告知"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安点点头，问道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“刚好符箐起了南边，不如让陈溪进入国师府？”", "instruct": "商议口吻"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "容鱼试探性问道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“国师是打算让陈溪成为类似符箐的人物，还只是帮她找个落脚地儿？”", "instruct": "试探询问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“当然是后者。”", "instruct": "肯定明确"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "容鱼说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“那我觉得国师府未必是最好的选择，太过引人瞩目，她一辈子都无法与国师府撇清关系了。陈溪看似柔弱，实则性格刚烈，以后总是要嫁人的，国师府侍女的身份，总会让她未来夫家在内的所有人难免多想。”", "instruct": "理性分析"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安点头说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“陈溪以后在京城的日常生活，你可以跟曹耕心商量着来。”", "instruct": "平静交代"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "容鱼领命，只是内心有几分奇怪感受，好像这趟白日斩鬼归来之后的国师……她也说不清道不明。",
                  "instruct": "略带疑惑"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== Entering courtyard, meeting 宋集薪 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "进了院子，见那洛王，已经带着几位扈从离开正屋，准备移步别处。卢钧挤眉弄眼，这么多外人在场，他总不好直接喊师父。陈平安跟这位不记名弟子与那大源新任国师笑着点头致意，道号抟泥的崇玄署杨后觉规规矩矩行了个稽首礼，陈平安坦然受之。再看向宋集薪，陈平安问道：",
                  "instruct": "叙述转场"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“跑什么？这会儿赶去参加小朝会议事啊？是苦口婆心劝说陛下杀殷绩，还是跟陛下诉苦蛮荒战场那边怎么办？”", "instruct": "讥讽调侃"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "下了台阶，宋集薪恼火道：", "instruct": "叙述动作"},
        "effects": [
            {"trigger_delay": 0.5, "duration": 2, "process_mode": "insert", "name": "下台阶脚步声",
             "sound_cn": "下台阶脚步声", "sound_en": "footsteps descending stone steps, wooden courtyard floor, deliberate pace", "volume": "-20%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“我见不得你在这边抖搂威风，这个理由，行[háng]不行？！”", "instruct": "恼火冲撞"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安点头道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“是你的真心话，但你还是别跑。藩王总得有点藩王的担当。”", "instruct": "平静但不乏威严"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪只好重新回到屋子，桌子酒水都已经撤掉，重新布置了一番，有几分官厅模样。看得出来，宋集薪是故意为陈平安如此安排，只要这位国师一回来，就可以马上“就地”议事，绝不会把决议拖延到国师府。至于他这位藩王，当然需要避嫌。宋集薪坐回椅子，瘫靠着椅背，使劲扯了扯领口。他娘的，这种怪话，也就你说了，老子忍了，不好跟你个隐官掰扯什么，换个人看看？",
                  "instruct": "叙述略带恼火"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“你既然喜欢耍官威，也行，换座院子，负责去跟礼部和鸿胪寺官员谈事情。”", "instruct": "半认真半调侃"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪皱眉道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“不妥吧。”", "instruct": "犹豫质疑"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安问道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“不妥在哪里，当着我的面子，藩王见几个京官，是宗室条例里边明文规定你宋睦僭越了？你告诉我，不如我去跟宗人府商量商量，斟酌斟酌？还是担心皇帝陛下你跟礼部、鸿胪寺的文官老爷们密事商量，暗中勾结，要揭竿而起造反？真是如此，你们不得先去兵部刑部衙门借刀弩、借几副甲胄啊？真有这本事，你洛王就叫成事绰绰有余了。”",
                  "instruct": "步步紧逼式反问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪哑口无言，指了指这位一离开家乡泥瓶巷就反而越来越像家乡人的家伙。记仇，你就记仇吧你。我宋集薪也就是上过学塾，读书比你陈平安多，所以不跟你有辱斯文的吵架。不然我真要不管不顾了开骂，也未必会输给你。宋集薪站起身，打算去丙字号院子“升堂办案”，至于那栋乙字号院子，他还真是嫌晦气。宫艳收起那柄纨扇，跟年轻隐官施了个万福。玉道人黄幔则与那位年轻国师拱手作别。",
                  "instruct": "叙述+内心活动"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 溪蛮、李拔段落 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "溪蛮浑然不觉，他的心思还是在高弑兄弟的那把宝刀上边，只是给那大端王朝的曹焽一打岔，东拉西扯，三人关系熟络了，溪蛮也不再好意思总想着在地上白捡了一把宝刀，借刀，耍几天，都是自家兄弟了，总是可以的吧？只有李拔，如芒在背。却不是敬畏眼前这个陈平安，而是一种好像修道之人亲眼见大道的窒息。陈平安聚音成线，与这位金甲洲仙人密语一句，",
                  "instruct": "叙述氛围转变"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“过了今天，焠掌道友就不会有这种感觉了。”", "instruct": "密语宽慰"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安犹豫了一下，先拉着宋集薪一起沿湖散步，跟他说起了国师府那棵桃树、关于桃花朵数的密事。",
                  "instruct": "叙述转换场景"},
        "effects": [
            {"trigger_delay": 1.0, "duration": 6, "process_mode": "insert", "name": "湖边散步脚步",
             "sound_cn": "两人沿湖散步脚步声", "sound_en": "two people walking slowly along lakeside gravel path, soft footsteps, evening quiet", "volume": "-22%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪皱眉道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“说得通。”", "instruct": "迟疑后认同"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "八十几朵的桃花，这就意味着大骊宋氏在那一刻的"真实国祚"，也就不到九十年。当今天子跟他们两个是同龄人，近两百年以来，大骊宋氏历任皇帝即便称不上是什么长寿皇帝，却也极少有夭折的，先帝是例外，这里边毕竟涉及到了山上和文庙禁忌。皇帝宋和算他还有二三十年的国主光阴，假设大皇子宋赓届时顺利继位登基，这位大骊新帝再坐龙椅二三十年……大骊是浩然天下排第三的王朝，国力正值鼎盛，这种庞然大物，是绝不可能在短短几年间就迅速崩塌、断了国祚的，一定会有至少一代人约莫二十年的朝野动荡，由此推断，问题就出在大皇子宋赓手上了，他以及他选中继承大统的，将会断送宋氏国祚？",
                  "instruct": "凝重推演"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪揉了揉太阳穴，",
                  "instruct": "叙述动作"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“我确实觉得宋赓的性格有问题，但是没有想到问题这么大，别看我先前在宋连那边，表现得很不念半点亲情，其实没觉得宋赓真就完完全全无药可救了。宋赓只是相较于父辈、祖辈，显得差劲，与浩然九洲各大王朝作个横向对比，也算拔尖。”",
                  "instruct": "深沉分析带惋惜"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“只用一句话评价宋赓。”", "instruct": "平静提问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪答道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“一位合格的守成之君。”", "instruct": "中肯评价"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“所以你也别把问题只往宋赓身上推，若是某位守土有功、开疆更有功的藩王，回了宝瓶洲，声望极高，朝野上下只知而不藩王占据陪都，信了某位、或是某些扶龙之臣的迷魂汤，觉得划渎而治，先将大骊宋氏一分为二，再由他来追究大统一，对自己好，对大骊宋氏更好。就像你自己说的，宋赓会是合格的守成之君，面对叔叔洛王宋睦的大兵压境，他还怎么守？”",
                  "instruct": "诛心之问，平静却尖锐"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "李拔几个都是道心震动，悚然而惊。陈国师也好，年轻隐官也罢，只差没有点名道姓了？",
                  "instruct": "紧张氛围"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪双手插袖，十指交错，微笑道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“这话就说得诛心了。”", "instruct": "微笑中带着警觉"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“你也别跟我故作轻松，就你那点气度和心眼，我这个邻居，还不了解？”", "instruct": "老友间的直接戳穿"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪无奈道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“好好好，你就可劲儿盯着我这个随时都有可能造反的藩王好了。”", "instruct": "无奈自嘲"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安轻声道：", "instruct": "语气转轻"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“宋集薪，我俩之间避嫌反是嫌疑。但是以后洛京辖境之外，宝瓶洲的山下事能不管，就别管了。话说回来，若是真遇到事了，如今的皇弟也好，将来的皇叔也罢，主动选择管与不管的权力，大骊洛王还是有的，始终都有。”",
                  "instruct": "诚恳而坦率"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪点点头，",
                  "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“也行吧。反正管一管山上神仙，也是我从小的志向。”", "instruct": "勉强同意，带点豪气"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "方才陈平安这话说得终于像几句人话了。",
                  "instruct": "内心感触"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 给李拔信 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安递给李拔一封信，",
                  "instruct": "叙述动作"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“焠掌道友，劳烦将这封密信交予你们王府君。关于大绶朝鬼物'蚬'的来龙去脉，我在信上都写清楚了。”", "instruct": "郑重托付"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "李拔双手接过信封，点头道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "李拔",
    "api": {
        "voice": {"role": "李拔", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“替府君先行谢过国师。”", "instruct": "恭敬致谢"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安笑道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“未来桐叶洲大渎统筹合龙一事，恐怕还需要焠掌道友多费费心。”", "instruct": "微笑嘱托"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "李拔说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "李拔",
    "api": {
        "voice": {"role": "李拔", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“责无旁贷，尽心尽力而已。”", "instruct": "郑重承诺"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 陈平安与宋集薪分别 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“洛王，那就各忙各的？”", "instruct": "轻松收尾"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪伸了个懒腰，瞥了眼明月当空的夜幕，看似随意问道：",
                  "instruct": "叙述动作"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“当真解决了？”", "instruct": "看似随意实则在意"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安嗯了一声，说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“所以接下来的山上事务会比较繁重了。”", "instruct": "从容回应"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "宋集薪呦了一声，",
                  "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“拭目以待。”", "instruct": "不以为然"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "散步玩月，夜游老莺湖，绕了一圈湖边柳荫路，重新回到甲字号院子附近，国师与藩王，各有各的"升堂办案"。宋集薪看似自言自语一句，",
                  "instruct": "叙述转场"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "宋集薪",
    "api": {
        "voice": {"role": "宋集薪", "role_voice": "元气少年-男声-磁性,性感", "speed": "+2%", "volume": "+2%", "pitch": "+3Hz",
                  "text": "“甘为万矢的，欲作万世师。”", "instruct": "低语感慨"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安笑道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“宋搬柴，这话说得诛心了啊。”", "instruct": "打趣回敬"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 洪霁、秦骠、司徒殿武段落 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "进了院子，容鱼很快喊来巡城兵马司的洪霁几人。秦骠还是第一次见到年轻国师的真人，没有坐着，而是站在椅子旁边，他也不知道该怎么开场白，与司徒殿武一起看向洪头儿。洪霁抱拳，他们就跟着。洪霁没说话，他们就不说话。陈平安与他们点头致意，伸手扶住椅圈，笑问道：",
                  "instruct": "叙述场景转入"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“秦校尉，去不去大渎附近的砺州，虽然是处贫瘠之地，但是当个副将，也不算亏待你，何况离家乡也近些。”",
                  "instruct": "和蔼询问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "秦骠瞬间满脸涨红，嚅嚅喏喏，竟是有些手足无措。见秦骠跟个娘们似的，司徒殿武替同僚着急起来，官升两级，一跃成为正四品的一州副将！你还犹豫个啥，搁我，这会儿就已经跟国师大人拱手致谢感恩戴德了，一发狠，我还要斗胆询问国师大人一句，君无戏言……僭越了僭越了，国师可不能糊弄人！洪霁啧了一声，见着了自己，窝里横，鼻子不是鼻子眼睛不是眼睛的，好，见了国师，就连话都说不出来了，丢人现眼嘛。",
                  "instruct": "鲜活叙述，带幽默感"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“秦校尉不着急下决定，回去跟你媳妇好好商量一下。明天给个准信，若是不去，就让洪统领捎句话到国师府，如果决定出京，就自己走一趟国师府。”",
                  "instruct": "体恤宽和"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "司徒殿武拿手肘轻轻一撞秦骠，别犯浑，什么明天不明天的，立即给老子点头答应下来……",
                  "instruct": "急切内心"},
        "effects": [
            {"trigger_delay": 1.0, "duration": 1, "process_mode": "insert", "name": "手肘轻撞",
             "sound_cn": "手肘轻撞声", "sound_en": "gentle elbow nudge against armored shoulder, fabric rustling, subtle impact", "volume": "-25%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "秦骠仍是拱手道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "秦骠",
    "api": {
        "voice": {"role": "秦骠", "role_voice": "爽朗少年-男声-低沉,稳重", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“属下领命，最晚明天朝会结束之前，就会给出答复。”", "instruct": "恭敬但持重"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安笑呵呵道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“听说秦校尉是个妻管严？”", "instruct": "打趣调侃"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "聊起此事，哪怕对方是位高权重的国师，秦骠仍然一下子就腰杆硬了，面不改色道：",
                  "instruct": "叙述神态变化"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "秦骠",
    "api": {
        "voice": {"role": "秦骠", "role_voice": "爽朗少年-男声-低沉,稳重", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“反正属下跟朋友外出喝酒，想喝到什么时辰回家都无妨。”", "instruct": "面不改色的硬气"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "她既不拦着也不说任何重话，秦骠很晚回到家，她也不吵也不骂，就只是每晚都等他，亲自给他开门，再给他煮好一碗醒酒汤。几次过后，秦骠就自己没脸出去喝酒到大半夜了，即便有酒局实在推脱不掉，他也会早些回家，由着洪头儿跟同僚们调侃取笑。如今秦骠在北衙的官职，跟司徒殿武一样都是正五品。如何高官厚禄算不上，但是要知道他们如今才不到四十岁。大骊王朝百余州，一州刺史，就是大骊王朝当之无愧的封疆大吏，正三品。用某些只会在私底下流传的官箴说，就是曾经的半个皇帝了。而一州将军，是从三品，跟北衙统领的洪霁品秩相同。但是一州将军不是每个州都有的，虽说比起刺史低半级，数量少啊。一州将军再往上，就是大骊常设的四镇四征，再往上，就是大骊某支边军的主帅，最上头，就是屈指可数的巡狩使！比上柱国还稀罕！一州副将，是正四品，关键属于大骊官场极有实权的。北衙有一点不好，就是升官图过于"一条线"了，越往上走，道路越窄，座椅就那么几把，就像司徒殿武，都不敢奢望这辈子能够接替洪头儿的位置。这也是长宁县韩祎明明只有六品，却会被大骊朝廷视为候补公卿的原因。韩祎往上走，道路多啊，大小九卿衙署都不成问题。这里熬个两三年，那边待个三两年，全是一笔笔只会越来越厚重的履历。有些官位，只要错过一个机会，或是与谁争不过一个机会，就要注定蹉跎一辈子了，韩祎他们则不然。",
                  "instruct": "温情叙述与官场背景"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 司徒殿武段落 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安转头望向负责堵门的司徒殿武，说道：", "instruct": "叙述转向"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“司徒校尉。”", "instruct": "点名"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "司徒殿武精神抖擞，拱手道：", "instruct": "叙述反应"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "司徒殿武",
    "api": {
        "voice": {"role": "司徒殿武", "role_voice": "热血少年-男声-明亮,成熟", "speed": "+1%", "volume": "0%", "pitch": "0Hz",
                  "text": "“末将在！”", "instruct": "精神抖擞"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“在北衙好好做事，多帮衬点洪统领。”", "instruct": "简洁交代"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "司徒殿武缓缓抬起头，眼神茫然，国师大人，下文呢？不说跟秦骠那个妻管严一样连升两级，提个一级也行，即便不升官，国师大人你口头嘉奖几句，也成！回了家，可以不用挨骂！洪霁也是服了，一个秦骠闷屁没有的，一个司徒殿武胆大包天的，一脚轻轻踹在后者小腿上，低声提醒道：",
                  "instruct": "内心失落与动作叙述"},
        "effects": [
            {"trigger_delay": 3.5, "duration": 1, "process_mode": "insert", "name": "轻踹小腿",
             "sound_cn": "轻踹声", "sound_en": "light kick on calf, boot brushing against boot, subtle impact", "volume": "-25%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "洪霁",
    "api": {
        "voice": {"role": "洪霁", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“一边去。”", "instruct": "低声提醒"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "司徒殿武悻悻然挪步，很快回过味来，毕竟也不是随便一个校尉，就能"帮衬"洪北衙的。行吧，回头到酒桌上，总要让洪头儿给自己敬个酒，好好感谢自己的帮衬，自己再跟他客气一句，唉，都是自家兄弟，见外了……这幅画面，真是想一想就开心。洪霁笑了笑，大概这也就是将种子弟与寒素出身的不同处之一了，心性到底是不一样的，但是，他们都是我大骊边军出身，是我北衙的校尉！一起走出屋子，洪霁故意放慢脚步，高过他们一个台阶，再抬起双臂，伸手环住俩校尉的脖子，加重力道，低声道：",
                  "instruct": "温暖叙述转豪迈"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "洪霁",
    "api": {
        "voice": {"role": "洪霁", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“都不孬，没给北衙丢脸！”", "instruct": "豪迈夸赞"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "司徒殿武嬉皮笑脸道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "司徒殿武",
    "api": {
        "voice": {"role": "司徒殿武", "role_voice": "热血少年-男声-明亮,成熟", "speed": "+1%", "volume": "0%", "pitch": "0Hz",
                  "text": "“秦副将，连升两级，跟我匀一匀也好啊。你自个儿摸摸良心，方才堵门的时候，你说了啥，不都是我在那边跟人骂街，你好意思么你。”",
                  "instruct": "嬉皮笑脸的调侃"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "秦骠拍了拍洪统领跟铁箍似的胳膊，板着脸说道：", "instruct": "叙述动作"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "秦骠",
    "api": {
        "voice": {"role": "秦骠", "role_voice": "爽朗少年-男声-低沉,稳重", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“小小北衙校尉，怎么跟一州副将说话呢。”", "instruct": "板脸假正经"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 王涌金段落 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "永泰县知县王涌金，被容鱼带进屋子。倒是比那个在国师府担任文秘书郎的余氏子弟，硬气些，没有手脚抽搐走路。陈平安沉默片刻，问道：",
                  "instruct": "转场叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“怎么说？”", "instruct": "沉默后的简短发问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金神色黯然道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "王涌金",
    "api": {
        "voice": {"role": "王涌金", "role_voice": "王几-儒雅男声", "speed": "-3%", "volume": "0%", "pitch": "0Hz",
                  "text": "“下官罪莫大焉，任凭国师责罚。”", "instruct": "黯然认罪"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安眯眼问道：", "instruct": "叙述神态"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“怎么说？”", "instruct": "眯眼，意味更深沉的问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金头皮发麻，身体颤抖起来，头脑一片空白，完全说不出话来。容鱼冷笑道：",
                  "instruct": "紧张氛围"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“大骊京城的文胆？轻骨头一个！”", "instruct": "冷笑讥讽"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金扑通一声跪下去，伏地不起。陈平安问道：",
                  "instruct": "叙述动作"},
        "effects": [
            {"trigger_delay": 0.3, "duration": 1, "process_mode": "insert", "name": "扑通跪地",
             "sound_cn": "跪地声", "sound_en": "knees hitting wooden floor with force, fabric rustling, sudden thud", "volume": "-18%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“要么当大官，要么出大事。所以如果想要当大官，就千万别想着挣大钱。这两句话，是谁说的？”", "instruct": "平静而锐利的质问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金泣不成声道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "王涌金",
    "api": {
        "voice": {"role": "王涌金", "role_voice": "王几-儒雅男声", "speed": "-3%", "volume": "0%", "pitch": "0Hz",
                  "text": "“不敢隐瞒国师大人。是下官刚刚升任永泰县知县，跟一位视若己出的同乡晚辈说的肺腑之言。却不是下官最早发明此说，而是从听愚庐先生一本书上看来的，深以为然，奉为圭臬。”",
                  "instruct": "泣不成声"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“很喜欢当官？”", "instruct": "简洁发问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金始终额头贴地，闷声道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "王涌金",
    "api": {
        "voice": {"role": "王涌金", "role_voice": "王几-儒雅男声", "speed": "-3%", "volume": "0%", "pitch": "0Hz",
                  "text": "“喜欢。”", "instruct": "闷声承认"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈平安缓缓说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“这么好的一个名字。”", "instruct": "意味深长"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金茫然。陈平安说道：", "instruct": "叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“那就让你再当三十年的永泰县知县。”", "instruct": "判决般的平静"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金抬起头，疑惑不解。陈平安说道：", "instruct": "叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“起来答话。”", "instruct": "命令式"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金战战兢兢站起身。陈平安说道：",
                  "instruct": "叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈平安",
    "api": {
        "voice": {"role": "陈平安", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "-2%", "volume": "0%", "pitch": "0Hz",
                  "text": "“哪天当腻了，觉得已经当到吐了，什么时候想要辞官，也不必跟谁打招呼，留下官印，走了便是。这个天子脚下的六品京官，你王涌金不当，还有一大把人想当。”",
                  "instruct": "冷峻中带深意"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "王涌金浑浑噩噩走出"厅屋"，下了台阶出了院子，那些衙署胥吏都望向这位也不清楚还是不是知县大人的男人。王涌金收拾好情绪，走到他们身边，牵起那匹马，淡然道："回衙。"竟然能够留任永泰县的堂官，既不是最坏的结局，也绝不是最好的结果，况且好像这辈子注定都要在这个位置上干到致仕回乡的那天了。翻身上马，王涌金一时间悲欣交集，一趟老莺湖之行，这位曾经确实简在帝心的青壮派实权官员，好像就将大好仕途和锦绣前程交待在园子里边了。",
                  "instruct": "悲凉叙述"},
        "effects": [
            {"trigger_delay": 5.5, "duration": 2, "process_mode": "insert", "name": "上马声",
             "sound_cn": "翻身上马声", "sound_en": "mounting horse saddle leather creak, horse hooves shifting, evening quiet", "volume": "-22%", "pitch": "+0Hz"}
        ]
    },
    "mix": {"mode": "mix"}
})
idx += 1

# ===== 水榭 → 陈溪、韩祎、韦赹 =====
data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "当容鱼来到水榭，唯有韩祎如临大敌，至于在菖蒲河开酒楼的韦赹，名叫陈溪的少女，不混官场的缘故，都没有太多感觉。容鱼笑道：",
                  "instruct": "转场"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“你们都一起。不过等会儿国师会先跟韩署理闲聊几句。”", "instruct": "温和引导"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "带着少女一起走在前边，容鱼问道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“陈溪，要不要先回去休息？”", "instruct": "关心询问"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "陈溪摇摇头，觉得还是跟在容鱼姐姐身边更好些。少女壮起胆子，怯生生问道：",
                  "instruct": "叙述神态"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "陈溪",
    "api": {
        "voice": {"role": "陈溪", "role_voice": "傲娇女友-女声-甜美,优雅", "speed": "-1%", "volume": "-1%", "pitch": "+4Hz",
                  "text": "“容鱼姐姐，他真是陈国师吗？”", "instruct": "怯生生"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "容鱼笑道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "容鱼",
    "api": {
        "voice": {"role": "容鱼", "role_voice": "清冷女神-女声-低沉女声,情感", "speed": "-2%", "volume": "0%", "pitch": "+1Hz",
                  "text": "“我们也不敢假冒国师招摇撞骗啊。韩署理他们，个个精明，不好骗吧？就算是开酒楼的韦老板，别看在园子里边说话嗓门不大，到了菖蒲河，也是八面玲珑、打惯了算盘的。”",
                  "instruct": "含笑安抚"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "少女掩嘴而笑。也是，刚才容鱼姐姐离开水榭期间，韦掌柜就邀请自己去他酒楼那边帮忙了，她还在犹豫，主要是韦掌柜给她的"官"太大了些，管着十多号人物呢，每月薪水也委实太多了些。她既感激他，也很佩服韦掌柜的胆子，就不嫌自己晦气么。跟着韩祎走在后边，韦赹小声问道：",
                  "instruct": "轻快叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "韦赹",
    "api": {
        "voice": {"role": "韦赹", "role_voice": "干净少年-男声-明亮,稳重", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“韩六儿，国师大人要去我酒楼喝点？”", "instruct": "小声试探"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "否则胖子实在想不明白，见自己这么个废物做什么。韩祎深呼吸一口气，强行挤出一个笑脸，",
                  "instruct": "叙述内心"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "韩祎",
    "api": {
        "voice": {"role": "韩祎", "role_voice": "风发少年-男声-潇洒,磁性", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“你觉得呢？！”", "instruct": "强忍情绪"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%", "volume": "0%", "pitch": "0Hz",
                  "text": "韦赹说道：", "instruct": "平实叙述"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "韦赹",
    "api": {
        "voice": {"role": "韦赹", "role_voice": "干净少年-男声-明亮,稳重", "speed": "0%", "volume": "0%", "pitch": "0Hz",
                  "text": "“我觉得完全可以啊，我可以亲自下厨露两手……”", "instruct": "大大咧咧"},
        "effects": []
    },
    "mix": {"mode": "mix"}
})
idx += 1

data.append({
    "id": idx, "role": "旁白",
    "api": {
        "voice": {"role": "旁白", "role_voice": "云健-中年男性磁性声音", "speed": "-10%",