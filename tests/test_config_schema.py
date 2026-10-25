"""RED 测试：统一配置系统（config.schema.json / scripts/dy_config.py）

验证 douyin_agent_kit.config.yaml 的加载、默认值、字段校验（非法 provider 报错）
与 get_asr()/get_vision() 访问器、select_asr_engine() 分发点。
"""
import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_schema():
    with open(os.path.join(REPO_ROOT, "config.schema.json"),
              encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def config_path(tmp_path):
    return tmp_path / "douyin_agent_kit.config.yaml"


class TestLoadConfig:
    """配置加载：缺失时返回全默认 + 警告；存在时与默认值深合并。"""

    def test_missing_file_returns_defaults(self, tmp_path, capsys):
        from scripts import dy_config
        cfg = dy_config.load_config(str(tmp_path / "no_such_config.yaml"))
        assert cfg["agent"] == "generic"
        assert cfg["asr"]["provider"] == "mlx-whisper"
        assert cfg["asr"]["model"] == "mlx-community/whisper-large-v3-turbo"
        assert cfg["asr"]["language"] == "zh"
        assert cfg["asr"]["offline"] is True
        assert cfg["vision"]["judge_provider"] == "ollama"
        assert cfg["vision"]["judge_model"] == "qwen2.5:7b"
        assert cfg["vision"]["ollama_url"] == "http://127.0.0.1:11434"
        assert cfg["vision"]["ocr_provider"] == "agent-vision"
        assert cfg["vision"]["fallback_ocr"] == "tesseract"
        assert cfg["vision"]["max_chars"] == 6000
        assert cfg["vision"]["verify_rounds"] == 2
        assert cfg["archive"]["enabled"] is True
        assert cfg["features"]["single_extract"] is True
        assert cfg["features"]["favorites_sync"] is False
        assert cfg["features"]["creator_distill"] is False
        # 应有警告提示用户使用默认配置
        assert "douyin_agent_kit.config.yaml" in capsys.readouterr().out

    def test_valid_config_merged(self, config_path):
        config_path.write_text(json.dumps({
            "agent": "hermes",
            "asr": {"provider": "faster-whisper", "model": "base"},
            "vision": {"judge_model": "llama3:8b", "max_chars": 3000},
            "features": {"favorites_sync": True},
        }), encoding="utf-8")
        from scripts import dy_config
        cfg = dy_config.load_config(str(config_path))
        assert cfg["agent"] == "hermes"
        assert cfg["asr"]["provider"] == "faster-whisper"
        assert cfg["asr"]["model"] == "base"
        # 未覆盖字段保留默认值
        assert cfg["asr"]["language"] == "zh"
        assert cfg["vision"]["judge_model"] == "llama3:8b"
        assert cfg["vision"]["max_chars"] == 3000
        assert cfg["vision"]["verify_rounds"] == 2
        assert cfg["features"]["favorites_sync"] is True
        assert cfg["features"]["single_extract"] is True

    def test_load_returns_fresh_copy(self, config_path):
        config_path.write_text(json.dumps({}), encoding="utf-8")
        from scripts import dy_config
        cfg1 = dy_config.load_config(str(config_path))
        cfg1["asr"]["provider"] = "hacked"
        cfg2 = dy_config.load_config(str(config_path))
        assert cfg2["asr"]["provider"] == "mlx-whisper", \
            "多次 load 不应共享同一份默认字典"


class TestSchemaId:
    """P3-1: config.schema.json 的 $id 不得用 example.com 占位。"""

    def test_schema_id_not_example_com(self):
        schema = _load_schema()
        assert "example.com" not in schema.get("$id", ""), \
            "$id 不应使用 example.com 占位"
        assert schema.get("$id", "").startswith(
            "https://github.com/senlib/douyin-agent-kit/"), \
            f"$id 应指向项目仓库，实际: {schema.get('$id')}"

    def test_schema_remains_valid_json(self):
        schema = _load_schema()
        assert isinstance(schema, dict) and "$id" in schema


class TestNaming:
    """项目改名：默认配置路径/文件名必须用新名 douyin_agent_kit.config.yaml。"""

    def test_default_config_path_uses_new_name(self):
        from scripts import dy_config
        assert dy_config.DEFAULT_CONFIG_PATH.endswith(
            "douyin_agent_kit.config.yaml"), \
            f"DEFAULT_CONFIG_PATH 应为新文件名，实际: {dy_config.DEFAULT_CONFIG_PATH}"
        assert dy_config._CONFIG_NAME == "douyin_agent_kit.config.yaml"


class TestValidation:
    """非法字段值应报 ValueError 并提示合法值。"""

    def test_invalid_agent_raises(self, config_path):
        config_path.write_text(json.dumps({"agent": "skynet"}), encoding="utf-8")
        from scripts import dy_config
        with pytest.raises(ValueError) as ei:
            dy_config.load_config(str(config_path))
        assert "hermes" in str(ei.value) and "generic" in str(ei.value)

    def test_invalid_asr_provider_raises(self, config_path):
        config_path.write_text(
            json.dumps({"asr": {"provider": "not-a-provider"}}), encoding="utf-8")
        from scripts import dy_config
        with pytest.raises(ValueError) as ei:
            dy_config.load_config(str(config_path))
        msg = str(ei.value)
        for legal in ("mlx-whisper", "faster-whisper", "whisper.cpp",
                      "external-command", "none"):
            assert legal in msg, f"错误消息应列出合法值 {legal}"

    def test_invalid_judge_provider_raises(self, config_path):
        config_path.write_text(
            json.dumps({"vision": {"judge_provider": "closedai"}}), encoding="utf-8")
        from scripts import dy_config
        with pytest.raises(ValueError) as ei:
            dy_config.load_config(str(config_path))
        assert "ollama" in str(ei.value) and "openai-compatible" in str(ei.value)

    def test_invalid_ocr_provider_raises(self, config_path):
        config_path.write_text(
            json.dumps({"vision": {"ocr_provider": "tesseract-ai"}}), encoding="utf-8")
        from scripts import dy_config
        with pytest.raises(ValueError) as ei:
            dy_config.load_config(str(config_path))
        assert "tesseract" in str(ei.value) and "agent-vision" in str(ei.value)

    def test_invalid_yaml_syntax_raises_clear_error(self, config_path):
        config_path.write_text("asr: [unclosed", encoding="utf-8")
        from scripts import dy_config
        with pytest.raises(Exception) as ei:
            dy_config.load_config(str(config_path))
        assert "douyin_agent_kit.config.yaml" in str(ei.value) or \
            "config" in str(ei.value).lower()


class TestAccessors:
    """get_asr() / get_vision() 访问器。"""

    def test_get_asr(self, tmp_path):
        from scripts import dy_config
        asr = dy_config.get_asr(dy_config.load_config(str(tmp_path / "x.yaml")))
        assert asr["provider"] == "mlx-whisper"
        assert asr["offline"] is True

    def test_get_vision(self, tmp_path):
        from scripts import dy_config
        vision = dy_config.get_vision(dy_config.load_config(str(tmp_path / "x.yaml")))
        assert vision["judge_provider"] == "ollama"
        assert vision["verify_rounds"] == 2


class TestSelectAsrEngine:
    """转录引擎分发点：返回当前 ASR provider 名。"""

    def test_default_is_mlx_whisper(self, tmp_path, monkeypatch):
        from scripts import dy_config
        import transcribe_archive
        monkeypatch.setattr(dy_config, "DEFAULT_CONFIG_PATH",
                            str(tmp_path / "no_such.yaml"))
        assert transcribe_archive.select_asr_engine() == "mlx-whisper"

    def test_from_config(self, tmp_path, monkeypatch):
        from scripts import dy_config
        import transcribe_archive
        cfg = tmp_path / "douyin_agent_kit.config.yaml"
        cfg.write_text(json.dumps({"asr": {"provider": "whisper.cpp"}}),
                       encoding="utf-8")
        monkeypatch.setattr(dy_config, "DEFAULT_CONFIG_PATH", str(cfg))
        assert transcribe_archive.select_asr_engine() == "whisper.cpp"

    def test_unimplemented_provider_raises_not_implemented(self, tmp_path, monkeypatch):
        """非 mlx-whisper 的引擎当前未实现，应明确 NotImplementedError 而非假装支持。"""
        from scripts import dy_config
        import transcribe_archive
        cfg = tmp_path / "douyin_agent_kit.config.yaml"
        cfg.write_text(json.dumps({"asr": {"provider": "faster-whisper"}}),
                       encoding="utf-8")
        monkeypatch.setattr(dy_config, "DEFAULT_CONFIG_PATH", str(cfg))
        with pytest.raises(NotImplementedError) as ei:
            transcribe_archive.ensure_asr_engine_supported()
        assert "faster-whisper" in str(ei.value)
