#!/bin/bash
# ============================================================================
# run_pipeline.sh —— 转译归档（GPU/离线版）
# 调用 transcribe_archive.py，使用系统 python3 (3.14) + mlx_whisper GPU 转录
# * 不设 PYTHONPATH（脚本内部自清理）
# * 不设旧 uv PATH（版本漂移源）
# * 工作目录可用 DOUYIN_SYNC_DIR 环境变量覆盖
# ============================================================================
# 工作目录：默认脚本上级目录，可用环境变量覆盖
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOUYIN_SYNC_DIR="${DOUYIN_SYNC_DIR:-$(dirname "$SCRIPT_DIR")}"

# 启动前风控检查
"$SCRIPT_DIR/preflight_check.sh" || exit 1

PY="${PYTHON_BIN:-/opt/homebrew/bin/python3}"
cd "$DOUYIN_SYNC_DIR"
exec "$PY" transcribe_archive.py "$@"
