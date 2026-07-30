#!/usr/bin/env python3
"""
批量 VoiceDesign 克隆音色生成脚本
读取配音表，为每个角色使用 voice-design 模式生成克隆声音，保存到 clone-audio 目录。
"""

import os
import sys

# HuggingFace 环境变量（须在导入 audio_processing_module 前设置）
os.environ['HUGGINGFACE_HUB_DISABLE_REPO_ID_VALIDATION'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_project_root():
    """向上查找项目根目录（包含 novel_tool 目录的父目录）"""
    d = SCRIPT_DIR
    for _ in range(5):
        if os.path.isdir(os.path.join(d, "novel_tool")):
            return d
        d = os.path.dirname(d)
    return SCRIPT_DIR  # 回退

PROJECT_ROOT = _find_project_root()

# 确保能导入 audio_processing_module 及 qwen_tts
sys.path.insert(0, os.path.join(PROJECT_ROOT, "novel_tool", "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "qwen3-tts"))
sys.path.insert(0, PROJECT_ROOT)

import json
import time
import argparse

from audio_processing_module import AudioEngine, VoiceParams


def load_voice_table(voice_table_path: str) -> dict:
    """加载角色配音表 JSON"""
    with open(voice_table_path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_all_characters(voice_table: dict):
    """遍历配音表中所有角色，返回 (角色条目, 所属级别)"""
    levels = ["旁白", "主要角色", "重要角色", "次要角色", "临时角色"]
    for level in levels:
        for char in voice_table.get(level, []):
            yield char, level


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return name.replace("/", "_").replace("\\", "_").replace(":", "_")


def main():
    parser = argparse.ArgumentParser(description="批量 VoiceDesign 克隆音色生成")
    parser.add_argument(
        "--voice-table",
        type=str,
        default=os.path.join(PROJECT_ROOT, "novel_tool", "character_voice_tables", "蜀山剑侠传角色配音表.json"),
        help="配音表 JSON 文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(PROJECT_ROOT, "clone-audio"),
        help="克隆音频输出目录（默认项目根下的 clone-audio）",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="我是{角色名}，这是我的声音样本，欢迎收听蜀山剑侠传有声剧，给你带来不一样的听觉盛宴，感谢收听。",
        help="用于生成克隆声音的文本模板，支持 {角色名} 占位符",
    )
    parser.add_argument(
        "--start-from",
        type=str,
        default="",
        help="从指定角色名开始处理（用于断点续传）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="最多处理的角色数量（0 表示不限制）",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="跳过已存在的音频文件（默认开启）",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="不跳过已存在的音频文件，重新生成",
    )
    parser.add_argument(
        "--levels",
        type=str,
        nargs="+",
        default=["旁白", "主要角色", "重要角色", "次要角色", "临时角色"],
        help="要处理的角色级别，可选: 旁白 主要角色 重要角色 次要角色 临时角色",
    )

    args = parser.parse_args()

    # 加载配音表
    print(f"加载配音表: {args.voice_table}")
    voice_table = load_voice_table(args.voice_table)
    stats = voice_table.get("统计", {})
    print(f"配音表统计: 总计 {stats.get('总计', '?')} 个角色")

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"输出目录: {args.output_dir}")

    # 初始化 AudioEngine（voice_design 模式）
    print("初始化 AudioEngine（VoiceDesign 模式）...")
    engine = AudioEngine(
        temp_dir=os.path.join(PROJECT_ROOT, "temp_audio"),
        tts_mode="voice_design",
    )

    # 收集所有要处理的角色
    tasks = []
    seen_names = set()
    for char, level in iter_all_characters(voice_table):
        if level not in args.levels:
            continue
        name = char.get("角色名", "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        tasks.append((char, level))

    print(f"\n共 {len(tasks)} 个角色待处理 (级别: {', '.join(args.levels)})")

    # 断点续传支持
    start_index = 0
    if args.start_from:
        for i, (char, _) in enumerate(tasks):
            if char.get("角色名") == args.start_from:
                start_index = i
                print(f"从角色「{args.start_from}」(索引 {i}) 开始处理")
                break
        else:
            print(f"警告: 未找到角色「{args.start_from}」，从头开始")

    tasks = tasks[start_index:]
    if args.limit > 0:
        tasks = tasks[: args.limit]
        print(f"限制处理数量: {args.limit}")

    # 批量处理
    success_count = 0
    skip_count = 0
    fail_count = 0
    total = len(tasks)
    t_start = time.time()

    def _progress(idx):
        """格式化进度: 第5个/共909个 剩余904个"""
        remain = total - idx if total >= idx else 0
        return f"第{idx}个/共{total}个  剩余{remain}个"

    for idx, (char, level) in enumerate(tasks, 1):
        name = char.get("角色名", "")
        voice_name = char.get("配音名", "")
        prompt = char.get("VoiceDesign_Prompt", "")

        if not prompt:
            print(f"\n{_progress(idx)} ⚠️ 跳过「{name}」: 缺少 VoiceDesign_Prompt")
            skip_count += 1
            continue

        filename = sanitize_filename(name) + ".mp3"
        output_path = os.path.join(args.output_dir, filename)

        if args.skip_existing and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"\n{_progress(idx)} ⏭ 跳过「{name}」({level}): 已存在")
            skip_count += 1
            continue

        text = args.text.format(角色名=name)

        print(f"\n{'='*60}")
        print(f"{_progress(idx)} 生成「{name}」({level})")
        print(f"  配音名: {voice_name}")
        print(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"  文本: {text}")
        print(f"  输出: {filename}")

        try:
            params = VoiceParams(
                text=text,
                role=name,
                role_voice=voice_name,
                speed="1.0",
                volume="1.0",
                pitch="1.0",
                tts_mode="voice_design",
                voice_design_prompt=prompt,
            )

            audio = engine.text_to_speech(params)
            audio.export(output_path, format="mp3")
            dur = len(audio) / 1000.0
            print(f"  ✅ 生成成功！音频时长: {dur:.1f}s, 文件: {filename}")
            success_count += 1

        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            fail_count += 1

        # 每 10 个输出一次进度统计
        if idx % 10 == 0:
            elapsed = time.time() - t_start
            rate = idx / elapsed if elapsed > 0 else 0
            eta = (total - idx) / rate if rate > 0 else 0
            remain = total - idx
            print(f"\n--- 进度汇总 [{_progress(idx)}] ---")
            print(f"  已合成: {success_count} | 已跳过: {skip_count} | 失败: {fail_count}")
            print(f"  速率: {rate:.2f} 个/秒 | 预计剩余: {eta:.0f}秒 ({eta/60:.1f}分钟)")

    # 最终统计
    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"批量生成完成！")
    print(f"  总计: {total} 个角色")
    print(f"  成功: {success_count}")
    print(f"  跳过: {skip_count}")
    print(f"  失败: {fail_count}")
    print(f"  耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    print(f"  输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
