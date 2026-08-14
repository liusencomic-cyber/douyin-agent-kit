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

PY=/opt/homebrew/bin/python3
cd "$HOME/Desktop/douyin-sync"
exec "$PY" transcribe_archive.py "$@"
