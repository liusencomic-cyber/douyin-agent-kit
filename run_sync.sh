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

PY="$HOME/Desktop/douyin-sync/venv/bin/python3"
cd "$HOME/Desktop/douyin-sync/douyin-downloader"
exec "$PY" run.py -c config.yml
