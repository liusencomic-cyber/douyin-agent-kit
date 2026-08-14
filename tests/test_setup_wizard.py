"""RED 测试：设置向导 setup/setup_douyin_agent_kit.py

--non-interactive 参数注入生成正确配置；交互模式由 input() 驱动（subprocess 喂 stdin）；
生成 douyin_agent_kit.config.yaml / archive_config.json / AGENT_SETUP.md。
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)  # 确保仓库根优先（避免 setup 顶层模块与 PYTHONPATH 冲突）
WIZARD = os.path.join(REPO_ROOT, "setup", "setup_douyin_agent_kit.py")


def run_wizard(tmp_path, *extra):
    out = tmp_path / "douyin_agent_kit.config.yaml"
    cmd = [sys.executable, WIZARD, "--non-interactive", "--skip-checks",
           "--config-out", str(out), "--wizard-dir", str(tmp_path)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return r, out


def _load_yaml(path):
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestNonInteractive:
    """--non-interactive + 参数注入。"""

    def test_agent_hermes_machine_apple_silicon(self, tmp_path):
        r, out = run_wizard(tmp_path, "--agent", "hermes", "--machine", "apple-silicon")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["agent"] == "hermes"
        assert cfg["asr"]["provider"] == "mlx-whisper"  # apple-silicon 推荐
        assert cfg["asr"]["offline"] is True
        assert cfg["vision"]["judge_provider"] == "ollama"
        assert cfg["vision"]["judge_model"] == "qwen2.5:7b"
        assert cfg["vision"]["ocr_provider"] == "agent-vision"

    def test_default_agent_is_generic(self, tmp_path):
        r, out = run_wizard(tmp_path)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["agent"] == "generic"
        assert cfg["asr"]["provider"] == "mlx-whisper"

    def test_nvidia_machine_recommends_faster_whisper(self, tmp_path):
        r, out = run_wizard(tmp_path, "--machine", "nvidia")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["asr"]["provider"] == "faster-whisper"

    def test_cpu_only_machine_recommendation(self, tmp_path):
        r, out = run_wizard(tmp_path, "--machine", "cpu-only")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["asr"]["provider"] in ("faster-whisper", "whisper.cpp")

    def test_explicit_asr_overrides_preset(self, tmp_path):
        r, out = run_wizard(tmp_path, "--machine", "apple-silicon",
                            "--asr", "whisper.cpp")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["asr"]["provider"] == "whisper.cpp"

    def test_explicit_vision_overrides(self, tmp_path):
        r, out = run_wizard(tmp_path, "--judge", "openai-compatible",
                            "--judge-model", "gpt-4o-mini",
                            "--ocr", "tesseract", "--ollama-url", "http://x:1")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["vision"]["judge_provider"] == "openai-compatible"
        assert cfg["vision"]["judge_model"] == "gpt-4o-mini"
        assert cfg["vision"]["ocr_provider"] == "tesseract"
        assert cfg["vision"]["ollama_url"] == "http://x:1"

    def test_explicit_features(self, tmp_path):
        r, out = run_wizard(tmp_path, "--features", "single_extract,favorites_sync")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["features"]["single_extract"] is True
        assert cfg["features"]["favorites_sync"] is True
        assert cfg["features"]["creator_distill"] is False

    def test_archive_enabled_writes_archive_config_json(self, tmp_path):
        vault = str(tmp_path / "vault" / "_inbox")
        r, out = run_wizard(tmp_path, "--vault-inbox", vault)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        cfg = _load_yaml(out)
        assert cfg["archive"]["enabled"] is True
        assert cfg["archive"]["vault_inbox"] == vault
        acfg = tmp_path / "archive_config.json"
        assert acfg.exists(), "启用归档时应生成 archive_config.json"
        assert json.loads(acfg.read_text(encoding="utf-8")) == {"vault_inbox": vault}

    def test_agent_setup_md_generated_for_agent(self, tmp_path):
        r, out = run_wizard(tmp_path, "--agent", "hermes")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        md = tmp_path / "AGENT_SETUP.md"
        assert md.exists(), "应生成 AGENT_SETUP.md"
        content = md.read_text(encoding="utf-8")
        assert "hermes" in content.lower(), "AGENT_SETUP.md 应含所选 Agent 名"

    def test_config_is_valid_per_dy_config(self, tmp_path):
        """生成的配置应能被 scripts/dy_config 校验通过。"""
        r, out = run_wizard(tmp_path, "--agent", "openclaw", "--machine", "nvidia")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        from scripts import dy_config
        cfg = dy_config.load_config(str(out))
        assert cfg["agent"] == "openclaw"


class TestInteractive:
    """交互模式：input() 驱动（subprocess 喂 stdin）。"""

    def test_interactive_answers_generate_config(self, tmp_path):
        answers = [
            "hermes",           # 1. Agent 类型
            "apple-silicon",    # 2. 机器类型
            "mlx-whisper",      # 3. ASR provider
            "ollama",           # 4. Vision judge provider
            "agent-vision",     # 5. OCR provider
            "1,2",              # 6. 功能 multi-select（single_extract,favorites_sync）
            "n",                # 7. Obsidian 归档：跳过
        ]
        out = tmp_path / "douyin_agent_kit.config.yaml"
        cmd = [sys.executable, WIZARD, "--skip-checks",
               "--config-out", str(out), "--wizard-dir", str(tmp_path)]
        r = subprocess.run(cmd, input="\n".join(answers) + "\n",
                           capture_output=True, text=True, cwd=REPO_ROOT)
        assert r.returncode == 0, f"stderr: {r.stderr}\nstdout: {r.stdout}"
        cfg = _load_yaml(out)
        assert cfg["agent"] == "hermes"
        assert cfg["asr"]["provider"] == "mlx-whisper"
        assert cfg["features"]["single_extract"] is True
        assert cfg["features"]["favorites_sync"] is True
        assert cfg["features"]["creator_distill"] is False
        assert cfg["archive"]["enabled"] is False
