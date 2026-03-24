#!/bin/bash

# Novel Audio Synthesizer
# 小说语音自动合成工具，用于生成单个小说章节的配音、音效和背景音
# 支持自动混音拼接，生成完整的音频文件

# 环境检测（跳过conda环境检测，直接使用系统python3）
echo "=== 环境检测 ==="
echo "使用系统python3环境"

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 配置项（使用绝对路径）
AUDIO_BASE_DIR="$SCRIPT_DIR/../audio"
SCRIPT_BASE_DIR="$SCRIPT_DIR/../小说剧本"
# 默认TEMP_DIR，将在process_single_file函数中根据小说名称动态覆盖
TEMP_DIR="$SCRIPT_DIR/temp"
TEMP_OUTPUT="temp_output.mp3"
TEMP_WITH_BGM="temp_with_bgm.mp3"
API_ENDPOINT="http://localhost:3000/api/v1/tts/generateJson"

# 确保所有目录存在
mkdir -p "$TEMP_DIR"
mkdir -p "$AUDIO_BASE_DIR"

# 检查并启动服务
check_and_start_service() {
    # 检查是否有旧的Docker容器在运行
    if docker ps -a --filter "name=easyvoice" | grep -q "easyvoice"; then
      log_warning "发现旧的easyvoice容器，尝试停止并删除"
      docker stop easyvoice 2>/dev/null
      docker rm easyvoice 2>/dev/null
      sleep 2
    fi
    
    # 使用Docker启动服务
    log_info "使用Docker启动 easyVoice 服务..."
    # 创建音频目录
    mkdir -p "$SCRIPT_DIR/../audio"
    # 启动Docker容器
    if docker run -d --name easyvoice -p 3000:3000 -v "$SCRIPT_DIR/../audio:/app/audio" cosincox/easyvoice:latest >/dev/null 2>&1; then
      log_success "easyVoice 服务启动成功"
      return 0
    else
      log_error "服务启动失败，请检查Docker容器日志: docker logs easyvoice"
      return 1
    fi
}

# 音效和背景音目录配置 (现在每个小说目录下都有自己的bgm和sfx目录)

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
  echo "用法1: $0 <JSON文件路径>"
  echo "示例: $0 小说批量工具/小说剧本/剑来/剑来第一章-入山门青峰山.json"
  echo "用法2: $0"
  echo "示例: $0"
  echo "说明: 不指定参数时，将处理小说剧本目录下所有小说的JSON文件"
  echo "      已生成音频的文件将被跳过"
  echo "      脚本会自动检查并启动easyVoice服务"
}

# 主函数
main() {
  # 确保临时目录存在
  mkdir -p "$TEMP_DIR"
  
  # 检查并启动服务
  check_and_start_service
  if [ $? -ne 0 ]; then
    log_error "服务启动失败，无法继续执行"
    exit 1
  fi
  
  # 处理命令行参数
  if [ $# -eq 0 ]; then
    # 不指定参数时，处理所有小说的JSON文件
    process_all_novels
  elif [ $# -eq 1 ]; then
    # 指定参数时，处理单个JSON文件
    local json_file="$1"
    if [ -f "$json_file" ]; then
      process_novel "$json_file"
    else
      log_error "文件不存在: $json_file"
      show_help
      exit 1
    fi
  else
    # 参数错误
    log_error "参数错误"
    show_help
    exit 1
  fi
}

# 清理临时文件
cleanup_temp_files() {
  local keep_segments="$1"
  log_debug "清理临时文件..."
  rm -f "$TEMP_OUTPUT"
  rm -f "${TEMP_OUTPUT%.mp3}.srt"
  rm -f "$TEMP_WITH_BGM"
  if [ -d "$TEMP_DIR" ]; then
    if [ "$keep_segments" != "keep" ]; then
      rm -rf "$TEMP_DIR"
      log_info "已清理临时片段文件目录: $TEMP_DIR"
    else
      log_info "保留临时片段文件在: $TEMP_DIR"
      # 使用更高效的方式计算文件数量
      local file_count=$(find "$TEMP_DIR" -type f | wc -l)
      log_info "临时片段文件目录包含: $file_count 个文件"
    fi
  else
    log_info "临时片段文件目录不存在: $TEMP_DIR"
  fi
}

# 下载文件函数
download_file() {
  local url="$1"
  local output_file="$2"
  local description="$3"
  
  log_info "正在下载${description}..."
  
  # 创建目录
  local dir=$(dirname "$output_file")
  mkdir -p "$dir"
  
  # 下载文件
  curl -L -o "$output_file" "$url"
  
  if [ $? -ne 0 ] || [ ! -s "$output_file" ] || [ $(stat -f%z "$output_file") -lt 10000 ]; then
    log_warning "${description}下载失败或文件过小，将跳过。"
    rm -f "$output_file"
    return 1
  else
    log_success "${description}下载成功。"
    return 0
  fi
}

# 生成背景音
generate_bgm() {
  local bgm_type="$1"
  local output_file="$2"
  local duration="$3"
  local prompt="$4"
  
  log_info "正在生成背景音: $bgm_type"
  
  # 创建目录
  local dir=$(dirname "$output_file")
  mkdir -p "$dir"
  log_debug "[背景音] 输出目录: $dir"
  log_debug "[背景音] 输出文件: $output_file"
  log_debug "[背景音] 时长: $duration 秒"
  log_debug "[背景音] 提示词: $prompt"

  # 如果没有获取到提示词，表示不用背景音
  if [ -z "$prompt" ]; then
    log_info "[背景音] 没有获取到提示词，表示没有背景音需要生成"
    return 1
  fi
  
  # 检查实际输出文件是否已经存在
  local actual_output_file="$output_file.wav"
  if [ -f "$actual_output_file" ] && [ -s "$actual_output_file" ]; then
    log_info "[背景音] 文件已存在，跳过生成: $actual_output_file"
    return 0
  fi
  
  # 调用magnet_test_tool.py工具生成背景音
  local magnet_script="$SCRIPT_DIR/../../AudioCraft/magnet_test_tool.py"
  if [ -f "$magnet_script" ]; then
    log_debug "[背景音] 使用magnet_test_tool.py工具生成背景音"
    log_info "[背景音] 生成音频可能需要几分钟时间，请耐心等待..."
    log_debug "[背景音] 正在启动音频生成进程..."
    
    # 将duration转换为整数，并限制最大为30秒（medium-30secs模型限制）
    local duration_int=$(echo "$duration" | awk '{print int($1+0.5)}')
    if [ "$duration_int" -gt 30 ]; then
      duration_int=10
      log_info "[背景音] 模型限制最大时长为30秒，已调整时长"
    fi
    
    # 运行生成音频的命令（使用完整的conda环境Python路径）
    /usr/bin/python3 "$magnet_script" "$prompt" \
      --type music \
      --duration "$duration_int" \
      --output-path "$output_file"
    
    # 检查结果 - magnet_test_tool.py会自动添加.wav扩展名
    local actual_output_file="$output_file.wav"
    if [ $? -eq 0 ] && [ -f "$actual_output_file" ] && [ -s "$actual_output_file" ]; then
      local file_size=$(stat -f%z "$actual_output_file" 2>/dev/null)
      log_success "背景音生成成功: $bgm_type"
      log_debug "[背景音] 生成的文件大小: $file_size 字节"
      log_debug "[背景音] 实际保存路径: $actual_output_file"
      return 0
    else
      log_error "背景音生成失败"
      return 1
    fi
  else
    log_error "generate_audio.py脚本未找到"
    return 1
  fi
}

# 智能分析对话内容，推荐合适的音效
analyze_dialog_for_sfx() {
  local dialog="$1"
  local recommended_sfx=()
  
  # 分析对话内容，推荐合适的音效
  # 使用更灵活的关键词匹配方式
  local sfx_patterns=(
    "风声:风|吹|凉|冷"
    "雨声:雨|淋|湿"
    "雷声:雷|鸣|闪电"
    "脚步声:走|行|跑|步"
    "开门声:门|开|关"
    "拔剑声:剑|拔|鞘"
    "自然环境音:自然|山|林|鸟"
    "人群声:人|群|吵|闹"
    "火焰声:火|烧|烤"
    "水声:水|流|河|海"
    "回声:回声|山谷|空旷"
    "庄重音效:庄重|严肃|仪式"
    "战斗音效:战斗|打斗|激烈|冲突"
    "神秘音效:神秘|奇幻|未知|探索"
    "悲伤音效:悲伤|难过|哭泣|失去"
    "紧张音效:紧张|危险|悬疑|恐怖"
    "欢快音效:快乐|高兴|笑声|欢乐"
    "魔法音效:魔法|咒语|法术"
    "金属碰撞声:金属|碰撞|敲击"
    "动物叫声:动物|兽|鸟|虫"
  )
  
  # 遍历所有音效模式
  for pattern in "${sfx_patterns[@]}"; do
    local sfx_name=$(echo "$pattern" | cut -d':' -f1)
    local keywords=$(echo "$pattern" | cut -d':' -f2)
    
    # 检查对话内容是否包含关键词
    if [[ "$dialog" =~ $keywords ]]; then
      recommended_sfx+=("$sfx_name")
    fi
  done
  
  echo "${recommended_sfx[@]}"
}

# 从小说剧本中提取音效描述并生成音效
generate_sfx_from_description() {
  local json_file="$1"
  local output_dir="$2"
  
  # 确保输出目录存在
  mkdir -p "$output_dir"
  
  # 从JSON文件中读取音效描述
  local sfx_description=$(jq -r '.sfx_config.description // ""' "$json_file" 2>/dev/null)
  local effects_config=$(jq -c '.sfx_config.effects // {}' "$json_file" 2>/dev/null)
  
  # 遍历所有段落，提取音效描述
  local paragraphs=$(jq -c '.data[]' "$json_file" 2>/dev/null)
  local paragraph_index=0
  
  while IFS= read -r paragraph; do
    paragraph_index=$((paragraph_index + 1))
    
    # 提取段落文本
    local text=$(echo "$paragraph" | jq -r '.text // ""' 2>/dev/null)
    
    # 提取剧本中指定的音效配置
    local sfx_list=$(echo "$paragraph" | jq -r '.sfx // []' 2>/dev/null)
    
    # 检查sfx_list是否为数组格式
    if [[ "$sfx_list" == "["*"]" ]]; then
      # 解析JSON数组
      local sfx_items=$(echo "$sfx_list" | jq -c '.[]' 2>/dev/null)
      
      # 为每个剧本中指定的音效生成文件
      while IFS= read -r sfx_item; do
        if [ -n "$sfx_item" ]; then
          # 检查sfx_item是否为对象格式
          if [[ "$sfx_item" == "{"*"}" ]]; then
            # 新格式：对象格式的音效配置
            local sfx_name=$(echo "$sfx_item" | jq -r '.name // ""' 2>/dev/null)
          else
            # 旧格式：字符串格式的音效名称
            local sfx_name="$sfx_item"
          fi
          
            if [ -n "$sfx_name" ]; then
              local sfx_file="$output_dir/${sfx_name}.mp3"
              local sfx_description_en=""
              local sfx_duration="3"
              
              # 从剧本中获取description_en和duration
              if [[ "$sfx_item" == "{"*"}" ]]; then
                sfx_description_en=$(echo "$sfx_item" | jq -r '.description_en // ""' 2>/dev/null)
                sfx_duration=$(echo "$sfx_item" | jq -r '.duration // "3"' 2>/dev/null)
              fi
  
              # 如果音效文件不存在，生成它
              if [ ! -f "$sfx_file" ]; then
                log_info "[音效] 为段落 $paragraph_index 生成音效: $sfx_name (基于剧本描述)"
                generate_scene_sfx "$sfx_file" "$sfx_duration" "$sfx_name" "$sfx_description_en"
              fi
            fi
        fi
      done < <(echo "$sfx_items")
    fi
  done < <(echo "$paragraphs")
  
  log_info "[音效] 从小说剧本中提取音效描述并生成音效完成"
}



# 基于场景生成音效
generate_scene_sfx() {
  local output_file="$1"
  local duration="$2"
  local sfx_type="$3"
  local prompt="$4"
  
  # 创建目录
  local dir=$(dirname "$output_file")
  mkdir -p "$dir"

  log_info "正在生成音效: $sfx_type"
  log_debug "[提示词] 提示词: $prompt"
  log_debug "[背景音] 输出文件: $dir"
  log_debug "[背景音] 时长: $duration 秒"
  
  # 如果没有获取到提示词，表示没有音效不用生成
  if [ -z "$prompt" ]; then
    log_info "[音效] 没有获取到提示词，表示没有音效需要生成"
    return 1
  fi
  
  # 检查实际输出文件是否已经存在
  local actual_output_file="$output_file.wav"
  if [ -f "$actual_output_file" ] && [ -s "$actual_output_file" ]; then
    log_info "[音效] 文件已存在，跳过生成: $actual_output_file"
    return 0
  fi
  
  # 调用magnet_test_tool.py工具生成音效
  local magnet_script="$SCRIPT_DIR/../../AudioCraft/magnet_test_tool.py"
  if [ -f "$magnet_script" ]; then
    log_debug "[音效] 使用magnet_test_tool.py工具生成音效"
    
    # 将duration转换为整数，并限制最大为10秒（模型限制）
    local duration_int=$(echo "$duration" | awk '{print int($1+0.5)}')
  
    
    # 运行生成音频的命令（使用完整的conda环境Python路径）
    /usr/bin/python3 "$magnet_script" "$prompt" \
      --type sound \
      --duration "$duration_int" \
      --output-path "$output_file"
    
    # 检查结果 - magnet_test_tool.py会自动添加.wav扩展名
    local actual_output_file="$output_file.wav"
    if [ $? -eq 0 ] && [ -f "$actual_output_file" ] && [ -s "$actual_output_file" ]; then
      log_success "场景音效生成成功"
      log_debug "[音效] 实际保存路径: $actual_output_file"
      return 0
    else
      log_error "音效生成失败"
      return 1
    fi
  else
    log_error "generate_audio.py脚本未找到"
    return 1
  fi
}

# 验证文件是否存在且有效
validate_file() {
  local file_path="$1"
  local file_type="$2"
  
  if [ -z "$file_path" ]; then
    log_info "[$file_type] 文件路径为空"
    return 1
  fi
  
  if [ ! -f "$file_path" ]; then
    log_info "[$file_type] 文件不存在或无效: $file_path"
    return 1
  fi
  
  if [ ! -s "$file_path" ]; then
    log_info "[$file_type] 文件为空: $file_path"
    return 1
  fi
  
  log_debug "[$file_type] 文件: $file_path"
  return 0
}

# 提取背景音处理结果
parse_bgm_result() {
  local bgm_result="$1"
  local bgm_file=""
  local bgm_volume=""
  
  # 只有当返回结果不为空时才提取
  if [ -n "$bgm_result" ]; then
    bgm_file=$(echo "$bgm_result" | awk '{print $1}')
    bgm_volume=$(echo "$bgm_result" | awk '{print $2}')
    
    # 显示提取的背景音信息
    log_debug "[背景音] 提取的背景音文件路径: '$bgm_file'"
    log_debug "[背景音] 提取的背景音音量: '$bgm_volume'"
  fi
  
  # 设置默认值，并确保音量足够大
  if [ -z "$bgm_volume" ]; then
    bgm_volume="0.8"
  else
    # 确保背景音音量至少为0.6
    if (( $(echo "$bgm_volume < 0.6" | bc -l) )); then
      bgm_volume="0.8"
    fi
  fi
  
  log_debug "调整后的背景音音量: $bgm_volume"
  
  echo "$bgm_file $bgm_volume"
}

# 提取音效处理结果
parse_sfx_result() {
  local sfx_result="$1"
  
  # 清理sfx_enabled值
  local sfx_enabled=$(echo "$sfx_result" | grep -E '^(true|false)$' | head -n 1)
  if [ -z "$sfx_enabled" ]; then
    sfx_enabled="false"
  fi
  
  log_debug "[音效] 启用状态: $sfx_enabled"
  echo "$sfx_enabled"
}

# 构建音频混合命令
build_mix_command() {
  local bgm_file="$1"
  local bgm_volume="$2"
  local sfx_enabled="$3"
  local json_file="$4"
  
  local ffmpeg_cmd="ffmpeg -y -i \"$TEMP_OUTPUT\""
  local filters="[0:a]volume=1.0[main]"
  local input_count=1
  local has_bgm=0
  local has_sfx=0
  local sfx_list=()
  local sfx_index=0
  
  # 添加背景音
  if [ -f "$bgm_file" ]; then
    ffmpeg_cmd="$ffmpeg_cmd -i \"$bgm_file\""
    filters="$filters [1:a]volume=$bgm_volume,apad[A];"
    input_count=$((input_count + 1))
    has_bgm=1
  fi
  
  # 添加音效
  if [ "$sfx_enabled" = "true" ]; then
    # 从文件路径中提取小说名
    local novel_dir=$(dirname "$json_file")
    local novel_name=$(basename "$novel_dir")
    local sfx_dir="$AUDIO_BASE_DIR/$novel_name/sfx"
    
    # 读取所有音效键到数组中
    local effect_names=()
    while IFS= read -r effect_name; do
      effect_names+=("$effect_name")
    done < <(jq -r '.sfx_config.effects | keys[]' "$json_file" 2>/dev/null)
    
    # 遍历所有音效
    for effect_name in "${effect_names[@]}"; do
      local effect_file="$sfx_dir/$effect_name.mp3"
      local effect_volume=$(jq -r ".sfx_config.effects.$effect_name.volume // \"0.1\"" "$json_file" 2>/dev/null)
      
      if [ -f "$effect_file" ]; then
          # 确保音效音量足够大
          if (( $(echo "$effect_volume < 0.6" | bc -l) )); then
            effect_volume="0.8"
          fi
          
          ffmpeg_cmd="$ffmpeg_cmd -i \"$effect_file\""
          filters="$filters [$input_count:a]volume=$effect_volume,trim=duration=3,apad[S$sfx_index];"
          sfx_list+=("S$sfx_index")
          input_count=$((input_count + 1))
          sfx_index=$((sfx_index + 1))
          has_sfx=1
        fi
    done
  fi
  
  # 只有当有背景音或音效时才执行混合
  if [ $has_bgm -eq 1 ] || [ $has_sfx -eq 1 ]; then
    # 构建混合部分
    local mix_part="[main]"
    if [ $has_bgm -eq 1 ]; then
      mix_part="$mix_part[A]"
    fi
    
    # 添加音效到混合部分
    for sfx in "${sfx_list[@]}"; do
      mix_part="$mix_part[$sfx]"
    done
    
    # 计算总输入数
    local total_inputs=1
    if [ $has_bgm -eq 1 ]; then
      total_inputs=$((total_inputs + 1))
    fi
    total_inputs=$((total_inputs + ${#sfx_list[@]}))
    
    # 完成滤镜链
    filters="$filters $mix_part amix=inputs=$total_inputs:duration=shortest,volume=1.0,afade=t=in:st=0:d=1.0,afade=t=out:st=10:d=2.0"
    
    # 执行ffmpeg命令
    eval "$ffmpeg_cmd -filter_complex \"$filters\" -c:a libmp3lame -q:a 4 \"$TEMP_WITH_BGM\"" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
      echo "$TEMP_WITH_BGM"
    else
      echo "$TEMP_OUTPUT"
    fi
  else
    echo "$TEMP_OUTPUT"
  fi
}

# 验证混合结果
validate_mix_result() {
  local mixed_file="$1"
  local original_file="$2"
  local mix_type="$3"
  
  log_info "[混合] 混合完成，最终文件: '$mixed_file'"
  log_debug "[混合] - 混合文件是否存在: $([ -f "$mixed_file" ] && echo "是" || echo "否")"
  
  if [ -f "$mixed_file" ]; then
    log_debug "[混合] - 混合文件大小: $(stat -f%z "$mixed_file" 2>/dev/null) 字节"
    return 0
  else
    # 检查temp_with_bgm.mp3文件是否存在
    if [ -f "$TEMP_WITH_BGM" ]; then
      log_debug "[混合] - temp_with_bgm.mp3 文件存在，大小: $(stat -f%z "$TEMP_WITH_BGM" 2>/dev/null) 字节"
      echo "$TEMP_WITH_BGM"
      return 0
    fi
    
    log_debug "[混合] 混合失败，使用原始文件"
    echo "$original_file"
    return 1
  fi
}

# 处理背景音配置 (支持章节和场景级配置)
process_bgm_config() {
  local json_file="$1"
  
  # 记录开始时间
  local start_time=$(date +%s)
  log_info "[背景音] 开始处理背景音配置: $(date '+%Y-%m-%d %H:%M:%S')"
  log_info "[背景音] JSON文件: $json_file"
  
  # 检查JSON文件是否存在
  if ! validate_file "$json_file" "背景音"; then
    log_error "[背景音] JSON文件不存在: $json_file"
    echo ""
    return
  fi
  
  # 从文件路径中提取小说名
  local novel_dir=$(dirname "$json_file")
  local novel_name=$(basename "$novel_dir")
  log_info "[背景音] 小说目录: $novel_dir"
  log_info "[背景音] 小说名称: $novel_name"
  
  # 设置当前小说的音频目录
  local novel_audio_dir="$AUDIO_BASE_DIR/$novel_name"
  local bgm_dir="$novel_audio_dir/bgm"
  log_info "[背景音] 小说音频目录: $novel_audio_dir"
  log_info "[背景音] 背景音目录: $bgm_dir"
  
  # 确保背景音目录存在
  mkdir -p "$bgm_dir"
  
  # 从JSON文件中读取背景音配置
  log_info "[背景音] 开始读取JSON配置..."
  local bgm_enabled=$(jq -r '.bgm_config.enabled // false' "$json_file" 2>&1)
  if [ $? -ne 0 ]; then
    log_error "[背景音] 读取bgm_enabled失败: $bgm_enabled"
    bgm_enabled="false"
  else
    log_info "[背景音] bgm_enabled: $bgm_enabled"
  fi
  
  local bgm_description=$(jq -r '.bgm_config.description // ""' "$json_file" 2>&1)
  if [ $? -ne 0 ]; then
    log_error "[背景音] 读取bgm_description失败: $bgm_description"
    bgm_description=""
  else
    log_info "[背景音] bgm_description: $bgm_description"
  fi
  
  local chapters=$(jq -c '.bgm_config.chapters // []' "$json_file" 2>&1)
  if [ $? -ne 0 ]; then
    log_error "[背景音] 读取chapters失败: $chapters"
    chapters="[]"
  else
    local chapter_count=$(echo "$chapters" | jq '. | length' 2>&1)
    if [ $? -ne 0 ]; then
      log_error "[背景音] 计算章节数量失败: $chapter_count"
      chapter_count=0
    else
      log_info "[背景音] 章节数量: $chapter_count"
    fi
  fi
  
  # 构建背景音文件路径
  local bgm_file=""
  local bgm_volume="0.15"
  
  # 检查并使用已存在的背景音文件
  if [ "$bgm_enabled" = "true" ]; then
    log_info "[背景音] 背景音已启用，开始处理..."
    
    # 检查是否有章节级配置
    local chapter_count=$(echo "$chapters" | jq '. | length' 2>/dev/null)
    if [ "$chapter_count" -gt 0 ]; then
      log_info "[背景音] 发现章节级背景音配置，共 $chapter_count 个章节"
      
      # 遍历章节
      local chapter_index=0
      while IFS= read -r chapter; do
        chapter_index=$((chapter_index + 1))
        log_info "[背景音] 处理章节 $chapter_index..."
        
        local chapter_id=$(echo "$chapter" | jq -r '.chapter_id // ""' 2>&1)
        if [ $? -ne 0 ]; then
          log_error "[背景音] 读取chapter_id失败: $chapter_id"
          chapter_id=""
        fi
        
        local chapter_name=$(echo "$chapter" | jq -r '.chapter_name // ""' 2>&1)
        if [ $? -ne 0 ]; then
          log_error "[背景音] 读取chapter_name失败: $chapter_name"
          chapter_name=""
        fi
        
        log_info "[背景音] 章节 $chapter_index: $chapter_name ($chapter_id)"
        
        local scenes=$(echo "$chapter" | jq -c '.scenes // []' 2>&1)
        if [ $? -ne 0 ]; then
          log_error "[背景音] 读取scenes失败: $scenes"
          scenes="[]"
        else
          local scene_count=$(echo "$scenes" | jq '. | length' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 计算场景数量失败: $scene_count"
            scene_count=0
          else
            log_info "[背景音] 场景数量: $scene_count"
          fi
        fi
        
        # 遍历场景
        local scene_index=0
        while IFS= read -r scene; do
          scene_index=$((scene_index + 1))
          log_info "[背景音] 处理场景 $scene_index..."
          
          local scene_id=$(echo "$scene" | jq -r '.scene_id // ""' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取scene_id失败: $scene_id"
            scene_id=""
          fi
          
          local scene_name=$(echo "$scene" | jq -r '.scene_name // ""' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取scene_name失败: $scene_name"
            scene_name=""
          fi
          
          local bgm_type=$(echo "$scene" | jq -r '.bgm_type // "peaceful"' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取bgm_type失败: $bgm_type"
            bgm_type="peaceful"
          fi
          
          local scene_description=$(echo "$scene" | jq -r '.scene_description // ""' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取scene_description失败: $scene_description"
            scene_description=""
          fi
          
          local bgm_scene_description=$(echo "$scene" | jq -r '.bgm_description // ""' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取bgm_description失败: $bgm_scene_description"
            bgm_scene_description=""
          fi
          
          local bgm_description_en=$(echo "$scene" | jq -r '.bgm_description_en // ""' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取bgm_description_en失败: $bgm_description_en"
            bgm_description_en=""
          fi
          
          # 解析背景音时长
          local duration=$(echo "$scene" | jq -r '.duration // "60"' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取duration失败: $duration"
            duration="60"
          fi
          
          log_info "[背景音] 背景音英文描述: $bgm_description_en"
          log_info "[背景音] 背景音时长: $duration 秒"
          
          local volume_config=$(echo "$scene" | jq -c '.volume // {}' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取volume失败: $volume_config"
            volume_config="{}"
          fi
          
          local default_volume=$(echo "$volume_config" | jq -r '.default // "0.4"' 2>&1)
          if [ $? -ne 0 ]; then
            log_error "[背景音] 读取default_volume失败: $default_volume"
            default_volume="0.4"
          fi
          
          log_info "[背景音] 场景 $scene_index: $scene_name ($scene_id)"
          log_info "[背景音] 背景音类型: $bgm_type"
          log_info "[背景音] 默认音量: $default_volume"
          
          # 构建背景音文件路径
          local scene_bgm_file="$bgm_dir/${bgm_type}.mp3"
          log_info "[背景音] 背景音文件路径: $scene_bgm_file"
          
          # 检查是否存在已下载的背景音文件
          if [ ! -f "$scene_bgm_file" ]; then
            # 生成背景音
            log_info "[背景音] 为场景 $scene_name 生成背景音: $bgm_type"
            log_info "[背景音] 开始调用generate_bgm函数..."
            generate_bgm "$bgm_type" "$scene_bgm_file" "$duration" "$bgm_description_en"
            if [ $? -ne 0 ]; then
              log_warning "[背景音] 背景音生成失败: $bgm_type"
            else
              log_info "[背景音] 背景音生成成功: $bgm_type.mp3"
            fi
          else
            log_info "[背景音] 使用已存在的背景音文件: $bgm_type.mp3"
          fi
          
          # 使用第一个场景的背景音作为默认背景音
          # 即使文件不存在，也设置bgm_file，以便返回一个合理的结果
          if [ -z "$bgm_file" ]; then
            bgm_file="$scene_bgm_file"
            bgm_volume="$default_volume"
            log_info "[背景音] 使用默认背景音: $bgm_type.mp3"
            log_info "[背景音] 默认背景音音量: $bgm_volume"
            if [ -f "$scene_bgm_file" ]; then
              log_info "[背景音] 背景音文件存在: $scene_bgm_file"
            else
              log_warning "[背景音] 背景音文件不存在: $scene_bgm_file，但仍使用此路径"
            fi
          fi
        done < <(echo "$scenes" | jq -c '.[]' 2>/dev/null)
      done < <(echo "$chapters" | jq -c '.[]' 2>/dev/null)
    else
      # 没有章节级背景音配置，设置为空
      log_info "[背景音] 没有章节级背景音配置，将跳过背景音。"
      bgm_file=""
      bgm_volume=""
    fi
    
    # 显示背景音配置信息
    if [ -n "$bgm_description" ]; then
      log_info "[背景音] 描述: $bgm_description"
    fi
    if [ -n "$bgm_file" ]; then
      log_info "[背景音] 音量设置: $bgm_volume"
    fi
  else
    log_info "[背景音] 已禁用或未配置"
    bgm_file=""
  fi
  
  # 记录结束时间
  local end_time=$(date +%s)
  local elapsed=$((end_time - start_time))
  log_info "[背景音] 背景音配置处理完成，耗时: $elapsed 秒"
  
  # 返回结果
  log_info "[背景音] 最终结果: bgm_file='$bgm_file', bgm_volume='$bgm_volume'"
  if [ -n "$bgm_file" ]; then
    log_info "[背景音] 返回结果: '$bgm_file $bgm_volume'"
    echo "$bgm_file $bgm_volume"
  else
    log_info "[背景音] 返回结果: ''"
    echo ""
  fi
}

# 处理音效配置 (支持详细的时间和音量控制)
process_sfx_config() {
  local json_file="$1"
  
  # 从文件路径中提取小说名
  local novel_dir=$(dirname "$json_file")
  local novel_name=$(basename "$novel_dir")
  
  # 设置当前小说的音频目录
  local novel_audio_dir="$AUDIO_BASE_DIR/$novel_name"
  local sfx_dir="$novel_audio_dir/sfx"
  
  # 从JSON文件中读取音效配置
  local sfx_enabled=$(jq -r '.sfx_config.enabled // false' "$json_file" 2>/dev/null)
  local sfx_description=$(jq -r '.sfx_config.description // ""' "$json_file" 2>/dev/null)
  local effects_config=$(jq -c '.sfx_config.effects // {}' "$json_file" 2>/dev/null)
  
  if [ "$sfx_enabled" = "true" ]; then
    log_info "[音效] 正在处理音效配置..."
    
    # 显示音效配置信息
    if [ -n "$sfx_description" ]; then
      log_info "[音效] 描述: $sfx_description"
    fi
    
    # 读取音效详情配置
    if [ -n "$effects_config" ] && [ "$effects_config" != "{}" ]; then
      log_info "[音效] 读取到音效配置详情"
      # 遍历所有音效配置
      local effect_names=$(echo "$effects_config" | jq -r 'keys[]' 2>/dev/null)
      while IFS= read -r effect_name; do
        local effect_desc=$(echo "$effects_config" | jq -r ".[$effect_name].description // \"\"" 2>/dev/null)
        local effect_desc_en=$(echo "$effects_config" | jq -r ".[$effect_name].description_en // \"\"" 2>/dev/null)
        local effect_vol=$(echo "$effects_config" | jq -r ".[$effect_name].volume // \"0.1\"" 2>/dev/null)
        local effect_duration=$(echo "$effects_config" | jq -r ".[$effect_name].duration // \"3.0\"" 2>/dev/null)
        local effect_fade_in=$(echo "$effects_config" | jq -r ".[$effect_name].fade_in // \"0.5\"" 2>/dev/null)
        local effect_fade_out=$(echo "$effects_config" | jq -r ".[$effect_name].fade_out // \"0.5\"" 2>/dev/null)
        if [ -n "$effect_name" ]; then
          log_info "[音效] $effect_name: $effect_desc (音量: $effect_vol, 时长: $effect_duration, 淡入: $effect_fade_in, 淡出: $effect_fade_out)"
          if [ -n "$effect_desc_en" ]; then
            log_info "[音效] $effect_name 英文描述: $effect_desc_en"
          fi
        fi
      done < <(echo "$effect_names")
    fi
    
    # 确保音效目录存在
    mkdir -p "$sfx_dir"
    
    # 从小说剧本中提取音效描述并生成音效
    generate_sfx_from_description "$json_file" "$sfx_dir"
    
    # 遍历所有段落，收集所有唯一的音效
    local unique_sfx=()
    local paragraphs=$(jq -c '.data[]' "$json_file" 2>/dev/null)
    local paragraph_index=0
    
    while IFS= read -r paragraph; do
      paragraph_index=$((paragraph_index + 1))
      
      # 提取段落文本
      local text=$(echo "$paragraph" | jq -r '.text // ""' 2>/dev/null)
      local paragraph_id=$(echo "$paragraph" | jq -r '.id // ""' 2>/dev/null)
      local scene_id=$(echo "$paragraph" | jq -r '.scene_id // ""' 2>/dev/null)
      
      # 提取现有的音效配置
      local sfx_list=$(echo "$paragraph" | jq -r '.sfx // []' 2>/dev/null)
      local existing_sfx=()
      
      if [ -n "$sfx_list" ] && [ "$sfx_list" != "[]" ]; then
        # 检查sfx_list是否为数组格式
        if [[ "$sfx_list" == "["*"]" ]]; then
          # 解析JSON数组
          local sfx_array=($(echo "$sfx_list" | jq -r '.[]' 2>/dev/null))
          
          # 为每个剧本中指定的音效生成文件
          for sfx_item in "${sfx_array[@]}"; do
            if [ -n "$sfx_item" ]; then
              # 检查sfx_item是否为对象格式
              if [[ "$sfx_item" == "{"*"}" ]]; then
                # 新格式：对象格式的音效配置
                local sfx_name=$(echo "$sfx_item" | jq -r '.name // ""' 2>/dev/null)
                local sfx_volume=$(echo "$sfx_item" | jq -r '.volume // "0.8"' 2>/dev/null)
                local sfx_start_time=$(echo "$sfx_item" | jq -r '.start_time // "0.0"' 2>/dev/null)
                local sfx_duration=$(echo "$sfx_item" | jq -r '.duration // "3.0"' 2>/dev/null)
                local sfx_fade_in=$(echo "$sfx_item" | jq -r '.fade_in // "0.5"' 2>/dev/null)
                local sfx_fade_out=$(echo "$sfx_item" | jq -r '.fade_out // "0.5"' 2>/dev/null)
                local sfx_description_en=$(echo "$sfx_item" | jq -r '.description_en // ""' 2>/dev/null)
                
                if [ -n "$sfx_name" ]; then
                  log_info "[音效] 段落 $paragraph_index ($paragraph_id) 配置音效: $sfx_name (音量: $sfx_volume, 开始时间: $sfx_start_time, 时长: $sfx_duration)"
                  existing_sfx+=($sfx_name)
                  # 检查音效是否已经添加到唯一列表
                  local exists=0
                  for sfx in "${unique_sfx[@]}"; do
                    if [ "$sfx" = "$sfx_name" ]; then
                      exists=1
                      break
                    fi
                  done
                  if [ $exists -eq 0 ]; then
                    unique_sfx+=($sfx_name)
                  fi
                fi
              fi
            fi
          done
        fi
      fi
      
      # 分析对话内容，推荐音效
      if [ -n "$text" ]; then
        local recommended_sfx=($(analyze_dialog_for_sfx "$text"))
        
        # 检查推荐的音效是否已经在现有配置中
        for sfx_name in "${recommended_sfx[@]}"; do
          local exists=0
          for existing in "${existing_sfx[@]}"; do
            if [ "$existing" = "$sfx_name" ]; then
              exists=1
              break
            fi
          done
          for sfx in "${unique_sfx[@]}"; do
            if [ "$sfx" = "$sfx_name" ]; then
              exists=1
              break
            fi
          done
          if [ $exists -eq 0 ]; then
            log_info "[音效] 段落 $paragraph_index ($paragraph_id) 推荐音效: $sfx_name (基于文本内容分析: '$text')"
            unique_sfx+=($sfx_name)
          fi
        done
      fi
    done < <(echo "$paragraphs")
    
    # 检查并使用已存在的音效文件
    for sfx_name in "${unique_sfx[@]}"; do
      # 构建音效文件路径
      local effect_file="$sfx_dir/$sfx_name.mp3"
      
      if [ -n "$sfx_name" ]; then
        if [ -f "$effect_file" ]; then
          log_info "[音效] 使用已存在的音效文件: $sfx_name.mp3"
        else
          log_warning "[音效] 未找到音效文件: $sfx_name.mp3，将跳过该音效"
        fi
      fi
    done
    
    # 检查段落中的音效配置
    local scene_sfx_count=0
    while IFS= read -r paragraph; do
      local sfx_list=$(echo "$paragraph" | jq -r '.sfx // []' 2>/dev/null)
      if [ -n "$sfx_list" ] && [ "$sfx_list" != "[]" ]; then
        scene_sfx_count=$((scene_sfx_count + 1))
      fi
    done < <(echo "$paragraphs")
    
    # 统计可用的音效文件数量
    local available_sfx_files=($(ls "$sfx_dir"/*.mp3 2>/dev/null))
    local available_count=${#available_sfx_files[@]}
    
    log_info "[音效] 检测到 $scene_sfx_count 个段落包含场景音效配置"
    log_info "[音效] 目录中共有 $available_count 个可用的音效文件"
  else
    log_info "[音效] 已禁用或未配置"
  fi
  
  echo "$sfx_enabled"
}

# 生成音频
generate_audio() {
  local json_file="$1"
  
  log_info "$json_file 正在生成音频，请稍候..."
  
  # 发送请求并保存响应
  curl -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$(cat "$json_file")" \
    -o "$TEMP_OUTPUT"
  
  # 检查生成是否成功
  if [ $? -eq 0 ] && [ -f "$TEMP_OUTPUT" ] && [ -s "$TEMP_OUTPUT" ]; then
    log_success "音频生成成功！"
    return 0
  else
    log_error "生成失败，请检查服务是否正常运行。"
    cleanup_temp_files "keep"
    return 1
  fi
}

# 混合背景音和音效 (传统方式)
mix_audio_traditional() {
  local bgm_file="$1"
  local bgm_volume="$2"
  local sfx_enabled="$3"
  local json_file="$4"
  local result="$TEMP_OUTPUT"
  
  # 构建ffmpeg命令
  local ffmpeg_cmd="ffmpeg -i \"$TEMP_OUTPUT\""
  local filters=""
  local input_count=1
  local sfx_index=0
  local sfx_list=()
  local has_bgm=0
  local has_sfx=0
  
  # 添加背景音
  if [ -f "$bgm_file" ]; then
    ffmpeg_cmd="$ffmpeg_cmd -i \"$bgm_file\""
    filters="$filters [1:a]volume=$bgm_volume,apad[A];"
    input_count=$((input_count + 1))
    has_bgm=1
  fi
  
  # 添加音效
  if [ "$sfx_enabled" = "true" ]; then
    # 从文件路径中提取小说名
    local novel_dir=$(dirname "$json_file")
    local novel_name=$(basename "$novel_dir")
    local sfx_dir="$AUDIO_BASE_DIR/$novel_name/sfx"
    
    # 读取所有音效键到数组中
    local effect_names=()
    while IFS= read -r effect_name; do
      effect_names+=("$effect_name")
    done < <(jq -r '.sfx_config.effects | keys[]' "$json_file" 2>/dev/null)
    
    # 遍历所有音效
    for effect_name in "${effect_names[@]}"; do
      local effect_file="$sfx_dir/$effect_name.mp3"
      local effect_volume=$(jq -r ".sfx_config.effects.$effect_name.volume // \"0.1\"" "$json_file" 2>/dev/null)
      
      if [ -f "$effect_file" ]; then
          # 确保音效音量足够大
          if (( $(echo "$effect_volume < 0.6" | bc -l) )); then
            effect_volume="0.8"
          fi
          
          ffmpeg_cmd="$ffmpeg_cmd -i \"$effect_file\""
          filters="$filters [$input_count:a]volume=$effect_volume,trim=duration=3,apad[S$sfx_index];"
          sfx_list+=("S$sfx_index")
          input_count=$((input_count + 1))
          sfx_index=$((sfx_index + 1))
          has_sfx=1
        fi
    done
  fi
  
  # 只有当有背景音或音效时才执行混合
  if [ $has_bgm -eq 1 ] || [ $has_sfx -eq 1 ]; then
    # 构建混合部分
    local mix_part="[0:a]"
    if [ $has_bgm -eq 1 ]; then
      mix_part="$mix_part[A]"
    fi
    
    # 添加音效到混合部分
    for sfx in "${sfx_list[@]}"; do
      mix_part="$mix_part[$sfx]"
    done
    
    # 计算总输入数
    local total_inputs=1
    if [ $has_bgm -eq 1 ]; then
      total_inputs=$((total_inputs + 1))
    fi
    total_inputs=$((total_inputs + ${#sfx_list[@]}))
    
    # 完成滤镜链
    # 使用duration=shortest确保所有音频都能完整播放，而不是只播放第一个结束的音频
    # 添加主音量控制和最终的淡入淡出效果
    filters="$filters $mix_part amix=inputs=$total_inputs:duration=shortest,volume=1.0,afade=t=in:st=0:d=1.0,afade=t=out:st=10:d=2.0"
    
    # 执行ffmpeg命令，将输出重定向到/dev/null
    eval "$ffmpeg_cmd -filter_complex \"$filters\" -c:a libmp3lame -q:a 4 \"$TEMP_WITH_BGM\"" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
      result="$TEMP_WITH_BGM"
    fi
  fi
  
  # 只返回纯净的文件路径
  echo "$result"
}

# 混合背景音和音效 (基于字幕的段落混合)
mix_audio_with_subtitles() {
  local bgm_file="$1"
  local bgm_volume="$2"
  local sfx_enabled="$3"
  local json_file="$4"
  local result="$TEMP_OUTPUT"
  
  # 创建临时目录
  mkdir -p "$TEMP_DIR"
  
  # 读取JSON文件中的段落信息
  log_info "[混合] 开始读取JSON文件中的段落信息..."
  local paragraphs=$(jq -c '.data[]' "$json_file" 2>&1)
  log_info "[混合] 读取段落信息完成"
  
  # 构建一个包含每个段落时间的文件
  local timestamp_file="$TEMP_DIR/timestamps.txt"
  echo "" > "$timestamp_file"
  log_info "[混合] 已创建时间戳文件: $timestamp_file"
  
  # 检查是否有字幕文件
  local subtitle_file="${TEMP_OUTPUT%.mp3}.srt"
  log_info "[混合] 检查字幕文件: $subtitle_file"
  if [ -f "$subtitle_file" ]; then
    log_info "[混合] 存在字幕文件，基于字幕分割"
    # 解析SRT文件，提取时间戳
    while IFS= read -r line; do
      if [[ $line == *"-->*" ]]; then
        # 提取开始时间
        local start_time=$(echo "$line" | cut -d' ' -f1 | sed 's/,/./')
        # 提取结束时间
        local end_time=$(echo "$line" | cut -d' ' -f3 | sed 's/,/./')
        echo "$start_time $end_time" >> "$timestamp_file"
      fi
    done < "$subtitle_file"
  else
    log_info "[混合] 无字幕文件，基于平均时长分割"
    # 如果没有字幕文件，基于平均时长生成时间戳
    local total_duration=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$TEMP_OUTPUT")
    local paragraph_count=$(echo "$paragraphs" | wc -l)
    
    log_info "[混合] 总时长: $total_duration, 段落数: $paragraph_count"
    
    if [ "$paragraph_count" -gt 0 ] && [ -n "$total_duration" ]; then
      local avg_duration=$(echo "$total_duration / $paragraph_count" | bc -l)
      log_info "[混合] 平均每段时长: $avg_duration"
      
      local current_time=0
      local para_index=0
      while IFS= read -r paragraph && [ $para_index -lt 50 ]; do  # 添加安全限制，最多处理50个段落
        para_index=$((para_index + 1))
        local end_time=$(echo "$current_time + $avg_duration" | bc -l)
        # 确保结束时间不超过总时长
        if (( $(echo "$end_time > $total_duration" | bc -l) )); then
          end_time=$total_duration
        fi
        echo "$current_time $end_time" >> "$timestamp_file"
        log_info "[混合] 段落 $para_index 时间戳: $current_time -> $end_time"
        current_time=$end_time
      done < <(echo "$paragraphs")
    else
      log_error "[混合] 无法生成时间戳: 段落数为0或总时长未知"
    fi
  fi
  
  # 检查时间戳文件
  local timestamp_count=$(wc -l < "$timestamp_file" 2>/dev/null)
  log_info "[混合] 生成 $timestamp_count 个时间戳"
  log_info "[混合] 时间戳文件内容:"
  cat "$timestamp_file" 2>/dev/null
  
  # 分割原始音频
  local segment_file="$TEMP_DIR/segments.txt"
  echo "" > "$segment_file"
  log_info "[混合] 已创建segments文件: $segment_file"
  local line_num=0
  while IFS= read -r line; do
    if [[ -n "$line" ]]; then
      line_num=$((line_num + 1))
      local start_time=$(echo "$line" | cut -d' ' -f1)
      local end_time=$(echo "$line" | cut -d' ' -f2)
      echo "file '$TEMP_OUTPUT'" >> "$segment_file"
      echo "inpoint $start_time" >> "$segment_file"
      echo "outpoint $end_time" >> "$segment_file"
      log_info "[混合] 添加段落 $line_num 到segments文件: $start_time -> $end_time"
    fi
  done < "$timestamp_file"
  
  # 检查segments文件
  log_info "[混合] segments文件内容:"
  cat "$segment_file" 2>/dev/null
  
  # 检查segments文件
  log_debug "[混合] segments文件内容:"
  log_debug "$(cat "$segment_file" 2>/dev/null)"
  
  # 使用ffmpeg分割音频
  log_info "[混合] 开始分割音频..."
  # 不使用-c copy，因为可能会导致分割失败
  ffmpeg -f concat -safe 0 -i "$segment_file" -c:a libmp3lame -q:a 4 "$TEMP_DIR/segment_%03d.mp3" 2>&1
  
  # 检查分割结果
  local segment_count=$(ls "$TEMP_DIR/segment_*.mp3" 2>/dev/null | wc -l)
  log_info "[混合] 第一次分割完成，找到 $segment_count 个片段"
  
  # 如果分割失败，尝试使用另一种方法
  if [ "$segment_count" -eq 0 ]; then
    # 使用ffmpeg的segment滤镜直接分割
    log_info "[混合] 第一次分割失败，尝试使用另一种方法..."
    ffmpeg -i "$TEMP_OUTPUT" -f segment -segment_time $avg_duration -c:a libmp3lame -q:a 4 "$TEMP_DIR/segment_%03d.mp3" 2>&1
    
    # 再次检查
    segment_count=$(find "$TEMP_DIR" -name "segment_*.mp3" -type f | wc -l)
    log_info "[混合] 第二次分割完成，找到 $segment_count 个片段"
  fi
  
  # 为每个段落混合音效
  if [ "$segment_count" -gt 0 ]; then
    # 遍历每个段落
    local index=0
    local total_paragraphs=$(echo "$paragraphs" | wc -l)
    
    log_info "[混合] 总段落数: $total_paragraphs"
    
    # 直接遍历paragraphs变量，因为它已经是由jq生成的每行一个JSON对象的格式
    while IFS= read -r paragraph && [ $index -lt 50 ]; do  # 添加安全限制，最多处理50个段落
      index=$((index + 1))
      local segment_file="$TEMP_DIR/segment_$(printf "%03d" $index).mp3"
      
      # 即使segment_file不存在，也要为该段落生成output_segment文件
      if [ -f "$segment_file" ]; then
        log_info "[混合] 段落 $index: 找到分割片段文件: $segment_file"
      else
        log_warning "[混合] 段落 $index: 未找到分割片段文件，使用原始音频作为替代"
        # 使用原始音频作为替代
        cp "$TEMP_OUTPUT" "$segment_file"
      fi
      
      # 提取段落信息
      local paragraph_id=$(echo "$paragraph" | jq -r '.id // ""' 2>/dev/null)
      local text=$(echo "$paragraph" | jq -r '.text // ""' 2>/dev/null)
      local scene_id=$(echo "$paragraph" | jq -r '.scene_id // ""' 2>/dev/null)
      local type=$(echo "$paragraph" | jq -r '.type // "narrative"' 2>/dev/null)
      
      # 提取该段落的背景音配置
      local paragraph_bgm=$(echo "$paragraph" | jq -c '.bgm // {}' 2>/dev/null)
      local paragraph_bgm_type=$(echo "$paragraph_bgm" | jq -r '.type // ""' 2>/dev/null)
      local paragraph_bgm_volume=$(echo "$paragraph_bgm" | jq -r '.volume // ""' 2>/dev/null)
      local paragraph_bgm_fade_in=$(echo "$paragraph_bgm" | jq -r '.fade_in // "1.0"' 2>/dev/null)
      local paragraph_bgm_fade_out=$(echo "$paragraph_bgm" | jq -r '.fade_out // "1.0"' 2>/dev/null)
      
      # 提取该段落的音效配置
      local sfx_list=$(echo "$paragraph" | jq -r '.sfx // []' 2>/dev/null)
      
      # 获取语音片段时长
      local segment_duration=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$segment_file" 2>/dev/null)
      if [ -z "$segment_duration" ]; then
        segment_duration=5
      fi
      log_info "[混合] 段落 $index ($paragraph_id): 语音时长: ${segment_duration}秒"
      
      # 构建ffmpeg命令
      local segment_ffmpeg_cmd="ffmpeg -i \"$segment_file\""
      local segment_input_count=1
      local has_bgm=0
      local has_sfx=0
      local filters=""
      
      # 添加背景音
      if [ -f "$bgm_file" ]; then
        # 确定背景音音量
        local current_bgm_volume="$bgm_volume"
        if [ -n "$paragraph_bgm_volume" ]; then
          current_bgm_volume="$paragraph_bgm_volume"
        elif [ -n "$type" ]; then
          # 根据段落类型调整背景音音量
          local type_volume=$(jq -r ".bgm_config.chapters[0].scenes[] | select(.scene_id == \"$scene_id\") | .volume.$type // .volume.default" "$json_file" 2>/dev/null)
          if [ -n "$type_volume" ]; then
            current_bgm_volume="$type_volume"
          fi
        fi
        
        # 确定淡入淡出时间
        local fade_in="$paragraph_bgm_fade_in"
        local fade_out="$paragraph_bgm_fade_out"
        
        segment_ffmpeg_cmd="$segment_ffmpeg_cmd -i \"$bgm_file\""
        # 应用背景音音量控制和渐变
        filters="$filters [1:a]volume=$current_bgm_volume,afade=t=in:st=0:d=$fade_in,afade=t=out:st=$(echo "$segment_duration - $fade_out" | bc):d=$fade_out [bgm];"
        segment_input_count=$((segment_input_count + 1))
        has_bgm=1
        log_info "[混合] 段落 $index ($paragraph_id): 添加背景音，音量: $current_bgm_volume, 淡入: $fade_in, 淡出: $fade_out"
      fi
      
      # 添加该段落的音效
      if [ -n "$sfx_list" ] && [ "$sfx_list" != "[]" ]; then
        # 从文件路径中提取小说名
        local novel_dir=$(dirname "$json_file")
        local novel_name=$(basename "$novel_dir")
        local sfx_dir="$AUDIO_BASE_DIR/$novel_name/sfx"
        
        # 遍历该段落的音效
        local sfx_items=$(echo "$sfx_list" | jq -c '.[]' 2>/dev/null)
        
        while IFS= read -r sfx_item; do
          if [ -n "$sfx_item" ]; then
            # 检查sfx_item是否为对象格式
            if [[ "$sfx_item" == "{"*"}" ]]; then
              # 新格式：对象格式的音效配置
              local sfx_name=$(echo "$sfx_item" | jq -r '.name // ""' 2>/dev/null)
              local sfx_volume=$(echo "$sfx_item" | jq -r '.volume // "0.8"' 2>/dev/null)
              local sfx_start_time=$(echo "$sfx_item" | jq -r '.start_time // "0.0"' 2>/dev/null)
              local sfx_duration=$(echo "$sfx_item" | jq -r '.duration // "3.0"' 2>/dev/null)
              local sfx_fade_in=$(echo "$sfx_item" | jq -r '.fade_in // "0.5"' 2>/dev/null)
              local sfx_fade_out=$(echo "$sfx_item" | jq -r '.fade_out // "0.5"' 2>/dev/null)
              local sfx_description_en=$(echo "$sfx_item" | jq -r '.description_en // ""' 2>/dev/null)
              
              if [ -n "$sfx_name" ]; then
                # 构建音效文件路径
                local effect_file="$sfx_dir/$sfx_name.mp3"
                
                # 检查音效文件是否存在
                if [ -f "$effect_file" ]; then
                  # 显示音效信息
                  log_info "[混合] 段落 $index ($paragraph_id): 添加音效: $sfx_name, 文件: $effect_file, 音量: $sfx_volume, 开始时间: $sfx_start_time, 时长: $sfx_duration"
                  # 添加音效文件（带音量控制和渐变）
                  segment_ffmpeg_cmd="$segment_ffmpeg_cmd -i \"$effect_file\""
                  # 应用音效音量控制、时间偏移和渐变
                  filters="$filters [$segment_input_count:a]volume=$sfx_volume,trim=duration=$sfx_duration,afade=t=in:st=0:d=$sfx_fade_in,afade=t=out:st=$(echo "$sfx_duration - $sfx_fade_out" | bc):d=$sfx_fade_out,adelay=${sfx_start_time}s|${sfx_start_time}s [sfx$segment_input_count];"
                  segment_input_count=$((segment_input_count + 1))
                  has_sfx=1
                else
                  # 尝试基于场景上下文生成音效
                  local temp_effect_file="$sfx_dir/${sfx_name}_temp.mp3"
                  log_info "[混合] 段落 $index ($paragraph_id): 未找到指定音效: $sfx_name.mp3，基于场景生成"
                  # 生成场景音效
                  generate_scene_sfx "$temp_effect_file" "$sfx_duration" "$sfx_name" "$sfx_description_en"
                  if [ $? -eq 0 ] && [ -f "$temp_effect_file" ]; then
                    # 生成成功，使用生成的音效
                    log_info "[混合] 段落 $index ($paragraph_id): 场景音效生成成功，使用生成的音效: $temp_effect_file"
                    segment_ffmpeg_cmd="$segment_ffmpeg_cmd -i \"$temp_effect_file\""
                    # 应用音量控制、时间偏移和渐变
                    filters="$filters [$segment_input_count:a]volume=$sfx_volume,trim=duration=$sfx_duration,afade=t=in:st=0:d=$sfx_fade_in,afade=t=out:st=$(echo "$sfx_duration - $sfx_fade_out" | bc):d=$sfx_fade_out,adelay=${sfx_start_time}s|${sfx_start_time}s [sfx$segment_input_count];"
                    segment_input_count=$((segment_input_count + 1))
                    has_sfx=1
                  else
                    # 尝试查找目录中的其他音效文件
                    local existing_sfx_files=($(ls "$sfx_dir"/*.mp3 2>/dev/null))
                    if [ ${#existing_sfx_files[@]} -gt 0 ]; then
                      # 使用第一个找到的音效文件作为替代
                      local fallback_effect_file="${existing_sfx_files[0]}"
                      log_info "[混合] 段落 $index ($paragraph_id): 使用替代音效: $(basename "$fallback_effect_file"), 音量: $sfx_volume"
                      segment_ffmpeg_cmd="$segment_ffmpeg_cmd -i \"$fallback_effect_file\""
                      # 应用替代音效音量控制、时间偏移和渐变
                      filters="$filters [$segment_input_count:a]volume=$sfx_volume,trim=duration=$sfx_duration,afade=t=in:st=0:d=$sfx_fade_in,afade=t=out:st=$(echo "$sfx_duration - $sfx_fade_out" | bc):d=$sfx_fade_out,adelay=${sfx_start_time}s|${sfx_start_time}s [sfx$segment_input_count];"
                      segment_input_count=$((segment_input_count + 1))
                      has_sfx=1
                    else
                      log_warning "[混合] 段落 $index ($paragraph_id): 未找到音效文件，将跳过该音效: $sfx_name"
                    fi
                  fi
                fi
              fi
            fi
          fi
        done < <(echo "$sfx_items")
      fi
      
      # 定义输出文件路径
      local output_segment="$TEMP_DIR/output_segment_$(printf "%03d" $index).mp3"
      
      # 构建混合部分
      local mix_part="[0:a]"
      local actual_inputs=1
      
      if [ $has_bgm -eq 1 ]; then
        mix_part="$mix_part[bgm]"
        actual_inputs=$((actual_inputs + 1))
      fi
      
      # 添加音效到混合部分
      if [ $has_sfx -eq 1 ]; then
        local sfx_count=0
        for ((i=1; i<$segment_input_count; i++)); do
          if [ -n "$(echo "$filters" | grep "sfx$i")" ]; then
            mix_part="$mix_part[sfx$i]"
            sfx_count=$((sfx_count + 1))
          fi
        done
        actual_inputs=$((actual_inputs + sfx_count))
      fi
      
      log_info "[混合] 段落 $index: 实际输入数量: $actual_inputs"
      log_info "[混合] 段落 $index: 混合部分: $mix_part"
      
      # 完成滤镜链
      if [ -n "$filters" ]; then
        # 当有音效时，确保在mix_part中包含它们
        if [ $has_sfx -eq 1 ] && [ $has_bgm -eq 0 ]; then
          # 只有音效，没有背景音
          mix_part="[0:a]"
          for ((i=1; i<$segment_input_count; i++)); do
            mix_part="$mix_part[sfx$i]"
          done
        fi
        # 添加主音量控制和最终的淡入淡出效果
        filters="$filters $mix_part amix=inputs=$actual_inputs:duration=shortest,volume=1.0"
        # 只有当segment_duration有效时才添加淡入淡出效果
        if [ -n "$segment_duration" ] && (( $(echo "$segment_duration > 1" | bc -l) )); then
          filters="$filters,afade=t=in:st=0:d=0.5,afade=t=out:st=$(echo "$segment_duration - 0.5" | bc):d=0.5"
        fi
      else
        filters="amix=inputs=1:duration=shortest,volume=1.0"
        # 只有当segment_duration有效时才添加淡入淡出效果
        if [ -n "$segment_duration" ] && (( $(echo "$segment_duration > 1" | bc -l) )); then
          filters="$filters,afade=t=in:st=0:d=0.5,afade=t=out:st=$(echo "$segment_duration - 0.5" | bc):d=0.5"
        fi
      fi
      
      # 只有当有背景音或音效时才执行混合操作
      if [ $has_bgm -eq 1 ] || [ $has_sfx -eq 1 ]; then
        log_info "[混合] 段落 $index: 执行音频混合"
        # 构建ffmpeg命令
        log_info "[混合] 段落 $index: 执行ffmpeg命令"
        log_info "[混合] 命令: $segment_ffmpeg_cmd -filter_complex \"$filters\" -c:a libmp3lame -q:a 4 \"$output_segment\""
        
        # 执行命令并捕获错误信息
        log_info "[混合] 段落 $index: 开始执行ffmpeg命令"
        # 先删除旧的输出文件
        rm -f "$output_segment"
        # 执行ffmpeg命令
        # 使用eval来执行命令，确保路径正确解析
        eval "$segment_ffmpeg_cmd -filter_complex \"$filters\" -c:a libmp3lame -q:a 4 \"$output_segment\""
        
        if [ $? -eq 0 ]; then
          # 检查输出文件是否存在且不为空
          if [ -f "$output_segment" ] && [ -s "$output_segment" ]; then
            log_info "[混合] 段落 $index: 混合成功，输出文件大小: $(stat -f%z "$output_segment") 字节"
            # 检查原始文件大小
            local orig_size=$(stat -f%z "$segment_file" 2>/dev/null)
            log_info "[混合] 段落 $index: 原始文件大小: $orig_size 字节"
          else
            log_error "[混合] 段落 $index: 混合命令执行成功，但输出文件不存在或为空"
            # 复制原始片段
            cp "$segment_file" "$output_segment"
            log_info "[混合] 段落 $index: 已复制原始片段到输出文件"
          fi
        else
          log_error "[混合] 段落 $index: 混合失败"
          # 失败时复制原始片段
          cp "$segment_file" "$output_segment"
          log_info "[混合] 段落 $index: 已复制原始片段到输出文件"
        fi
      else
        # 如果没有背景音和音效，直接复制原始片段
        log_info "[混合] 段落 $index: 无背景音和音效，直接复制原始片段"
        cp "$segment_file" "$output_segment"
        if [ $? -ne 0 ]; then
          log_error "[混合] 段落 $index: 复制原始片段失败，尝试使用另一种方式"
          # 尝试使用cat命令复制
          cat "$segment_file" > "$output_segment"
          if [ $? -ne 0 ]; then
            log_error "[混合] 段落 $index: 无法生成output_segment文件"
          else
            log_info "[混合] 段落 $index: 使用cat命令复制成功"
          fi
        fi
      fi
    done < <(echo "$paragraphs")
    
    # 拼接所有处理后的片段
    local concat_list="$TEMP_DIR/concat_list.txt"
    echo "" > "$concat_list"
    local output_segments=0
    
    # 按照实际生成的片段数量处理，确保所有片段都被添加
    local max_segments=100  # 设置一个合理的上限
    for ((i=1; i<=$max_segments; i++)); do
      local file="$TEMP_DIR/output_segment_$(printf "%03d" $i).mp3"
      if [ -f "$file" ] && [ -s "$file" ]; then
        # 使用绝对路径
        local abs_path=$(realpath "$file")
        echo "file '$abs_path'" >> "$concat_list"
        output_segments=$((output_segments + 1))
        log_info "[混合] 添加片段到拼接列表: $file"
      else
        # 如果连续5个文件都不存在，就停止循环
        if [ $i -gt 5 ]; then
          local missing_count=0
          for ((j=i-4; j<=$i; j++)); do
            local check_file="$TEMP_DIR/output_segment_$(printf "%03d" $j).mp3"
            if [ ! -f "$check_file" ] || [ ! -s "$check_file" ]; then
              missing_count=$((missing_count + 1))
            fi
          done
          if [ $missing_count -ge 5 ]; then
            log_info "[混合] 连续5个片段文件不存在，停止循环"
            break
          fi
        fi
      fi
    done
    
    if [ -s "$concat_list" ]; then
      # 执行片段拼接
      log_info "[混合] 执行片段拼接，共 $output_segments 个片段"
      # 显示拼接命令
      log_debug "[混合] 拼接命令: ffmpeg -f concat -safe 0 -i \"$concat_list\" -c:a libmp3lame -q:a 4 \"$TEMP_WITH_BGM\""
      # 执行拼接并显示输出
      ffmpeg -f concat -safe 0 -i "$concat_list" -c:a libmp3lame -q:a 4 "$TEMP_WITH_BGM" 2>&1
      
      if [ $? -eq 0 ] && [ -f "$TEMP_WITH_BGM" ] && [ -s "$TEMP_WITH_BGM" ]; then
        log_info "[混合] 片段拼接成功，生成文件: $TEMP_WITH_BGM"
        log_info "[混合] 拼接后文件大小: $(stat -f%z "$TEMP_WITH_BGM" 2>/dev/null) 字节"
        result="$TEMP_WITH_BGM"
      else
        log_error "[混合] 片段拼接失败"
        # 尝试备选方案：直接使用第一个处理后的片段
        local first_segment=$(ls "$TEMP_DIR/output_segment_"*.mp3 2>/dev/null | head -n 1)
        if [ -f "$first_segment" ]; then
          log_info "[混合] 使用第一个处理后的片段作为备选方案: $first_segment"
          cp "$first_segment" "$TEMP_WITH_BGM"
          result="$TEMP_WITH_BGM"
        else
          log_error "[混合] 没有可用的处理后片段，使用原始音频"
          result="$TEMP_OUTPUT"
        fi
      fi
    else
      log_error "[混合] 没有可拼接的片段文件，使用原始音频"
      result="$TEMP_OUTPUT"
    fi
  else
    # 如果分割音频失败，使用改进的传统方式混合音效
    # 直接基于段落信息混合音效，不依赖分割
    local temp_output="$TEMP_DIR/combined.mp3"
    
    # 构建ffmpeg命令
    local ffmpeg_cmd="ffmpeg -i \"$TEMP_OUTPUT\""
    local filters=""
    local input_count=1
    local has_bgm=0
    
    # 添加背景音
    if [ -f "$bgm_file" ]; then
      ffmpeg_cmd="$ffmpeg_cmd -i \"$bgm_file\""
      filters="$filters [1:a]volume=$bgm_volume,apad[A];"
      input_count=$((input_count + 1))
      has_bgm=1
    fi
    
    # 构建混合部分
    local mix_part="[0:a]"
    if [ $has_bgm -eq 1 ]; then
      mix_part="$mix_part[A]"
    fi
    
    # 执行ffmpeg命令混合背景音
    if [ $has_bgm -eq 1 ]; then
      filters="$filters $mix_part amix=inputs=$((has_bgm + 1)):duration=shortest"
      eval "$ffmpeg_cmd -filter_complex \"$filters\" -c:a libmp3lame -q:a 4 \"$temp_output\"" > /dev/null 2>&1
      
      if [ $? -eq 0 ]; then
        # 现在处理场景音效
        # 由于无法分割音频，我们将为整个音频添加所有可能的音效
        # 这不是理想的解决方案，但至少能确保音效被添加
        local final_output="$TEMP_WITH_BGM"
        local sfx_ffmpeg_cmd="ffmpeg -i \"$temp_output\""
        local sfx_filters=""
        local sfx_input_count=1
        local sfx_index=0
        
        # 从文件路径中提取小说名
        local novel_dir=$(dirname "$json_file")
        local novel_name=$(basename "$novel_dir")
        local sfx_dir="$AUDIO_BASE_DIR/$novel_name/sfx"
        
        # 遍历所有段落，收集所有唯一的音效
        local unique_sfx=()
        while IFS= read -r paragraph; do
          local sfx_list=$(echo "$paragraph" | jq -r '.sfx // []' 2>/dev/null)
          if [ -n "$sfx_list" ] && [ "$sfx_list" != "[]" ]; then
            while IFS= read -r sfx_name; do
              # 检查音效是否已经添加
              local exists=0
              for sfx in "${unique_sfx[@]}"; do
                if [ "$sfx" = "$sfx_name" ]; then
                  exists=1
                  break
                fi
              done
              if [ $exists -eq 0 ]; then
                unique_sfx+=("$sfx_name")
              fi
            done < <(echo "$sfx_list" | jq -r '.[]' 2>/dev/null)
          fi
        done < <(echo "$paragraphs")
        
        # 添加所有唯一的音效
        for sfx_name in "${unique_sfx[@]}"; do
          local effect_file="$sfx_dir/$sfx_name.mp3"
          local effect_volume=$(jq -r ".sfx_config.effects.$sfx_name.volume // \"0.1\"" "$json_file" 2>/dev/null)
          
          if [ -f "$effect_file" ]; then
            # 确保音效音量足够大
          if (( $(echo "$effect_volume < 0.6" | bc -l) )); then
            effect_volume="0.8"
          fi
          
          sfx_ffmpeg_cmd="$sfx_ffmpeg_cmd -i \"$effect_file\""
          sfx_filters="$sfx_filters [$sfx_input_count:a]volume=$effect_volume,apad[S$sfx_index];"
          sfx_input_count=$((sfx_input_count + 1))
          sfx_index=$((sfx_index + 1))
          fi
        done
        
        # 构建混合部分
        local sfx_mix_part="[0:a]"
        for ((i=0; i<${#unique_sfx[@]}; i++)); do
          sfx_mix_part="$sfx_mix_part[S$i]"
        done
        
        # 完成滤镜链
        if [ ${#unique_sfx[@]} -gt 0 ]; then
          sfx_filters="$sfx_filters $sfx_mix_part amix=inputs=$sfx_input_count:duration=shortest"
          eval "$sfx_ffmpeg_cmd -filter_complex \"$sfx_filters\" -c:a libmp3lame -q:a 4 \"$final_output\"" > /dev/null 2>&1
          
          if [ $? -eq 0 ]; then
            result="$final_output"
          else
            result="$temp_output"
          fi
        else
          result="$temp_output"
        fi
      else
        result="$TEMP_OUTPUT"
      fi
    else
      result="$TEMP_OUTPUT"
    fi
  fi
  
  # 清理临时目录 (保留片段文件)
  # rm -rf "$TEMP_DIR"
  
  # 只返回纯净的文件路径
  echo "$result"
}

# 处理单个JSON文件
process_single_file() {
  local json_file="$1"
  local custom_api_endpoint="$2"
  
  # 如果提供了自定义API端点，则使用它
  if [ -n "$custom_api_endpoint" ]; then
    API_ENDPOINT="$custom_api_endpoint"
  fi
  
  # 检查JSON文件是否存在
  if [ ! -f "$json_file" ]; then
    log_error "错误: JSON文件不存在: $json_file"
    return 1
  fi
  
  # 从文件路径中提取小说名和章节名
  local novel_dir=$(dirname "$json_file")
  local novel_name=$(basename "$novel_dir")
  local json_basename=$(basename "$json_file" .json)
  
  # 设置当前小说的音频目录和临时目录
  local raw_audio_dir="$AUDIO_BASE_DIR/$novel_name/原始音频"
  local processed_audio_dir="$AUDIO_BASE_DIR/$novel_name/合成音频"
  local TEMP_DIR="$AUDIO_BASE_DIR/$novel_name/$json_basename/temp_audio_segments"
  local TEMP_OUTPUT="$TEMP_DIR/temp_output.mp3"
  local TEMP_WITH_BGM="$TEMP_DIR/temp_with_bgm.mp3"
  
  # 创建输出目录和临时目录
  mkdir -p "$raw_audio_dir"
  mkdir -p "$processed_audio_dir"
  mkdir -p "$TEMP_DIR"
  

  

  
  # 根据JSON文件名生成输出文件名
  local json_basename=$(basename "$json_file" .json)
  local timestamp=$(date +"%Y%m%d_%H%M%S")
  local raw_output_filename="${json_basename}_原始.mp3"
  local processed_output_filename="${json_basename}_合成_$timestamp.mp3"
  local raw_output_path="$raw_audio_dir/$raw_output_filename"
  local processed_output_path="$processed_audio_dir/$processed_output_filename"
  
  # 清理旧的临时文件，但保留片段文件
  cleanup_temp_files "keep"
  

  
  # 检查原始音频文件是否已存在
  if [ -f "$raw_output_path" ]; then
    log_info "原始音频文件已存在，跳过生成: $raw_output_filename"
    # 检查合成音频文件是否已存在
    if [ -f "$processed_output_path" ]; then
      log_info "合成音频文件已存在，跳过生成: $processed_output_filename"
      return 0
    fi
    
    # 使用已存在的原始音频文件
    cp "$raw_output_path" "$TEMP_OUTPUT"
    log_info "已复制原始音频文件到临时位置"
    
    # 复制字幕文件（如果存在）
    local existing_subtitle="$raw_audio_dir/${raw_output_filename%.mp3}.srt"
    if [ -f "$existing_subtitle" ]; then
      cp "$existing_subtitle" "${TEMP_OUTPUT%.mp3}.srt"
      log_info "已复制字幕文件到临时位置"
    fi
  else
    # 生成音频
    generate_audio "$json_file"
    if [ $? -ne 0 ]; then
      return 1
    fi
    
    # 保存生成的音频到原始音频目录
    cp "$TEMP_OUTPUT" "$raw_output_path"
    log_info "原始音频已保存到: $raw_output_path"
  fi
  
  # 处理背景音配置
  log_info "[背景音] 开始处理背景音配置"
  # 执行process_bgm_config并捕获输出，同时显示所有日志
  local bgm_result
  process_bgm_config "$json_file"
  #bgm_result=$(process_bgm_config "$json_file" 2>&1 | tail -n 1)
  log_info "[背景音] 背景音配置结果: '$bgm_result'"
  
  # 提取背景音文件路径和音量
  local bgm_file=""
  local bgm_volume=""
  
  # 只有当返回结果不为空时才提取
  if [ -n "$bgm_result" ]; then
    bgm_file=$(echo "$bgm_result" | awk '{print $1}')
    bgm_volume=$(echo "$bgm_result" | awk '{print $2}')
  fi
  
  # 显示提取的背景音信息
  log_info "[背景音] 提取的背景音文件路径: '$bgm_file'"
  log_info "[背景音] 提取的背景音音量: '$bgm_volume'"
  
  # 设置默认值，并确保音量足够大
  if [ -z "$bgm_volume" ]; then
    bgm_volume="0.8"
  else
    # 确保背景音音量至少为0.6
    if (( $(echo "$bgm_volume < 0.6" | bc -l) )); then
      bgm_volume="0.8"
    fi
  fi
  
  log_info "调整后的背景音音量: $bgm_volume"
  
  # 处理音效配置
  local sfx_enabled=$(process_sfx_config "$json_file")
  
  # 清理sfx_enabled值
  sfx_enabled=$(echo "$sfx_enabled" | grep -E '^(true|false)$' | head -n 1)
  if [ -z "$sfx_enabled" ]; then
    sfx_enabled="false"
  fi
  
  # 验证背景音文件
  if [ -n "$bgm_file" ]; then
    if validate_file "$bgm_file" "背景音"; then
      log_info "[背景音] 音量: $bgm_volume"
    else
      bgm_file=""
    fi
  fi
  
  log_info "[音效] 启用状态: $sfx_enabled"
  
  # 混合背景音和音效
  local final_file="$TEMP_OUTPUT"
  if [ -n "$bgm_file" ] || [ "$sfx_enabled" = "true" ]; then
    # 检查是否有字幕文件
    local subtitle_file="${TEMP_OUTPUT%.mp3}.srt"
    log_info "[混合] 字幕文件存在: $([ -f "$subtitle_file" ] && echo "是" || echo "否")"
    
    # 使用基于字幕的段落混合方式，这样可以根据JSON文件中的段落信息来播放场景音效
    log_info "[混合] 使用基于字幕的段落混合方式"
    
    # 显示混合前的信息
    log_info "[混合] 混合前的信息:"
    log_info "[混合] - 背景音文件: $bgm_file"
    log_info "[混合] - 背景音音量: $bgm_volume"
    log_info "[混合] - 音效启用: $sfx_enabled"
    
    # 调用混合函数
    final_file=$(mix_audio_with_subtitles "$bgm_file" "$bgm_volume" "$sfx_enabled" "$json_file")
    
    # 清理final_file值，移除可能的多余字符
    final_file=$(echo "$final_file" | tr -d ' ' | tr -d '\n' | tr -d '\r')
    
    # 显示混合后的信息
    log_info "[混合] 混合完成，最终文件: '$final_file'"
    log_info "[混合] - 混合文件是否存在: $([ -f "$final_file" ] && echo "是" || echo "否")"
    if [ -f "$final_file" ]; then
      log_info "[混合] - 混合文件大小: $(stat -f%z "$final_file") 字节"
    else
      # 检查temp_with_bgm.mp3文件是否存在
      if [ -f "$TEMP_WITH_BGM" ]; then
        log_info "[混合] - temp_with_bgm.mp3 文件存在，大小: $(stat -f%z "$TEMP_WITH_BGM") 字节"
        final_file="$TEMP_WITH_BGM"
      fi
    fi
    
    # 验证混合结果，如果混合后的文件与原始文件相同，尝试使用传统混合方式
    if [ "$final_file" = "$TEMP_OUTPUT" ] && ([ -n "$bgm_file" ] || [ "$sfx_enabled" = "true" ]); then
      log_info "[混合] 尝试使用传统混合方式添加背景音和音效"
      local traditional_mixed=$(mix_audio_traditional "$bgm_file" "$bgm_volume" "$sfx_enabled" "$json_file")
      if [ "$traditional_mixed" != "$TEMP_OUTPUT" ] && [ -f "$traditional_mixed" ]; then
        log_info "[混合] 传统混合方式成功，使用传统混合结果"
        final_file="$traditional_mixed"
      fi
    fi
  else
    log_info "[混合] 没有背景音和音效需要混合"
  fi
  
  # 确保合成音频目录存在
  mkdir -p "$processed_audio_dir"
  
  # 保存final_file的当前值
  local current_final_file="$final_file"
  
  # 移动合成后的音频到合成音频目录
  if [ -f "$current_final_file" ]; then
    mv "$current_final_file" "$processed_audio_dir/$processed_output_filename"
    log_success "[混合] 合成音频已保存到: $processed_audio_dir/$processed_output_filename"
  else
    # 如果final_file不存在，检查TEMP_WITH_BGM是否存在
    if [ -f "$TEMP_WITH_BGM" ]; then
      log_info "[混合] final_file不存在，使用TEMP_WITH_BGM"
      mv "$TEMP_WITH_BGM" "$processed_audio_dir/$processed_output_filename"
      log_success "[混合] 合成音频已保存到: $processed_audio_dir/$processed_output_filename"
    elif [ -f "$TEMP_OUTPUT" ]; then
      log_info "[混合] final_file和TEMP_WITH_BGM都不存在，使用TEMP_OUTPUT"
      mv "$TEMP_OUTPUT" "$processed_audio_dir/$processed_output_filename"
      log_success "[混合] 合成音频已保存到: $processed_audio_dir/$processed_output_filename"
    else
      log_error "[混合] 所有临时文件都不存在，无法保存合成音频"
    fi
  fi
  
  # 验证最终合成音频文件
  local final_saved_file="$processed_audio_dir/$processed_output_filename"
  if [ -f "$final_saved_file" ]; then
    local file_size=$(stat -f%z "$final_saved_file" 2>/dev/null)
    log_info "[混合] 最终合成音频文件大小: $file_size 字节"
    if [ -n "$file_size" ] && [ "$file_size" -gt 0 ]; then
      log_success "[混合] 合成音频生成成功，文件大小: $file_size 字节"
    else
      log_warning "[混合] 合成音频文件存在但可能为空，大小: $file_size 字节"
    fi
  else
    log_error "[混合] 合成音频文件未生成: $final_saved_file"
  fi
  
  # 移动原始音频到原始音频目录（仅当是新生成的音频时）
  if [ ! -f "$raw_output_path" ] && [ -f "$TEMP_OUTPUT" ]; then
    mv "$TEMP_OUTPUT" "$raw_audio_dir/$raw_output_filename"
    log_success "原始音频已保存到: $raw_audio_dir/$raw_output_filename"
  fi
  
  # 处理字幕文件（如果存在）
  local subtitle_file="${TEMP_OUTPUT%.mp3}.srt"
  if [ -f "$subtitle_file" ]; then
    # 移动原始字幕文件到原始音频目录（仅当是新生成的音频时）
    if [ ! -f "$raw_audio_dir/${raw_output_filename%.mp3}.srt" ]; then
      mv "$subtitle_file" "$raw_audio_dir/${raw_output_filename%.mp3}.srt"
      log_info "原始字幕文件也已生成并移动到原始音频目录。"
    else
      # 如果原始字幕文件已存在，删除临时字幕文件
      rm -f "$subtitle_file"
    fi
    
    # 复制字幕文件到合成音频目录
    if [ -f "$raw_audio_dir/${raw_output_filename%.mp3}.srt" ]; then
      cp "$raw_audio_dir/${raw_output_filename%.mp3}.srt" "$processed_audio_dir/${processed_output_filename%.mp3}.srt"
      log_info "字幕文件已复制到合成音频目录。"
    fi
  fi
  
  log_success "合成音频已保存到: $processed_audio_dir/$processed_output_filename"
  
  # 清理临时文件，但保留片段文件
  cleanup_temp_files "keep"
  
  return 0
}

# 处理所有小说的JSON文件
process_all_files() {
  log_info "正在处理小说剧本目录下所有小说的JSON文件..."
  
  # 遍历小说剧本目录下的所有小说子目录
  for novel_dir in "$SCRIPT_BASE_DIR"/*; do
    if [ -d "$novel_dir" ]; then
      local novel_name=$(basename "$novel_dir")
      log_info "\n正在处理小说: $novel_name"
      
      # 遍历当前小说目录中的所有JSON文件
      for json_file in "$novel_dir"/*.json; do
        if [ -f "$json_file" ]; then
          log_info "\n正在处理: $(basename "$json_file")"
          process_single_file "$json_file"
        fi
      done
    fi
  done
  
  log_success "\n所有文件处理完成！"
}

# 主函数
main() {
  # 检查命令行参数
  if [ $# -eq 0 ]; then
    # 处理所有小说的JSON文件
    process_all_files
  elif [ $# -eq 1 ]; then
    # 处理单个JSON文件
    process_single_file "$1"
  elif [ $# -eq 2 ]; then
    # 处理单个JSON文件并使用自定义API端点
    process_single_file "$1" "$2"
  else
    log_error "错误: 参数过多，请检查命令行参数"
    echo "用法: $0 [JSON_FILE] [API_ENDPOINT]"
    exit 1
  fi
}

# 检查依赖
check_dependencies() {
  local missing=0
  
  if ! command -v jq &> /dev/null; then
    log_error "错误: jq 命令未找到，请安装 jq。"
    missing=1
  fi
  
  if ! command -v ffmpeg &> /dev/null; then
    log_error "错误: ffmpeg 命令未找到，请安装 ffmpeg。"
    missing=1
  fi
  
  if ! command -v curl &> /dev/null; then
    log_error "错误: curl 命令未找到，请安装 curl。"
    missing=1
  fi
  
  return $missing
}

# 更新JSON文件，为每个段落添加role和audio_notes字段


# 显示帮助信息
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  show_help
  exit 0
fi

# 检查依赖
check_dependencies
if [ $? -ne 0 ]; then
  exit 1
fi

# 确保临时目录存在
mkdir -p "$TEMP_DIR"

# 检查并启动服务
check_and_start_service
if [ $? -ne 0 ]; then
  log_error "服务启动失败，无法继续执行"
  exit 1
fi

# 执行主函数
main "$@"

# 退出状态
exit $?
