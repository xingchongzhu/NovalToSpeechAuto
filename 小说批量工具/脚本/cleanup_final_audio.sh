#!/bin/bash
# ============================================================
# 清理脚本：删除每个章节下合成的最终音频文件和标题缓存文件
#   - 删除章节根目录的 .mp3 文件（最终合成的有声书音频）
#   - 删除章节根目录的 chunk_title_*.wav 文件（标题语音缓存）
#   - 保留 配音/、音效/、混音/、背景音/ 等子目录中的音频
#
# 用法: bash cleanup_final_audio.sh
# ============================================================
set -euo pipefail

OUTPUT_DIR="output/蜀山剑侠传json稿"

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误: 目录 $OUTPUT_DIR 不存在"
    exit 1
fi

echo "开始清理最终合成音频文件..."

# 1. 删除每个章节根目录下的 .mp3 最终合成音频（maxdepth 2 确保不深入子目录）
MP3_COUNT=$(find "$OUTPUT_DIR" -maxdepth 2 -name "*.mp3" -type f | wc -l | tr -d ' ')
if [ "$MP3_COUNT" -gt 0 ]; then
    find "$OUTPUT_DIR" -maxdepth 2 -name "*.mp3" -type f -delete
    echo "  已删除 ${MP3_COUNT} 个 .mp3 文件"
else
    echo "  没有找到 .mp3 文件，跳过"
fi

# 2. 删除每个章节根目录下的 chunk_title_*.wav 标题缓存
CHUNK_COUNT=$(find "$OUTPUT_DIR" -maxdepth 2 -name "chunk_title_*.wav" -type f | wc -l | tr -d ' ')
if [ "$CHUNK_COUNT" -gt 0 ]; then
    find "$OUTPUT_DIR" -maxdepth 2 -name "chunk_title_*.wav" -type f -delete
    echo "  已删除 ${CHUNK_COUNT} 个 chunk_title_*.wav 文件"
else
    echo "  没有找到 chunk_title_*.wav 文件，跳过"
fi

# 3. 验证子目录音频未被误删
VOICE_COUNT=$(find "$OUTPUT_DIR" -path "*/配音/*" -type f 2>/dev/null | wc -l | tr -d ' ')
EFFECT_COUNT=$(find "$OUTPUT_DIR" -path "*/音效/*" -type f 2>/dev/null | wc -l | tr -d ' ')
MIX_COUNT=$(find "$OUTPUT_DIR" -path "*/混音/*" -type f 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "清理完成！子目录状态:"
echo "  配音/ : ${VOICE_COUNT} 个文件"
echo "  音效/ : ${EFFECT_COUNT} 个文件"
echo "  混音/ : ${MIX_COUNT} 个文件"
