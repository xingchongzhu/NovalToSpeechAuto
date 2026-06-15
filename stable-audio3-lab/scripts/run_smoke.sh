#!/bin/zsh
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$LAB_DIR/.venv/bin/activate"
python "$LAB_DIR/scripts/run_probe.py" "$@"
