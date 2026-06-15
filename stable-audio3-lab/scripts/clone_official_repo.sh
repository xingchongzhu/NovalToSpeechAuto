#!/bin/zsh
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLONE_DIR="$LAB_DIR/stable-audio-3"

if [ -d "$CLONE_DIR/.git" ]; then
  echo "Official repo already exists: $CLONE_DIR"
  exit 0
fi

git clone https://github.com/Stability-AI/stable-audio-3.git "$CLONE_DIR"
echo "Cloned to: $CLONE_DIR"
