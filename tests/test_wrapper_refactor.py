"""run_pipeline.sh / run_sync.sh 环境 wrapper 重构测试 (RED → GREEN)
验证：
- run_pipeline.sh 调用系统 python3 (/opt/homebrew/bin/python3)
- 不设旧 uv PATH / PYTHONPATH
- 有 HOME 兜底逻辑
- preflight_check.sh 调用
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUN_PIPELINE = ROOT / "run_pipeline.sh"
RUN_SYNC = ROOT / "run_sync.sh"


def _read_script(path):
    return path.read_text(encoding="utf-8")


class TestRunPipelineEnv:
    """run_pipeline.sh 环境清理与可移植性"""

    def test_respects_douyin_sync_dir(self):
        """必须读取 DOUYIN_SYNC_DIR（可移植），不得硬编码本机路径"""
        content = _read_script(RUN_PIPELINE)
        assert "DOUYIN_SYNC_DIR" in content, (
            f"run_pipeline.sh 应读取 DOUYIN_SYNC_DIR\n内容:\n{content[:500]}"
        )
        assert "/opt/homebrew/bin/python3" not in content, (
            f"run_pipeline.sh 不得硬编码本机 python 路径\n内容:\n{content[:500]}"
        )
        assert "$HOME/Desktop/douyin-sync" not in content, (
            f"run_pipeline.sh 不得硬编码本机 sync 目录\n内容:\n{content[:500]}"
        )

    def test_python_resolved_via_path_or_env(self):
        """PY 应取 $PYTHON 或 PATH 上的 python3，而非写死的绝对路径"""
        content = _read_script(RUN_PIPELINE)
        assert "${PYTHON:-python3}" in content or "PYTHON" in content, (
            f"run_pipeline.sh 应支持 $PYTHON 覆盖或 PATH 解析\n内容:\n{content[:500]}"
        )

    def test_no_uv_path(self):
        """不得包含旧 uv PATH"""
        content = _read_script(RUN_PIPELINE)
        assert ".local/share/uv/python" not in content, (
            f"run_pipeline.sh 不得包含旧 uv PATH\n内容:\n{content[:500]}"
        )

    def test_no_pythonpath_injection(self):
        """不得设置 PYTHONPATH"""
        content = _read_script(RUN_PIPELINE)
        # 允许注释中出现 PYTHONPATH 但 export 中不行
        for line in content.split("\n"):
            if "export" in line and "PYTHONPATH" in line:
                pytest.fail(f"run_pipeline.sh 不得 export PYTHONPATH: {line.strip()}")

    def test_home_fallback_present(self):
        """必须有 HOME 兜底逻辑"""
        content = _read_script(RUN_PIPELINE)
        has_fallback = ("-d" in content and "HOME" in content and "Desktop" in content) or \
                       ("HOME=" in content and "~" in content)
        assert has_fallback, (
            f"run_pipeline.sh 必须有 HOME 兜底逻辑\n内容:\n{content[:500]}"
        )

    def test_calls_preflight(self):
        """必须调用 preflight_check.sh"""
        content = _read_script(RUN_PIPELINE)
        assert "preflight_check.sh" in content, (
            f"run_pipeline.sh 必须调用 preflight_check.sh\n内容:\n{content[:500]}"
        )

    def test_no_kmp_duplicate_lib(self):
        """不得设置 KMP_DUPLICATE_LIB_OK（mlx_whisper 不需要）"""
        content = _read_script(RUN_PIPELINE)
        # KMP 是 Intel MKL 的环境变量，mlx_whisper 用 Metal/GPU 不需要
        if "KMP_DUPLICATE_LIB_OK" in content:
            # 如果在注释中则可以接受
            for line in content.split("\n"):
                stripped = line.strip()
                if "KMP_DUPLICATE_LIB_OK" in stripped and not stripped.startswith("#"):
                    pytest.fail(
                        f"run_pipeline.sh 不应设置 KMP_DUPLICATE_LIB_OK（mlx_whisper 不需要 Intel MKL）: {line.strip()}"
                    )

    def test_passes_args_through(self):
        """必须透传 $@ 参数"""
        content = _read_script(RUN_PIPELINE)
        assert '"$@"' in content, (
            f"run_pipeline.sh 必须透传 $@ 参数\n内容:\n{content[:500]}"
        )


class TestRunSyncEnv:
    """run_sync.sh 环境修复"""

    def test_no_uv_path(self):
        """不得包含旧 uv PATH"""
        content = _read_script(RUN_SYNC)
        assert ".local/share/uv/python" not in content, (
            f"run_sync.sh 不得包含旧 uv PATH\n内容:\n{content[:500]}"
        )

    def test_no_pythonpath_injection(self):
        """不得设置 PYTHONPATH"""
        content = _read_script(RUN_SYNC)
        for line in content.split("\n"):
            if "export" in line and "PYTHONPATH" in line:
                pytest.fail(f"run_sync.sh 不得 export PYTHONPATH: {line.strip()}")

    def test_home_fallback_present(self):
        """必须有 HOME 兜底逻辑"""
        content = _read_script(RUN_SYNC)
        has_fallback = ("-d" in content and "HOME" in content and "Desktop" in content) or \
                       ("HOME=" in content and "~" in content)
        assert has_fallback, (
            f"run_sync.sh 必须有 HOME 兜底逻辑\n内容:\n{content[:500]}"
        )

    def test_venv_python_under_sync_dir(self):
        """venv python 应位于 DOUYIN_SYNC_DIR 下，而非硬编码 HOME 路径"""
        content = _read_script(RUN_SYNC)
        assert "DOUYIN_SYNC_DIR" in content, (
            f"run_sync.sh 应读取 DOUYIN_SYNC_DIR\n内容:\n{content[:500]}"
        )
        assert "venv/bin/python3" in content, (
            f"run_sync.sh 应使用 sync 目录下 venv/bin/python3\n内容:\n{content[:500]}"
        )
        assert "$HOME/Desktop/douyin-sync" not in content, (
            f"run_sync.sh 不得硬编码本机 sync 目录\n内容:\n{content[:500]}"
        )

    def test_calls_run_py_with_config(self):
        """必须调用 run.py -c config.yml"""
        content = _read_script(RUN_SYNC)
        assert "run.py" in content, "run_sync.sh 必须调用 run.py"
        assert "config" in content.lower(), "run_sync.sh 必须使用 config"


class TestDouyinDownloadProxy:
    """douyin_download.py 代理不得硬编码本机端口，应从环境变量读。"""

    DOUYIN_DOWNLOAD = ROOT / "skills/video-transcribe/scripts/douyin_download.py"

    def test_no_hardcoded_proxy_port(self):
        """不得硬编码代理端口 7897（本机路径幽灵）。"""
        content = self.DOUYIN_DOWNLOAD.read_text(encoding="utf-8")
        assert "7897" not in content, (
            f"douyin_download.py 不得硬编码代理端口 7897\n内容:\n{content[:300]}"
        )

    def test_proxy_read_from_env(self):
        """代理应从 DOUYIN_PROXY / HTTPS_PROXY 环境变量读取。"""
        content = self.DOUYIN_DOWNLOAD.read_text(encoding="utf-8")
        assert "DOUYIN_PROXY" in content or "HTTPS_PROXY" in content, (
            f"douyin_download.py 应从环境变量读取代理\n内容:\n{content[:300]}"
        )

    def test_docstring_no_duplicate_support_line(self):
        """P3-7: docstring 中「支持:」行不得重复（第 7-9 行）。"""
        content = self.DOUYIN_DOWNLOAD.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines()]
        assert lines.count("支持:") == 1, "「支持:」行重复出现"
