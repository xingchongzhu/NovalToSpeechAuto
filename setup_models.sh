#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WOOSH_DIR="$ROOT_DIR/Woosh"
COSYVOICE_DIR="$ROOT_DIR/CosyVoice"
COSYVOICE_ENV_DIR="$ROOT_DIR/.venv-cosyvoice"
SETUP_COSYVOICE="${SETUP_COSYVOICE:-0}"

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

setup_cosyvoice() {
  if [ "$SETUP_COSYVOICE" != "1" ]; then
    log "跳过 CosyVoice 环境准备；如需启用请执行: SETUP_COSYVOICE=1 zsh setup_models.sh"
    return
  fi

  if ! command -v brew >/dev/null 2>&1; then
    log "未检测到 Homebrew，无法自动安装 Python 3.10，请先手动准备。"
    return
  fi

  if ! command -v python3.10 >/dev/null 2>&1; then
    log "安装 Python 3.10..."
    brew install python@3.10
  fi

  if [ -d "$COSYVOICE_DIR/.git" ]; then
    log "CosyVoice 仓库已存在，跳过克隆: $COSYVOICE_DIR"
  else
    log "克隆 CosyVoice 仓库..."
    rm -rf "$COSYVOICE_DIR"
    git clone --depth 1 https://github.com/FunAudioLLM/CosyVoice.git "$COSYVOICE_DIR"
  fi

  if [ ! -d "$COSYVOICE_ENV_DIR" ]; then
    log "创建 CosyVoice 独立虚拟环境..."
    python3.10 -m venv "$COSYVOICE_ENV_DIR"
  fi

  log "安装 CosyVoice 依赖..."
  "$COSYVOICE_ENV_DIR/bin/pip" install --upgrade pip setuptools wheel
  "$COSYVOICE_ENV_DIR/bin/pip" install -r "$COSYVOICE_DIR/requirements.txt"

  log "下载 CosyVoice 基础模型与 ttsfrd 资源..."
  (cd "$ROOT_DIR" && "$COSYVOICE_ENV_DIR/bin/python" scripts/download_cosyvoice_models.py)

  if [ -f "$ROOT_DIR/pretrained_models/CosyVoice-ttsfrd/resource.zip" ]; then
    log "检测到 CosyVoice-ttsfrd resource.zip，可按需手动解压。"
  fi

  if [ "$(uname -s)" = "Darwin" ]; then
    log "当前为 macOS，默认不安装 Linux 专用 ttsfrd wheel，推理会回退到 wetext。"
  fi

  log "CosyVoice 环境准备完成"
  log "验证命令: $COSYVOICE_ENV_DIR/bin/python test_cosyvoice_clone.py --role-limit 3"
}

print_stable_audio3_instructions() {
  log "Stable Audio 3 采用隔离实验环境，当前不并入主模型安装流程"
  log "安装说明:"
  log "  1. zsh stable-audio3-lab/scripts/setup_lab.sh"
  log "  2. zsh stable-audio3-lab/scripts/run_smoke.sh"
  log "  3. zsh stable-audio3-lab/scripts/clone_official_repo.sh"
  log "下载 / 克隆链接:"
  log "  - 官方仓库: https://github.com/Stability-AI/stable-audio-3"
  log "  - 模型集合: https://huggingface.co/collections/stabilityai/stable-audio-3"
  log "  - 小模型 music: https://huggingface.co/stabilityai/stable-audio-3-small-music"
  log "  - 小模型 sfx: https://huggingface.co/stabilityai/stable-audio-3-small-sfx"
  log "说明:"
  log "  - 实验目录: stable-audio3-lab/"
  log "  - 独立虚拟环境: stable-audio3-lab/.venv"
  log "  - clone_official_repo.sh 内部会执行: git clone https://github.com/Stability-AI/stable-audio-3.git stable-audio3-lab/stable-audio-3"
  log "  - 适合先验证 small-music / small-sfx，不建议直接替代当前章节级背景音链路"
}

main() {
  ensure_uv
  setup_woosh_repo
  setup_woosh_models
  setup_qwen3_tts
  verify_woosh
  setup_cosyvoice
  print_stable_audio3_instructions
  log "模型环境准备完成"
}

main "$@"
