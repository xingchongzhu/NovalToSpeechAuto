#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预下载 Qwen3-TTS 模型到本地目录。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_ID = os.environ.get("QWEN3_TTS_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
DEFAULT_LOCAL_DIR = Path(os.environ.get("QWEN3_TTS_LOCAL_DIR", ROOT_DIR / "qwen3-tts-model"))


def log(message: str) -> None:
    print(f"[download_qwen3_tts] {message}", flush=True)


def ensure_huggingface_hub() -> None:
    try:
        import huggingface_hub  # noqa: F401
        return
    except Exception:
        pass
    log("安装 huggingface_hub...")
    subprocess.run([sys.executable, "-m", "pip", "install", "huggingface_hub"], check=True)


def download_model(model_id: str, local_dir: Path) -> None:
    ensure_huggingface_hub()
    from huggingface_hub import snapshot_download

    local_dir.mkdir(parents=True, exist_ok=True)
    log(f"下载 {model_id} -> {local_dir}")
    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    log("Qwen3-TTS 模型准备完成")


def main() -> None:
    download_model(DEFAULT_MODEL_ID, DEFAULT_LOCAL_DIR)


if __name__ == "__main__":
    main()
