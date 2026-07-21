#!/usr/bin/env python3
"""
下载爱给网 (aigei.com) AI配音 - 所有分类的角色配音及音频

基于参考脚本「配朵朵download_peiyin默认文本.py」的结构改写，
适配爱给网的反爬机制（加密 API、需登录），使用 Playwright 浏览器自动化。

使用方式：
  1. pip install playwright && playwright install chromium
  2. python3 download_aigei_voices.py
  3. 浏览器窗口弹出后，手动登录爱给网（QQ一键登录或手机号）
  4. 按终端提示回车，脚本自动：保存Cookie → 抓取角色 → 下载音频 → 生成文档

Cookie 保存在 aigei-audio-voices/cookies.json，下次运行可复用免重复登录。
"""

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============================================================
# 配置
# ============================================================
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(PROJECT_DIR, "aigei-audio-voices")
DOC_PATH = os.path.join(AUDIO_DIR, "爱给网AI配音角色列表说明.md")
PROMPT_TEXTS_PATH = os.path.join(AUDIO_DIR, "prompt_texts.json")
COOKIES_PATH = os.path.join(AUDIO_DIR, "cookies.json")

CLONE_PROMPT_TEXT = (
    "这是一段用于语音克隆的标准文本，发音清晰、语调平稳，"
    "我会用自然流畅的语速朗读，涵盖叙述、对话与情绪表达，能完整呈现音色特质。"
)

# TTS 分类列表：(中文名, URL路径)
# 取消注释即可下载更多分类
TTS_CATEGORIES = [
    ("小说", "novel"),
    # ("影视", "tv"),
    # ("宣传片", "promo"),
    # ("纪录片", "documentary"),
    # ("广告", "ad"),
    # ("情感", "emotion"),
    # ("动漫", "cartoon"),
    # ("游戏", "game"),
    # ("角色", "role"),
    # ("娱乐", "entertainment"),
    # ("评书", "pingshu"),
    # ("闲聊", "chat"),
    # ("直播", "live"),
    # ("助理", "assistant"),
    # ("美食", "food"),
    # ("书单", "booklist"),
    # ("朗诵", "recite"),
    # ("百科", "encyclopedia"),
    # ("体育", "sport"),
    # ("资讯", "information"),
    # ("童声", "children"),
    # ("方言", "dialect"),
    # ("外语", "foreign"),
]

BASE_URL = "https://www.aigei.com"
TTS_PAGE_TEMPLATE = "/sound/tts/{category}"

os.makedirs(AUDIO_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    return sanitized.replace("\n", " ").replace("\r", " ")


# ============================================================
# Cookie 管理
# ============================================================

def load_cookies() -> Optional[list]:
    if os.path.exists(COOKIES_PATH):
        with open(COOKIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def login_and_save_cookies() -> Optional[list]:
    """打开浏览器让用户手动登录，保存并返回 cookies"""
    print("\n" + "=" * 60)
    print("正在启动浏览器，请在浏览器窗口中手动登录爱给网...")
    print("支持：QQ一键登录 / 手机号登录")
    print("=" * 60 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto(f"{BASE_URL}/sound/tts/novel", wait_until="domcontentloaded", timeout=60000)

        input("\n>>> 请在浏览器中完成登录后，按回车键继续...\n")

        cookies = context.cookies()
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"Cookie 已保存到: {COOKIES_PATH}")

        # 验证登录状态
        page.goto(f"{BASE_URL}/sound/tts/novel", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        try:
            modal = page.locator(".modal:has-text('请登录后进行访问')").first
            if modal.is_visible(timeout=3000):
                print("⚠️  警告：登录弹窗仍然存在，Cookie 可能未生效")
            else:
                print("✅ 登录状态确认成功！")
        except PlaywrightTimeout:
            print("✅ 登录状态确认成功！")

        browser.close()

    return load_cookies()


def create_session(cookies: list) -> requests.Session:
    """使用 cookies 创建 requests.Session，用于后续下载音频"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": BASE_URL,
    })
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".aigei.com"))
    return session


def new_browser_context(playwright, cookies: list, headless: bool = True):
    """创建带 Cookie 的 Playwright browser context"""
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720},
    )
    if cookies:
        context.add_cookies(cookies)
    return browser, context


# ============================================================
# 页面数据提取
# ============================================================

def close_login_modal(page):
    """尝试关闭登录弹窗"""
    close_selectors = [
        ".modal .close",
        ".modal [data-btn-type='cancel']",
        ".modal .btn-default",
        ".bootstrap-dialog .close",
    ]
    for sel in close_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                return True
        except PlaywrightTimeout:
            continue
    return False


def extract_voices_via_js_api(page) -> list[dict]:
    """通过页面的 gei.search 全局 JS API 提取音色数据"""
    return page.evaluate("""() => {
        const results = [];
        const seen = new Set();
        // 策略1：提取 data-voice-id 元素
        document.querySelectorAll('[data-voice-id]').forEach(el => {
            const voiceId = el.getAttribute('data-voice-id');
            const infoEl = el.querySelector('.js-tts-voice-info') || el;
            const name = infoEl.getAttribute('data-voice-name') || el.textContent.trim().substring(0, 50);
            const audioUrl = infoEl.getAttribute('data-voice-audio-url') || '';
            const price = infoEl.getAttribute('data-voice-price') || '';
            const duration = infoEl.getAttribute('data-voice-durationDesc') || '';
            const key = voiceId + '|' + name;
            if (!seen.has(key) && name) {
                seen.add(key);
                results.push({
                    id: voiceId,
                    name: name,
                    audio_url: audioUrl,
                    price: price,
                    duration: duration,
                    tags: [],
                    language: ''
                });
            }
        });
        // 策略2：如果没有 data-voice-id，尝试从声音项提取
        if (results.length === 0) {
            document.querySelectorAll('[data-sound-id]').forEach(el => {
                const soundId = el.getAttribute('data-sound-id');
                const nameEl = el.querySelector('.title, .name, h4, h3, h5, [class*="name"]');
                const name = nameEl ? nameEl.textContent.trim() : el.textContent.trim().substring(0, 50);
                const key = soundId + '|' + name;
                if (!seen.has(key) && name) {
                    seen.add(key);
                    results.push({
                        id: soundId,
                        name: name,
                        audio_url: '',
                        tags: [],
                        language: ''
                    });
                }
            });
        }
        // 策略3：尝试从 dGallery 列表项提取
        if (results.length === 0) {
            document.querySelectorAll('.dGallery-item, [class*="item-detail"], [class*="sound-card"]').forEach(el => {
                const nameEl = el.querySelector('.title, .name, h4, h3');
                const name = nameEl ? nameEl.textContent.trim() : '';
                const audioEl = el.querySelector('audio');
                const audioUrl = audioEl ? audioEl.getAttribute('src') || '' : '';
                const id = el.getAttribute('data-id') || el.getAttribute('id') || '';
                const tagEls = el.querySelectorAll('.tag, .label, [class*="tag"], [class*="badge"]');
                const tags = [...tagEls].map(t => t.textContent.trim()).filter(Boolean);
                const key = id + '|' + name;
                if (!seen.has(key) && name) {
                    seen.add(key);
                    results.push({ id, name, audio_url: audioUrl, tags, language: '' });
                }
            });
        }
        return results;
    }""")


def extract_voices_detail_mode(page, category_name: str) -> list[dict]:
    """
    逐个打开搜索结果详情提取音色数据。
    爱给网需要点击声音项展开详情面板才能看到 voice 按钮。
    """
    results = []

    # 找到所有搜索结果项
    item_selectors = [
        ".dGallery-item",
        "[data-sound-id]",
        ".search-list-item",
        ".item-box",
    ]
    items = []
    for sel in item_selectors:
        items = page.query_selector_all(sel)
        if items:
            print(f"  找到 {len(items)} 个搜索结果项 (选择器: {sel})")
            break

    for idx, item in enumerate(items):
        try:
            # 提取声音基本信息
            sound_id = (
                item.get_attribute("data-sound-id")
                or item.get_attribute("data-id")
                or ""
            )
            # 点击展开详情
            detail_trigger = item.query_selector(".js-open-detail, .item-detail-trigger, a[class*='detail']")
            if not detail_trigger:
                detail_trigger = item.query_selector("a, button")
            if detail_trigger:
                detail_trigger.click()
            else:
                item.click()
            page.wait_for_timeout(2000)

            # 提取音色列表
            voice_buttons = page.query_selector_all(".js-tts-voice-btn, [data-voice-id]")
            for btn in voice_buttons:
                voice_info = btn.query_selector(".js-tts-voice-info")
                if voice_info:
                    v = {
                        "id": voice_info.get_attribute("data-voice-id") or "",
                        "name": voice_info.get_attribute("data-voice-name") or "",
                        "audio_url": voice_info.get_attribute("data-voice-audio-url") or "",
                        "price": voice_info.get_attribute("data-voice-price") or "",
                        "duration": voice_info.get_attribute("data-voice-durationDesc") or "",
                        "sound_id": sound_id,
                        "tags": [],
                        "language": "",
                        "source_category": category_name,
                    }
                    if v["name"]:
                        results.append(v)

            # 关闭详情
            close_btn = page.query_selector(
                ".item-detail-close, .js-close-detail, .detail-panel .close, [class*='detail'] [class*='close']"
            )
            if close_btn:
                close_btn.click()
                page.wait_for_timeout(500)

        except Exception as e:
            print(f"  处理第 {idx + 1} 项时出错: {e}")
            continue

    return results


def extract_from_category(page, category_name: str, category_path: str) -> list[dict]:
    """从一个 TTS 分类页面提取所有角色配音数据"""
    url = f"{BASE_URL}{TTS_PAGE_TEMPLATE.format(category=category_path)}"

    print(f"\n正在加载: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
    except PlaywrightTimeout:
        print("  ⚠️  页面加载超时，尝试继续处理...")
    page.wait_for_timeout(8000)

    # 关闭登录弹窗
    close_login_modal(page)

    # 策略1：直接通过 JS API 提取（最快）
    voices = extract_voices_via_js_api(page)

    # 策略2：如果需要，进入详情模式逐个提取
    if not voices:
        print("  直接提取为空，尝试详情模式提取...")
        voices = extract_voices_detail_mode(page, category_name)

    print(f"  从「{category_name}」提取到 {len(voices)} 个角色")
    return voices


# ============================================================
# 音频下载
# ============================================================

def download_audio_via_playwright(page, voice: dict) -> bool:
    """通过 Playwright 下载音频（可绕过 referer 检查）"""
    audio_url = voice.get("audio_url", "")
    if not audio_url:
        return False

    filename = f"{sanitize_filename(voice.get('name', 'unknown'))}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return True  # 跳过已存在

    try:
        response = page.request.get(audio_url, timeout=30000)
        if response.status == 200:
            with open(filepath, "wb") as f:
                f.write(response.body())
            print(f"  ✅ 下载: {filename}")
            return True
        else:
            print(f"  ❌ HTTP {response.status}: {filename}")
    except Exception as e:
        print(f"  ❌ 下载失败: {filename} - {e}")
    return False


def download_audio_via_requests(session: requests.Session, voice: dict) -> bool:
    """通过 requests 下载音频（备选方案）"""
    audio_url = voice.get("audio_url", "")
    if not audio_url:
        return False

    filename = f"{sanitize_filename(voice.get('name', 'unknown'))}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return True

    try:
        resp = session.get(audio_url, timeout=30)
        if resp.status_code == 200 and resp.content:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"  ✅ 下载: {filename}")
            return True
    except requests.RequestException as e:
        print(f"  ❌ 下载失败: {filename} - {e}")
    return False


def enrich_audio_urls(page, voices: list[dict]) -> None:
    """为没有 audio_url 的角色补全音频下载链接"""
    missing = [v for v in voices if not v.get("audio_url")]
    if not missing:
        return

    print(f"\n  有 {len(missing)} 个角色缺少音频链接，尝试补全...")

    # 回到搜索页面
    for i, voice in enumerate(missing):
        if i % 20 == 0:
            print(f"    进度: {i}/{len(missing)}")

        cat = voice.get("source_category", "novel")
        url = f"{BASE_URL}{TTS_PAGE_TEMPLATE.format(category=cat.lower())}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeout:
            continue
        page.wait_for_timeout(3000)
        close_login_modal(page)

        # 尝试通过 data-voice-id 查找
        voice_id = voice.get("id", "")
        if voice_id:
            try:
                voice_info = page.query_selector(f'[data-voice-id="{voice_id}"] .js-tts-voice-info')
                if voice_info:
                    audio_url = voice_info.get_attribute("data-voice-audio-url")
                    if audio_url:
                        voice["audio_url"] = audio_url
                        continue
            except Exception:
                pass

        # 通过名字匹配
        name = voice.get("name", "")
        if name:
            escaped_name = name.replace('"', '\\"')
            try:
                el = page.query_selector(f'[data-voice-name*="{escaped_name}"]')
                if el:
                    audio_url = el.get_attribute("data-voice-audio-url")
                    if audio_url:
                        voice["audio_url"] = audio_url
            except Exception:
                pass


# ============================================================
# 分类与文档
# ============================================================

CATEGORY_ORDER = ["其他", "女声", "男声", "童声", "老人", "方言", "外语"]


def classify_voice(voice: dict) -> tuple[str, str]:
    """根据名字和标签推断角色分类"""
    tags = voice.get("tags", [])
    tags_str = " ".join(tags)
    name = voice.get("name", "")

    is_female = any(kw in tags_str + name for kw in ["女", "female", "少", "姐", "妹", "娘", "妈", "姨", "婆"])
    is_male = any(kw in tags_str + name for kw in ["男", "male", "哥", "叔", "伯", "爷", "爸", "弟"])
    is_child = any(kw in tags_str + name for kw in ["童", "儿童", "小孩", "kid", "child", "宝贝"])
    is_elder = any(kw in tags_str + name for kw in ["老人", "老年", "爷爷", "奶奶", "elder"])
    is_dialect = any(kw in tags_str for kw in ["方言", "粤语", "四川话", "东北话", "河南话", "北京话"])
    is_foreign = any(kw in tags_str for kw in ["英语", "英文", "日语", "韩语", "外语", "en"])

    if is_dialect:
        return "方言", tags[0] if tags else "方言"
    if is_foreign:
        return "外语", tags[0] if tags else "外语"
    if is_child:
        return "童声", "女童声" if is_female else ("男童声" if is_male else "童声")
    if is_elder:
        return "老人", "女老人" if is_female else ("男老人" if is_male else "老人")
    if is_female:
        if "中年" in tags_str:
            return "女声", "女中年"
        if "少年" in tags_str or "少女" in tags_str:
            return "女声", "女少年"
        return "女声", "女青年"
    if is_male:
        if "中年" in tags_str:
            return "男声", "男中年"
        if "少年" in tags_str:
            return "男声", "男少年"
        if "老年" in tags_str:
            return "男声", "男老年"
        return "男声", "男青年"
    return "其他", "特色角色"


SCENARIO_TAG_MAP = {
    "影视": "影视解说、纪录片", "纪实": "影视解说、纪录片",
    "情感": "情感电台、故事旁白", "书单": "书单推荐、有声书",
    "故事": "有声读物、故事讲述", "广告": "广告配音、品牌宣传",
    "宣传": "广告配音、品牌宣传", "美食": "美食视频、生活内容",
    "解说": "解说视频、口播内容", "知识": "知识科普、讲解内容",
    "新闻": "新闻播报、资讯内容", "动漫": "动漫配音、角色对白",
    "小说": "有声小说、角色演绎", "游戏": "游戏配音、角色语音",
    "直播": "直播带货、互动口播", "客服": "客服播报、助手提示音",
    "朗诵": "朗诵配音、诗歌朗读", "童声": "儿童配音、少儿内容",
    "娱乐": "娱乐节目、综艺配音", "资讯": "新闻资讯、信息播报",
    "百科": "知识科普、百科讲解", "体育": "体育赛事、运动解说",
    "方言": "方言配音、地域特色", "英语": "英语教学、外语配音",
    "外语": "多语种内容、外语配音",
}


def infer_scenario(tags: list[str]) -> str:
    for tag in tags:
        for keyword, scenario in SCENARIO_TAG_MAP.items():
            if keyword in tag:
                return scenario
    return "通用配音场景"


def sort_cats(cats: list[str]) -> list[str]:
    return sorted(cats, key=lambda x: (CATEGORY_ORDER.index(x) if x in CATEGORY_ORDER else 99, x))


def build_doc(voices: list[dict]) -> str:
    grouped = defaultdict(lambda: defaultdict(list))
    for v in voices:
        grouped[v.get("category", "其他")][v.get("subcategory", "特色角色")].append(v)

    lines = [
        "# 爱给网 AI配音角色列表说明",
        "",
        "> 数据来源：https://www.aigei.com/sound/tts",
        "",
        "## 角色分类总览",
        "",
    ]
    for cat in sort_cats(list(grouped.keys())):
        subs = grouped[cat]
        total = sum(len(items) for items in subs.values())
        lines.append(f"- **{cat}**: {total} 个角色")
        for sub in sorted(subs.keys()):
            lines.append(f"  - {sub}: {len(subs[sub])} 个")
    lines.extend(["", f"**总计**: {len(voices)} 个角色", ""])

    for cat in sort_cats(list(grouped.keys())):
        lines.extend([f"## {cat}", ""])
        for sub in sorted(grouped[cat].keys()):
            records = sorted(grouped[cat][sub], key=lambda v: v.get("name", ""))
            lines.extend([f"### {sub}（共 {len(records)} 个）", ""])
            lines.append("| 角色名 | 音频文件 | 角色特色 | 适用场景 |")
            lines.append("| --- | --- | --- | --- |")
            for r in records:
                scenario = infer_scenario(r.get("tags", []))
                tags_str = ", ".join(r.get("tags", [])) or "通用"
                lines.append(
                    f"| {r.get('name', '未知')} | "
                    f"`{sanitize_filename(r.get('name', 'unknown'))}.mp3` | "
                    f"{tags_str} | {scenario} |"
                )
            lines.append("")
    return "\n".join(lines)


def write_prompt_texts(voices: list[dict]) -> None:
    prompt_text_map = {}
    for v in voices:
        name = v.get("name", "unknown")
        stem = sanitize_filename(name)
        prompt_text_map[name] = CLONE_PROMPT_TEXT
        prompt_text_map[stem] = CLONE_PROMPT_TEXT
        prompt_text_map[f"{stem}.mp3"] = CLONE_PROMPT_TEXT
    with open(PROMPT_TEXTS_PATH, "w", encoding="utf-8") as f:
        json.dump(prompt_text_map, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ============================================================
# 主流程
# ============================================================

def main() -> None:
    print("=" * 60)
    print("  爱给网 AI配音 - 角色配音批量下载工具")
    print("  https://www.aigei.com/sound/tts")
    print("=" * 60)

    # 1. 获取 cookies
    cookies = load_cookies()
    if not cookies:
        cookies = login_and_save_cookies()
        if not cookies:
            print("❌ 未获取到 Cookie，退出")
            sys.exit(1)

    # 2. 创建浏览器会话
    with sync_playwright() as p:
        browser, context = new_browser_context(p, cookies, headless=True)
        page = context.new_page()

        # 3. 提取各分类的角色数据
        all_voices = []
        for cat_name, cat_path in TTS_CATEGORIES:
            voices = extract_from_category(page, cat_name, cat_path)
            for v in voices:
                v["source_category"] = cat_name
                cat, subcat = classify_voice(v)
                v["category"] = cat
                v["subcategory"] = subcat
            all_voices.extend(voices)

        print(f"\n📊 共提取到 {len(all_voices)} 个角色")

        if not all_voices:
            print("\n❌ 未提取到任何角色数据。可能原因：")
            print("  1. Cookie 已过期 → 请删除 aigei-audio-voices/cookies.json 重新登录")
            print("  2. 网站结构变更 → 请检查页面选择器是否需要更新")
            browser.close()
            return

        # 4. 补全音频链接
        enrich_audio_urls(page, all_voices)

        # 5. 下载音频
        print(f"\n📥 开始下载音频文件...")
        has_audio = sum(1 for v in all_voices if v.get("audio_url"))
        print(f"  有音频链接的角色: {has_audio}/{len(all_voices)}")

        downloaded = []
        for v in all_voices:
            if download_audio_via_playwright(page, v):
                downloaded.append(v)

        print(f"\n✅ 下载完成！成功：{len(downloaded)}/{len(all_voices)}")

        browser.close()

    # 6. 创建 requests session 用于后续可能的下载
    session = create_session(cookies)

    # 7. 生成文档
    doc = build_doc(downloaded)
    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"📄 角色说明文档: {DOC_PATH}")

    # 8. 生成 prompt 文本映射
    write_prompt_texts(downloaded)
    print(f"📄 克隆音文本映射: {PROMPT_TEXTS_PATH}")

    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()
