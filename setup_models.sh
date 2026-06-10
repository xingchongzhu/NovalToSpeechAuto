#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WOOSH_DIR="$ROOT_DIR/Woosh"

log() {
  echo "[setup_models] $1"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
    return
  fi
  if [ -x "$HOME/Library/Python/3.9/bin/uv" ]; then
    UV_BIN="$HOME/Library/Python/3.9/bin/uv"
    return
  fi
  log "uv 未安装，正在安装..."
  python3 -m pip install --user uv
  UV_BIN="$HOME/Library/Python/3.9/bin/uv"
}

setup_woosh_repo() {
  if [ -d "$WOOSH_DIR/.git" ]; then
    log "Woosh 仓库已存在，跳过克隆: $WOOSH_DIR"
  else
    log "克隆 Woosh 仓库..."
    rm -rf "$WOOSH_DIR"
    git clone --depth 1 https://github.com/SonyResearch/Woosh.git "$WOOSH_DIR"
  fi

  log "安装 Woosh 依赖..."
  (cd "$WOOSH_DIR" && "$UV_BIN" sync --extra cpu)
}

setup_woosh_models() {
  log "下载 Woosh 模型权重..."
  (cd "$ROOT_DIR" && python3 scripts/download_woosh_models.py)
}

setup_qwen3_tts() {
  log "下载 Qwen3-TTS 模型..."
  (cd "$ROOT_DIR" && python3 scripts/download_qwen3_tts.py)
}

verify_woosh() {
  log "验证 Woosh 最小推理..."
  (cd "$ROOT_DIR" && python3 scripts/verify_woosh.py)
}

main() {
  ensure_uv
  setup_woosh_repo
  setup_woosh_models
  setup_qwen3_tts
  verify_woosh
  log "模型环境准备完成"
}

main "$@"
