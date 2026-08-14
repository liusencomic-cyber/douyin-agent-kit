"""RED 测试：setup/checks.py 环境检查分级逻辑（OK / WARN / MISSING）。

mock 各检查项返回值，验证汇总计数、exit code 与 main 流程。
"""
import os
import sys
import pytest


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
