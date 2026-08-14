"""RED 测试：transcribe_archive.py 引擎迁移

在迁移到 mlx_whisper 之前，这些测试会失败 —— 证明现状缺陷。
迁移完成后全部 GREEN。
"""
import json
import os
import sys
import tempfile
import pytest
from unittest import mock


# ── helpers ──────────────────────────────────────────────────

def make_video_dir(base, date, title, aweme_id, *, with_mp4=True, with_meta=True):
    folder = os.path.join(base, f"{date}_{title}_{aweme_id}")
    os.makedirs(folder, exist_ok=True)
    if with_mp4:
        with open(os.path.join(folder, f"{aweme_id}.mp4"), "wb") as f:
            f.write(b"\x00\x00\x00\x18ftypmp42")
    if with_meta:
        with open(os.path.join(folder, f"{aweme_id}_data.json"), "w") as f:
            json.dump({
                "desc": f"文案_{title}",
                "create_time": 1719705600,
                "author": {"nickname": "测试作者"},
                "text_extra": [{"hashtag_name": "投资"}, {"hashtag_name": "理财"}]
            }, f)
    return folder


def run_main(src_dir, processed_path, vault_inbox, limit=0):
    """导入 transcribe_archive 并调用 main()。"""
    import transcribe_archive
    with mock.patch.object(sys, "argv", [
        "transcribe_archive.py",
        "--src-dir", src_dir,
        "--processed", processed_path,
    ] + (["--limit", str(limit)] if limit else [])):
        with mock.patch("transcribe_archive.VAULT_INBOX", vault_inbox):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(returncode=0)
                transcribe_archive.main()


# ── RED 测试：引擎迁移 ───────────────────────────────────────

class TestMlxWhisperMigration:
    """证明当前代码使用 faster_whisper 而 *不* 使用 mlx_whisper。"""

    def test_uses_mlx_whisper_transcribe(self, tmp_path):
        """RED: 转录时应调用 mlx_whisper.transcribe 而非 faster_whisper。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "收藏视频", "98765432101")
        processed = tmp_path / "p.json"

        mock_result = {"text": "收藏转录内容", "segments": [
            {"id": 0, "start": 0.0, "end": 2.0, "text": "收藏转录内容", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as mock_transcribe:
            run_main(str(src), str(processed), str(vault))
            mock_transcribe.assert_called_once()
            call_args = mock_transcribe.call_args
            assert call_args.kwargs.get("path_or_hf_repo") == "mlx-community/whisper-large-v3-turbo", \
                f"Expected model mlx-community/whisper-large-v3-turbo, got {call_args.kwargs}"
            assert call_args.kwargs.get("language") == "zh"

    def test_no_faster_whisper_import(self, tmp_path):
        """RED: 运行 main 时不应导入 faster_whisper。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "无faster", "11111111102")
        processed = tmp_path / "p.json"

        mock_result = {"text": "无faster", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "无faster", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch.dict(sys.modules, {"faster_whisper": None}):
            with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
                run_main(str(src), str(processed), str(vault))
        # 不应崩溃

    def test_mlx_whisper_params_no_vad_filter(self, tmp_path):
        """RED: mlx_whisper 调用不含 vad_filter。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "参数检查", "22222222202")
        processed = tmp_path / "p.json"

        mock_result = {"text": "参数", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "参数", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(processed), str(vault))
            m.assert_called_once()
            assert "vad_filter" not in m.call_args.kwargs, \
                "mlx_whisper does not support vad_filter"


# ── 功能回归测试 ─────────────────────────────────────────────

class TestNoteGeneration:
    """Obsidian 笔记格式不变。"""

    def test_note_format(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "笔记格式测试", "33333333303")
        processed = tmp_path / "p.json"

        mock_result = {"text": "格式测试转录", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "格式测试转录", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_main(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1, f"Expected 1 note, got {len(md_files)}: {md_files}"
        content = md_files[0].read_text(encoding="utf-8")
        assert "# 笔记格式测试" in content
        assert "抖音 - 测试作者" in content
        assert "## 视频文案（作者自述）" in content
        assert "## 原文转录（Whisper）" in content
        assert "格式测试转录" in content
        assert "收藏同步日期：2026-07-01" in content
        assert "#投资" in content
        assert "#理财" in content
        assert "> 本文由收藏自动归档流水线生成" in content

    def test_processed_dedup(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "已处理", "44444444404")
        make_video_dir(str(src), "2026-07-02", "新视频", "55555555505")
        processed = tmp_path / "p.json"
        processed.write_text(json.dumps(["44444444404"]))

        mock_result = {"text": "新内容", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "新内容", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(processed), str(vault))
            assert m.call_count == 1

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1
        assert "新视频" in md_files[0].read_text()

        saved = json.loads(processed.read_text())
        assert "44444444404" in saved
        assert "55555555505" in saved

    def test_image_only_no_transcribe(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "图文收藏", "66666666606", with_mp4=False)
        processed = tmp_path / "p.json"

        mock_result = {"text": "", "segments": [], "language": "zh"}
        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(processed), str(vault))
            m.assert_not_called()

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text()
        assert "图文作品或无声视频" in content

    def test_failure_tolerance(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "失败视频", "77777777707")
        make_video_dir(str(src), "2026-07-02", "成功视频", "88888888808")
        processed = tmp_path / "p.json"

        call_count = [0]
        def side_effect(audio, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("模拟转录失败")
            return {"text": "成功", "segments": [
                {"id": 0, "start": 0.0, "end": 1.0, "text": "成功", "tokens": [], "words": []}
            ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", side_effect=side_effect):
            run_main(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) >= 1  # 成功那条应有笔记

    def test_missing_src_dir(self, tmp_path):
        src = tmp_path / "nonexistent"
        vault = tmp_path / "vault"
        vault.mkdir()
        processed = tmp_path / "p.json"

        mock_result = {"text": "", "segments": [], "language": "zh"}
        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            with pytest.raises(SystemExit):
                run_main(str(src), str(processed), str(vault))

    def test_limit(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        for i in range(5):
            make_video_dir(str(src), f"2026-07-0{i+1}", f"视频{i}", f"9999999990{i}")
        processed = tmp_path / "p.json"

        mock_result = {"text": "限", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "限", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            import transcribe_archive
            with mock.patch.object(sys, "argv", [
                "transcribe_archive.py",
                "--src-dir", str(src),
                "--processed", str(processed),
                "--limit", "2",
            ]):
                with mock.patch("transcribe_archive.VAULT_INBOX", str(vault)):
                    with mock.patch("subprocess.run") as mock_run:
                        mock_run.return_value = mock.MagicMock(returncode=0)
                        transcribe_archive.main()
            assert m.call_count == 2, f"Expected 2 (limit), got {m.call_count}"


class TestEnvironment:
    """环境适配测试。"""

    def test_pythonpath_cleanup(self, tmp_path):
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "环境", "12345678902")
        processed = tmp_path / "p.json"

        mock_result = {"text": "环境OK", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "环境OK", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch.dict(os.environ, {"PYTHONPATH": "/dirty/path"}, clear=False):
            with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
                run_main(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1

    def test_hf_hub_offline_set(self, tmp_path):
        """RED: main() 必须设置 HF_HUB_OFFLINE=1，确保 huggingface_hub 完全离线。
        当前代码未设置 → 预期 RED 失败（无代理环境下会卡死）。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "离线收藏", "11111111103")
        processed = tmp_path / "p.json"

        mock_result = {"text": "离线收藏OK", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "离线收藏OK", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HF_HUB_OFFLINE", None)
            with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
                run_main(str(src), str(processed), str(vault))
            assert os.environ.get("HF_HUB_OFFLINE") == "1", \
                "HF_HUB_OFFLINE must be set to '1' for offline transcription in China network"


# ── RED 测试：Obsidian 归档路径解耦 ───────────────────────────

class TestArchiveConfigDecoupling:
    """证明 VAULT_INBOX 应由共享配置 archive_config.json 读取，而非硬编码。"""

    def test_load_archive_config_exists(self):
        """RED: load_archive_config() 函数应存在。"""
        import transcribe_archive
        assert hasattr(transcribe_archive, 'load_archive_config'), \
            "load_archive_config 函数尚未定义（当前 VAULT_INBOX 为硬编码常量 → RED）"

    def test_load_archive_config_reads_file(self, tmp_path):
        """RED: load_archive_config() 应从 archive_config.json 读取并返回 dict。"""
        import transcribe_archive
        test_path = str(tmp_path / "custom_inbox")
        cfg = {"vault_inbox": test_path}
        cfg_file = tmp_path / "archive_config.json"
        cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

        with mock.patch.object(transcribe_archive, 'BASE', str(tmp_path)):
            result = transcribe_archive.load_archive_config()
            assert result.get("vault_inbox") == test_path, \
                f"load_archive_config 应返回配置中的路径 '{test_path}'"

    def test_vault_inbox_not_hardcoded(self):
        """RED: VAULT_INBOX 赋值行不应包含硬编码的 iCloud 路径字符串。"""
        import transcribe_archive
        src = open(transcribe_archive.__file__).read()
        hardcoded = (
            "~/Library/Mobile Documents/"
            "iCloud~md~obsidian/Documents/KnocksenVault/"
            "_inbox/赫尔墨斯_inbox"
        )
        assign_line = None
        for line in src.splitlines():
            if 'VAULT_INBOX' in line and '=' in line and 'load_archive_config' not in line:
                assign_line = line.strip()
                break
        if assign_line and hardcoded in assign_line:
            pytest.fail(
                f"VAULT_INBOX 不应硬编码路径，应使用 load_archive_config() 读取。\n"
                f"当前赋值行: {assign_line}"
            )

    def test_missing_config_raises_clear_error(self, tmp_path):
        """RED: 配置文件缺失时应抛清晰错误，不静默 fallback。"""
        import transcribe_archive
        nonexistent = tmp_path / "no_such_config"
        with mock.patch.object(transcribe_archive, 'BASE', str(nonexistent)):
            with mock.patch.object(
                transcribe_archive, '__builtins__',
                transcribe_archive.__builtins__ | {'open': open}
            ):
                with pytest.raises(Exception) as exc_info:
                    transcribe_archive.load_archive_config()
                # 错误消息应包含 archive_config.json，指引用户创建
                assert "archive_config.json" in str(exc_info.value).lower() or \
                       "archive_config" in str(exc_info.value), \
                    f"错误消息应提及 archive_config.json，实际: {exc_info.value}"
