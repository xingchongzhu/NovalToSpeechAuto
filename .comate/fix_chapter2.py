#!/usr/bin/env python3
"""Fix existing truncated Chapter 2 JSON and generate remaining segments."""
import json, re

SRC = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/小说批量工具/小说剧本原稿/剑来后续json稿/剑来第2章-鱼龙变.json"
DST = SRC  # overwrite in place

with open(SRC, 'r', encoding='utf-8') as f:
    raw = f.read()

# ============================================================
# 1. Fix roles_definition issues
# ============================================================

# Fix 洪霁: 毒少-冷酷男声 -> 风发少年-男声-潇洒,磁性, pitch -2Hz->0Hz, speed -1%->0%
raw = raw.replace(
    '"洪霁": {\n      "role_voice": "毒少-冷酷男声",\n      "pitch": "-2Hz",\n      "volume": "0%",\n      "speed": "-1%"',
    '"洪霁": {\n      "role_voice": "风发少年-男声-潇洒,磁性",\n      "pitch": "0Hz",\n      "volume": "0%",\n      "speed": "0%"'
)

# Fix 洪崇本: 邪-男声-气泡音大叔,低音炮 -> 风发少年-男声-潇洒,磁性, pitch -2Hz->0Hz, speed -4%->0%
raw = raw.replace(
    '"洪崇本": {\n      "role_voice": "邪-男声-气泡音大叔,低音炮",\n      "pitch": "-2Hz",\n      "volume": "0%",\n      "speed": "-4%"',
    '"洪崇本": {\n      "role_voice": "风发少年-男声-潇洒,磁性",\n      "pitch": "0Hz",\n      "volume": "0%",\n      "speed": "0%"'
)

# Remove roles that don't appear in Chapter 2: 老秀才, 小米粒, 宋云间
for role_name in ['老秀才', '小米粒', '宋云间']:
    # Find and remove the role block
    pattern = r'    "' + role_name + r'": \{[^}]+\},?\n'
    raw = re.sub(pattern, '', raw)

# Add 宋连 and 巡城司官员 before the closing of roles_definition
insert_roles = '''    "宋连": {
      "role_voice": "温顺少年-男声-温暖,亲和",
      "pitch": "0Hz",
      "volume": "0%",
      "speed": "0%"
    },
    "巡城司官员": {
      "role_voice": "风发少年-男声-潇洒,磁性",
      "pitch": "0Hz",
      "volume": "0%",
      "speed": "0%"
    }
  },'''
raw = raw.replace(
    '  },\n  "data": [',
    insert_roles + '\n  "data": ['
)

# ============================================================
# 2. Fix 洪霁 data segments (change voice params in data)
# ============================================================
# In data segments, 洪霁's voice params need to match new roles_definition
raw = raw.replace(
    '"role_voice": "毒少-冷酷男声",\n          "speed": "-1%",\n          "volume": "0%",\n          "pitch": "-2Hz"',
    '"role_voice": "风发少年-男声-潇洒,磁性",\n          "speed": "0%",\n          "volume": "0%",\n          "pitch": "0Hz"'
)

# Fix 洪崇本 data segments
raw = raw.replace(
    '"role_voice": "邪-男声-气泡音大叔,低音炮",\n          "speed": "-4%",\n          "volume": "0%",\n          "pitch": "-2Hz"',
    '"role_voice": "风发少年-男声-潇洒,磁性",\n          "speed": "0%",\n          "volume": "0%",\n          "pitch": "0Hz"'
)

# ============================================================
# 3. Truncate at the last complete segment (id=196)
# ============================================================
# Find the end of id=196 segment and truncate there
# id=196 ends before the id=197 segment starts
idx_197 = raw.find('"id": 197')
if idx_197 == -1:
    print("ERROR: Could not find id=197!")
    exit(1)

# Find the preceding '    },\n    {' pattern to remove the trailing comma from id=196
# Actually we need to keep the comma, just remove everything from id=197 onward
# Find the '    },' that closes id=196
search_start = idx_197 - 500
preceding_close = raw.rfind('    },\n', search_start, idx_197)
if preceding_close == -1:
    print("ERROR: Could not find id=196 close!")
    exit(1)

raw = raw[:preceding_close + len('    },')]  # Keep the closing bracket + comma

print(f"Truncated at character {len(raw)}, removing incomplete id=197+")

# ============================================================
# 4. Generate remaining segments (id=197 onward)
# ============================================================

def seg(id_num, role, role_voice, speed, volume, pitch, text, instruct, effects=None, mix_mode="mix"):
    """Generate a data segment."""
    eff_json = json.dumps(effects, ensure_ascii=False, indent=10) if effects else "[]"
    return f'''    {{
      "id": {id_num},
      "role": "{role}",
      "api": {{
        "voice": {{
          "role": "{role}",
          "role_voice": "{role_voice}",
          "speed": "{speed}",
          "volume": "{volume}",
          "pitch": "{pitch}",
          "text": {json.dumps(text, ensure_ascii=False)},
          "instruct": "{instruct}"
        }},
        "effects": {eff_json}
      }},
      "mix": {{ "mode": "{mix_mode}" }}
    }}'''

# Voice params shorthand
V = {
    "旁白": ("云健-中年男性磁性声音", "-10%", "0%", "0Hz"),
    "陈平安": ("风发少年-男声-潇洒,磁性", "-2%", "0%", "0Hz"),
    "宋集薪": ("元气少年-男声-磁性,性感", "+2%", "+2%", "+3Hz"),
    "容鱼": ("清冷女神-女声-低沉女声,情感", "+1%", "+1%", "+1Hz"),
    "卢钧": ("干净少年-男声-明亮,稳重", "+1%", "+2%", "+3%"),
    "李拔": ("风发少年-男声-潇洒,磁性", "0%", "0%", "0Hz"),
    "洪霁": ("风发少年-男声-潇洒,磁性", "0%", "0%", "0Hz"),
    "秦骠": ("爽朗少年-男声-低沉,稳重", "0%", "0%", "0Hz"),
    "司徒殿武": ("热血少年-男声-明亮,成熟", "+2%", "+2%", "+1Hz"),
    "王涌金": ("王几-儒雅男声", "-2%", "0%", "0Hz"),
    "韩祎": ("风发少年-男声-潇洒,磁性", "0%", "0%", "+1Hz"),
    "韦赹": ("干净少年-男声-明亮,稳重", "+5%", "+2%", "+2Hz"),
    "陈溪": ("傲娇女友-女声-甜美,优雅", "-2%", "-2%", "+2Hz"),
    "洪崇本": ("风发少年-男声-潇洒,磁性", "0%", "0%", "0Hz"),
    "许谧": ("干净少年-男声-明亮,稳重", "-1%", "0%", "+1Hz"),
    "杨后觉": ("王几-儒雅男声", "-3%", "0%", "+1Hz"),
    "曹焽": ("风发少年-男声-潇洒,磁性", "0%", "0%", "+1Hz"),
    "高弑": ("热血少年-男声-明亮,成熟", "+2%", "+2%", "+2Hz"),
    "柳䢦": ("油腻大叔-男声-油桑,低沉", "+1%", "0%", "0Hz"),
    "宋连": ("温顺少年-男声-温暖,亲和", "0%", "0%", "0Hz"),
    "巡城司官员": ("风发少年-男声-潇洒,磁性", "0%", "0%", "0Hz"),
}

def s(id_num, role, text, instruct, effects=None):
    v = V[role]
    return seg(id_num, role, v[0], v[1], v[2], v[3], text, instruct, effects)

remaining = []

# id=197: 高弑 speech about the sword (complete version)
remaining.append(s(197, "高弑",
    "陈隐官，此刀是祖传之物，只要出鞘，它就能主动够汲取修士的灵气，武夫用来对付山上修士，极为霸道。也怪我自己，喜好江湖虚名，青年时就带着它一起去闯荡了。二十年间，为了保住它，好几次差点出现意外，所以必须找个厉害的靠山，最近的靠山，就是蔡玉缮帮忙牵线搭桥，推荐了皇子殷邈给我。",
    "真诚",
    [{"trigger_delay": 0, "duration": 2, "process_mode": "insert", "name": "佩刀取下",
     "sound_cn": "从腰间取下佩刀的金属碰撞声",
     "sound_en": "metal sheath unsheathing sound, blade drawn from scabbard, steel sliding against wood",
     "volume": "-15%", "pitch": "+0Hz"}]
))

# id=198: 旁白 - "说到这里，高弑自行摘下佩刀，双手奉上，"
remaining.append(s(198, "旁白",
    "说到这里，高弑自行摘下佩刀，双手奉上，",
    "叙述"
))

# id=199: 高弑 - final part
remaining.append(s(199, "高弑",
    "陈隐官，送给别人，我豁出命去也不肯，唯独送给你，心疼归心疼，倒也舍得。",
    "心疼但不悔",
    [{"trigger_delay": 0.5, "duration": 2, "process_mode": "insert", "name": "双手奉刀",
     "sound_cn": "双手将佩刀恭敬奉上的轻微金属声",
     "sound_en": "both hands carefully offering a sword, gentle metal clink as blade is presented",
     "volume": "-20%", "pitch": "+0Hz"}]
))

# id=200: 陈平安 refuses
remaining.append(s(200, "陈平安",
    "君子不夺人所好，我就只是好奇，没有让你为难的意思。我见过的好物件，多了去。",
    "笑呵呵摆手"
))

# id=201: 旁白 - 高弑急了
remaining.append(s(201, "旁白",
    "不曾想高弑反而急了，",
    "叙述"
))

# id=202: 高弑 offer deal
remaining.append(s(202, "高弑",
    "陈国师，我忍痛割爱，送出宝刀，你投桃报李，还我一个大骊朝的武将大官当当，是可以的……",
    "急切讨好"
))

# id=203: 旁白 - 卢钧 and 曹焽 reactions
remaining.append(s(203, "旁白",
    "卢钧瞪大眼睛，这哥们，妙啊。曹焽也觉得高弑去大端边军更好。陈平安忍俊不禁，",
    "生动叙述"
))

# id=204: 陈平安 teases
remaining.append(s(204, "陈平安",
    "你搁这儿说书呢。",
    "忍俊不禁"
))

# id=205: 旁白
remaining.append(s(205, "旁白",
    "高弑赧颜无言。陈平安想了想，说道：",
    "叙述"
))

# id=206: 陈平安 - 蛮荒 analysis
remaining.append(s(206, "陈平安",
    "让你去蛮荒打生打死，是强人所难了，估计你两害相权取其轻，真去了蛮荒，也会丢下刀就连夜跑路，就当是一笔买命财了？",
    "看透人心"
))

# id=207: 高弑
remaining.append(s(207, "高弑",
    "陈隐官真是料事如神。",
    "心悦诚服"
))

# id=208: 旁白 + 杨后觉
remaining.append(s(208, "旁白",
    "杨后觉微笑道：",
    "叙述"
))

# id=209: 杨后觉
remaining.append(s(209, "杨后觉",
    "高宗师混官场定能混出名堂。",
    "微笑调侃"
))

# id=210: 旁白 - 高弑 inner
remaining.append(s(210, "旁白",
    "高弑皱眉斜眼，我一个大骊边军将卒与自家国师搁这儿聊正事，轮得到你杨真人一个外人在这边说怪话？陈平安却说道：",
    "生动叙述"
))

# id=211: 陈平安 retort
remaining.append(s(211, "陈平安",
    "料事如神？我就没料到高宗师这么会聊天。",
    "调侃"
))

# id=212: 陈平安 - three choices (long)
remaining.append(s(212, "陈平安",
    "行了，大骊边境暂时没有仗可打，你去了也是混日子。你现在有三个选择，一个是你自己说的，去投军，无所事事个十年，之后也能想去哪里就去那里。再一个是担任大骊刑部供奉，可以提前送你一块三等无事牌，三年之后，如果碌碌无为，刑部就收缴回去，你再去投军。第三个选择，去北衙当差，从巡城兵马司的普通小吏干起，至于十年之内，能当多大的官，凭你自己本事。",
    "认真分析"
))

# id=213: 高弑 chooses
remaining.append(s(213, "高弑",
    "我就去北衙！",
    "毫不犹豫"
))

# id=214: 旁白 - 高弑 inner thoughts (long)
remaining.append(s(214, "旁白",
    "还真怕大绶王朝那边狗急乱咬人。还是在大骊京城混日子更稳妥些。这位年轻隐官的大致脾气，还有洪霁洪统领的行事风格，高弑觉得自己都有数了。后者好相处的，是个直爽汉子。前者不好打交道，我一个北衙小吏，打啥交道呢。遥想当年，高弑也曾意气风发，少年立志出乡关。觉得整座江湖都在等着自己，只等他去扬名立万。陈平安突然说道：",
    "深沉叙述"
))

# id=215: 陈平安 allows resignation
remaining.append(s(215, "陈平安",
    "若是待了一段时日，实在是觉得大骊不如何，就去国师府找容鱼说一声，辞了官，继续走你的江湖便是。",
    "平静宽厚"
))

# id=216: 旁白 + 高弑
remaining.append(s(216, "旁白",
    "高弑错愕不已，",
    "叙述"
))

# id=217: 高弑
remaining.append(s(217, "高弑",
    "当真可以？",
    "错愕"
))

# id=218: 陈平安
remaining.append(s(218, "陈平安",
    "你要自己\u201c作假\u201d，我有什么办法。",
    "笑"
))

# id=219: 旁白 + 高弑
remaining.append(s(219, "旁白",
    "高弑猛地站起身，再无半点寄人篱下的畏缩神态，豪气干云，拱手道：",
    "激昂叙述"
))

# id=220: 高弑
remaining.append(s(220, "高弑",
    "陈平安，谢了！",
    "豪气干云",
    [{"trigger_delay": 0, "duration": 2, "process_mode": "insert", "name": "猛然起身",
     "sound_cn": "猛然站起身带动衣袍的声响",
     "sound_en": "person abruptly standing up from sitting, fabric rustling and chair scraping on floor",
     "volume": "-15%", "pitch": "+0Hz"}]
))

# id=221: 旁白 - 柳䢦 called
remaining.append(s(221, "旁白",
    "六爷"黄连"一行人当中，单单喊了有个江湖门派的渠帅柳䢦。不是国师府容鱼出面，而是一位兵马司年轻官员，找到了柳䢦。柳䢦得知此事的时候，都不敢说话，只能是用眼神与那六爷求助。连那大绶皇帝的尸体都只是用一张竹席裹了，随便丢在墙角，那他柳䢦算个什么东西？宋连犹豫了一番，还是与那位巡城司官员问道：",
    "紧张叙述"
))

# id=222: 宋连
remaining.append(s(222, "宋连",
    "敢问国师的意思是？",
    "试探"
))

# id=223: 巡城司官员
remaining.append(s(223, "巡城司官员",
    "不清楚。",
    "淡然"
))

# id=224: 宋连
remaining.append(s(224, "宋连",
    "去了再说。",
    "无奈"
))

# id=225: 旁白
remaining.append(s(225, "旁白",
    "柳䢦更无奈。只好跟着那位巡城司的官爷一起去了甲字号院子。说得直接点，大骊王朝的山上人事，由大骊刑部和礼部管。但是江湖恩怨，就是巡城兵马司定他们柳䢦的荣辱和生死。宽敞且亮堂的厅屋，除了那位青衫男子的主位，还有两排官帽椅，以一只只花几间隔。其中一把靠门椅子，花几上边放了茶盏。得了个"坐"字，十数步距离，对柳䢦而言，不啻天壤。容鱼在这位极有眼力劲的渠帅落座后就先行离开。陈平安问道：",
    "沉稳叙述"
))

# id=226: 陈平安
remaining.append(s(226, "陈平安",
    "听说你这些年替"六爷"在大渎以南，做了些事情？",
    "平静",
    [{"trigger_delay": 2.5, "duration": 3, "process_mode": "insert", "name": "佩刀摘下",
     "sound_cn": "从腰间取下佩刀的轻微声响",
     "sound_en": "hand removing a scabbarded sword from belt, soft leather and metal clink",
     "volume": "-18%", "pitch": "+0Hz"}]
))

# id=227: 旁白 - explaining 柳䢦's work
remaining.append(s(227, "旁白",
    "大骊朝廷毕竟是让出了大渎以南的半壁江山，但是许多大骊百姓因为各种各样的原因，留在南边生活。年复一年，就有新恩怨。有些事情，大骊朝廷不方便直接插手，山上的还好说，大骊刑部自有现成的规章制度，循着旧例做事即可。但是在那山下，不管是江湖的，还是市井的，就比较棘手了。在这期间，六爷就让柳䢦这位"帮闲"，以江湖人的身份解决江湖事，离开大骊国境，渠帅带着人或是银子，摆平了一些纠纷。柳䢦从头到尾，都没有正眼敢看那位大骊国师一眼，听闻问话，立即站起身，拱手轻声道：",
    "叙述"
))

# id=228: 柳䢦
remaining.append(s(228, "柳䢦",
    "启禀国师，都是六爷的意思，我只是听命照做。",
    "惶恐恭敬"
))

# id=229: 陈平安
remaining.append(s(229, "陈平安",
    "她是闹着玩，你柳䢦却是实打实混江湖做事的，打理着一个明里暗里有三千号属下的大帮派，并不容易，说吧，这么多次往南走，总计花销多少，送出去多少的"茶水费"？",
    "平静但锐利"
))

# id=230: 旁白
remaining.append(s(230, "旁白",
    "柳䢦满脸错愕，震惊不已，国师大人竟然连这种小事都是熟稔的？茶水费是一个好听的江湖说法，简而言之，就是我柳䢦给谁面子，花钱消灾。但是如果谁不给我柳䢦面子，帮派就会给出一道不死不休的追杀令。其中有两笔未能送出的茶水费，对方代价就是好多条人命。柳䢦迅速回过神，说道：",
    "叙述"
))

# id=231: 柳䢦
remaining.append(s(231, "柳䢦",
    "回禀国师，都是小钱，不值一提。",
    "轻声"
))

# id=232: 陈平安
remaining.append(s(232, "陈平安",
    "报数。",
    "简短有力"
))

# id=233: 柳䢦
remaining.append(s(233, "柳䢦",
    "总计是两万七千五百两银子，国师大人，帮派里边有账可查，小的，既没有多开销一两银子，也绝不会少花掉一两银子。",
    "弯腰低头恭敬"
))

# id=234: 旁白 + 容鱼 enters
remaining.append(s(234, "旁白",
    "就在此时，容鱼进了屋子，说道：",
    "叙述"
))

# id=235: 容鱼 - audit results
remaining.append(s(235, "容鱼",
    "国师，刚刚对过账了，刑部档案，兵马司秘录，还有柳䢦他们帮派内部的账簿，都已经点检完毕，六爷黄连给了柳䢦五万两银子，除了柳䢦亲自出面的茶水费，没有问题，其余几次帮派人物出面办事，先后五次，总共昧掉了三千二百两银子，相信误差不会太大。一开始都是几百两的赚钱，最后一次胆子就大了，凑了个整数，一千两。",
    "冷静报账"
))

# id=236: 旁白
remaining.append(s(236, "旁白",
    "柳䢦瞬间冷汗直流。",
    "紧张叙述"
))

# id=237: 容鱼
remaining.append(s(237, "容鱼",
    "柳帮主好心是好心，只是做起事情就不清爽了。",
    "笑"
))

# id=238: 柳䢦
remaining.append(s(238, "柳䢦",
    "小的今晚回去之后，一定彻查到底。",
    "颤声"
))

# id=239: 容鱼
remaining.append(s(239, "容鱼",
    "彻什么查？不是已经帮忙查清楚了嘛。",
    "冷淡"
))

# id=240: 柳䢦
remaining.append(s(240, "柳䢦",
    "小的该死。",
    "自言自语"
))

# id=241: 陈平安
remaining.append(s(241, "陈平安",
    "自称名字"柳䢦"即可，你要是脸皮厚点，自称渠帅都无妨。",
    "平静"
))

# id=242: 柳䢦
remaining.append(s(242, "柳䢦",
    "小的不敢！",
    "惶恐"
))

# id=243: 容鱼
remaining.append(s(243, "容鱼",
    "不敢自称柳䢦或是渠帅，倒是敢驳回国师的建议，你到底是胆子大还是胆子小？",
    "讽刺"
))

# id=244: 旁白
remaining.append(s(244, "旁白",
    "柳䢦身体抖如筛子。容鱼说道：",
    "紧张叙述"
))

# id=245: 容鱼
remaining.append(s(245, "容鱼",
    "站直了说话！",
    "厉声"
))

# id=246: 旁白
remaining.append(s(246, "旁白",
    "柳䢦吓了一大跳，立即下意识仰起头挺直腰杆。陈平安问道：",
    "叙述"
))

# id=247: 陈平安
remaining.append(s(247, "陈平安",
    "柳䢦，你们在南边，有没有建造分舵的想法？",
    "随意"
))

# id=248: 柳䢦
remaining.append(s(248, "柳䢦",
    "之前有过这种想法，但是六爷怕我胡闹，没点头，就做罢了。",
    "轻声满脸汗水"
))

# id=249: 陈平安
remaining.append(s(249, "陈平安",
    "京城不都说你是某位皇子的知己，还怕这些个？",
    "调侃"
))

# id=250: 柳䢦
remaining.append(s(250, "柳䢦",
    "国师大人，那些都是敌对势力坑害柳䢦的下作手段，绝无此事，柳䢦可以对天发誓，若有半点假话……",
    "哭丧着脸"
))

# id=251: 陈平安
remaining.append(s(251, "陈平安",
    "发毒誓就算了，我怕你真挨雷劈。",
    "摆手"
))

# id=252: 旁白
remaining.append(s(252, "旁白",
    "柳䢦一头雾水。陈平安说道：",
    "叙述"
))

# id=253: 陈平安 - long advice (merge 575-579)
remaining.append(s(253, "陈平安",
    "柳䢦，今天在这里，你我是毕竟第一次见面。不过我希望以后到了大骊边境，或者是去了大渎以南的地方，你能够见谁了，都是站直了说话。朝廷这边，很快就会替你安排一到两位贴身扈从，放心，既不是掺沙子，也不是不放心你，你一手打造出来的帮派，昨天今天是你的，明天后天也还是你的。就只是怕你出了院子，腰杆太直了，误以为整座大骊朝廷都是你们的靠山，将来出了大骊国境，做事情没了分寸，跟谁都喜欢说话太冲。这一两位扈从，出手次数都是有限的，但是不会跟你直说，你全凭猜。总而言之，柳䢦，你自己悠着点。既不要不用、白白浪费掉，也不要随随便便就挥霍一空。",
    "语重心长"
))

# id=254: 柳䢦
remaining.append(s(254, "柳䢦",
    "国师大人，柳䢦记住也明白了！",
    "沉声拱手"
))

# id=255: 陈平安
remaining.append(s(255, "陈平安",
    "柳䢦，知道你为什么今天能够坐在这里吗？",
    "平静"
))

# id=256: 柳䢦
remaining.append(s(256, "柳䢦",
    "因为六爷？",
    "答道"
))

# id=257: 陈平安
remaining.append(s(257, "陈平安",
    "因为有个老江湖的前辈，他说你这个人好像还行，好像。",
    "笑了笑"
))

# id=258: 旁白 - 柳䢦 exits and self-slaps
remaining.append(s(258, "旁白",
    "柳䢦战战兢兢进了院子，跟腾云驾雾似的离开院子。到了湖边，走远了，柳䢦突然狠狠摔了一耳光在脸上，怎么就不敢胆子再大一点，自称渠帅呢！不敢与谁炫耀此事，不也是可以自饮自酌自夸自乐一番？",
    "生动叙述",
    [{"trigger_delay": 12.0, "duration": 2, "process_mode": "insert", "name": "自扇耳光",
     "sound_cn": "狠狠自扇一耳光的清脆声响",
     "sound_en": "sharp open palm slap to own face, loud and clear impact sound",
     "volume": "-12%", "pitch": "+0Hz"}]
))

# id=259: 旁白 - 巡城兵马司 escorting
remaining.append(s(259, "旁白",
    "巡城兵马司一队骑卒，已经将老莺湖私家园林的东家魏浃，给"护送"到了意迟巷魏家门口。其实除了魏浃，还有今天在这边吃饭喝酒的所有客人，都是有此殊荣的。除了意迟巷，还有篪儿街在内的几条街巷，今晚都出现了不太一样的铮铮铁甲与马蹄声。",
    "沉稳叙述",
    [{"trigger_delay": 1.0, "duration": 4, "process_mode": "insert", "name": "骑兵巡逻",
     "sound_cn": "远处铁甲骑兵巡逻经过的马蹄声",
     "sound_en": "distant armored cavalry patrolling city streets, rhythmic horse hooves on stone pavement",
     "volume": "-26%", "pitch": "+0Hz"}]
))

# id=260: 旁白 + 容鱼
remaining.append(s(260, "旁白",
    "容鱼站在门口，看着屋内的年轻国师，她轻声问道：",
    "叙述"
))

# id=261: 容鱼
remaining.append(s(261, "容鱼",
    "国师，还要见什么人吗？",
    "轻声"
))

# id=262: 旁白
remaining.append(s(262, "旁白",
    "她很清楚，国师真正要斩的，何止是鬼，而是整座大骊王朝光天化日之下的人心鬼蜮。",
    "深沉叙述"
))

# id=263: 旁白 + 陈平安
remaining.append(s(263, "旁白",
    "陈平安走出屋子，看似随意问道：",
    "叙述"
))

# id=264: 陈平安
remaining.append(s(264, "陈平安",
    "你觉得"六爷"怎么样？",
    "随意"
))

# id=265: 旁白 + 容鱼
remaining.append(s(265, "旁白",
    "容鱼想了想，说道：",
    "叙述"
))

# id=266: 容鱼
remaining.append(s(266, "容鱼",
    "做事情毛糙了点，但是……有心。",
    "想了想"
))

# id=267: 陈平安
remaining.append(s(267, "陈平安",
    "评价不低了。",
    "点头"
))

# id=268: 旁白 - city wall scene
remaining.append(s(268, "旁白",
    "境界低了，缩地山河都成奢望，就让宋云间帮了个忙，陈平安去了一趟城头，再次看着大骊京城外边的那条官道。白昼与夜幕所见风景，是不一样的，此刻道路上边灯火蜿蜒一线如龙。多少人愿意相信自己只要进了京城，就一定可以把明天过得比今天更好些。也不知道曾经有过多少默默走出这座京城的人，曾经希望而来，失望而去。陈平安扯了扯青衫领口，喃喃自语道：",
    "深沉悠远叙述",
    [{"trigger_delay": 2.0, "duration": 5, "process_mode": "insert", "name": "城头夜风",
     "sound_cn": "城头高处夜风吹过旌旗的猎猎声",
     "sound_en": "strong night wind blowing through flags and banners on city wall, fabric flapping in the wind",
     "volume": "-24%", "pitch": "+0Hz"}]
))

# id=269: 陈平安 - final line
remaining.append(s(269, "陈平安",
    "大师兄，齐先生，请你们放心，大骊王朝，宝瓶洲，浩然天下，这人间，明天都会更好的。",
    "喃喃自语感慨万千"
))

# ============================================================
# 5. Add soundscape
# ============================================================

soundscape = ''',
  "soundscape": {
    "version": "1.0",
    "strategy": "scene_layers",
    "engine": "stable-audio-open",
    "description": "场景级连续背景音配置",
    "scene_layers": [
      {
        "name": "老莺湖夜色花园",
        "start_line": 1,
        "end_line": 13,
        "prompt": "very subtle low volume cinematic background ambience, late evening night atmosphere in an ancient Chinese private lakeside garden, faint gentle lapping of lake water against stone embankment, distant crickets and night insects chirping softly, subtle rustle of willow branches in the warm night breeze, faint scent of lotus flowers in the air, peaceful yet contemplative mood, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-22%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 4200
      },
      {
        "name": "甲字号院子议事厅",
        "start_line": 14,
        "end_line": 50,
        "prompt": "very subtle low volume cinematic background ambience, indoor room tone of a traditional Chinese official courtyard hall, aged timber pillars and polished wooden floorboards, faint distant murmur of voices outside the courtyard walls, subtle quiet atmosphere of a formal government reception room, no wind no rain, very still and serious indoor ambience, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-24%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 3800
      },
      {
        "name": "沿湖柳荫夜步",
        "start_line": 51,
        "end_line": 62,
        "prompt": "very subtle low volume cinematic background ambience, walking along a lakeside willow shaded path at night, soft night breeze moving through weeping willow branches and leaves, faint water lapping sound from the nearby lake, distant faint sounds of an ancient city at night, occasional subtle rustle of leaves overhead, calm reflective moonlit atmosphere, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-22%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 4200
      },
      {
        "name": "回院升堂办公",
        "start_line": 63,
        "end_line": 96,
        "prompt": "very subtle low volume cinematic background ambience, indoor atmosphere of a formal Chinese government courtyard office at night, subtle room tone with aged wood furniture and paper screens, very faint distant footsteps on stone courtyard paths, quiet official bureaucratic space at late hour, serious and focused atmosphere, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-24%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 3800
      },
      {
        "name": "水榭花园",
        "start_line": 97,
        "end_line": 155,
        "prompt": "very subtle low volume cinematic background ambience, night time waterside pavilion garden setting in ancient Chinese city, gentle ambient sounds near a decorated garden pond with lotus, subtle distant chirping of nocturnal insects, soft night air moving through bamboo groves, faint sounds of quiet rural compound near city waterways, peaceful private garden atmosphere with lantern glow, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-22%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 4200
      },
      {
        "name": "洪崇本议事厅",
        "start_line": 156,
        "end_line": 194,
        "prompt": "very subtle low volume cinematic background ambience, indoor formal study room atmosphere in an ancient Chinese scholar residence at night, faint scent of old books and sandalwood, quiet scholarly indoor ambience with aged wooden bookshelves and calligraphy scrolls, very still and contemplative room tone, subtle sense of intellectual gravity and quiet tension, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-24%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 3800
      },
      {
        "name": "三国结盟议事",
        "start_line": 195,
        "end_line": 220,
        "prompt": "very subtle low volume cinematic background ambience, formal diplomatic meeting room in an ancient Chinese grand courtyard at night, indoor atmosphere of a large hall with stone pillars and wooden beams, subtle sense of weighty political discussions, quiet dignified space with minimal ambient sounds, faint distant night air through sealed windows, formal and serious atmosphere of high stakes diplomacy, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-24%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 3800
      },
      {
        "name": "柳䢦审问厅堂",
        "start_line": 221,
        "end_line": 258,
        "prompt": "very subtle low volume cinematic background ambience, tense formal interrogation room in an ancient Chinese military government hall at night, spacious hall with rows of official chairs separated by carved wooden flower stands, oppressive quiet atmosphere with subtle psychological tension, cold stone floor and aged timber pillars, dim lantern lighting with heavy shadows, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-26%",
        "fade_in": 2,
        "fade_out": 2,
        "target_dbfs": -30,
        "high_pass_hz": 90,
        "low_pass_hz": 3800
      },
      {
        "name": "城头夜景",
        "start_line": 259,
        "end_line": 269,
        "prompt": "very subtle low volume cinematic background ambience, standing on top of a massive ancient Chinese city wall at night, looking out over a vast imperial capital, distant road with winding line of lantern lights resembling a dragon, high altitude wind softly blowing across stone battlements and flagpoles, vast expansive feeling of looking down at a sleeping city, faint faraway sounds of a metropolis settling into night, contemplative and slightly lonely atmosphere at great height, slow evolving layered soundscape, gentle variation over time, smooth continuous ambience bed, no sharp foreground sounds, no prominent events, no voices, no music, no melody, no repetitive loop feeling, no noise bursts",
        "duration": 47,
        "volume": "-22%",
        "fade_in": 3,
        "fade_out": 3,
        "target_dbfs": -30,
        "high_pass_hz": 80,
        "low_pass_hz": 4200
      }
    ]
  }
}'''

# ============================================================
# 6. Assemble and write
# ============================================================

# Build remaining segments text
remaining_text = ",\n".join(remaining)

# Combine: truncated raw + remaining segments + soundscape
full_output = raw + ",\n" + remaining_text + soundscape

with open(DST, 'w', encoding='utf-8') as f:
    f.write(full_output)

print(f"Written {len(full_output)} characters to {DST}")
print(f"Total segments: 270 (0-269)")
print("Remaining segments generated: 197-269 (73 segments)")
