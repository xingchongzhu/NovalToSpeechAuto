#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

import whisper


DEFAULT_AUDIO_FILES = [
    "云健-中年男性磁性声音.mp3",
    "风发少年-男声-潇洒,磁性.mp3",
    "高冷姐-女声-知性,冷漠.mp3",
]
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a"}
DEFAULT_PLACEHOLDER_TEXT = "这是一段用于语音克隆的标准文本，发音清晰、语调平稳，我会用自然流畅的语速朗读，涵盖叙述、对话与情绪表达，能完整呈现音色特质。"


def clean_text(text: str) -> str:
    return " ".join(text.strip().split())


def should_skip_transcription(audio_path: Path, prompt_map: dict) -> bool:
    stem_text = prompt_map.get(audio_path.stem, "").strip()
    name_text = prompt_map.get(audio_path.name, "").strip()
    existing_text = stem_text or name_text
    return bool(existing_text and existing_text != DEFAULT_PLACEHOLDER_TEXT)


def collect_audio_files(clone_audio_dir: Path, requested_files: list[str], include_all_files: bool) -> list[Path]:
    if include_all_files:
        return sorted(
            [
                item
                for item in clone_audio_dir.iterdir()
                if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES
            ],
            key=lambda item: item.name,
        )

    audio_files = []
    for file_name in requested_files:
        audio_path = clone_audio_dir / file_name
        if not audio_path.exists():
            print(f"⚠️ 跳过不存在的文件: {audio_path}")
            continue
        audio_files.append(audio_path)
    return audio_files


def main() -> None:
    parser = argparse.ArgumentParser(description="转写参考音频并回填 prompt_texts.json")
    parser.add_argument(
        "--clone-audio-dir",
        default="clone-audio",
        help="参考音频目录，默认 clone-audio",
    )
    parser.add_argument(
        "--prompt-json",
        default="clone-audio/prompt_texts.json",
        help="prompt_texts.json 路径",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Whisper 模型名，默认 small",
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="Whisper 语言参数，默认 zh",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=DEFAULT_AUDIO_FILES,
        help="指定需要转写的音频文件名",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="转写目录中所有参考音频文件",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    clone_audio_dir = (project_root / args.clone_audio_dir).resolve()
    prompt_json_path = (project_root / args.prompt_json).resolve()

    prompt_map = {}
    if prompt_json_path.exists():
        with prompt_json_path.open("r", encoding="utf-8") as file:
            prompt_map = json.load(file)

    audio_files = collect_audio_files(clone_audio_dir, args.files, args.all_files)
    if not audio_files:
        raise RuntimeError(f"未找到可转写的音频文件: {clone_audio_dir}")

    print(f"🚀 加载 Whisper 模型: {args.model}")
    model = whisper.load_model(args.model)

    updates = {}
    processed_count = 0
    skipped_count = 0
    for audio_path in audio_files:
        if should_skip_transcription(audio_path, prompt_map):
            skipped_count += 1
            print(f"\n⏭️ 跳过已转写: {audio_path.name}")
            continue

        print(f"\n🎧 转写: {audio_path.name}")
        result = model.transcribe(str(audio_path), language=args.language, fp16=False)
        text = clean_text(result.get("text", ""))
        updates[audio_path.stem] = text
        updates[audio_path.name] = text
        prompt_map[audio_path.stem] = text
        prompt_map[audio_path.name] = text
        processed_count += 1
        with prompt_json_path.open("w", encoding="utf-8") as file:
            json.dump(prompt_map, file, ensure_ascii=False, indent=2)
            file.write("\n")
        print(f"📝 初稿: {text}")

    print("\n✅ 已回填 prompt_texts.json")
    print(f"📂 文件: {prompt_json_path}")
    print(f"🧾 本次新增转写: {processed_count} 个音频，跳过 {skipped_count} 个，累计更新键 {len(updates)} 个")
    print("⚠️ 这些内容仍需人工逐字校对后再用于高质量克隆。")


if __name__ == "__main__":
    main()
