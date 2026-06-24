import json
import os
import re
from collections import defaultdict

import requests

AUDIO_DIR = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio-02"
DOC_PATH = os.path.join(AUDIO_DIR, "克隆音频角色列表说明.md")
PROMPT_TEXTS_PATH = os.path.join(AUDIO_DIR, "prompt_texts.json")
CLONE_PROMPT_TEXT = "这是一段用于语音克隆的标准文本，发音清晰、语调平稳，我会用自然流畅的语速朗读，涵盖叙述、对话与情绪表达，能完整呈现音色特质。"
ROLE_LIST_API = "https://www.pdd5.com/api/peiyin/roleList"
DEFAULT_AUDIO_BASE_URL = "https://pdd5.oss-cn-shanghai.aliyuncs.com/static/tts/audio/"

os.makedirs(AUDIO_DIR, exist_ok=True)

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.pdd5.com/lbpeiyin.html",
    }
)


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    return sanitized.replace("\n", " ").replace("\r", " ")


CATEGORY_ORDER = ["其他", "女声", "男声", "童声", "老人"]
SUBCATEGORY_ORDER = {
    "其他": ["特色角色"],
    "女声": ["女中年", "女少年", "女青年", "女儿童", "女童声", "女声"],
    "男声": ["男中年", "男少年", "男老年", "男青年", "男儿童", "男童声", "男声"],
    "童声": ["女童声", "男童声", "童声"],
    "老人": ["男老人", "女老人", "老人"],
}
TIMBRE_TO_CATEGORY = {
    "woman": "女声",
    "man": "男声",
    "child": "童声",
    "old": "老人",
}


def build_style(character: dict) -> str:
    tags = [str(tag).strip() for tag in character.get("tags") or [] if str(tag).strip()]
    base_style = {
        "woman": "女声",
        "man": "男声",
        "child": "童声",
        "old": "老人",
    }.get(character.get("timbre"), "特色角色")
    if tags:
        return f"{base_style}-{','.join(tags)}"
    return base_style


def infer_subcategory(category: str, style: str) -> str:
    if category == "其他":
        return "特色角色"

    style_suffix = style.split("-", 1)[1] if "-" in style else style

    if category == "女声":
        if "中年" in style_suffix:
            return "女中年"
        if "少年" in style_suffix:
            return "女少年"
        if "儿童" in style_suffix:
            return "女儿童"
        if "童声" in style_suffix or "小孩" in style_suffix:
            return "女童声"
        return "女青年" if style_suffix else "女声"

    if category == "男声":
        if "中年" in style_suffix:
            return "男中年"
        if "少年" in style_suffix:
            return "男少年"
        if "老年" in style_suffix:
            return "男老年"
        if "儿童" in style_suffix:
            return "男儿童"
        if "童声" in style_suffix or "小孩" in style_suffix:
            return "男童声"
        return "男青年" if style_suffix else "男声"

    if category == "童声":
        if "女" in style_suffix:
            return "女童声"
        if "男" in style_suffix:
            return "男童声"
        if "儿童" in style_suffix or "小孩" in style_suffix or "童声" in style_suffix:
            return "童声"
        return "童声"

    if category == "老人":
        if "女" in style_suffix:
            return "女老人"
        if "男" in style_suffix:
            return "男老人"
        return "老人"

    return category


SCENARIO_TAG_MAP = {
    "影视": "影视解说、纪录片",
    "纪实": "影视解说、纪录片",
    "情感": "情感电台、故事旁白",
    "书单": "书单推荐、有声书",
    "故事": "有声读物、故事讲述",
    "广告": "广告配音、品牌宣传",
    "宣传": "广告配音、品牌宣传",
    "美食": "美食视频、生活内容",
    "解说": "解说视频、口播内容",
    "知识": "知识科普、讲解内容",
    "新闻": "新闻播报、资讯内容",
    "动漫": "动漫配音、角色对白",
    "小说": "有声小说、角色演绎",
    "英语": "英语教学、外语配音",
    "外语": "多语种内容、外语配音",
    "粤语": "粤语配音、本地方言内容",
    "四川话": "四川话配音、方言内容",
    "台湾话": "方言内容、地域口播",
    "直播": "直播带货、互动口播",
    "客服": "客服播报、助手提示音",
}


def infer_scenario(tags: list[str]) -> str:
    for tag in tags:
        for keyword, scenario in SCENARIO_TAG_MAP.items():
            if keyword in tag:
                return scenario
    return "通用配音场景"


def fetch_all_characters() -> list[dict]:
    characters = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = {
            "page": page,
            "pagesize": 16,
            "search": "",
            "type": "",
            "area": "",
            "cate": "",
            "timbre": "",
            "language": "",
        }
        response = session.get(ROLE_LIST_API, params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("data", {})
        items = data.get("data", [])
        total_pages = int(data.get("last_page", total_pages))

        for item in items:
            category = TIMBRE_TO_CATEGORY.get(item.get("timbre"), "其他")
            style = build_style(item)
            style_suffix = style.split("-", 1)[1] if "-" in style else style
            role_name = f"{item.get('nickname', '').strip()}-{style_suffix}" if style_suffix else item.get("nickname", "").strip()
            filename = f"{sanitize_filename(role_name)}.mp3"
            characters.append(
                {
                    "id": str(item.get("id", "")).strip(),
                    "name": (item.get("nickname") or "").strip(),
                    "category": category,
                    "subcategory": infer_subcategory(category, style),
                    "style": style,
                    "style_suffix": style_suffix,
                    "role_name": role_name,
                    "filename": filename,
                    "tags": [str(tag).strip() for tag in item.get("tags") or [] if str(tag).strip()],
                    "language": item.get("language") or "",
                    "mood_list": item.get("mood_list") or [],
                }
            )

        print(f"获取第 {page}/{total_pages} 页，累计 {len(characters)} 个角色")
        page += 1

    return characters


def download_audio(character: dict) -> bool:
    audio_candidates = []
    for mood in character.get("mood_list", []):
        mood_audio = (mood or {}).get("mood_audio")
        if mood_audio:
            audio_candidates.append(mood_audio)

    audio_candidates.extend(
        [
            f"{DEFAULT_AUDIO_BASE_URL}{character['id']}_default.mp3",
            f"{DEFAULT_AUDIO_BASE_URL}{character['id']}_0.mp3",
        ]
    )

    seen_urls = set()
    filepath = os.path.join(AUDIO_DIR, character["filename"])
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"跳过已存在: {character['filename']}")
        return True

    for audio_url in audio_candidates:
        if not audio_url or audio_url in seen_urls:
            continue
        seen_urls.add(audio_url)
        try:
            response = session.get(audio_url, timeout=30)
            if response.status_code == 200 and response.content:
                with open(filepath, "wb") as file_obj:
                    file_obj.write(response.content)
                print(f"下载成功: {character['filename']}")
                return True
        except requests.RequestException:
            continue

    print(f"下载失败: {character['role_name']}")
    return False


def sort_categories(categories: list[str]) -> list[str]:
    return sorted(categories, key=lambda item: (CATEGORY_ORDER.index(item) if item in CATEGORY_ORDER else len(CATEGORY_ORDER), item))


def sort_subcategories(category: str, subcategories: list[str]) -> list[str]:
    preferred = SUBCATEGORY_ORDER.get(category, [])
    return sorted(subcategories, key=lambda item: (preferred.index(item) if item in preferred else len(preferred), item))


def build_doc(downloaded_characters: list[dict]) -> str:
    grouped = defaultdict(lambda: defaultdict(list))
    for character in downloaded_characters:
        grouped[character["category"]][character["subcategory"]].append(character)

    lines = ["# 克隆音频角色列表说明", "", "## 角色分类总览", ""]

    for category in sort_categories(list(grouped.keys())):
        subgroups = grouped[category]
        category_total = sum(len(items) for items in subgroups.values())
        lines.append(f"- **{category}**: {category_total} 个角色")
        for subcategory in sort_subcategories(category, list(subgroups.keys())):
            lines.append(f"  - {subcategory}: {len(subgroups[subcategory])} 个")
    lines.extend(["", f"**总计**: {len(downloaded_characters)} 个角色", ""])

    for category in sort_categories(list(grouped.keys())):
        lines.extend([f"## {category}", ""])
        for subcategory in sort_subcategories(category, list(grouped[category].keys())):
            records = sorted(grouped[category][subcategory], key=lambda item: item["role_name"])
            lines.extend([f"### {subcategory}（共 {len(records)} 个）", ""])
            lines.append("| 角色名 | 音频文件 | 角色特色 | 试用场景 |")
            lines.append("| --- | --- | --- | --- |")
            for record in records:
                scenario = infer_scenario(record["tags"])
                lines.append(
                    f"| {record['role_name']} | `{record['filename']}` | {record['style_suffix'] or record['style']} | {scenario} |"
                )
            lines.append("")

    return "\n".join(lines)


def write_prompt_texts(downloaded_characters: list[dict]) -> None:
    prompt_text_map = {}
    for character in downloaded_characters:
        stem = os.path.splitext(character["filename"])[0]
        prompt_text_map[character["role_name"]] = CLONE_PROMPT_TEXT
        prompt_text_map[stem] = CLONE_PROMPT_TEXT
        prompt_text_map[character["filename"]] = CLONE_PROMPT_TEXT

    with open(PROMPT_TEXTS_PATH, "w", encoding="utf-8") as file_obj:
        json.dump(prompt_text_map, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")


def main() -> None:
    all_characters = fetch_all_characters()
    print(f"\n共获取到 {len(all_characters)} 个角色")

    downloaded_characters = []
    for character in all_characters:
        if download_audio(character):
            downloaded_characters.append(character)

    print(f"\n下载完成！成功下载 {len(downloaded_characters)}/{len(all_characters)} 个音频文件")

    doc_content = build_doc(downloaded_characters)
    with open(DOC_PATH, "w", encoding="utf-8") as file_obj:
        file_obj.write(doc_content)
    print(f"角色说明文档已创建: {DOC_PATH}")

    write_prompt_texts(downloaded_characters)
    print(f"克隆音文本映射已创建: {PROMPT_TEXTS_PATH}")


if __name__ == "__main__":
    main()
