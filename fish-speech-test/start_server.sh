#!/bin/bash
# Fish Speech 推理服务启动脚本 (pip 模式)
#
# 前置条件: bash setup.sh --pip 已完成安装
#
# 启动后:
#   WebUI: http://localhost:7860
#   API:   http://localhost:8080

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-fish"
REPO_DIR="$SCRIPT_DIR/fish-speech"
MODEL_DIR="$SCRIPT_DIR/checkpoints/fish-speech-1.5"

log() { echo -e "\033[1;32m[FishSpeech]\033[0m $*"; }
warn() { echo -e "\033[1;33m[FishSpeech]\033[0m $*"; }

if [ ! -d "$VENV_DIR" ]; then
    warn "虚拟环境未找到，请先运行: bash setup.sh --pip"
    exit 1
fi

if [ ! -d "$MODEL_DIR" ]; then
    warn "模型未下载，请先运行: bash setup.sh --pip"
    exit 1
fi

source "$VENV_DIR/bin/activate"

log "启动 Fish Speech 推理服务..."
log "模型: $MODEL_DIR"
log "WebUI: http://localhost:7860"
log "API:   http://localhost:8080"
echo ""

cd "$REPO_DIR"

# 启动 WebUI (包含 API 服务)
python tools/run_webui.py \
    --listen 0.0.0.0:7860 \
    --checkpoint-path "$MODEL_DIR" \
    --device cpu \
    --half false \
    "$@"
