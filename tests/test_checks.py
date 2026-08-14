"""RED 测试：setup/checks.py 环境检查分级逻辑（OK / WARN / MISSING）。

mock 各检查项返回值，验证汇总计数、exit code 与 main 流程。
"""
import os
import sys
import pytest

# 确保仓库根优先于被 PYTHONPATH 污染的路径（避免 setup 顶层模块冲突）
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


class TestDownloaderConditional:
    """P1-2: douyin-downloader 检查按 features 条件化，未启用不阻断。

    现状 check_downloader 缺失即 MISSING → exit 1；但单条提取（默认功能）
    用 scrapling 版 douyin_download.py，不需要 douyin-downloader/。
    """

    def test_warn_when_only_single_extract(self, tmp_path, monkeypatch):
        """仅启用单条提取时，缺下载器为 WARN 而非 MISSING。"""
        import setup.checks as checks
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        monkeypatch.setattr(checks, "REPO_ROOT", str(tmp_path))
        cfg = {"features": {"single_extract": True,
                            "favorites_sync": False, "creator_distill": False}}
        assert checks.check_downloader(cfg)[1] == "WARN"

    def test_missing_when_favorites_sync_enabled(self, tmp_path, monkeypatch):
        """启用 favorites_sync 时缺下载器仍为 MISSING（阻断）。"""
        import setup.checks as checks
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        monkeypatch.setattr(checks, "REPO_ROOT", str(tmp_path))
        cfg = {"features": {"favorites_sync": True, "creator_distill": False}}
        assert checks.check_downloader(cfg)[1] == "MISSING"

    def test_warn_without_config(self, tmp_path, monkeypatch):
        """无配置（默认检查）时缺下载器不阻断（WARN）。"""
        import setup.checks as checks
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        monkeypatch.setattr(checks, "REPO_ROOT", str(tmp_path))
        assert checks.check_downloader(None)[1] == "WARN"

    def test_exit_zero_when_downloader_missing_and_not_needed(self, tmp_path, monkeypatch):
        """组合验证：无配置缺下载器 → exit_code 0。"""
        import setup.checks as checks
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        monkeypatch.setattr(checks, "REPO_ROOT", str(tmp_path))
        results = [checks.check_downloader(None), ("ffmpeg", "OK", "")]
        assert checks.exit_code(results) == 0

    def test_ok_when_downloader_present(self, tmp_path, monkeypatch):
        """下载器存在时仍为 OK。"""
        import setup.checks as checks
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        d = tmp_path / "douyin-downloader"; d.mkdir()
        monkeypatch.setattr(checks, "REPO_ROOT", str(tmp_path))
        assert checks.check_downloader(None)[1] == "OK"


def make_check(name, status, detail=""):
    return (name, status, detail)


class TestCheckClassification:
    """分级与 exit code 逻辑。"""

    def test_exit_code_zero_all_ok(self):
        import setup.checks as checks
        results = [make_check("ffmpeg", "OK"), make_check("mlx_whisper", "OK")]
        assert checks.exit_code(results) == 0

    def test_exit_code_one_on_any_missing(self):
        import setup.checks as checks
        results = [make_check("ffmpeg", "OK"),
                   make_check("douyin-downloader", "MISSING", "目录不存在")]
        assert checks.exit_code(results) == 1

    def test_warn_does_not_fail(self):
        import setup.checks as checks
        results = [make_check("ollama", "WARN", "服务未启动")]
        assert checks.exit_code(results) == 0

    def test_summary_counts(self):
        import setup.checks as checks
        results = [
            make_check("a", "OK"),
            make_check("b", "WARN"),
            make_check("c", "MISSING"),
            make_check("d", "MISSING"),
        ]
        ok, warn, missing = checks.summarize(results)
        assert (ok, warn, missing) == (1, 1, 2)

    def test_run_checks_calls_functions(self):
        """run_checks 应逐个调用检查函数并收集 (name, status, detail)。"""
        import setup.checks as checks
        fake = [
            lambda: ("ffmpeg", "OK", ""),
            lambda: ("mlx_whisper", "MISSING", "module not found"),
        ]
        results = checks.run_checks(functions=fake)
        assert len(results) == 2
        assert results[0] == ("ffmpeg", "OK", "")
        assert results[1] == ("mlx_whisper", "MISSING", "module not found")

    def test_default_checks_are_registered(self):
        """内置检查项名称应包含核心环境依赖。"""
        import setup.checks as checks
        names = [c[0] for c in checks.CHECK_FUNCTIONS]
        for required in ("python3", "ffmpeg", "mlx_whisper", "ollama",
                         "douyin-downloader", "model_cache"):
            assert required in names, f"应包含检查项 {required}"

    def test_main_exits_one_on_missing(self, monkeypatch, capsys):
        import setup.checks as checks
        monkeypatch.setattr(checks, "run_checks",
                            lambda **kw: [make_check("x", "MISSING", "")])
        with pytest.raises(SystemExit) as ei:
            checks.main()
        assert ei.value.code == 1
        out = capsys.readouterr().out
        assert "MISSING" in out

    def test_main_exits_zero_all_ok(self, monkeypatch, capsys):
        import setup.checks as checks
        monkeypatch.setattr(checks, "run_checks",
                            lambda **kw: [make_check("x", "OK", "")])
        with pytest.raises(SystemExit) as ei:
            checks.main()
        assert ei.value.code == 0

    def test_main_supports_config_arg(self, tmp_path, monkeypatch):
        """--config 指定配置后应传给 run_checks（用于条件检查项）。"""
        import setup.checks as checks
        captured = {}

        def fake_run_checks(**kw):
            captured.update(kw)
            return [make_check("x", "OK", "")]

        monkeypatch.setattr(checks, "run_checks", fake_run_checks)
        monkeypatch.setattr(sys, "argv", ["checks.py", "--config", "/tmp/c.yaml"])
        with pytest.raises(SystemExit):
            checks.main()
        assert captured.get("config_path") == "/tmp/c.yaml"
