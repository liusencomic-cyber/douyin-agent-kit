"""RED 测试：核心逻辑抽公共模块（P1-3）。

transcribe_archive.py 与 transcribe_only.py 的 select_asr_engine /
ensure_asr_engine_supported / format_timestamp / segments_to_timestamps
四函数逐字重复；scripts/dy_config.py 已有 select_asr_engine 未被复用。
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


def _src(module_name):
    import importlib
    mod = importlib.import_module(module_name)
    return open(mod.__file__, encoding="utf-8").read()


class TestSharedModulesImported:
    """两脚本必须 import 公共模块而非本地副本。"""

    def test_transcribe_only_imports_asr_utils(self):
        src = _src("transcribe_only")
        assert "from scripts.asr_utils import" in src, \
            "transcribe_only.py 应复用 scripts/asr_utils.py"

    def test_transcribe_archive_imports_shared_modules(self):
        src = _src("transcribe_archive")
        assert "from scripts.asr_utils import" in src, \
            "transcribe_archive.py 应复用 scripts/asr_utils.py"
        assert "from scripts.format_utils import" in src, \
            "transcribe_archive.py 应复用 scripts/format_utils.py"

    def test_no_local_copies_in_transcribe_only(self):
        src = _src("transcribe_only")
        assert "def format_timestamp" not in src, "本地副本应删除"
        assert "def select_asr_engine" not in src, "本地副本应删除"

    def test_no_local_copies_in_transcribe_archive(self):
        src = _src("transcribe_archive")
        assert "def format_timestamp" not in src, "本地副本应删除"
        assert "def select_asr_engine" not in src, "本地副本应删除"


class TestSharedModuleBehavior:
    """公共模块行为与原实现一致（现有功能测试全绿即证明）。"""

    def test_format_timestamp(self):
        from scripts.format_utils import format_timestamp
        assert format_timestamp(0.0) == "00:00.000"
        assert format_timestamp(61.5) == "01:01.500"
        assert format_timestamp(3661.0) == "01:01:01.000"

    def test_segments_to_timestamps(self):
        from scripts.format_utils import segments_to_timestamps
        segs = [{"start": 0.0, "end": 1.36, "text": "第一段。"}]
        out = segments_to_timestamps(segs)
        assert "[00:00.000 --> 00:01.360] 第一段。" in out
        assert segments_to_timestamps([]) == ""

    def test_select_asr_engine_fallback(self, tmp_path, monkeypatch):
        """配置不可读时回落 mlx-whisper（与原实现一致）。"""
        from scripts import dy_config
        from scripts.asr_utils import select_asr_engine, ensure_asr_engine_supported
        monkeypatch.setattr(dy_config, "DEFAULT_CONFIG_PATH",
                            str(tmp_path / "no_such.yaml"))
        assert select_asr_engine() == "mlx-whisper"
        assert ensure_asr_engine_supported() == "mlx-whisper"

    def test_ensure_asr_engine_raises_for_unimplemented(self, tmp_path, monkeypatch):
        """非 mlx-whisper 的 provider 抛 NotImplementedError（接口预留不假装支持）。"""
        import pytest
        from scripts import dy_config
        from scripts.asr_utils import ensure_asr_engine_supported
        cfg = tmp_path / "douyin_agent_kit.config.yaml"
        cfg.write_text(json.dumps({"asr": {"provider": "faster-whisper"}}),
                       encoding="utf-8")
        monkeypatch.setattr(dy_config, "DEFAULT_CONFIG_PATH", str(cfg))
        with pytest.raises(NotImplementedError) as ei:
            ensure_asr_engine_supported()
        assert "faster-whisper" in str(ei.value)
