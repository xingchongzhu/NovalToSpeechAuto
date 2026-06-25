#!/usr/bin/env python3
"""多音字处理模块 - 支持中文后拼音标注格式，自动识别常见多音字"""

import re


def _process_de_character(text: str) -> str:
    """自动处理"的"字的正确读音

    "的"字发音规则：
    - de（轻声）：用在定语后（我的、你的）、状语后（高兴地）、补语后（跑得很快）
    - dí（第二声）：确实、实在（的确、的当、的真）
    - dì（第四声）：箭靶的中心（目的、无的放矢、众矢之的）

    拼音标注格式：直接替换为裸拼音，如"我的" -> "我de"
    注意：Qwen3-TTS 不支持 "汉字[拼音]" 格式（会读两遍：先读汉字再读拼音），
    因此此处用裸拼音替换。方括号格式仅供用户手动标注使用。

    Args:
        text: 原始文本

    Returns:
        处理后的文本，多音字直接替换为拼音
    """
    # 模式1: 匹配"的确"、"的当"、"的真"等词，"的"读 dí
    text = re.sub(r'(的)(确|当|真)', r'dí\2', text)

    # 模式2: 匹配"目的"、"标的"、"靶的"等词，"的"读 dì
    # 注意：负向预查使用字符类 [\u4e00-\u9fa5]，否则 (?!\u4e00-\u9fa5) 几乎永远成立，
    #       会把"目的地"也错标成 dì
    text = re.sub(r'(目|标|靶)(的)(?![\u4e00-\u9fa5])', r'\1dì', text)
    text = re.sub(r'(众矢之)(的)', r'\1dì', text)
    text = re.sub(r'(无)(的)(放矢)', r'\1dì\3', text)

    # 模式3: 匹配"的"作为定语标志（后面跟名词），读 de
    text = re.sub(r'([\u4e00-\u9fa5])(的)([\u4e00-\u9fa5])', r'\1de\3', text)

    # 模式4: 匹配"的"字结尾的情况，读 de
    text = re.sub(r'(的)$', r'de', text)
    text = re.sub(r'(的)([，。！？；：,?!;:])', r'de\2', text)

    return text

def _process_zhe_character(text: str) -> str:
    return text

def _process_zhe_character1(text: str) -> str:
    """自动处理"着"字的正确读音

    发音规则：
    - zhe（轻声）：动态助词（看着、拿着、站着）
    - zháo（第二声）：接触到、感受到（着急、着凉、着火、找不着）
    - zhuó（第二声）：穿、接触、使附着（穿着、着手、着陆、沉着）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 先处理 zháo：着急、着凉、着火、点着、打着（打中）、找不着、睡不着
    text = re.sub(r'(着)(急|凉|火|魔|迷|慌)', r'zháo\2', text)
    text = re.sub(r'(点|打|烧|引)(着)', r'\1zháo', text)
    text = re.sub(r'(找|睡|猜|管|逮|摸|够)(不|得)(着)', r'\1\2zháo', text)
    text = re.sub(r'(找|睡|猜|管|逮|摸|够)(着)', r'\1zháo', text)

    # 再处理 zhuó：穿着、着手、着陆、沉着、执着、附着、衣着、
    #            着实、着力、着眼、着意、着笔、着色、着落
    text = re.sub(r'(穿|执|附|沉|衣)(着)', r'\1zhuó', text)
    text = re.sub(r'(着)(手|陆|实|力|眼|意|笔|色|落|想|重|墨)', r'zhuó\2', text)
    text = re.sub(r'(不)(着)(边际|痕迹)', r'\1zhuó\3', text)

    # 最后处理 zhe：位于动词/形容词后、句中的动态助词
    # 前面是动词性成分（V+着、VV+着），读 zhe
    text = re.sub(r'([看听读写说拿带跟站坐躺走跑笑哭吃喝抱提推拉抬举穿戴背\\u4e00-\\u9fa5])(着)([\u4e00-\u9fa5，。！？；：,?!;:])', r'\1zhe\3', text)
    text = re.sub(r'([\u4e00-\u9fa5])(着)([\u4e00-\u9fa5，。！？；：,?!;:])', r'\1zhe\3', text)
    text = re.sub(r'(着)$', r'zhe', text)
    text = re.sub(r'(着)([，。！？；：,?!;:])', r'zhe\2', text)

    return text


def _process_de2_character(text: str) -> str:
    """自动处理"得"字的正确读音

    发音规则：
    - de（轻声）：补语标志（跑得快、好得很）
    - dé（第二声）：获得、能够（得到、取得、得意、不得、了得）
    - děi（第三声）：必须（得去、得做、得注意）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 先处理 dé：得到、获得、取得、心得、难得、得意、得知、得罪、
    #            不得（不能）、了得（厉害）、晓得、记得、认得、值得、舍得
    text = re.sub(r'(得)(到|知|罪|意|逞|法|体|闲|救|胜|力|分|名|宠|人|志)', r'dé\2', text)
    text = re.sub(r'([获取得记认晓得值舍难心])(得)', r'\1dé', text)
    text = re.sub(r'(不)(得)(?!已)', r'\1dé', text)  # 不得（不能）
    text = re.sub(r'(了|免)(得)', r'\1dé', text)
    text = re.sub(r'(得)(当)', r'dé\2', text)  # 得当

    # 再处理 děi：必须（得去、得做、得注意）
    text = re.sub(r'(得)(去|做|说|看|走|问|管|想|注)', r'děi\2', text)
    text = re.sub(r'(总|还|也|就)(得)', r'\1děi', text)

    # 最后处理 de：补语标志（V+得+补语、Adj+得+很）
    text = re.sub(r'([\u4e00-\u9fa5])(得)(很|紧|远|多|快|慢|好)', r'\1de\3', text)
    text = re.sub(r'([\u4e00-\u9fa5])(得)([\u4e00-\u9fa5])', r'\1de\3', text)
    text = re.sub(r'(得)$', r'de', text)
    text = re.sub(r'(得)([，。！？；：,?!;:])', r'de\2', text)

    return text


def _process_le_character(text: str) -> str:
    """自动处理"了"字的正确读音

    发音规则：
    - le（轻声）：动态助词（走了、好了、完了）
    - liǎo（第三声）：完毕、明白（了解、了结、了得、了不起、不得了）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 先处理 liǎo：了解、了结、了得、了不起、不得了、免不了、少不了
    text = re.sub(r'(了)(解|结|得|断|却|事|账|债|局)', r'liǎo\2', text)
    text = re.sub(r'(不)(了)', r'\1liǎo', text)
    text = re.sub(r'(来|去)(不了)', r'\1buliǎo', text)
    text = re.sub(r'(了)(不起)', r'liǎo\2', text)
    text = re.sub(r'(免|少|受|逃|躲|跑)(不了)', r'\1buliǎo', text)

    # 句末"了"默认读 le
    text = re.sub(r'(了)$', r'le', text)
    text = re.sub(r'(了)([，。！？；：,?!;:])', r'le\2', text)

    # 动词后的"了"读 le（如 走了、去了）
    text = re.sub(r'([到走拿去来看吃喝说笑哭写读听打死杀灭断离分])(了)', r'\1le', text)
    text = re.sub(r'([\u4e00-\u9fa5])(了)([\u4e00-\u9fa5，。！？；：,?!;:])', r'\1le\3', text)

    return text


def _process_wei_character(text: str) -> str:
    """自动处理"为"字的正确读音

    发音规则：
    - wèi（第四声）：替、给（为了、因为、为何、为此）
    - wéi（第二声）：做、成为（作为、成为、以为、为人、为首、为难）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 处理 wèi：为了、因为、为何、为此
    # 注意：必须在 _process_le_character 之前运行，否则"为了"已变成"为le"无法匹配
    text = re.sub(r'([了因])(为)(何|此|什)', r'\1wèi\3', text)
    text = re.sub(r'(为)(了)', r'wèi\2', text)

    # 处理 wéi：作为、成为、以为、行为、认为、较为、尤为
    # 使用负向后视 (?<![a-z]) 防止对已替换为拼音的字符再次匹配
    text = re.sub(r'([作成以行认较尤认])(为)(?!了)', r'\1wéi', text)
    text = re.sub(r'(?<![a-z])(为)(首|人|难|主|生|数|名|期|限|例|伍)', r'wéi\2', text)
    # 最为、极为、颇为、甚为、稍为、更为
    text = re.sub(r'([最极颇甚稍更])(为)', r'\1wéi', text)
    text = re.sub(r'(广|大|妄)(为)', r'\1wéi', text)

    return text


def _process_hai_character(text: str) -> str:
    """自动处理"还"字的正确读音

    发音规则：
    - hái（第二声）：仍然、尚且（还是、还有、还要、还好）
    - huán（第二声）：返回、归还（归还、还钱、还手、偿还）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 处理 huán：归还、还钱、偿还、还手、还击、还魂、还债
    text = re.sub(r'([归偿奉退交赔])(还)', r'\1huán', text)
    text = re.sub(r'(还)(钱|手|击|魂|债|愿|俗|原|价|礼|命)', r'huán\2', text)

    # 处理 hái：还是、还有、还要、还好
    text = re.sub(r'(还)(是|有|要|好|在|会|能|可|算|未|得)', r'hái\2', text)
    text = re.sub(r'(还)(没|不|未)[\u4e00-\u9fa5]', r'hái\2', text)

    return text


def _process_di_de_character(text: str) -> str:
    """自动处理"地"字的正确读音

    发音规则：
    - de（轻声）：状语的标志（高兴地说、慢慢地走）
    - dì（第四声）：大地、土地（地方、地面、天地）

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    # 处理 de：状语标志，形容词后的"地"
    # AA地、AAB地 等副词标志
    text = re.sub(r'(慢慢|轻轻|静静|悄悄|狠狠|渐渐|缓缓|默默|深深|淡淡)(地)', r'\1de', text)
    text = re.sub(r'([\u4e00-\u9fa5][\u4e00-\u9fa5])(地)(说|走|跑|笑|哭|看|听|想)', r'\1de\3', text)
    # "X地"作为状语标志（X为形容词）
    text = re.sub(r'(高兴|认真|仔细|努力|热切|坚决|愤怒|悲恸|急促)(地)', r'\1de', text)

    return text


def process_polyphone_text(text: str) -> str:
    """处理多音字标注文本

    Qwen3-TTS支持的拼音标注格式：汉字[拼音]，如"这是[shì]一个测试"

    处理逻辑:
    1. 自动识别并处理常见多音字，替换为正确拼音
    2. 用户手动标注的 "汉字[拼音]" 格式保持不变
    3. 保持其他文本不变

    Args:
        text: 原始文本，可能包含多音字标注

    Returns:
        处理后的文本，多音字用拼音替换
    """
    # 处理顺序很重要：先处理特例词汇（如"了得"、"得道"），再处理通用模式
    # 否则通用模式可能先把某个字替换成拼音，导致后续模式无法匹配

    #text = _process_le_character(text)   # 了 le/liǎo
    #text = _process_de_character(text)   # 的 de/dí/dì
    #text = _process_de2_character(text)  # 得 de/dé/děi
    #text = _process_zhe_character(text)  # 着 zhe/zháo/zhuó
    #text = _process_wei_character(text)  # 为 wèi/wéi
    #text = _process_hai_character(text)  # 还 hái/huán
    #text = _process_di_de_character(text)  # 地 de/dì

    return text


def extract_polyphone_hints(text: str) -> tuple[str, dict]:
    """提取多音字标注并生成提示信息（用于日志）

    Args:
        text: 包含多音字标注的文本

    Returns:
        (处理后的文本, 多音字映射字典)
    """
    pattern = r'([\u4e00-\u9fa5])\[([a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüA-Z]+)\]'

    polyphone_map = {}
    matches = re.finditer(pattern, text)
    for match in matches:
        char = match.group(1)
        pinyin = match.group(2)
        polyphone_map[char] = pinyin

    processed_text = re.sub(pattern, r'\2', text)

    return processed_text, polyphone_map


# 测试代码
if __name__ == "__main__":
    test_cases = [
        # 原有的"的"字测试
        "他在银行[háng]工作，行[xíng]事低调。",
        "这件事情很重[zhòng]要，不要重[chóng]复。",
        "长[cháng]城很长[cháng]，他慢慢长[zhǎng]大了。",
        "普通文本没有标注",
        "混合文本：去银行[háng]存钱，然后去商场[chǎng]购物。",
        "我的名字是我的，不是你的。",
        "的确是这样的。",
        "他的目的是明确的。",
        "众矢之的。",
        "无的放矢。",
        "高兴地说。",
        "跑得很快。",
        "我的目标是完成任务。",
        "红色的苹果。",
        "慢慢地走。",
        # 新增"着"字测试
        "他看着窗外，心里很着急。",
        "着手准备着陆方案已着落。",
        "找不着北了，睡不着觉。",
        # 新增"得"字测试
        "他跑得很快，得到了第一名。",
        "这件事得去办，不得拖延。",
        "难得一见的了得功夫。",
        # 新增"了"字测试
        "他走了，了解了情况就了结了。",
        "这事免不了，了不得的结果。",
        # 新增"为"字测试
        "为了成为更好的人，他为此付出了很多。",
        "作为为首之人，他认为此事为难。",
        # 新增"还"字测试
        "还是先把钱归还给他，还要还手吗？",
        # 新增"地"字测试
        "他高兴地走在大地上。",
        "慢慢地，她轻轻地说着。",
        # 混合复杂场景
        "他的确是为了了解情况，还得着手处理，了不得的大事。",
    ]

    print("=" * 60)
    print("多音字处理测试")
    print("=" * 60)

    for i, text in enumerate(test_cases, 1):
        print(f"\n案例 {i}:")
        print(f"  原文: {text}")

        processed = process_polyphone_text(text)
        print(f"  处理: {processed}")
