#!/bin/zsh
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$LAB_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

printf "[stable-audio3-lab] lab dir: %s\n" "$LAB_DIR"
printf "[stable-audio3-lab] python: %s\n" "$PYTHON_BIN"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN"
  echo "Tip: brew install python@3.11"
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchaudio huggingface_hub transformers accelerate safetensors soundfile librosa numpy scipy

printf "[stable-audio3-lab] done. activate with: source %s/bin/activate\n" "$VENV_DIR"
