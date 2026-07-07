#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 Woosh 音效生成链路是否可用。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT_DIR / "novel_tool" / "scripts"
OUTPUT_PATH = ROOT_DIR / "output" / "verify" / "woosh_verify.wav"


def main() -> None:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    sys.path.insert(0, str(SCRIPT_DIR))

    from woosh_generate_audio import generate_audio

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = generate_audio(
        "sharp metallic sword unsheathing sound, steel blade sliding out of leather scabbard",
        duration=2,
        output_path=str(OUTPUT_PATH),
    )
    if not result or not Path(result).exists():
        raise RuntimeError("Woosh 验证失败：未生成音频")
    print(f"[verify_woosh] OK: {result}")


if __name__ == "__main__":
    main()
