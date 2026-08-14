#!/bin/bash
# ============================================================================
# run_pipeline.sh —— 转译归档（GPU/离线版）
# 调用 transcribe_archive.py，使用系统 python3 (3.14) + mlx_whisper GPU 转录
# * 不设 PYTHONPATH（脚本内部自清理）
# * 不设旧 uv PATH（版本漂移源）
# * HOME 兜底（enclave 沙箱可能改写）
# ============================================================================
# HOME 兜底（沙箱环境可能改写 HOME；可用 REAL_HOME 显式指定真实用户目录）
if [ ! -d "$HOME/Desktop" ] && [ -n "${REAL_HOME:-}" ]; then
    HOME="$REAL_HOME"
    export HOME
fi

# 启动前风控检查
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/preflight_check.sh" || exit 1

# sync 目录：优先环境变量 DOUYIN_SYNC_DIR，否则脚本所在目录（可移植，不硬编码本机路径）
SYNC_DIR="${DOUYIN_SYNC_DIR:-$SCRIPT_DIR}"
PY="${PYTHON:-python3}"
cd "$SYNC_DIR"
exec "$PY" transcribe_archive.py "$@"
