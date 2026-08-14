#!/bin/bash
# ============================================================================
# run_sync.sh —— 收藏同步
# 调用 douyin-downloader/run.py，使用 venv python3（需要 playwright 等 venv 依赖）
# * 不设 PYTHONPATH（避免污染）
# * 不设旧 uv PATH（版本漂移源）
# * 工作目录可用 DOUYIN_SYNC_DIR 环境变量覆盖
# ============================================================================
# 工作目录：默认脚本上级目录，可用环境变量覆盖
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOUYIN_SYNC_DIR="${DOUYIN_SYNC_DIR:-$(dirname "$SCRIPT_DIR")}"

PY="${DOUYIN_VENV_PYTHON:-$DOUYIN_SYNC_DIR/venv/bin/python3}"
cd "$DOUYIN_SYNC_DIR/douyin-downloader"
exec "$PY" run.py -c config.yml
