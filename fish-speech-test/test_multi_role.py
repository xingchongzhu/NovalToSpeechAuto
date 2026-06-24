#!/usr/bin/env python3
"""
Fish Speech 多角色 + 多语气批量测试

测试维度：
1. 同一对话台词，不同角色声音参考音频 → 听角色区分度
2. 同一角色，不同风格台词 → 听语气跟随程度
3. 多角色对话场景 → 模拟剧本片段
"""

import os
import sys
import json
import base64
import time
import requests

API = os.environ.get("FISH_API", "http://localhost:8080")
CLONE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "clone-audio"))
OUTPUT = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT, exist_ok=True)

# ========== 测试场景 ==========

# 场景1: 同一台词，多角色对比
SCENE_1_SAME_LINE = "你究竟是何人？为何擅闯我蜀山禁地？"

# 场景2: 对话场景 —— 蜀山剑侠传风格
SCENE_2_DIALOGUE = [
    {
        "role": "英琼",
        "voice": "英琼-新闻,官方",
        "line": "师父，山下有妖气，弟子愿下山降妖！",
    },
    {
        "role": "师父",
        "voice": "老禅师-老者教导之声",
        "line": "不可急躁。那妖物已有千年道行，你修为尚浅。",
    },
    {
        "role": "英琼",
        "voice": "英琼-新闻,官方",
        "line": "弟子不怕！蜀山剑法已练至第七重，定能斩妖除魔！",
    },
    {
        "role": "师兄",
        "voice": "云野-情感,磁性",
        "line": "师妹，师父说得对。不如我们三人同去，也好有个照应。",
    },
    {
        "role": "师父",
        "voice": "老禅师-老者教导之声",
        "line": "也罢。你二人速去速回，切莫恋战。这柄青冥剑带上。",
    },
]

# 场景3: 同一角色，不同情绪文本 → 测试语气跟随
SCENE_3_EMOTIONS = [
    ("愤怒", "大胆贼子！竟敢在我蜀山撒野，今日定叫你魂飞魄散！"),
    ("悲伤", "师叔他...他真的已经仙逝了么？我不信...我不信啊。"),
    ("喜悦", "太好了！师妹的伤势终于痊愈了，咱们今晚好好庆贺一番！"),
    ("威严", "尔等听令！剑阵起，四方封，不得放过一个妖孽！"),
    ("平静", "今日天气晴好，不如去后山采些药草，顺便看看那株千年灵芝。"),
]


def find_audio(voice_name: str) -> tuple[str | None, str | None]:
    """查找参考音频和文本"""
    # 精确匹配
    exact = os.path.join(CLONE_DIR, f"{voice_name}.mp3")
    if os.path.exists(exact):
        ref_text = _ref_text(voice_name)
        return exact, ref_text
    
    # 前缀匹配
    import glob
    for pattern in [f"{voice_name}-*.mp3", f"{voice_name}*.mp3"]:
        matches = glob.glob(os.path.join(CLONE_DIR, pattern))
        if matches:
            ref_text = _ref_text(voice_name)
            return matches[0], ref_text

    # 模糊匹配  
    all_files = [f for f in os.listdir(CLONE_DIR) if f.endswith('.mp3')]
    keywords = voice_name.lower().replace("-", " ").replace(",", " ").split()
    for keyword in keywords:
        for f in all_files:
            if keyword in f.lower():
                return os.path.join(CLONE_DIR, f), _ref_text(voice_name)
    
    return None, None


def _ref_text(voice_name: str) -> str:
    prompt_file = os.path.join(CLONE_DIR, "prompt_texts.json")
    if not os.path.exists(prompt_file):
        return ""

    with open(prompt_file, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    for key in [voice_name, f"{voice_name}.mp3"]:
        if key in prompts:
            return prompts[key]

    name_clean = voice_name.split("-")[0].split(",")[0]
    for key in prompts:
        if key.startswith(name_clean):
            return prompts[key]

    return ""


def synthesize(text: str, voice_name: str, label: str = "") -> str | None:
    """调用 Fish Speech API 合成语音"""
    ref_path, ref_text = find_audio(voice_name)
    if not ref_path:
        print(f"  ⚠️ 未找到声音 '{voice_name}' 的参考音频")
        return None

    with open(ref_path, "rb") as f:
        ref_bytes = f.read()

    payload = {
        "text": text,
        "references": [{
            "audio": base64.b64encode(ref_bytes).decode("utf-8"),
            "text": ref_text or "",
        }],
        "format": "wav",
        "max_new_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.8,
    }

    t0 = time.time()
    try:
        resp = requests.post(f"{API}/v1/tts", json=payload, timeout=180)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:100]}")
            return None

        ct = resp.headers.get("content-type", "")
        if "audio/wav" in ct:
            audio_data = resp.content
        else:
            audio_data = base64.b64decode(resp.json()["audio"])

        # 安全文件名
        safe_label = "".join(c if c.isalnum() or c in "._- " else "_" for c in label)
        safe_label = safe_label.replace(" ", "_")[:60]
        safe_text = "".join(c if c.isalnum() else "_" for c in text[:15])
        fname = f"{safe_label}_{safe_text}.wav"
        out_path = os.path.join(OUTPUT, fname)

        with open(out_path, "wb") as f:
            f.write(audio_data)

        print(f"  ✅ {elapsed:.1f}s | {len(audio_data)/1024:.0f}KB | {out_path}")
        return out_path

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  Fish Speech 多角色 + 多语气对比测试           ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"API: {API}")
    print(f"参考音频目录: {CLONE_DIR}")
    print(f"输出目录: {OUTPUT}\n")

    # ====== 场景1: 同一台词多角色 ======
    print("=" * 60)
    print("【场景1】同一台词 × 多角色对比")
    print(f"台词: 「{SCENE_1_SAME_LINE}」")
    print("=" * 60)

    voices_1 = [
        ("英琼-新闻,官方", "年轻女剑客"),
        ("老禅师-老者教导之声", "苍老长者"),
        ("云野-情感,磁性", "磁性男声"),
        ("云希-全能配音,全网最热", "全能配音"),
        ("书君-苍老声,影视,小说,百科", "苍老旁白"),
        ("可依-童声", "童声"),
        ("小昭-动漫,小说,影视", "动漫女声"),
        ("冷峻上司-磁性,稳重", "冷峻男声"),
    ]

    for voice, label in voices_1:
        ref_path, _ = find_audio(voice)
        if not ref_path:
            print(f"  ⚠️ 跳过 {label}({voice}): 无参考音频")
            continue
        print(f"\n  [{label}] → 声音: {voice}")
        synthesize(SCENE_1_SAME_LINE, voice, f"same_line_{label}")

    # ====== 场景2: 多角色对话 ======
    print(f"\n{'=' * 60}")
    print("【场景2】多角色对话场景")
    print("=" * 60)

    for i, seg in enumerate(SCENE_2_DIALOGUE):
        print(f"\n  [{i+1}] {seg['role']}({seg['voice']}): 「{seg['line']}」")
        synthesize(seg["line"], seg["voice"], f"dialogue_{i+1:02d}_{seg['role']}")

    # ====== 场景3: 同一角色 + 不同情绪台词 ======
    print(f"\n{'=' * 60}")
    print("【场景3】同一角色「云野-情感,磁性」 × 不同情绪文本")
    print("=" * 60)

    for emotion, line in SCENE_3_EMOTIONS:
        print(f"\n  [{emotion}] 「{line}」")
        synthesize(line, "云野-情感,磁性", f"emotion_{emotion}")

    # ====== 汇总 ======
    print(f"\n{'=' * 60}")
    print("所有测试完成!")
    print(f"输出文件 ({len(os.listdir(OUTPUT))} 个):")
    for f in sorted(os.listdir(OUTPUT)):
        size = os.path.getsize(os.path.join(OUTPUT, f))
        print(f"  {f} ({size/1024:.0f} KB)")
    print(f"\n目录: {OUTPUT}")
    print("建议用 Finder 或音频播放器逐一听对比效果。")


if __name__ == "__main__":
    main()
