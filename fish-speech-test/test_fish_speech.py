#!/usr/bin/env python3
"""
Fish Speech 本地测试脚本

在 fish-speech-test/ 目录内独立运行，不影响主项目代码。

用途：
1. 使用 clone-audio/ 目录中的参考音频做声音克隆测试
2. 中文文本合成效果对比
3. 通过 REST API 调用 Fish Speech 推理服务

前置条件：
- Fish Speech 服务已启动（Docker 或本地 pip install）
- 默认 API 地址 http://localhost:8080
"""

import os
import sys
import json
import base64
import time
import argparse
import requests

# 项目根目录（fish-speech-test 的上级）
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLONE_AUDIO_DIR = os.path.join(ROOT_DIR, "clone-audio")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_reference_audio(voice_name: str) -> tuple[str | None, str | None]:
    """
    根据角色名查找参考音频和对应文本。
    
    查找规则：
    1. 精确匹配: clone-audio/{voice_name}.mp3
    2. 前缀匹配: clone-audio/{voice_name}-*.mp3
    """
    import glob

    # 精确匹配
    exact_path = os.path.join(CLONE_AUDIO_DIR, f"{voice_name}.mp3")
    if os.path.exists(exact_path):
        ref_text = _get_ref_text(voice_name)
        return exact_path, ref_text

    # .wav 格式
    exact_wav = os.path.join(CLONE_AUDIO_DIR, f"{voice_name}.wav")
    if os.path.exists(exact_wav):
        ref_text = _get_ref_text(voice_name)
        return exact_wav, ref_text

    # 前缀匹配: "voice_name-*"
    pattern = os.path.join(CLONE_AUDIO_DIR, f"{voice_name}-*.mp3")
    matches = glob.glob(pattern)
    if matches:
        ref_text = _get_ref_text(voice_name)
        return matches[0], ref_text

    return None, None


def _get_ref_text(voice_name: str) -> str | None:
    """从 prompt_texts.json 获取参考文本"""
    prompt_file = os.path.join(CLONE_AUDIO_DIR, "prompt_texts.json")
    if not os.path.exists(prompt_file):
        return None
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompts = json.load(f)
    
    # 尝试多种键格式匹配
    for key in [voice_name, f"{voice_name}.mp3", f"{voice_name}.wav"]:
        if key in prompts:
            return prompts[key]
    
    # 前缀匹配
    for key in prompts:
        if key.startswith(voice_name):
            return prompts[key]
    
    return None


def list_available_voices():
    """列出 clone-audio 中所有可用的声音"""
    voices = []
    for f in sorted(os.listdir(CLONE_AUDIO_DIR)):
        if f.endswith(('.mp3', '.wav')):
            name = os.path.splitext(f)[0]
            voices.append(name)
    return voices


def encode_audio_base64(audio_path: str) -> str:
    """将音频文件编码为 Base64 字符串"""
    with open(audio_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_tts_api(
    api_url: str,
    text: str,
    ref_audio_path: str,
    ref_text: str = "",
    language: str = "zh",
) -> str | None:
    """
    调用 Fish Speech TTS API 生成语音。
    
    返回: 生成的音频文件路径
    """
    print(f"  API 地址: {api_url}")
    print(f"  合成文本: {text[:60]}{'...' if len(text) > 60 else ''}")
    print(f"  参考音频: {os.path.basename(ref_audio_path)}")
    if ref_text:
        print(f"  参考文本: {ref_text[:40]}{'...' if len(ref_text) > 40 else ''}")
    
    ref_audio_b64 = encode_audio_base64(ref_audio_path)
    
    payload = {
        "text": text,
        "reference_audio": ref_audio_b64,
        "reference_text": ref_text,
    }
    
    start = time.time()
    try:
        resp = requests.post(
            f"{api_url}/v1/tts",
            json=payload,
            timeout=120,
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            print(f"  ❌ API 返回错误 {resp.status_code}: {resp.text[:200]}")
            return None
        
        result = resp.json()
        
        # 解码返回的音频
        if "audio" in result:
            audio_bytes = base64.b64decode(result["audio"])
        elif "data" in result:
            audio_bytes = base64.b64decode(result["data"])
        else:
            print(f"  ❌ 返回数据中未找到音频字段: {list(result.keys())}")
            return None
        
        # 保存到文件
        import uuid
        output_file = os.path.join(
            OUTPUT_DIR,
            f"fish_{uuid.uuid4().hex[:8]}.wav"
        )
        with open(output_file, "wb") as f:
            f.write(audio_bytes)
        
        print(f"  ✅ 生成成功! 耗时 {elapsed:.1f}s, 大小 {len(audio_bytes)/1024:.1f}KB")
        print(f"  输出: {output_file}")
        return output_file
        
    except requests.exceptions.ConnectionError:
        print(f"  ❌ 无法连接到 {api_url}，请确保 Fish Speech 服务已启动")
        return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def test_single_voice(
    api_url: str,
    voice_name: str,
    text: str,
):
    """测试单个声音克隆"""
    print(f"\n{'='*60}")
    print(f"测试声音: {voice_name}")
    print(f"{'='*60}")
    
    ref_audio, ref_text = find_reference_audio(voice_name)
    if not ref_audio:
        print(f"  ❌ 未找到参考音频: {voice_name}")
        return None
    
    print(f"  参考音频路径: {ref_audio}")
    
    return call_tts_api(api_url, text, ref_audio, ref_text or "")


def test_batch_voices(
    api_url: str,
    voices: list[str],
    texts: list[str],
):
    """批量测试多个声音"""
    results = []
    for i, voice in enumerate(voices):
        text = texts[i % len(texts)] if texts else "这是一段测试文本，用于验证声音克隆效果。"
        result = test_single_voice(api_url, voice, text)
        results.append({"voice": voice, "text": text, "output": result})
    
    # 打印汇总
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    success = [r for r in results if r["output"]]
    print(f"成功: {len(success)}/{len(results)}")
    for r in results:
        status = "✅" if r["output"] else "❌"
        print(f"  {status} {r['voice']}")
    
    return results


def test_qwentts_comparison(
    api_url: str,
    voice_name: str,
    text: str,
):
    """
    与 Qwen3-TTS 效果对比测试。
    
    生成相同文本、相同参考音频的 Fish Speech 版本，
    方便人工 AB 对比音质。
    """
    print(f"\n{'='*60}")
    print(f"对比测试: Fish Speech vs Qwen3-TTS")
    print(f"声音: {voice_name}")
    print(f"文本: {text}")
    print(f"{'='*60}")
    
    ref_audio, ref_text = find_reference_audio(voice_name)
    if not ref_audio:
        print(f"  ❌ 未找到参考音频: {voice_name}")
        return None
    
    return call_tts_api(api_url, text, ref_audio, ref_text or "")


def print_usage():
    """打印使用说明"""
    print("""
╔══════════════════════════════════════════════════════╗
║          Fish Speech 本地测试工具                      ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  前置步骤 - 启动 Fish Speech 服务:                     ║
║                                                      ║
║  方式 1: Docker (推荐)                                ║
║    cd fish-speech-test                                ║
║    docker compose up -d                               ║
║    # API 将监听 http://localhost:8080                  ║
║                                                      ║
║  方式 2: 本地 pip install (CPU 模式, Mac 可用)         ║
║    cd fish-speech-test                                ║
║    bash setup.sh                                      ║
║    bash start_server.sh                               ║
║                                                      ║
║  使用示例:                                            ║
║    python test_fish_speech.py --list                  ║
║    python test_fish_speech.py --voice "云希-全能配音"  ║
║    python test_fish_speech.py --compare "云希-全能配音" ║
║    python test_fish_speech.py --batch "云希,云野,云夏" ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fish Speech 本地测试工具")
    parser.add_argument("--api-url", default="http://localhost:8080", help="API 地址")
    parser.add_argument("--list", action="store_true", help="列出所有可用声音")
    parser.add_argument("--voice", type=str, help="测试单个声音克隆")
    parser.add_argument("--text", type=str, default="蜀山剑派乃是天下修真第一大门派，弟子遍布三山五岳。", help="合成文本")
    parser.add_argument("--batch", type=str, help="批量测试，逗号分隔的声音名")
    parser.add_argument("--compare", type=str, help="对比模式：指定声音名，生成对比音频")
    parser.add_argument("--search", type=str, help="搜索声音名（模糊匹配）")
    
    args = parser.parse_args()
    
    if args.list:
        voices = list_available_voices()
        print(f"\n可用声音 ({len(voices)} 个):")
        for i, v in enumerate(voices, 1):
            print(f"  {i:3d}. {v}")
        sys.exit(0)
    
    if args.search:
        keyword = args.search.lower()
        voices = list_available_voices()
        matches = [v for v in voices if keyword in v.lower()]
        print(f"\n搜索 '{args.search}' 结果 ({len(matches)} 个):")
        for v in matches:
            print(f"  - {v}")
        sys.exit(0)
    
    if args.compare:
        test_qwentts_comparison(args.api_url, args.compare, args.text)
        sys.exit(0)
    
    if args.voice:
        test_single_voice(args.api_url, args.voice, args.text)
        sys.exit(0)
    
    if args.batch:
        voices = [v.strip() for v in args.batch.split(",") if v.strip()]
        test_batch_voices(args.api_url, voices, [args.text])
        sys.exit(0)
    
    # 默认显示帮助
    print_usage()
    # 显示部分可用声音
    voices = list_available_voices()
    print(f"当前可用声音: {len(voices)} 个")
    print("使用 --list 查看全部，--search <关键词> 搜索")
