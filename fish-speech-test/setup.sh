#!/bin/bash
# Fish Speech 本地环境安装脚本（macOS/Linux 通用）
#
# 安装方式 1: pip install (CPU/MPS 模式)
#   bash setup.sh --pip
#
# 安装方式 2: Docker (需要先安装 Docker Desktop)
#   bash setup.sh --docker
#
# 注意：
# - macOS Apple Silicon 只能使用 CPU/MPS 模式
# - NVIDIA GPU 推荐 Docker 模式
# - CPU 模式推理较慢但功能完整

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:---help}"

log() { echo -e "\033[1;32m[FishSpeech-Setup]\033[0m $*"; }
warn() { echo -e "\033[1;33m[FishSpeech-Warn]\033[0m $*"; }
err() { echo -e "\033[1;31m[FishSpeech-Error]\033[0m $*"; }

print_help() {
    cat << 'EOF'
Fish Speech 本地测试环境安装

用法:
  bash setup.sh --help      显示帮助
  bash setup.sh --pip       使用 pip 安装 (CPU/MPS 模式, Mac 可用)
  bash setup.sh --docker    使用 Docker 启动
  bash setup.sh --docker-cpu 使用 Docker CPU 模式启动 (Mac 可用)
  bash setup.sh --status    检查服务状态

前置要求:
  - Python >= 3.10 (pip 方式)
  - Docker Desktop (docker 方式) — macOS 需先安装 Docker.app
EOF
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        err "需要 Python 3.10+"
        exit 1
    fi
    local pyver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log "Python 版本: $pyver"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        err "未检测到 Docker。macOS 请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
        err "或使用 --pip 方式安装"
        exit 1
    fi
    log "Docker 已安装"
    docker --version
}

setup_pip() {
    log "=== pip 安装模式 (CPU/MPS) ==="
    check_python

    # 创建虚拟环境（需要 Python >= 3.10）
    local venv_dir="$SCRIPT_DIR/.venv-fish"
    local py_bin="python3.11"
    if command -v python3.12 &>/dev/null; then
        py_bin="python3.12"
    elif command -v python3.11 &>/dev/null; then
        py_bin="python3.11"
    elif command -v python3.10 &>/dev/null; then
        py_bin="python3.10"
    fi
    log "使用 Python: $($py_bin --version)"
    if [ ! -d "$venv_dir" ]; then
        log "创建虚拟环境: $venv_dir"
        $py_bin -m venv "$venv_dir"
    fi
    
    source "$venv_dir/bin/activate"
    log "升级 pip..."
    pip install --upgrade pip -q

    # 克隆 Fish Speech 仓库
    local repo_dir="$SCRIPT_DIR/fish-speech"
    if [ ! -d "$repo_dir" ]; then
        log "克隆 Fish Speech 仓库..."
        git clone https://github.com/fishaudio/fish-speech.git "$repo_dir"
    else
        log "Fish Speech 仓库已存在，更新..."
        (cd "$repo_dir" && git pull --ff-only 2>/dev/null || true)
    fi

    cd "$repo_dir"
    
    # 安装 CPU 依赖
    log "安装 Fish Speech + CPU 依赖..."
    pip install -e ".[cpu]" 2>&1 | tail -5

    # 下载模型
    local model_dir="$SCRIPT_DIR/checkpoints/fish-speech-1.5"
    if [ ! -d "$model_dir" ]; then
        log "下载 Fish Speech 1.5 模型 (~1.5GB)..."
        mkdir -p "$(dirname "$model_dir")"
        huggingface-cli download fishaudio/fish-speech-1.5 \
            --local-dir "$model_dir" 2>&1 | tail -5
    else
        log "模型已存在: $model_dir"
    fi

    log "安装完成!"
    log "启动服务: bash start_server.sh"
}

setup_docker() {
    log "=== Docker 模式 ==="
    check_docker
    
    # 确保有模型目录
    mkdir -p "$SCRIPT_DIR/checkpoints"
    
    local compose_file="$SCRIPT_DIR/compose.yml"
    if [ "$MODE" = "--docker-cpu" ]; then
        compose_file="$SCRIPT_DIR/compose.cpu.yml"
        log "使用 CPU 模式 Docker Compose"
    fi
    
    # 拉取镜像并启动
    log "拉取 Fish Speech Docker 镜像..."
    docker compose -f "$compose_file" pull
    
    log "启动服务..."
    docker compose -f "$compose_file" up -d
    
    log "等待服务就绪..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
            log "服务已就绪!"
            log "API: http://localhost:8080"
            log "WebUI: http://localhost:7860"
            return 0
        fi
        sleep 2
        echo -n "."
    done
    
    warn "服务可能尚未就绪，请查看日志: docker compose -f $compose_file logs"
}

check_status() {
    log "=== 服务状态 ==="
    
    # 检查 API
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        log "✅ API 服务运行中: http://localhost:8080"
    else
        warn "❌ API 服务未运行: http://localhost:8080"
    fi
    
    # 检查 WebUI
    if curl -sf http://localhost:7860 > /dev/null 2>&1; then
        log "✅ WebUI 运行中: http://localhost:7860"
    else
        warn "❌ WebUI 未运行: http://localhost:7860"
    fi
    
    # 检查 Docker 容器
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q fish-speech; then
        log "✅ Docker 容器运行中"
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|fish-speech'
    fi
}

case "$MODE" in
    --help|-h)
        print_help
        ;;
    --pip)
        setup_pip
        ;;
    --docker)
        setup_docker
        ;;
    --docker-cpu)
        setup_docker
        ;;
    --status)
        check_status
        ;;
    *)
        print_help
        exit 1
        ;;
esac
