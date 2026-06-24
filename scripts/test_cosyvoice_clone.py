#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import torchaudio


ROLE_TESTS = [
    {
        "role": "沉稳旁白",
        "audio_file": "Adam-成熟,稳重.mp3",
        "text": "夜色沉下来以后，街道安静了许多，这一段用于验证成熟稳重男声的克隆效果。",
    },
    {
        "role": "温柔女声",
        "audio_file": "Adela-外语,温柔女声.mp3",
        "text": "她轻声开口，语气柔和自然，这一段用于验证温柔女声路线的克隆配音效果。",
    },
    {
        "role": "惊悚反派",
        "audio_file": "Alastor-搞怪,惊悚.mp3",
        "text": "黑暗里忽然传来一声低笑，这一段用于验证惊悚诡异风格音色的克隆表现。",
    },
    {
        "role": "英文男声",
        "audio_file": "Alex-外语.mp3",
        "text": "This short line is used to verify whether the cloned English male voice stays clear and natural.",
    },
    {
        "role": "知性成熟女性",
        "audio_file": "Amanda-知性,成熟.mp3",
        "text": "她说话节奏平稳，表达清晰，这一段用于验证知性成熟女声的克隆稳定性。",
    },
    {
        "role": "优雅女声",
        "audio_file": "Anna-知性,优雅.mp3",
        "text": "她的声音从容而克制，这一段用于验证优雅知性路线的克隆效果。",
    },
    {
        "role": "双语讲述者",
        "audio_file": "Bella-双语.mp3",
        "text": "今天我们继续讲这个故事，这一段用于验证双语风格角色在中文场景下的克隆效果。",
    },
    {
        "role": "低沉解说",
        "audio_file": "Brian-影视,小说,低沉男声.mp3",
        "text": "镜头缓缓推进，真相也逐渐浮出水面，这一段用于验证低沉男声解说路线的克隆表现。",
    },
    {
        "role": "美式英语女声",
        "audio_file": "Candice-愉悦,美式英语.mp3",
        "text": "This sample checks whether the cloned female English voice keeps a bright and lively tone.",
    },
    {
        "role": "沙哑低沉",
        "audio_file": "Clown Man-沙哑,低沉.mp3",
        "text": "他压低声音慢慢说出真相，这一段用于验证沙哑低沉音色的克隆相似度。",
    },
]

DEFAULT_REFERENCE_FILES = [item["audio_file"] for item in ROLE_TESTS[:3]]

DEFAULT_PROMPT_TEXT = "这是一段用于声音克隆的参考音频。"


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_").replace(" ", "_")


def load_prompt_text_map(clone_audio_dir: Path) -> dict:
    prompt_file = clone_audio_dir / "prompt_texts.json"
    if not prompt_file.exists():
        return {}
    with prompt_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def pick_reference_audio(clone_audio_dir: Path, explicit_name: Optional[str] = None) -> Path:
    if explicit_name:
        candidate = clone_audio_dir / explicit_name
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"指定参考音频不存在: {candidate}")

    for name in DEFAULT_REFERENCE_FILES:
        candidate = clone_audio_dir / name
        if candidate.exists():
            return candidate

    for item in sorted(clone_audio_dir.iterdir()):
        if item.suffix.lower() in {".mp3", ".wav", ".m4a"}:
            return item

    raise FileNotFoundError(f"未在目录中找到可用参考音频: {clone_audio_dir}")


def build_role_cases(clone_audio_dir: Path, role_limit: Optional[int]) -> list[dict]:
    role_cases = []
    for role_test in ROLE_TESTS:
        audio_path = clone_audio_dir / role_test["audio_file"]
        if not audio_path.exists():
            continue
        role_cases.append(
            {
                "role": role_test["role"],
                "audio_path": audio_path,
                "text": role_test["text"],
            }
        )

    if role_limit is not None:
        role_cases = role_cases[:role_limit]

    if not role_cases:
        raise RuntimeError("未找到可用于 CosyVoice 克隆验证的参考音频，请先补充样本。")

    return role_cases


def ensure_cosyvoice_importable(cosyvoice_dir: Path) -> None:
    sys.path.insert(0, str(cosyvoice_dir))
    third_party_matcha = cosyvoice_dir / "third_party" / "Matcha-TTS"
    third_party_codec = cosyvoice_dir / "third_party" / "AcademiCodec"
    if third_party_matcha.exists():
        sys.path.insert(0, str(third_party_matcha))
    if third_party_codec.exists():
        sys.path.insert(0, str(third_party_codec))


def build_prompt_text(audio_path: Path, prompt_text_map: dict) -> str:
    audio_stem = audio_path.stem
    prompt_text = prompt_text_map.get(audio_stem, "")
    if prompt_text and "请填写" not in prompt_text:
        return prompt_text
    return DEFAULT_PROMPT_TEXT


def main() -> None:
    parser = argparse.ArgumentParser(description="CosyVoice zero-shot 声音克隆验证脚本")
    parser.add_argument(
        "--cosyvoice-dir",
        default="CosyVoice",
        help="CosyVoice 仓库目录，默认项目根目录下的 CosyVoice",
    )
    parser.add_argument(
        "--model-dir",
        default="pretrained_models/CosyVoice-300M",
        help="CosyVoice-300M 模型目录",
    )
    parser.add_argument(
        "--clone-audio-dir",
        default="clone-audio",
        help="参考音频目录，默认 clone-audio",
    )
    parser.add_argument(
        "--reference-audio",
        default=None,
        help="指定主参考音频文件名，默认自动选择",
    )
    parser.add_argument(
        "--role-limit",
        type=int,
        default=10,
        help="限制多角色克隆验证数量，默认 10",
    )
    parser.add_argument(
        "--output-dir",
        default="cosyvoice_clone_output",
        help="输出目录，默认 cosyvoice_clone_output",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"当前 Python 版本为 {sys.version.split()[0]}，建议使用 Python >= 3.10 运行 CosyVoice。"
        )

    project_root = Path(__file__).resolve().parent
    cosyvoice_dir = (project_root / args.cosyvoice_dir).resolve()
    model_dir = (project_root / args.model_dir).resolve()
    clone_audio_dir = (project_root / args.clone_audio_dir).resolve()
    output_dir = (project_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not cosyvoice_dir.exists():
        raise FileNotFoundError(f"未找到 CosyVoice 仓库目录: {cosyvoice_dir}")
    if not model_dir.exists():
        raise FileNotFoundError(f"未找到 CosyVoice 模型目录: {model_dir}")
    if not clone_audio_dir.exists():
        raise FileNotFoundError(f"未找到克隆音频目录: {clone_audio_dir}")

    ensure_cosyvoice_importable(cosyvoice_dir)

    from cosyvoice.cli.cosyvoice import CosyVoice

    prompt_text_map = load_prompt_text_map(clone_audio_dir)
    reference_audio = pick_reference_audio(clone_audio_dir, args.reference_audio)
    role_cases = build_role_cases(clone_audio_dir, args.role_limit)

    print("\n🚀 初始化 CosyVoice 模型...")
    start_time = time.time()
    cosyvoice = CosyVoice(str(model_dir))
    init_time = time.time() - start_time
    sample_rate = getattr(cosyvoice, "sample_rate", 22050)
    print(f"✅ 模型初始化完成，耗时: {init_time:.2f}秒")
    print(f"🎚️ 输出采样率: {sample_rate}Hz")
    print(f"🎤 主参考音频: {reference_audio}")
    print(f"🎭 多角色克隆样本数: {len(role_cases)}")

    single_prompt_text = build_prompt_text(reference_audio, prompt_text_map)
    single_cases = [
        {
            "name": "single_reference_clone_01",
            "text": "这是一段仅使用参考音频进行声音克隆的验证示例。",
            "prompt_text": single_prompt_text,
            "prompt_audio_path": str(reference_audio),
        },
        {
            "name": "single_reference_clone_02",
            "text": "如果这段音频的音色接近参考音频，就说明 CosyVoice 直接克隆方案是成立的。",
            "prompt_text": single_prompt_text,
            "prompt_audio_path": str(reference_audio),
        },
    ]

    print("\n================ 单参考音频克隆验证 ================")
    for index, case in enumerate(single_cases, 1):
        print(f"\n🎯 [{index}/{len(single_cases)}] {case['name']}")
        print(f"   文本: {case['text']}")
        start_time = time.time()
        outputs = list(
            cosyvoice.inference_zero_shot(
                case["text"],
                case["prompt_text"],
                case["prompt_audio_path"],
                stream=False,
            )
        )
        gen_time = time.time() - start_time
        if not outputs:
            raise RuntimeError("CosyVoice 未返回生成结果")
        output_path = output_dir / f"{case['name']}.wav"
        torchaudio.save(str(output_path), outputs[0]["tts_speech"], sample_rate)
        print(f"💾 保存到: {output_path}")
        print(f"⏱️ 耗时: {gen_time:.2f}秒")

    print("\n================ 多角色参考音频克隆验证 ================")
    for index, role_case in enumerate(role_cases, 1):
        role_name = role_case["role"]
        role_slug = safe_name(role_name)
        prompt_text = build_prompt_text(role_case["audio_path"], prompt_text_map)
        print(f"\n🎭 [{index}/{len(role_cases)}] 角色: {role_name}")
        print(f"   参考音频: {role_case['audio_path']}")
        print(f"   prompt_text: {prompt_text}")
        print(f"   克隆文本: {role_case['text']}")
        start_time = time.time()
        outputs = list(
            cosyvoice.inference_zero_shot(
                role_case["text"],
                prompt_text,
                str(role_case["audio_path"]),
                stream=False,
            )
        )
        gen_time = time.time() - start_time
        if not outputs:
            raise RuntimeError(f"角色 {role_name} 未返回生成结果")
        output_path = output_dir / f"role_{index:02d}_{role_slug}_clone.wav"
        torchaudio.save(str(output_path), outputs[0]["tts_speech"], sample_rate)
        print(f"   💾 克隆输出: {output_path}")
        print(f"   ⏱️ 克隆耗时: {gen_time:.2f}秒")

    print("\n🎉 CosyVoice 克隆 demo 验证完成！")
    print(f"📂 输出目录: {output_dir}")
    print("✅ 重点听不同角色之间的音色差异，以及生成音色和参考音频的相似度。")
    if single_prompt_text == DEFAULT_PROMPT_TEXT:
        print("⚠️ 当前使用默认 prompt_text。若要提升克隆稳定性，请先填写 clone-audio/prompt_texts.json 中对应参考音频的真实转写文本。")


if __name__ == "__main__":
    main()
