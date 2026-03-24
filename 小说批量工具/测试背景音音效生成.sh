#!/bin/bash

# 测试背景音和音效生成功能

echo "=== 测试背景音和音效生成功能 ==="

# 创建测试目录
TEST_DIR="/Users/zhuxingchong/easyVoice-git/小说批量工具/audio/test"
BGM_DIR="$TEST_DIR/bgm"
SFX_DIR="$TEST_DIR/sfx"

mkdir -p "$BGM_DIR"
mkdir -p "$SFX_DIR"

echo "测试目录创建成功: $TEST_DIR"
echo "背景音目录: $BGM_DIR"
echo "音效目录: $SFX_DIR"

# 测试背景音生成
echo "\n=== 测试背景音生成 ==="

# 测试不同类型的背景音
bgm_types=("peaceful" "mysterious" "tense" "battle" "sad" "solemn")

for bgm_type in "${bgm_types[@]}"; do
  bgm_file="$BGM_DIR/${bgm_type}.mp3"
  echo "生成背景音: $bgm_type"
  echo "输出文件: $bgm_file"
  
  # 使用ffmpeg生成背景音
  case "$bgm_type" in
    "peaceful")
      ffmpeg -f lavfi -i "sine=frequency=800:duration=10" -f lavfi -i "sine=frequency=1200:duration=10" -filter_complex "[0:a]volume=0.1[a0];[1:a]volume=0.05[a1];[a0][a1]mix=inputs=2:weights=0.6 0.4" -y "$bgm_file"
      ;;
    "mysterious")
      ffmpeg -f lavfi -i "sine=frequency=400:duration=10" -f lavfi -i "sine=frequency=600:duration=10" -filter_complex "[0:a]volume=0.08[a0];[1:a]volume=0.03[a1];[a0][a1]mix=inputs=2:weights=0.7 0.3" -y "$bgm_file"
      ;;
    "tense")
      ffmpeg -f lavfi -i "sine=frequency=200:duration=10" -filter_complex "[0:a]volume=0.12,tremolo=f=4:d=0.5" -y "$bgm_file"
      ;;
    "battle")
      ffmpeg -f lavfi -i "sine=frequency=100:duration=10" -filter_complex "[0:a]volume=0.15,tremolo=f=8:d=0.8" -y "$bgm_file"
      ;;
    "sad")
      ffmpeg -f lavfi -i "sine=frequency=200:duration=10" -filter_complex "[0:a]volume=0.06,lowpass=f=800" -y "$bgm_file"
      ;;
    "solemn")
      ffmpeg -f lavfi -i "sine=frequency=150:duration=10" -filter_complex "[0:a]volume=0.09,lowpass=f=600" -y "$bgm_file"
      ;;
  esac
  
  if [ $? -eq 0 ] && [ -f "$bgm_file" ] && [ -s "$bgm_file" ]; then
    echo "✓ 背景音生成成功: $bgm_type"
    ls -lh "$bgm_file"
  else
    echo "✗ 背景音生成失败: $bgm_type"
  fi
done

# 测试音效生成
echo "\n=== 测试音效生成 ==="

# 测试不同类型的音效
sfx_types=("wind" "rain" "footsteps" "door_open" "sword_unsheathe" "fire")

for sfx_type in "${sfx_types[@]}"; do
  sfx_file="$SFX_DIR/${sfx_type}.mp3"
  echo "生成音效: $sfx_type"
  echo "输出文件: $sfx_file"
  
  # 使用ffmpeg生成音效
  case "$sfx_type" in
    "wind")
      ffmpeg -f lavfi -i "sine=frequency=400:duration=3" -filter_complex "[0:a]volume=0.05,tremolo=f=2:d=0.3" -y "$sfx_file"
      ;;
    "rain")
      ffmpeg -f lavfi -i "sine=frequency=600:duration=3" -filter_complex "[0:a]volume=0.03,tremolo=f=8:d=0.5" -y "$sfx_file"
      ;;
    "footsteps")
      ffmpeg -f lavfi -i "sine=frequency=800:duration=3" -filter_complex "[0:a]volume=0.1,tremolo=f=2:d=0.8" -y "$sfx_file"
      ;;
    "door_open")
      ffmpeg -f lavfi -i "sine=frequency=600:duration=3" -filter_complex "[0:a]volume=0.08,tremolo=f=1:d=0.5" -y "$sfx_file"
      ;;
    "sword_unsheathe")
      ffmpeg -f lavfi -i "sine=frequency=1000:duration=3" -filter_complex "[0:a]volume=0.12,tremolo=f=10:d=0.3" -y "$sfx_file"
      ;;
    "fire")
      ffmpeg -f lavfi -i "sine=frequency=300:duration=3" -filter_complex "[0:a]volume=0.06,tremolo=f=4:d=0.6" -y "$sfx_file"
      ;;
  esac
  
  if [ $? -eq 0 ] && [ -f "$sfx_file" ] && [ -s "$sfx_file" ]; then
    echo "✓ 音效生成成功: $sfx_type"
    ls -lh "$sfx_file"
  else
    echo "✗ 音效生成失败: $sfx_type"
  fi
done

echo "\n=== 测试完成 ==="
echo "测试结果:"
echo "背景音文件: $(ls -l "$BGM_DIR" | wc -l) 个文件"
echo "音效文件: $(ls -l "$SFX_DIR" | wc -l) 个文件"

echo "\n测试目录: $TEST_DIR"
echo "可以查看生成的音频文件来验证测试结果。"
