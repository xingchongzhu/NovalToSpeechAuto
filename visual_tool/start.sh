#!/bin/bash
# Novel Audio Visual Tool - Start Script
# Usage: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  小说有声剧可视化工具"
echo "========================================"
echo ""

# Check Python
if ! python3 --version >/dev/null 2>&1; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

echo "Starting server..."
echo "Open: http://localhost:8088"
echo ""

python3 server.py
