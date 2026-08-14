#!/bin/bash
# ============================================================================
# run_sync.sh —— 收藏同步
# 调用 douyin-downloader/run.py，使用 venv python3.11（需要 playwright 等 venv 依赖）
# * 不设 PYTHONPATH（避免污染）
# * 不设旧 uv PATH（版本漂移源）
# * HOME 兜底（enclave 沙箱可能改写）
# ============================================================================
# HOME 兜底
if [ ! -d "$HOME/Desktop" ] && [ -n "${REAL_HOME:-}" ]; then
    HOME="$REAL_HOME"
    export HOME
fi

# sync 目录：优先环境变量 DOUYIN_SYNC_DIR，否则脚本所在目录（可移植，不硬编码本机路径）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_DIR="${DOUYIN_SYNC_DIR:-$SCRIPT_DIR}"
PY="${PYTHON:-$SYNC_DIR/venv/bin/python3}"
cd "$SYNC_DIR/douyin-downloader"
exec "$PY" run.py -c config.yml
