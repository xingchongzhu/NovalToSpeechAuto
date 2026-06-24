import argparse
import json
import os
import re
import time
from collections import defaultdict
from html import unescape
from typing import Optional

import requests

DEFAULT_AUDIO_DIR = "/Users/zhuxingchong/Documents/trae_projects/NovelToSpeechAutoTool/clone-audio-same-text"
DEFAULT_TEXT = "这是一段用于语音克隆的标准文本，发音清晰、语调平稳，我会用自然流畅的语速朗读，涵盖叙述、对话与情绪表达，能完整呈现音色特质。"
ROLE_LIST_API = "https://www.pdd5.com/api/peiyin/roleList"
TEST_TTS_API = "https://www.pdd5.com/api/peiyin/testTts"
SINGLE_TTS_API = "https://www.pdd5.com/api/peiyin/singleTts"
SINGLE_TTS_RECORDS_API = "https://www.pdd5.com/api/peiyin/singleTtsRecords"
DEFAULT_AUDIO_BASE_URL = "https://pdd5.oss-cn-shanghai.aliyuncs.com/static/tts/audio/"
SUCCESS_CODES = {0, 1, 200, "0", "1", "200"}

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

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.pdd5.com/lbpeiyin.html",
        "Origin": "https://www.pdd5.com",
        "X-Requested-With": "XMLHttpRequest",
    }
)


def apply_cookie(cookie: str) -> None:
    if cookie.strip():
        session.headers["Cookie"] = cookie.strip()


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    return sanitized.replace("\n", " ").replace("\r", " ")


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
        return "童声"

    if category == "老人":
        if "女" in style_suffix:
            return "女老人"
        if "男" in style_suffix:
            return "男老人"
        return "老人"

    return category


def infer_scenario(tags: list[str]) -> str:
    for tag in tags:
        for keyword, scenario in SCENARIO_TAG_MAP.items():
            if keyword in tag:
                return scenario
    return "通用配音场景"


def sort_categories(categories: list[str]) -> list[str]:
    return sorted(categories, key=lambda item: (CATEGORY_ORDER.index(item) if item in CATEGORY_ORDER else len(CATEGORY_ORDER), item))


def sort_subcategories(category: str, subcategories: list[str]) -> list[str]:
    preferred = SUBCATEGORY_ORDER.get(category, [])
    return sorted(subcategories, key=lambda item: (preferred.index(item) if item in preferred else len(preferred), item))


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
            default_mood_key = ""
            mood_list = item.get("mood_list") or []
            if mood_list:
                first_mood = mood_list[0] or {}
                mood_key = first_mood.get("mood_key")
                if mood_key is None or mood_key == "":
                    mood_key = first_mood.get("style", "")
                default_mood_key = str(mood_key).strip()

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
                    "mood_list": mood_list,
                    "mood_key": default_mood_key,
                }
            )

        print(f"获取第 {page}/{total_pages} 页，累计 {len(characters)} 个角色")
        page += 1

    return characters


def normalize_audio_url(audio_url: str) -> str:
    if not audio_url:
        return ""
    if audio_url.startswith("//"):
        return f"https:{audio_url}"
    if audio_url.startswith("/"):
        return f"https://www.pdd5.com{audio_url}"
    if audio_url.startswith("http://") or audio_url.startswith("https://"):
        return audio_url
    return f"{DEFAULT_AUDIO_BASE_URL}{audio_url.lstrip('/')}"


def is_success_response(result: dict) -> bool:
    return result.get("code") in SUCCESS_CODES or bool(result.get("data"))


def request_json(method: str, url: str, **kwargs) -> Optional[dict]:
    try:
        response = session.request(method, url, timeout=40, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"请求失败: {url} - {exc}")
    except ValueError:
        print(f"返回非 JSON: {url}")
    return None


def extract_record_audio_url(record: dict) -> str:
    audio_info = record.get("audio_info") or {}
    for key in ("audio_url", "audio_down_url"):
        audio_url = normalize_audio_url(str(audio_info.get(key) or "").strip())
        if audio_url:
            return audio_url
    return ""


def find_matching_record(records: list[dict], character: dict, text: str) -> Optional[dict]:
    for record in records:
        voice_info = record.get("voice_info") or {}
        voice_id = str(voice_info.get("id") or record.get("voice_id") or "").strip()
        content = str(record.get("content") or "").strip()
        task_status = record.get("task_status")
        if voice_id != character["id"]:
            continue
        if content != text.strip():
            continue
        if str(task_status) not in {"1", "2"}:
            continue
        if extract_record_audio_url(record):
            return record
    return None


def fetch_single_tts_records(*, page: int, limit: int = 20) -> list[dict]:
    result = request_json("GET", SINGLE_TTS_RECORDS_API, params={"page": page, "limit": limit})
    if not result or not is_success_response(result):
        return []
    data = result.get("data") or {}
    return data.get("data") or data.get("list") or []


def poll_single_tts_record(character: dict, text: str, *, poll_interval: float, poll_attempts: int) -> Optional[dict]:
    for attempt in range(1, poll_attempts + 1):
        records = fetch_single_tts_records(page=1, limit=20)
        matched = find_matching_record(records, character, text)
        if matched:
            return matched
        time.sleep(poll_interval)
    return None


def submit_single_tts(character: dict, text: str, *, pitch_rate: int, volume: int, speech_rate: int, aisign: int) -> Optional[dict]:
    payload = {
        "text": text,
        "voice_id": character["id"],
        "volume": volume,
        "speech_rate": speech_rate,
        "pitch_rate": pitch_rate,
        "mood_key": character.get("mood_key", ""),
        "aisign": aisign,
    }
    return request_json("POST", SINGLE_TTS_API, data=payload)


def extract_audio_url_from_html(html_text: str) -> str:
    patterns = [
        r'<source\s+src=["\']([^"\']+\.mp3[^"\']*)["\']',
        r'<a\s+href=["\']([^"\']+\.mp3[^"\']*)["\'][^>]*download=',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            return normalize_audio_url(unescape(match.group(1).strip()))
    return ""


def is_probably_html(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "text/html" in content_type:
        return True
    prefix = response.content[:256].lstrip().lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html")


def download_audio_file(audio_url: str, filepath: str, role_name: str) -> bool:
    try:
        audio_response = session.get(audio_url, timeout=40)
        audio_response.raise_for_status()
        if not audio_response.content:
            print(f"音频内容为空: {role_name}")
            return False

        if is_probably_html(audio_response):
            html_text = audio_response.text
            nested_audio_url = extract_audio_url_from_html(html_text)
            if not nested_audio_url:
                print(f"下载返回的是页面而非音频: {role_name}")
                return False
            audio_response = session.get(nested_audio_url, timeout=40)
            audio_response.raise_for_status()
            if not audio_response.content or is_probably_html(audio_response):
                print(f"二次下载仍未拿到音频: {role_name}")
                return False

        with open(filepath, "wb") as file_obj:
            file_obj.write(audio_response.content)
        return True
    except requests.RequestException as exc:
        print(f"下载音频失败: {role_name} - {exc}")
        return False


def synthesize_audio(character: dict, text: str, output_dir: str, *, pitch_rate: int, volume: int, speech_rate: int, overwrite: bool, use_formal_api: bool, poll_interval: float, poll_attempts: int, aisign: int) -> bool:
    filepath = os.path.join(output_dir, character["filename"])
    if not overwrite and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        print(f"跳过已存在: {character['filename']}")
        return True

    if use_formal_api:
        submit_result = submit_single_tts(
            character,
            text,
            pitch_rate=pitch_rate,
            volume=volume,
            speech_rate=speech_rate,
            aisign=aisign,
        )
        if not submit_result:
            print(f"正式配音提交失败: {character['role_name']}")
            return False
        if not is_success_response(submit_result):
            print(f"正式配音失败: {character['role_name']} - {submit_result.get('msg') or submit_result}")
            return False

        record = poll_single_tts_record(character, text, poll_interval=poll_interval, poll_attempts=poll_attempts)
        if not record:
            print(f"未在记录中等到可下载音频: {character['role_name']}")
            return False

        audio_url = extract_record_audio_url(record)
        if not audio_url:
            print(f"记录中缺少音频地址: {character['role_name']}")
            return False

        if download_audio_file(audio_url, filepath, character["role_name"]):
            print(f"正式配音成功: {character['filename']}")
            return True
        return False

    payload = {
        "text": text,
        "voice_id": character["id"],
        "mood_key": character.get("mood_key", ""),
        "pitch_rate": pitch_rate,
        "volume": volume,
        "speech_rate": speech_rate,
    }
    result = request_json("POST", TEST_TTS_API, data=payload)
    if not result:
        print(f"试听合成请求失败: {character['role_name']}")
        return False
    if not is_success_response(result):
        print(f"试听合成失败: {character['role_name']} - {result.get('msg') or result}")
        return False

    audio_info = (result.get("data") or {}).get("audio_info") or {}
    audio_url = normalize_audio_url(str(audio_info.get("audio_url") or "").strip())
    if not audio_url:
        print(f"试听未返回音频地址: {character['role_name']} - {result.get('msg') or result}")
        return False

    if download_audio_file(audio_url, filepath, character["role_name"]):
        print(f"试听合成成功: {character['filename']}")
        return True
    return False


def build_doc(downloaded_characters: list[dict], text: str) -> str:
    grouped = defaultdict(lambda: defaultdict(list))
    for character in downloaded_characters:
        grouped[character["category"]][character["subcategory"]].append(character)

    lines = [
        "# 配朵朵统一文本角色音频列表",
        "",
        "## 本次统一配音文本",
        "",
        f"> {text}",
        "",
        "## 角色分类总览",
        "",
    ]

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


def write_prompt_texts(downloaded_characters: list[dict], text: str, output_dir: str) -> None:
    prompt_text_path = os.path.join(output_dir, "prompt_texts.json")
    prompt_text_map = {}
    for character in downloaded_characters:
        stem = os.path.splitext(character["filename"])[0]
        prompt_text_map[character["role_name"]] = text
        prompt_text_map[stem] = text
        prompt_text_map[character["filename"]] = text

    with open(prompt_text_path, "w", encoding="utf-8") as file_obj:
        json.dump(prompt_text_map, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")


def write_manifest(downloaded_characters: list[dict], text: str, output_dir: str) -> None:
    manifest_path = os.path.join(output_dir, "same_text_manifest.json")
    payload = {
        "text": text,
        "count": len(downloaded_characters),
        "roles": downloaded_characters,
    }
    with open(manifest_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为配朵朵全部角色批量生成同一段文本的音频")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="所有角色统一朗读的文本")
    parser.add_argument("--output-dir", default=DEFAULT_AUDIO_DIR, help="输出目录")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个角色，0 表示全部")
    parser.add_argument("--match", default="", help="仅处理角色名/标签/风格中包含该关键词的角色")
    parser.add_argument("--pitch-rate", type=int, default=0, help="音调，默认 0")
    parser.add_argument("--volume", type=int, default=0, help="音量，默认 0")
    parser.add_argument("--speech-rate", type=int, default=0, help="语速，默认 0")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的音频文件")
    parser.add_argument("--sleep", type=float, default=0.2, help="每次合成后的额外等待秒数，避免请求过快")
    parser.add_argument("--cookie", default="", help="登录后的 Cookie 字符串")
    parser.add_argument("--mode", choices=["preview", "formal", "records"], default="formal", help="preview 使用试听接口，formal 使用正式配音记录接口，records 只下载历史记录")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="正式配音模式轮询记录间隔秒数")
    parser.add_argument("--poll-attempts", type=int, default=20, help="正式配音模式最多轮询次数")
    parser.add_argument("--record-pages", type=int, default=10, help="records 模式最多扫描的历史记录页数")
    parser.add_argument("--aisign", type=int, choices=[0, 1], default=0, help="是否启用 AI 润色，0 关闭，1 开启")
    return parser.parse_args()


def filter_characters(characters: list[dict], keyword: str) -> list[dict]:
    if not keyword:
        return characters

    needle = keyword.strip().lower()
    filtered = []
    for character in characters:
        haystacks = [
            character["role_name"],
            character["name"],
            character["style"],
            character["style_suffix"],
            character["language"],
            " ".join(character["tags"]),
        ]
        if any(needle in str(item).lower() for item in haystacks if item):
            filtered.append(character)
    return filtered


def build_character_lookup(characters: list[dict]) -> dict[str, dict]:
    lookup = {}
    for character in characters:
        lookup[character["id"]] = character
    return lookup


def download_existing_records(characters: list[dict], text: str, output_dir: str, *, overwrite: bool, page_limit: int) -> list[dict]:
    lookup = build_character_lookup(characters)
    downloaded = []
    seen_voice_ids = set()
    for page in range(1, page_limit + 1):
        records = fetch_single_tts_records(page=page, limit=20)
        if not records:
            break
        for record in records:
            if str(record.get("content") or "").strip() != text.strip():
                continue
            voice_info = record.get("voice_info") or {}
            voice_id = str(voice_info.get("id") or record.get("voice_id") or "").strip()
            if not voice_id or voice_id in seen_voice_ids:
                continue
            character = lookup.get(voice_id)
            if not character:
                continue
            audio_url = extract_record_audio_url(record)
            if not audio_url:
                continue
            filepath = os.path.join(output_dir, character["filename"])
            if not overwrite and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                downloaded.append(character)
                seen_voice_ids.add(voice_id)
                continue
            if download_audio_file(audio_url, filepath, character["role_name"]):
                print(f"历史记录下载成功: {character['filename']}")
                downloaded.append(character)
                seen_voice_ids.add(voice_id)
    return downloaded


def main() -> None:
    args = parse_args()
    if args.cookie:
        apply_cookie(args.cookie)
    os.makedirs(args.output_dir, exist_ok=True)

    all_characters = fetch_all_characters()
    print(f"\n共获取到 {len(all_characters)} 个角色")

    target_characters = filter_characters(all_characters, args.match)
    if args.limit > 0:
        target_characters = target_characters[: args.limit]
    print(f"本次准备处理 {len(target_characters)} 个角色")

    downloaded_characters = []
    for index, character in enumerate(target_characters, start=1):
        print(f"[{index}/{len(target_characters)}] 正在处理 {character['role_name']}")
        if synthesize_audio(
            character,
            args.text,
            args.output_dir,
            pitch_rate=args.pitch_rate,
            volume=args.volume,
            speech_rate=args.speech_rate,
            overwrite=args.overwrite,
            use_formal_api=args.mode == "formal",
            poll_interval=args.poll_interval,
            poll_attempts=args.poll_attempts,
            aisign=args.aisign,
        ):
            downloaded_characters.append(character)
        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"\n处理完成！成功生成 {len(downloaded_characters)}/{len(target_characters)} 个音频文件")

    doc_path = os.path.join(args.output_dir, "统一文本角色列表说明.md")
    doc_content = build_doc(downloaded_characters, args.text)
    with open(doc_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(doc_content)
    print(f"角色说明文档已创建: {doc_path}")

    write_prompt_texts(downloaded_characters, args.text, args.output_dir)
    print(f"克隆音文本映射已创建: {os.path.join(args.output_dir, 'prompt_texts.json')}")

    write_manifest(downloaded_characters, args.text, args.output_dir)
    print(f"角色清单已创建: {os.path.join(args.output_dir, 'same_text_manifest.json')}")


if __name__ == "__main__":
    main()
