#!/bin/bash

# Novel Batch Generator
# 结合audio_processing_module.py和novel_audio_synthesizer.sh的功能
# 自动解析小说剧本目录下的所有剧本文件，生成小说配音+音效+背景音，并完成自动混音拼接

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 配置项（使用绝对路径）
SCRIPT_BASE_DIR="$SCRIPT_DIR/../小说剧本"
# 统一输出目录到项目根目录
OUTPUT_BASE_DIR="$SCRIPT_DIR/../../output"
# 统一临时目录到项目根目录的output下
TEMP_BASE_DIR="$OUTPUT_BASE_DIR/temp"
API_ENDPOINT="http://localhost:3000/api/v1/tts/generateJson"
# 默认TTS引擎
TTS_ENGINE="qwen3-tts"

# 确保所有目录存在
mkdir -p "$TEMP_BASE_DIR"
mkdir -p "$OUTPUT_BASE_DIR"

# 日志级别: 0=静默, 1=正常, 2=详细
LOG_LEVEL=1

# 颜色定义
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

# 日志函数
log_info() {
  if [ -n "$LOG_LEVEL" ] && [ "$LOG_LEVEL" -ge 1 ]; then
    echo -e "${BLUE}INFO:${NC} $1"
  fi
}

log_success() {
  if [ -n "$LOG_LEVEL" ] && [ "$LOG_LEVEL" -ge 1 ]; then
    echo -e "${GREEN}SUCCESS:${NC} $1"
  fi
}

log_warning() {
  if [ -n "$LOG_LEVEL" ] && [ "$LOG_LEVEL" -ge 1 ]; then
    echo -e "${YELLOW}WARNING:${NC} $1"
  fi
}

log_error() {
  if [ -z "$LOG_LEVEL" ] || [ "$LOG_LEVEL" -ge 0 ]; then
    echo -e "${RED}ERROR:${NC} $1"
  fi
}

log_debug() {
  if [ -n "$LOG_LEVEL" ] && [ "$LOG_LEVEL" -ge 2 ]; then
    echo -e "${BLUE}DEBUG:${NC} $1"
  fi
}

# 显示帮助信息
show_help() {
  echo "小说批量生成工具"
  echo ""
  echo "用法: $0 [选项]"
  echo ""
  echo "选项:"
  echo "  --script-dir <目录>  指定小说剧本目录 (默认: $SCRIPT_BASE_DIR)"
  echo "  --output-dir <目录>  指定输出目录 (默认: $OUTPUT_BASE_DIR)"
  echo "  --temp-dir <目录>    指定临时目录 (默认: $TEMP_BASE_DIR)"
  echo "  --api-endpoint <URL> 指定API端点 (默认: $API_ENDPOINT)"
  echo "  --keep-segments      保留临时片段文件"
  echo "  --debug              启用调试模式"
  echo "  -h, --help           显示帮助信息"
  echo ""
  echo "示例:"
  echo "  $0"
  echo "  $0 --script-dir /path/to/scripts --output-dir /path/to/output"
  echo "  $0 --debug --keep-segments"
}

# 检查Python依赖
check_python_deps() {
  log_info "检查Python依赖..."
  
  # 检查Python是否安装
  if ! python3 --version >/dev/null 2>&1; then
    log_error "Python 3 未安装，请先安装Python 3"
    return 1
  fi
  
  # 检查pydub是否安装
  if ! python3 -c "import pydub" >/dev/null 2>&1; then
    log_warning "未安装pydub，正在安装..."
    pip3 install pydub ffmpeg-python
    if [ $? -ne 0 ]; then
      log_error "安装pydub失败，请手动安装: pip3 install pydub ffmpeg-python"
      return 1
    fi
  fi
  
  # 检查jq是否安装（用于JSON解析）
  if ! jq --version >/dev/null 2>&1; then
    log_warning "未安装jq，正在安装..."
    if [ "$(uname)" = "Darwin" ]; then
      # macOS
      brew install jq
    elif [ -f /etc/debian_version ]; then
      # Debian/Ubuntu
      sudo apt-get update && sudo apt-get install -y jq
    elif [ -f /etc/redhat-release ]; then
      # RHEL/CentOS
      sudo yum install -y jq
    else
      log_error "未安装jq，请手动安装jq工具"
      return 1
    fi
    
    if [ $? -ne 0 ]; then
      log_error "安装jq失败，请手动安装jq工具"
      return 1
    fi
  fi
  
  # 检查ffmpeg是否安装
  if ! ffmpeg -version >/dev/null 2>&1; then
    log_warning "未安装ffmpeg，正在安装..."
    if [ "$(uname)" = "Darwin" ]; then
      # macOS
      brew install ffmpeg
    elif [ -f /etc/debian_version ]; then
      # Debian/Ubuntu
      sudo apt-get update && sudo apt-get install -y ffmpeg
    elif [ -f /etc/redhat-release ]; then
      # RHEL/CentOS
      sudo yum install -y ffmpeg
    else
      log_error "未安装ffmpeg，请手动安装ffmpeg工具"
      return 1
    fi
    
    if [ $? -ne 0 ]; then
      log_error "安装ffmpeg失败，请手动安装ffmpeg工具"
      return 1
    fi
  fi
  
  # 检查Docker是否安装（只有当使用easyvoice时需要）
  if [ "$TTS_ENGINE" = "easyvoice" ]; then
    if ! docker --version >/dev/null 2>&1; then
      log_error "Docker 未安装，请先安装Docker"
      return 1
    fi
    
    # 检查Docker是否正在运行
    if ! docker info >/dev/null 2>&1; then
      log_error "Docker 未运行，请先启动Docker"
      return 1
    fi
  fi
  
  log_success "所有依赖检查通过"
  return 0
}

# 主函数
main() {
  # 解析命令行参数
  local script_dir="$SCRIPT_BASE_DIR"
  local output_dir="$OUTPUT_BASE_DIR"
  local temp_dir="$TEMP_BASE_DIR"
  local api_endpoint="$API_ENDPOINT"
  local tts_engine="$TTS_ENGINE"
  local keep_segments=""
  local debug=""
  
  while [ $# -gt 0 ]; do
    case "$1" in
      --script-dir)
        script_dir="$2"
        shift 2
        ;;
      --output-dir)
        output_dir="$2"
        shift 2
        ;;
      --temp-dir)
        temp_dir="$2"
        shift 2
        ;;
      --api-endpoint)
        api_endpoint="$2"
        shift 2
        ;;
      --keep-segments)
        keep_segments="--keep-segments"
        shift 1
        ;;
      --tts-engine)
        tts_engine="$2"
        shift 2
        ;;
      --debug)
        debug="--debug"
        LOG_LEVEL=2
        shift 1
        ;;
      -h|--help)
        show_help
        exit 0
        ;;
      *)
        log_error "未知参数: $1"
        show_help
        exit 1
        ;;
    esac
  done
  
  # 确保目录存在
  mkdir -p "$script_dir"
  mkdir -p "$output_dir"
  mkdir -p "$temp_dir"
  
  # 检查依赖
  check_python_deps
  if [ $? -ne 0 ]; then
    log_error "依赖检查失败，无法继续执行"
    exit 1
  fi
  
  # 执行Python脚本
  log_info "启动小说自动批量生成工具..."
  log_info "小说剧本目录: $script_dir"
  log_info "输出目录: $output_dir"
  log_info "临时目录: $temp_dir"
  
  python3 "$SCRIPT_DIR/novel_batch_executor.py" \
    --script-dir "$script_dir" \
    --output-dir "$output_dir" \
    --temp-dir "$temp_dir" \
    --api-endpoint "$api_endpoint" \
    --tts-engine "$tts_engine" \
    $keep_segments \
    $debug
  
  local exit_code=$?
  
  if [ $exit_code -eq 0 ]; then
    log_success "小说自动批量生成工具执行完成"
  else
    log_error "小说自动批量生成工具执行失败，退出码: $exit_code"
  fi
  
  return $exit_code
}

# 执行主函数
main "$@"