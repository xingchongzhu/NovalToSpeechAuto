#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 Woosh-DFlow 推理所需模型权重。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WOOSH_DIR = ROOT_DIR / "Woosh"
CHECKPOINTS_DIR = WOOSH_DIR / "checkpoints"
MODELSCOPE_CACHE_DIR = WOOSH_DIR / ".cache"
HF_MIRROR = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")

REQUIRED_COMPONENTS = {
    "Woosh-DFlow": {
        "source": "huggingface",
        "files": ["config.yaml", "weights.safetensors"],
    },
    "Woosh-AE": {
        "source": "modelscope",
        "files": ["config.yaml", "weights.safetensors"],
    },
    "TextConditionerA": {
        "source": "modelscope",
        "files": ["config.yaml", "weights.safetensors"],
    },
}


def log(message: str) -> None:
    print(f"[download_woosh] {message}", flush=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_ready(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 1024


def download_with_curl(url: str, dest: Path) -> None:
    ensure_dir(dest.parent)
    tmp = dest.with_suffix(dest.suffix + ".part")
    cmd = ["curl", "-L", "--fail", "--progress-bar", "-o", str(tmp), url]
    subprocess.run(cmd, check=True)
    tmp.replace(dest)


def download_with_urllib(url: str, dest: Path) -> None:
    ensure_dir(dest.parent)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as output:
        shutil.copyfileobj(response, output)
    tmp.replace(dest)


def download_url(url: str, dest: Path) -> None:
    if is_ready(dest):
        log(f"已存在，跳过: {dest.relative_to(ROOT_DIR)}")
        return
    log(f"下载: {url}")
    try:
        download_with_curl(url, dest)
    except Exception:
        download_with_urllib(url, dest)


def ensure_modelscope_package() -> None:
    try:
        import modelscope  # noqa: F401
        return
    except Exception:
        pass

    log("安装 modelscope...")
    subprocess.run([sys.executable, "-m", "pip", "install", "modelscope"], check=True)


def download_modelscope_components() -> None:
    missing = []
    for component, meta in REQUIRED_COMPONENTS.items():
        if meta["source"] != "modelscope":
            continue
        for filename in meta["files"]:
            target = CHECKPOINTS_DIR / component / filename
            if not is_ready(target):
                missing.append((component, filename))

    if not missing:
        return

    ensure_modelscope_package()
    from modelscope import snapshot_download

    log("从 ModelScope 下载 HuaCHayu/Woosh...")
    model_dir = Path(snapshot_download("HuaCHayu/Woosh", cache_dir=str(MODELSCOPE_CACHE_DIR)))

    for component, filename in missing:
        source = model_dir / "checkpoints" / component / filename
        target = CHECKPOINTS_DIR / component / filename
        if not source.exists():
            raise FileNotFoundError(f"ModelScope 文件不存在: {source}")
        ensure_dir(target.parent)
        shutil.copy2(source, target)
        log(f"复制: {target.relative_to(ROOT_DIR)}")


def download_huggingface_dflow() -> None:
    component = "Woosh-DFlow"
    for filename in REQUIRED_COMPONENTS[component]["files"]:
        target = CHECKPOINTS_DIR / component / filename
        url = f"{HF_MIRROR}/drbaph/Woosh/resolve/main/{component}/{filename}"
        download_url(url, target)


def verify_required_files() -> None:
    missing = []
    for component, meta in REQUIRED_COMPONENTS.items():
        for filename in meta["files"]:
            target = CHECKPOINTS_DIR / component / filename
            if not is_ready(target):
                missing.append(str(target.relative_to(ROOT_DIR)))
    if missing:
        raise RuntimeError("缺少模型文件:\n" + "\n".join(missing))


def main() -> None:
    if not WOOSH_DIR.exists():
        raise FileNotFoundError(f"Woosh 仓库不存在，请先运行 setup_models.sh: {WOOSH_DIR}")
    download_modelscope_components()
    download_huggingface_dflow()
    verify_required_files()
    log("Woosh 模型权重准备完成")


if __name__ == "__main__":
    main()
