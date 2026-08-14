"""测试：transcribe_only.py mlx_whisper 引擎迁移 + 功能回归"""
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
            json.dump({"desc": f"文案_{title}", "create_time": 1719705600}, f)
    return folder


def run_main(src_dir, out_path, processed_path):
    import transcribe_only
    with mock.patch.object(sys, "argv", [
        "transcribe_only.py",
        "--src-dir", src_dir,
        "--out", out_path,
        "--processed", processed_path,
    ]):
        transcribe_only.main()


# ── 引擎迁移测试 ─────────────────────────────────────────────

class TestMlxWhisperMigration:

    def test_does_not_import_faster_whisper_at_module_level(self):
        with mock.patch.dict(sys.modules, {"faster_whisper": None}):
            try:
                import transcribe_only
            except ImportError:
                pytest.fail("faster_whisper should not be needed after migration")

    def test_uses_mlx_whisper_transcribe(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "测试视频", "12345678901")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_segments = [{"id": 0, "start": 0.0, "end": 2.0, "text": "这是测试转录内容。", "tokens": [], "words": []}]
        mock_result = {"text": "这是测试转录内容。", "segments": mock_segments, "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as mock_transcribe:
            run_main(str(src), str(out), str(processed))
            mock_transcribe.assert_called_once()
            call_args = mock_transcribe.call_args
            assert call_args.kwargs.get("path_or_hf_repo") == "mlx-community/whisper-large-v3-turbo", \
                f"Expected model mlx-community/whisper-large-v3-turbo, got {call_args.kwargs}"
            assert call_args.kwargs.get("language") == "zh"

    def test_mlx_whisper_params_correct(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "参数测试", "99999999999")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "参数测试内容", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "参数测试内容", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(out), str(processed))
            m.assert_called_once()
            assert "vad_filter" not in m.call_args.kwargs, "mlx_whisper does not support vad_filter"


# ── 功能回归测试 ─────────────────────────────────────────────

class TestCliAndOutput:

    def test_output_format(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "测试标题", "11111111111")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "转录正文", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "转录正文", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_main(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        assert "===== [2026-07-01] 测试标题 =====" in content
        assert "视频文案:" in content
        assert "原文转录:" in content
        assert "转录正文" in content

    def test_processed_dedup(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "视频A", "12121212121")
        make_video_dir(str(src), "2026-07-02", "视频B", "34343434343")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"
        processed.write_text(json.dumps(["12121212121"]))

        mock_result = {"text": "内容", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "内容", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(out), str(processed))
            assert m.call_count == 1, f"Expected 1 transcription, got {m.call_count}"

        content = out.read_text(encoding="utf-8")
        assert "视频A" not in content
        assert "视频B" in content

        saved = json.loads(processed.read_text())
        assert "12121212121" in saved
        assert "34343434343" in saved

    def test_image_only_no_transcribe(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "图文条目", "56565656565", with_mp4=False)
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "", "segments": [], "language": "zh"}
        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(out), str(processed))
            m.assert_not_called()

        content = out.read_text(encoding="utf-8")
        assert "===== [2026-07-01] 图文条目 =====" in content
        assert "视频文案: 文案_图文条目" in content
        assert "原文转录: （无音频内容）" in content or "（无音频内容）" in content

    def test_failure_tolerance(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "会失败", "78787878787")
        make_video_dir(str(src), "2026-07-02", "会成功", "90909090909")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        call_count = [0]
        def side_effect(audio, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("模拟转录失败")
            return {"text": "成功转录", "segments": [
                {"id": 0, "start": 0.0, "end": 1.0, "text": "成功转录", "tokens": [], "words": []}
            ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", side_effect=side_effect):
            run_main(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        assert "会成功" in content
        assert "成功转录" in content
        saved = json.loads(processed.read_text())
        # 失败条目不会被标记为已处理（save_processed 在 try 块内）
        assert "78787878787" not in saved, "failed item should NOT be marked processed"
        assert "90909090909" in saved

    def test_missing_src_dir_graceful(self, tmp_path):
        src = tmp_path / "empty_src"; src.mkdir()
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "", "segments": [], "language": "zh"}
        with mock.patch("mlx_whisper.transcribe", return_value=mock_result) as m:
            run_main(str(src), str(out), str(processed))
            m.assert_not_called()


class TestEnvironment:

    def test_pythonpath_cleanup(self, tmp_path):
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "环境测试", "23232323232")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "环境OK", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "环境OK", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch.dict(os.environ, {"PYTHONPATH": "/dirty/path"}, clear=False):
            with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
                run_main(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        assert "环境OK" in content

    def test_hf_hub_offline_set(self, tmp_path):
        """RED: main() 必须设置 HF_HUB_OFFLINE=1，确保 huggingface_hub 完全离线。
        当前代码未设置 → 预期 RED 失败（无代理环境下会卡死）。"""
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "离线测试", "11111111112")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "离线OK", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "离线OK", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch.dict(os.environ, {}, clear=False):
            # 清掉可能已有的 HF_HUB_OFFLINE，模拟当前代码不设置的状态
            os.environ.pop("HF_HUB_OFFLINE", None)
            with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
                run_main(str(src), str(out), str(processed))
            assert os.environ.get("HF_HUB_OFFLINE") == "1", \
                "HF_HUB_OFFLINE must be set to '1' for offline transcription in China network"
