#!/bin/bash
# ============================================================================
# preflight_check.sh —— 启动前风控检查
# 检查项:
#   1. 无残留转录进程 (ps aux | grep transcribe)
#   2. 无并发 douyin-downloader (ps aux | grep run.py)
#   3. 模型缓存存在 (mlx-community/whisper-large-v3-turbo)
#   4. Ollama 在线 (可选，不可达 WARNING 不阻断)
#
# 环境变量 (测试用 mock):
#   PREFLIGHT_SKIP_TRANSCRIBE=1    跳过转录进程检查
#   PREFLIGHT_SKIP_DOWNLOADER=1    跳过下载器检查
#   PREFLIGHT_SKIP_OLLAMA=1       跳过 Ollama 检查
#   PREFLIGHT_MOCK_TRANSCRIBE=1   模拟有残留转录进程
#   PREFLIGHT_MOCK_TRANSCRIBE=0   模拟无残留转录进程
#   PREFLIGHT_MOCK_DOWNLOADER=1   模拟有并发下载器
#   PREFLIGHT_MOCK_DOWNLOADER=0   模拟无并发下载器
#   PREFLIGHT_MOCK_MODEL=path     覆盖模型权重路径
#   PREFLIGHT_MOCK_OLLAMA=1       模拟 Ollama 可达
#   PREFLIGHT_MOCK_OLLAMA=0       模拟 Ollama 不可达
# ============================================================================
set -uo pipefail

# --- HOME 兜底（enclave 沙箱可能改写 HOME） ---
if [ ! -d "$HOME/Desktop" ] && [ -n "${REAL_HOME:-}" ]; then
	HOME="$REAL_HOME"
	export HOME
fi

# --- 配置 ---
FAIL_COUNT=0
WARN_COUNT=0
MODEL_CACHE_DIR="${HOME}/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo"
OLLAMA_URL="http://127.0.0.1:11434/api/tags"

fail() {
	echo "  FAIL: $*"
	FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
	echo "  WARN: $*"
	WARN_COUNT=$((WARN_COUNT + 1))
}

ok() {
	echo "  OK: $*"
}

# ===================================================================
# 检查 1: 无残留转录进程
# ===================================================================
check_transcribe() {
	echo "[1/4] 检查残留转录进程..."

	if [ "${PREFLIGHT_SKIP_TRANSCRIBE:-}" = "1" ]; then
		echo "  SKIP (PREFLIGHT_SKIP_TRANSCRIBE=1)"
		return 0
	fi

	if [ "${PREFLIGHT_MOCK_TRANSCRIBE:-}" = "1" ]; then
		fail "检测到残留转录进程 (mock)"
		return 1
	elif [ "${PREFLIGHT_MOCK_TRANSCRIBE:-}" = "0" ]; then
		ok "无残留转录进程 (mock)"
		return 0
	fi

	# 真实检查
	if ps aux 2>/dev/null | grep -q "[t]ranscribe"; then
		fail "检测到残留转录进程，请等待完成后再启动"
		return 1
	fi
	ok "无残留转录进程"
}

# ===================================================================
# 检查 2: 无并发 douyin-downloader
# ===================================================================
check_downloader() {
	echo "[2/4] 检查并发 douyin-downloader..."

	if [ "${PREFLIGHT_SKIP_DOWNLOADER:-}" = "1" ]; then
		echo "  SKIP (PREFLIGHT_SKIP_DOWNLOADER=1)"
		return 0
	fi

	if [ "${PREFLIGHT_MOCK_DOWNLOADER:-}" = "1" ]; then
		fail "检测到并发 douyin-downloader 进程 (mock)"
		return 1
	elif [ "${PREFLIGHT_MOCK_DOWNLOADER:-}" = "0" ]; then
		ok "无并发 douyin-downloader (mock)"
		return 0
	fi

	# 真实检查
	if ps aux 2>/dev/null | grep -q "[r]un.py.*config"; then
		fail "检测到并发 douyin-downloader 进程（同一 Cookie 并发 = 风控风险）"
		return 1
	fi
	ok "无并发 douyin-downloader"
}

# ===================================================================
# 检查 3: 模型缓存存在
# ===================================================================
check_model_cache() {
	echo "[3/4] 检查 mlx_whisper 模型缓存..."

	local model_path
	if [ -n "${PREFLIGHT_MOCK_MODEL:-}" ]; then
		model_path="${PREFLIGHT_MOCK_MODEL}"
	else
		# 查找 snapshots 目录下的 weights.safetensors
		model_path=$(find "$MODEL_CACHE_DIR/snapshots" -name "weights.safetensors" 2>/dev/null | head -1 || echo "")
	fi

	if [ -z "$model_path" ] || [ ! -f "$model_path" ]; then
		fail "模型缓存缺失: $MODEL_CACHE_DIR/snapshots/*/weights.safetensors"
		echo "  提示: 手动运行一次 transcribe_archive.py --limit 1 触发模型下载"
		return 1
	fi
	ok "模型缓存: $model_path"
}

# ===================================================================
# 检查 4: Ollama 在线（可选）
# ===================================================================
check_ollama() {
	echo "[4/4] 检查 Ollama 服务..."

	if [ "${PREFLIGHT_SKIP_OLLAMA:-}" = "1" ]; then
		echo "  SKIP (PREFLIGHT_SKIP_OLLAMA=1)"
		return 0
	fi

	if [ "${PREFLIGHT_MOCK_OLLAMA:-}" = "1" ]; then
		ok "Ollama 在线 (mock)"
		return 0
	elif [ "${PREFLIGHT_MOCK_OLLAMA:-}" = "0" ]; then
		warn "Ollama 不可达 (mock) —— 语义分析将跳过，仅影响 analyze_visual_needs"
		return 0
	fi

	# 真实检查
	if curl -s --max-time 3 "$OLLAMA_URL" >/dev/null 2>&1; then
		ok "Ollama 在线"
	else
		warn "Ollama 不可达 —— 语义分析将跳过，仅影响 analyze_visual_needs"
	fi
}

# ===================================================================
# 主流程
# ===================================================================
main() {
	echo "=== preflight_check.sh === $(date '+%Y-%m-%d %H:%M:%S')"
	echo ""

	check_transcribe
	check_downloader
	check_model_cache
	check_ollama

	echo ""
	echo "--- 检查汇总 ---"
	echo "  硬性失败: $FAIL_COUNT"
	echo "  警告:     $WARN_COUNT"

	if [ "$FAIL_COUNT" -gt 0 ]; then
		echo ""
		echo "PREFLIGHT FAIL —— 请处理以上 $FAIL_COUNT 个问题后重试"
		exit 1
	fi

	if [ "$WARN_COUNT" -gt 0 ]; then
		echo ""
		echo "PREFLIGHT WARN —— 以上警告不影响运行"
		exit 0
	fi

	echo ""
	echo "PREFLIGHT OK"
	exit 0
}

main "$@"
