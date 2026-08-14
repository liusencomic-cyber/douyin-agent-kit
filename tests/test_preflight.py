"""preflight_check.sh 风控检查脚本测试 (RED → GREEN)
运行方式: cd douyin-sync && python -m pytest tests/test_preflight.py -v
"""
import os
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

# 项目根
ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT = ROOT / "preflight_check.sh"


def _run_preflight(env_overrides=None, exit_expected=True):
    """执行 preflight_check.sh，返回 (returncode, stdout, stderr)。"""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    # 确保 HOME 正常
    if "HOME" not in env or not os.path.isdir(env["HOME"]):
        env["HOME"] = str(Path.home())
    proc = subprocess.run(
        ["bash", str(PREFLIGHT)],
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    combined = proc.stdout + proc.stderr
    return proc.returncode, combined


class TestPreflightScriptExists:
    """preflight_check.sh 存在且可执行"""

    def test_script_exists(self):
        assert PREFLIGHT.exists(), f"preflight_check.sh 缺失: {PREFLIGHT}"

    def test_script_executable(self):
        st = os.stat(str(PREFLIGHT))
        assert st.st_mode & stat.S_IXUSR, "preflight_check.sh 不可执行"


class TestPreflightAllPass:
    """所有检查通过 → exit 0 + PREFLIGHT OK"""

    def test_all_checks_pass(self):
        """跳过实际 ps 检查（测试环境无残留进程），但模型缓存 + ollama 检查应通过。

        PREFLIGHT_MOCK_OLLAMA=1 mock Ollama 可达，使脚本走无警告路径输出
        PREFLIGHT OK：不依赖 CI/本机是否真实运行 Ollama（GitHub Actions 无 Ollama
        时脚本输出 PREFLIGHT WARN，断言 PREFLIGHT OK 会失败）。
        """
        env = {
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
            # 模型走 conftest autouse PREFLIGHT_MOCK_MODEL（指向临时假缓存）；
            # ollama mock 可达（方案 A：保持断言强度，见类注释）
            "PREFLIGHT_MOCK_OLLAMA": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"期望 exit 0，实际 {rc}\n输出: {out}"
        assert "PREFLIGHT OK" in out, f"期望 PREFLIGHT OK\n输出: {out}"


class TestPreflightTranscribeProcess:
    """残留转录进程检测"""

    def test_transcribe_process_detected(self):
        """模拟有残留转录进程 → exit 1"""
        env = {
            "PREFLIGHT_MOCK_TRANSCRIBE": "1",  # 脚本内部应当作有残留进程
        }
        rc, out = _run_preflight(env)
        assert rc != 0, f"期望非零退出码，实际 {rc}\n输出: {out}"
        assert "transcribe" in out.lower() or "转录" in out, f"期望提及转录进程\n输出: {out}"

    def test_transcribe_process_clean(self):
        """无残留转录进程 → 该检查通过"""
        env = {
            "PREFLIGHT_MOCK_TRANSCRIBE": "0",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"期望 exit 0，实际 {rc}\n输出: {out}"


class TestPreflightDownloaderProcess:
    """并发下载器检测"""

    def test_downloader_process_detected(self):
        env = {
            "PREFLIGHT_MOCK_DOWNLOADER": "1",
        }
        rc, out = _run_preflight(env)
        assert rc != 0, f"期望非零退出码，实际 {rc}\n输出: {out}"
        assert "run.py" in out.lower() or "douyin" in out.lower() or "下载" in out, f"期望提及下载器进程\n输出: {out}"

    def test_downloader_process_clean(self):
        env = {
            "PREFLIGHT_MOCK_DOWNLOADER": "0",
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"期望 exit 0，实际 {rc}\n输出: {out}"


class TestPreflightModelCache:
    """模型缓存检测"""

    def test_model_cache_missing(self, tmp_path):
        """缓存路径不存在 → exit 1"""
        fake_path = tmp_path / "nonexistent" / "weights.safetensors"
        env = {
            "PREFLIGHT_MOCK_MODEL": str(fake_path),
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
            "PREFLIGHT_SKIP_OLLAMA": "1",
        }
        rc, out = _run_preflight(env)
        assert rc != 0, f"期望非零退出码，实际 {rc}\n输出: {out}"
        assert "model" in out.lower() or "模型" in out, f"期望提及模型缓存\n输出: {out}"

    def test_model_cache_present(self, tmp_path):
        """缓存路径存在 → 通过"""
        model_dir = tmp_path / "models--mlx-community--whisper-large-v3-turbo" / "snapshots" / "abc123"
        model_dir.mkdir(parents=True)
        weights = model_dir / "weights.safetensors"
        weights.write_text("fake weights")
        env = {
            "PREFLIGHT_MOCK_MODEL": str(weights),
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
            "PREFLIGHT_SKIP_OLLAMA": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"期望 exit 0，实际 {rc}\n输出: {out}"


class TestPreflightOllama:
    """Ollama 在线检测（可选检查，WARNING 不阻断）"""

    def test_ollama_unreachable_warns(self):
        """Ollama 不可达 → WARNING，不阻断"""
        env = {
            "PREFLIGHT_MOCK_OLLAMA": "0",  # 不可达
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"Ollama 不可达不应阻断，实际 {rc}\n输出: {out}"
        assert "WARN" in out, f"期望 PREFLIGHT WARN\n输出: {out}"

    def test_ollama_reachable_ok(self):
        env = {
            "PREFLIGHT_MOCK_OLLAMA": "1",  # 可达
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
        }
        rc, out = _run_preflight(env)
        assert rc == 0, f"期望 exit 0，实际 {rc}\n输出: {out}"
        assert "PREFLIGHT OK" in out, f"期望 PREFLIGHT OK\n输出: {out}"


class TestPreflightHomeFallback:
    """HOME 兜底检测"""

    def test_bad_home_fallback(self):
        """HOME 指向不存在的路径时自动 fallback"""
        env = {
            "HOME": "/nonexistent/path/12345",
            "PREFLIGHT_SKIP_TRANSCRIBE": "1",
            "PREFLIGHT_SKIP_DOWNLOADER": "1",
            "PREFLIGHT_SKIP_OLLAMA": "1",
        }
        rc, out = _run_preflight(env)
        # 应该能正常运行（HOME fallback 生效），不崩溃
        assert rc in (0, 1), f"期望正常退出，实际 {rc}\n输出: {out}"
        # HOME fallback 不应导致脚本找不到自身
        assert "No such file" not in out, f"脚本不应因 HOME 异常而崩溃\n输出: {out}"


class TestPreflightMultipleFailures:
    """多个硬性检查失败 → 汇总所有失败原因"""

    def test_multiple_failures_reported(self, tmp_path):
        fake_path = tmp_path / "nonexistent" / "weights.safetensors"
        env = {
            "PREFLIGHT_MOCK_TRANSCRIBE": "1",  # 残留转录
            "PREFLIGHT_MOCK_DOWNLOADER": "1",  # 并发下载
            "PREFLIGHT_MOCK_MODEL": str(fake_path),  # 模型缺失
        }
        rc, out = _run_preflight(env)
        assert rc != 0, f"期望非零退出码，实际 {rc}\n输出: {out}"
        # 应包含多个失败信息
        fail_count = out.count("FAIL") + out.count("失败")
        assert fail_count >= 2, f"期望至少 2 个失败项\n输出: {out}"
