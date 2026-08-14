"""RED 测试：extract_target_frames.py 定向截帧

测试 find_video_dir（目录匹配）、extract_frames（ffmpeg 参数）、
main() 整体流程。全部 mock ffmpeg subprocess 调用。
"""
import json
import os
import sys
import tempfile
import pytest
from unittest import mock


# ── helpers ──────────────────────────────────────────────────

SAMPLE_NEEDS_JSON = {
    "items": [
        {
            "title": "2026-07-01_纳指标普7月前瞻",
            "needs_visual": True,
            "reason": "讲K线需要截图",
            "segments": [
                {"start": 5.0, "end": 8.0, "text": "看K线图", "hint": "图表"},
                {"start": 12.0, "end": 15.5, "text": "数据表格", "hint": "数据"},
            ]
        },
        {
            "title": "2026-06-23_坚持拿着就行",
            "needs_visual": False,
            "reason": "纯口播观点",
            "segments": []
        },
        {
            "title": "2025-12-01_无视频条目",
            "needs_visual": True,
            "reason": "测试",
            "segments": [{"start": 0.0, "end": 5.0, "text": "test", "hint": "test"}]
        }
    ]
}


# ── find_video_dir 测试 ──────────────────────────────────────

class TestFindVideoDir:

    def test_match_video_directory(self, tmp_path):
        """RED→GREEN: 根据条目标题匹配视频目录。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        # 创建匹配的目录（条目标题格式：日期_标题）
        item_dir = video_base / "2026-07-01_纳指标普7月前瞻_1234567890123"
        item_dir.mkdir()
        mp4 = item_dir / "test.mp4"
        mp4.write_text("fake mp4")

        result = extract_target_frames.find_video_dir(str(video_base), "2026-07-01_纳指标普7月前瞻")
        assert result is not None
        assert result.endswith(".mp4")

    def test_no_match_returns_none(self, tmp_path):
        """GREEN: 无匹配目录返回 None。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        result = extract_target_frames.find_video_dir(str(video_base), "2026-07-01_不存在")
        assert result is None

    def test_partial_title_match(self, tmp_path):
        """GREEN: 条目标题是目录名前缀时正确匹配。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        # 目录格式: 日期_标题_aweme_id
        item_dir = video_base / "2026-07-01_纳指标普7月前瞻_9999999999999"
        item_dir.mkdir()
        mp4 = item_dir / "video.mp4"
        mp4.write_text("fake")

        result = extract_target_frames.find_video_dir(str(video_base), "2026-07-01_纳指标普7月前瞻")
        assert result is not None

    def test_exact_match_preferred_over_prefix(self, tmp_path):
        """P3-6 RED→GREEN: 同名前缀歧义时精确匹配优先（而非 startswith 首个）。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        # 非精确但前缀匹配的目录（标题="投资_1abc"，排序在前）
        d1 = video_base / "2026-07-01_投资_1abc_1111111111"
        d1.mkdir()
        (d1 / "v1.mp4").write_text("fake")
        # 精确匹配的目录（标题="投资"，排序在后）
        d2 = video_base / "2026-07-01_投资_2222222222"
        d2.mkdir()
        (d2 / "v2.mp4").write_text("fake")

        result = extract_target_frames.find_video_dir(str(video_base), "2026-07-01_投资")
        assert result is not None
        assert result.endswith("v2.mp4"), (
            f"精确匹配应优先（目录标题完全一致），实际: {result}"
        )

    def test_title_sanitize_aligned_with_transcribe_single(self, tmp_path):
        """P3-6 RED→GREEN: 标题非法字符处理与 transcribe_single.sanitize_title 对齐。"""
        import extract_target_frames
        from transcribe_single import sanitize_title

        video_base = tmp_path / "videos"
        video_base.mkdir()
        # setup_video_dir 用 sanitize_title 生成目录：标题 "测试/视频" → "测试_视频"
        item_dir = video_base / f"2026-07-01_{sanitize_title('测试/视频')}_1234567890123"
        item_dir.mkdir()
        (item_dir / "v.mp4").write_text("fake")

        # needs.json 里的标题可能含原始非法字符
        result = extract_target_frames.find_video_dir(
            str(video_base), "2026-07-01_测试/视频")
        assert result is not None, "非法字符标题应与 sanitize 后的目录对齐匹配"
        assert result.endswith("v.mp4")


# ── extract_frames 测试 ──────────────────────────────────────

class TestExtractFrames:

    def test_ffmpeg_command_format(self, tmp_path):
        """RED→GREEN: ffmpeg 命令参数正确。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [
            {"start": 5.0, "end": 8.0, "text": "test", "hint": "图表"},
        ]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            n = extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2, out_dir=str(out_dir), item_name="test_item"
            )

            assert mock_run.called
            # 检查 ffmpeg 命令参数
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "ffmpeg"  # 或 "ffmpeg" 完整路径
            # 检查 -ss 和 -to 参数
            cmd_str = " ".join(call_args)
            assert "-ss" in cmd_str
            assert "-to" in cmd_str
            assert "fps=2" in cmd_str

    def test_multiple_segments(self, tmp_path):
        """GREEN: 多个时间段各自截帧。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [
            {"start": 5.0, "end": 8.0, "text": "A", "hint": "图表"},
            {"start": 12.0, "end": 15.0, "text": "B", "hint": "数据"},
        ]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            n = extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2, out_dir=str(out_dir), item_name="test"
            )

            # 应调用 2 次（每个 segment 一次）
            assert mock_run.call_count == 2

    def test_ss_before_i_for_fast_seek(self, tmp_path):
        """GREEN: -ss 放在 -i 之前实现快速定位。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [{"start": 10.0, "end": 15.0, "text": "test", "hint": "test"}]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2, out_dir=str(out_dir), item_name="test"
            )

            cmd = mock_run.call_args[0][0]
            # 找 -ss 和 -i 的位置
            ss_idx = cmd.index("-ss") if "-ss" in cmd else -1
            i_idx = cmd.index("-i") if "-i" in cmd else -1
            assert ss_idx >= 0 and i_idx >= 0
            assert ss_idx < i_idx, f"-ss should be before -i for fast seek, got cmd: {cmd}"

    def test_output_filename_format(self, tmp_path):
        """GREEN: 帧文件命名格式正确。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [{"start": 5.0, "end": 8.0, "text": "test", "hint": "图表"}]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2, out_dir=str(out_dir), item_name="my_item"
            )

            cmd = mock_run.call_args[0][0]
            cmd_str = " ".join(cmd)
            # 输出文件名应包含条目名和段落序号
            assert "my_item" in cmd_str
            # 检查输出路径在 out_dir 下
            assert str(out_dir) in cmd_str

    def test_ffmpeg_failure(self, tmp_path):
        """GREEN: ffmpeg 失败时返回 0 帧并记录。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [{"start": 5.0, "end": 8.0, "text": "test", "hint": "图表"}]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg")
            n = extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2, out_dir=str(out_dir), item_name="test"
            )
            assert n == 0

    def test_to_parameter_uses_relative_duration(self, tmp_path):
        """RED: -to 参数应为相对时长 (end-start)，而非绝对时间戳 end。
        ffmpeg 的 -ss 在 -i 前时，-to 表示从 seek 点起的时长，
        传 end（绝对秒数）会多截 start 秒，导致帧数膨胀 3-4 倍。
        """
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [
            {"start": 8.8, "end": 11.5, "text": "制度对比", "hint": "图表"},
            {"start": 22.7, "end": 30.0, "text": "数据统计", "hint": "数据"},
        ]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2,
                out_dir=str(out_dir), item_name="test"
            )

        # 每个 segment 各一次调用
        assert mock_run.call_count == 2
        for i, seg in enumerate(segments):
            cmd = mock_run.call_args_list[i][0][0]
            to_idx = cmd.index("-to") if "-to" in cmd else -1
            assert to_idx >= 0, f"seg#{i}: -to not found in {cmd}"
            to_value = float(cmd[to_idx + 1])
            expected = round(seg["end"] - seg["start"], 3)
            assert to_value == expected, (
                f"seg#{i} [{seg['start']}-{seg['end']}]: "
                f"-to should be {expected} (relative), got {to_value}"
            )

    def test_to_parameter_with_start_zero(self, tmp_path):
        """GREEN: start=0 时 -to 等于 end（退化情形，end-0=end）。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [{"start": 0.0, "end": 8.0, "text": "从头开始", "hint": "图表"}]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2,
                out_dir=str(out_dir), item_name="test"
            )

        cmd = mock_run.call_args[0][0]
        to_idx = cmd.index("-to")
        to_value = float(cmd[to_idx + 1])
        assert to_value == 8.0, f"start=0 should keep -to=8.0, got {to_value}"

    def test_to_skips_start_ge_end(self, tmp_path):
        """GREEN: start>=end 或 end-start<=0 的段跳过，不调用 ffmpeg。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [
            {"start": 5.0, "end": 5.0, "text": "零时长", "hint": "图表"},
            {"start": 10.0, "end": 8.0, "text": "倒序", "hint": "图表"},
        ]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            n = extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2,
                out_dir=str(out_dir), item_name="test"
            )

        # 两个段都应被跳过
        assert mock_run.call_count == 0
        assert n == 0

    def test_to_skips_negative_start(self, tmp_path):
        """GREEN: start<0 的段跳过。"""
        import extract_target_frames

        out_dir = tmp_path / "frames"
        out_dir.mkdir()

        segments = [
            {"start": -1.0, "end": 3.0, "text": "负起点", "hint": "图表"},
        ]

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            n = extract_target_frames.extract_frames(
                "/fake/video.mp4", segments, fps=2,
                out_dir=str(out_dir), item_name="test"
            )

        assert mock_run.call_count == 0
        assert n == 0


# ── main() 集成测试 ───────────────────────────────────────────

class TestMainIntegration:

    def test_full_pipeline(self, tmp_path):
        """RED→GREEN: 完整管线：读needs JSON→匹配视频→截帧。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        # 创建视频目录
        item_dir = video_base / "2026-07-01_纳指标普7月前瞻_1234567890"
        item_dir.mkdir()
        mp4 = item_dir / "video.mp4"
        mp4.write_text("fake mp4")

        # 写入 needs JSON
        needs_file = tmp_path / "needs.json"
        needs_file.write_text(json.dumps(SAMPLE_NEEDS_JSON, ensure_ascii=False))

        out_dir = tmp_path / "frames"

        with mock.patch.object(sys, "argv", [
            "extract_target_frames.py",
            "--video-dir", str(video_base),
            "--needs", str(needs_file),
            "--out", str(out_dir),
        ]):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(returncode=0)
                extract_target_frames.main()

        # 验证截帧目录存在
        assert (out_dir / "2026-07-01_纳指标普7月前瞻").exists()
        # needs_visual=false 的条目不截帧
        assert not (out_dir / "2026-06-23_坚持拿着就行").exists()

    def test_skip_no_video_found(self, tmp_path):
        """GREEN: 视频目录不存在时跳过并记录错误。"""
        import extract_target_frames

        video_base = tmp_path / "empty_videos"
        video_base.mkdir()

        needs_file = tmp_path / "needs.json"
        needs_file.write_text(json.dumps(SAMPLE_NEEDS_JSON, ensure_ascii=False))

        out_dir = tmp_path / "frames"

        with mock.patch.object(sys, "argv", [
            "extract_target_frames.py",
            "--video-dir", str(video_base),
            "--needs", str(needs_file),
            "--out", str(out_dir),
        ]):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(returncode=0)
                extract_target_frames.main()

        # 不应崩溃

    def test_no_needs_visual_items(self, tmp_path):
        """GREEN: 所有条目 needs_visual=false 时正常退出。"""
        import extract_target_frames

        video_base = tmp_path / "videos"
        video_base.mkdir()

        no_needs_json = {
            "items": [
                {"title": "test", "needs_visual": False, "reason": "口播", "segments": []}
            ]
        }
        needs_file = tmp_path / "needs.json"
        needs_file.write_text(json.dumps(no_needs_json))

        out_dir = tmp_path / "frames"

        with mock.patch.object(sys, "argv", [
            "extract_target_frames.py",
            "--video-dir", str(video_base),
            "--needs", str(needs_file),
            "--out", str(out_dir),
        ]):
            with mock.patch("subprocess.run") as mock_run:
                extract_target_frames.main()
            # subprocess 不应被调用（没有需要截帧的条目）
            mock_run.assert_not_called()


import subprocess
