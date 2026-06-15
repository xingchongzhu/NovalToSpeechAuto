#!/bin/zsh
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MLX_DIR="$LAB_DIR/stable-audio-3/optimized/mlx"
OUT_DIR="$LAB_DIR/outputs"
LOG_DIR="$LAB_DIR/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

cd "$MLX_DIR"

./sa3 --prompt "ambient background music, calm and relaxing, soft piano, gentle rain, distant forest birds, no drums, no vocals, smooth loop, seamless transition, high fidelity stereo" \
  --dit sm-music --decoder same-s --seconds 20 --out "$OUT_DIR/sm_music_ambient_20s.wav" \
  > "$LOG_DIR/sm_music_ambient_20s.log" 2>&1

./sa3 --prompt "forest night ambience, distant insects, gentle wind through trees, subtle water drops, no music, no vocals, no sharp foreground sounds, smooth continuous ambience bed" \
  --dit sm-sfx --decoder same-s --seconds 20 --out "$OUT_DIR/sm_sfx_forest_20s.wav" \
  > "$LOG_DIR/sm_sfx_forest_20s.log" 2>&1

printf "verification done\n"
