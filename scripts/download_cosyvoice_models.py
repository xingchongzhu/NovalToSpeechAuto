#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys

from modelscope import snapshot_download


DEFAULT_MODELS = [
    "iic/CosyVoice-300M",
    "iic/CosyVoice-ttsfrd",
]

OPTIONAL_MODELS = {
    "sft": "iic/CosyVoice-300M-SFT",
    "instruct": "iic/CosyVoice-300M-Instruct",
    "cosyvoice2": "iic/CosyVoice2-0.5B",
}


def download_model(model_id: str, target_root: str) -> str:
    local_dir = os.path.join(target_root, model_id.split("/")[-1])
    print(f"📥 下载模型: {model_id}")
    print(f"   目标目录: {local_dir}")
    snapshot_download(model_id, local_dir=local_dir)
    print(f"✅ 完成: {model_id}")
    return local_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 CosyVoice 相关模型到项目目录")
    parser.add_argument(
        "--model-root",
        default="pretrained_models",
        help="模型下载根目录，默认 pretrained_models",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=[],
        choices=sorted(OPTIONAL_MODELS.keys()),
        help="附加下载可选模型: sft / instruct / cosyvoice2",
    )
    args = parser.parse_args()

    model_root = os.path.abspath(args.model_root)
    os.makedirs(model_root, exist_ok=True)

    model_ids = list(DEFAULT_MODELS)
    for item in args.include:
        model_ids.append(OPTIONAL_MODELS[item])

    try:
        for model_id in model_ids:
            download_model(model_id, model_root)
    except Exception as error:
        print(f"\n❌ 模型下载失败: {error}")
        raise

    print("\n🎉 CosyVoice 模型下载完成")
    print(f"📂 模型目录: {model_root}")
    if sys.platform == "darwin":
        print("ℹ️ macOS 下通常不直接安装 ttsfrd wheel，默认可回退到 wetext 做文本规范化。")


if __name__ == "__main__":
    main()
