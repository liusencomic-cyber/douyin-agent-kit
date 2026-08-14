"""RED 测试：转录输出应包含时间戳分段

当前现状：mlx_whisper segments 自带 start/end 时间戳，
但 transcribe_only.py 和 transcribe_archive.py 都丢弃了时间戳
（只用 "".join(s["text"] for s in result["segments"]) 拼接纯文本）。

这些测试断言输出中应有「时间戳分段:」段，格式为 [MM:SS.mmm --> MM:SS.mmm] 文本。
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
            json.dump({"desc": f"文案_{title}", "create_time": 1719705600,
                       "author": {"nickname": "测试作者"}}, f)
    return folder


def run_transcribe_only(src_dir, out_path, processed_path):
    import transcribe_only
    with mock.patch.object(sys, "argv", [
        "transcribe_only.py",
        "--src-dir", src_dir,
        "--out", out_path,
        "--processed", processed_path,
    ]):
        transcribe_only.main()


def run_transcribe_archive(src_dir, processed_path, vault_inbox, limit=0):
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


# ── RED 测试：transcribe_only.py 时间戳分段 ──────────────────

class TestTranscribeOnlyTimestamp:
    """RED: transcribe_only.py 输出现阶段无「时间戳分段:」。"""

    def test_output_lacks_timestamp_section(self, tmp_path):
        """RED: 当前输出没有时间戳分段 —— 等实现后此测试应反转。"""
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "时间戳测试", "11111111111")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "这是测试转录内容。", "segments": [
            {"id": 0, "start": 0.0, "end": 1.36, "text": "这是测试转录内容。", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_only(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        # RED 断言：当前输出没有时间戳分段
        shown = bool(re.search(r"时间戳分段:", content))
        # 现阶段为 False（RED），GREEN 后改为 assert shown
        if not shown:
            pytest.fail("RED: 输出无「时间戳分段:」段 —— 需实现时间戳输出")

    def test_timestamp_format_after_fix(self, tmp_path):
        """RED→GREEN: 时间戳格式应为 [MM:SS.mmm --> MM:SS.mmm] 文本。"""
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "格式测试", "22222222222")
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_segments = [
            {"id": 0, "start": 0.0, "end": 1.36, "text": "第一段。", "tokens": [], "words": []},
            {"id": 1, "start": 1.36, "end": 3.0, "text": "第二段。", "tokens": [], "words": []},
        ]
        mock_result = {"text": "第一段。第二段。", "segments": mock_segments, "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_only(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        # 检查格式
        import re
        assert re.search(r"时间戳分段:", content), "缺少「时间戳分段:」标题"
        assert "[00:00.000 --> 00:01.360]" in content, f"第一段时间戳格式不对，内容: {content[:500]}"
        assert "[00:01.360 --> 00:03.000]" in content, f"第二段时间戳格式不对"
        assert "第一段。" in content
        assert "第二段。" in content

    def test_no_audio_output_no_timestamps(self, tmp_path):
        """GREEN: 无音频/图文条目不输出时间戳段。"""
        src = tmp_path / "src"; src.mkdir()
        make_video_dir(str(src), "2026-07-01", "图文条目", "33333333333", with_mp4=False)
        out = tmp_path / "out.txt"
        processed = tmp_path / "p.json"

        mock_result = {"text": "", "segments": [], "language": "zh"}
        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_only(str(src), str(out), str(processed))

        content = out.read_text(encoding="utf-8")
        assert "（无音频内容）" in content
        # 图文条目无音频，不应有时间戳分段
        lines_after_no_audio = content.split("（无音频内容）")[1] if "（无音频内容）" in content else ""
        assert "时间戳分段:" not in lines_after_no_audio, \
            "图文条目不应有时间戳分段"


# ── RED 测试：transcribe_archive.py 时间戳分段 ──────────────────

class TestTranscribeArchiveTimestamp:
    """RED: transcribe_archive.py 笔记现阶段无时间戳分段。"""

    def test_note_lacks_timestamp_section(self, tmp_path):
        """RED: 当前 Obsidian 笔记没有时间戳分段。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "收藏格式", "98765432101")
        processed = tmp_path / "p.json"

        mock_result = {"text": "收藏转录内容。", "segments": [
            {"id": 0, "start": 0.0, "end": 2.0, "text": "收藏转录内容。", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_archive(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text(encoding="utf-8")
        # RED 断言：当前笔记没有时间戳分段
        if "时间戳分段" not in content:
            pytest.fail("RED: Obsidian 笔记无「时间戳分段」章节 —— 需实现")

    def test_note_timestamp_format(self, tmp_path):
        """RED→GREEN: 笔记中时间戳格式正确。"""
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "笔记格式", "11111111101")
        processed = tmp_path / "p.json"

        mock_segments = [
            {"id": 0, "start": 0.0, "end": 1.5, "text": "分段一。", "tokens": [], "words": []},
            {"id": 1, "start": 1.5, "end": 3.2, "text": "分段二。", "tokens": [], "words": []},
        ]
        mock_result = {"text": "分段一。分段二。", "segments": mock_segments, "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_archive(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text(encoding="utf-8")
        assert "## 时间戳分段" in content, "缺少「## 时间戳分段」章节"
        assert "[00:00.000 --> 00:01.500]" in content
        assert "[00:01.500 --> 00:03.200]" in content

    def test_transcribe_returns_segments(self, tmp_path):
        """RED: transcribe_archive.transcribe() 当前只返回纯文本字符串。
        GREEN: 应返回 (text, segments) 元组以便下游使用时间戳。"""
        # 此测试验证 transcribe() 返回值的结构
        import transcribe_archive
        from unittest import mock

        mock_result = {"text": "测试", "segments": [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "测试", "tokens": [], "words": []}
        ], "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(returncode=0)
                with mock.patch("tempfile.NamedTemporaryFile"):
                    # 不能直接调用 transcribe，因为它用临时文件
                    # 改为检查 main() 中调用 transcribe 后是否正确拿到 segments
                    pass

        # 直接测 transcribe 函数返回值类型
        # 当前 transcribe 返回 str，RED 阶段此断言会通过
        # GREEN 阶段 transcribe 要改为返回 (str, list) 元组
        # 此测试用 mock 绕过文件操作
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        src.mkdir(); vault.mkdir()
        make_video_dir(str(src), "2026-07-01", "返回值", "12121212121")
        processed = tmp_path / "p.json"

        mock_segments = [
            {"id": 0, "start": 0.0, "end": 1.0, "text": "返回值测试", "tokens": [], "words": []}
        ]
        mock_result = {"text": "返回值测试", "segments": mock_segments, "language": "zh"}

        with mock.patch("mlx_whisper.transcribe", return_value=mock_result):
            run_transcribe_archive(str(src), str(processed), str(vault))

        md_files = list(vault.glob("*.md"))
        assert len(md_files) == 1
        content = md_files[0].read_text(encoding="utf-8")
        # GREEN 后应包含时间戳分段
        assert "## 时间戳分段" in content, \
            "RED: transcribe() 未返回 segments，笔记无时间戳"


# ── 时间戳格式化函数测试 ──────────────────────────────────────

class TestFormatTimestamp:
    """测试秒 → HH:MM:SS.mmm / MM:SS.mmm 格式化。"""

    def test_format_seconds_basic(self):
        """基本格式化：秒转 MM:SS.mmm。"""
        # 此函数应实现在 transcribe_only.py 或共享模块中
        # 先用内联实现测试逻辑
        def format_ts(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
            return f"{minutes:02d}:{secs:06.3f}"

        assert format_ts(0.0) == "00:00.000"
        assert format_ts(1.36) == "00:01.360"
        assert format_ts(61.5) == "01:01.500"
        assert format_ts(3661.0) == "01:01:01.000"

    def test_format_edge_cases(self):
        """边界情况。"""
        def format_ts(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
            return f"{minutes:02d}:{secs:06.3f}"

        assert format_ts(0.001) == "00:00.001"
        assert format_ts(59.999) == "00:59.999"
        assert format_ts(3599.999) == "59:59.999"
        assert format_ts(3600.0) == "01:00:00.000"


# 需要 re 模块
import re
