"""测试：transcribe_single.py 单条视频智能转录适配器（RED → GREEN）"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import pytest
from unittest import mock
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────

def make_dummy_mp4(path, size=1024):
    """创建一个占位 mp4 文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x00" * size)


def make_dummy_transcript(path, content=""):
    """创建占位转录文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not content:
        content = "===== [2026-07-01] 测试视频 =====\n视频文案: 测试文案\n原文转录: 测试转录内容\n时间戳分段:\n[00:00.000 --> 00:02.000] 测试内容\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_dummy_needs_json(path, needs_visual=True):
    """创建占位 needs.json。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "items": [{
            "title": "2026-07-01_测试视频",
            "needs_visual": needs_visual,
            "reason": "测试判断理由",
            "segments": [{"start": 0.0, "end": 2.0, "text": "测试内容", "hint": "图表"}],
            "heuristic": True,
            "llm_verdict": needs_visual,
            "heuristic_keywords": ["对比"],
        }]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ── aweme_id 提取 ──────────────────────────────────────────

class TestAwemeIdExtraction:
    """测试 mp4 文件名中提取 aweme_id 的逻辑。"""

    def test_extract_from_standard_name(self):
        """从标准命名 /tmp/douyin_1234567890123456789.mp4 提取 aweme_id。"""
        from transcribe_single import extract_aweme_id_from_mp4
        result = extract_aweme_id_from_mp4("/tmp/douyin_1234567890123456789.mp4")
        assert result == "1234567890123456789"

    def test_extract_from_path_with_dirs(self):
        """从含目录路径提取 aweme_id。"""
        from transcribe_single import extract_aweme_id_from_mp4
        result = extract_aweme_id_from_mp4("/some/deep/path/douyin_7659023070690752114.mp4")
        assert result == "7659023070690752114"

    def test_fallback_when_no_match(self):
        """无法匹配时返回时间戳字符串（长度≥13）。"""
        from transcribe_single import extract_aweme_id_from_mp4
        result = extract_aweme_id_from_mp4("/tmp/random_video.mp4")
        # 回退到时间戳，应该是纯数字且长度合理
        assert re.match(r"^\d{10,}$", result), f"fallback should be timestamp digits, got: {result}"

    def test_fallback_unique(self):
        """两次回退值应不同。"""
        from transcribe_single import extract_aweme_id_from_mp4
        r1 = extract_aweme_id_from_mp4("/tmp/a.mp4")
        r2 = extract_aweme_id_from_mp4("/tmp/b.mp4")
        assert r1 != r2, "fallback timestamps should be unique"


# ── 目录结构 ────────────────────────────────────────────

class TestDirectoryStructure:
    """测试 日期_标题_awemeid 目录结构的创建。"""

    def test_creates_correct_dir_name(self, tmp_path):
        """验证创建的目录名格式为 日期_标题_awemeid。"""
        from transcribe_single import setup_video_dir
        mp4_path = str(tmp_path / "douyin_1234567890123456789.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = setup_video_dir(work_dir, mp4_path, "测试标题", "2026-07-01", "1234567890123456789")
        assert os.path.isdir(video_dir)
        assert os.path.basename(video_dir) == "2026-07-01_测试标题_1234567890123456789"
        assert video_dir.startswith(work_dir)

    def test_copies_mp4_into_dir(self, tmp_path):
        """验证 mp4 被复制到目标目录。"""
        from transcribe_single import setup_video_dir
        mp4_path = str(tmp_path / "douyin_1234567890123456789.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = setup_video_dir(work_dir, mp4_path, "标题A", "2026-07-01", "1234567890123456789")
        mp4s = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
        assert len(mp4s) >= 1, f"No mp4 found in {video_dir}, contents: {os.listdir(video_dir)}"

    def test_sanitizes_title(self, tmp_path):
        """验证标题中的特殊字符被清理（不能有 /: 等文件名非法字符）。"""
        from transcribe_single import setup_video_dir
        mp4_path = str(tmp_path / "douyin_1234567890123456789.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = setup_video_dir(work_dir, mp4_path, "标题/有:特殊?字符", "2026-07-01", "1234567890123456789")
        dirname = os.path.basename(video_dir)
        assert "/" not in dirname
        assert ":" not in dirname
        assert "?" not in dirname


# ── 管道调用 ────────────────────────────────────────────

class TestPipelineCalls:
    """测试完整管道：transcribe_only → analyze_visual_needs → extract_target_frames 调用流程。"""

    def test_full_pipeline_call_order(self, tmp_path):
        """验证三个组件按正确顺序调用，且参数正确。"""
        from transcribe_single import run_pipeline
        mp4_path = str(tmp_path / "douyin_7659023070690752114.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = os.path.join(work_dir, "2026-07-01_测试视频_7659023070690752114")
        os.makedirs(video_dir)
        shutil.copy2(mp4_path, os.path.join(video_dir, "7659023070690752114.mp4"))

        transcript_path = os.path.join(work_dir, "transcripts.txt")
        processed_path = os.path.join(work_dir, "processed.json")
        needs_path = os.path.join(work_dir, "needs.json")
        frames_dir = os.path.join(work_dir, "frames")

        make_dummy_transcript(transcript_path)
        make_dummy_needs_json(needs_path, needs_visual=True)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            result = run_pipeline(
                work_dir=work_dir,
                video_dir=video_dir,
                mp4_path=mp4_path,
                title="测试视频",
                date="2026-07-01",
                aweme_id="7659023070690752114",
                skip_judge=False,
                fps=2,
            )

        # 验证 subprocess.run 被调用至少3次（transcribe，analyze，extract）
        calls = mock_run.call_args_list
        assert len(calls) >= 3, f"Expected at least 3 subprocess calls, got {len(calls)}"

        # 第1次：transcribe_only.py
        args0 = calls[0][0][0] if calls[0][0] else []
        assert any("transcribe_only.py" in a for a in args0), f"Call 1 should be transcribe_only, got {args0}"

        # 第2次：analyze_visual_needs.py
        args1 = calls[1][0][0] if calls[1][0] else []
        assert any("analyze_visual_needs.py" in a for a in args1), f"Call 2 should be analyze_visual_needs, got {args1}"

        # 第3次：extract_target_frames.py
        args2 = calls[2][0][0] if calls[2][0] else []
        assert any("extract_target_frames.py" in a for a in args2), f"Call 3 should be extract_target_frames, got {args2}"

        # 验证结果
        assert result.get("transcript_path") == transcript_path
        assert result.get("needs_visual") is True
        assert "测试判断理由" in result.get("reason", "")

    def test_transcribe_only_args(self, tmp_path):
        """验证 transcribe_only.py 调用参数。"""
        from transcribe_single import run_pipeline
        mp4_path = str(tmp_path / "douyin_1111111111111111111.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = os.path.join(work_dir, "2026-07-01_测试_1111111111111111111")
        os.makedirs(video_dir)
        shutil.copy2(mp4_path, os.path.join(video_dir, "1111111111111111111.mp4"))

        transcript_path = os.path.join(work_dir, "transcripts.txt")
        processed_path = os.path.join(work_dir, "processed.json")
        needs_path = os.path.join(work_dir, "needs.json")
        frames_dir = os.path.join(work_dir, "frames")

        make_dummy_transcript(transcript_path, "")
        make_dummy_needs_json(needs_path, needs_visual=False)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            run_pipeline(
                work_dir=work_dir,
                video_dir=video_dir,
                mp4_path=mp4_path,
                title="测试",
                date="2026-07-01",
                aweme_id="1111111111111111111",
                skip_judge=False,
                fps=2,
            )

        # 检查 transcribe_only 调用的参数
        transcribe_call = mock_run.call_args_list[0]
        args_list = transcribe_call[0][0]
        # 验证 --src-dir
        src_idx = args_list.index("--src-dir") if "--src-dir" in args_list else -1
        assert src_idx >= 0
        assert args_list[src_idx + 1] == work_dir
        # 验证 --out
        out_idx = args_list.index("--out") if "--out" in args_list else -1
        assert out_idx >= 0
        # 验证 --processed
        proc_idx = args_list.index("--processed") if "--processed" in args_list else -1
        assert proc_idx >= 0

    def test_skip_judge_flag(self, tmp_path):
        """验证 --skip-judge 跳过语义判断和截帧。"""
        from transcribe_single import run_pipeline
        mp4_path = str(tmp_path / "douyin_2222222222222222222.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = os.path.join(work_dir, "2026-07-01_口播_2222222222222222222")
        os.makedirs(video_dir)
        shutil.copy2(mp4_path, os.path.join(video_dir, "2222222222222222222.mp4"))

        transcript_path = os.path.join(work_dir, "transcripts.txt")
        make_dummy_transcript(transcript_path, "")

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            result = run_pipeline(
                work_dir=work_dir,
                video_dir=video_dir,
                mp4_path=mp4_path,
                title="口播",
                date="2026-07-01",
                aweme_id="2222222222222222222",
                skip_judge=True,
                fps=2,
            )

        # 只有 transcribe_only 调用
        calls = mock_run.call_args_list
        assert len(calls) == 1, f"Expected 1 subprocess call with skip_judge, got {len(calls)}"
        args0 = calls[0][0][0] if calls[0][0] else []
        assert any("transcribe_only.py" in a for a in args0)

        # 结果不应包含 needs_visual
        assert result.get("needs_visual") is None

    def test_no_extract_when_needs_visual_false(self, tmp_path):
        """验证 needs_visual=false 时不调用 extract_target_frames。"""
        from transcribe_single import run_pipeline
        mp4_path = str(tmp_path / "douyin_3333333333333333333.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = str(tmp_path / "work")
        video_dir = os.path.join(work_dir, "2026-07-01_闲聊_3333333333333333333")
        os.makedirs(video_dir)
        shutil.copy2(mp4_path, os.path.join(video_dir, "3333333333333333333.mp4"))

        transcript_path = os.path.join(work_dir, "transcripts.txt")
        processed_path = os.path.join(work_dir, "processed.json")
        needs_path = os.path.join(work_dir, "needs.json")

        make_dummy_transcript(transcript_path, "")
        make_dummy_needs_json(needs_path, needs_visual=False)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            result = run_pipeline(
                work_dir=work_dir,
                video_dir=video_dir,
                mp4_path=mp4_path,
                title="闲聊",
                date="2026-07-01",
                aweme_id="3333333333333333333",
                skip_judge=False,
                fps=2,
            )

        # 应该有 transcribe_only + analyze，没有 extract
        calls = mock_run.call_args_list
        assert len(calls) == 2, f"Expected 2 calls (transcribe + analyze), got {len(calls)}"
        args1 = calls[1][0][0] if calls[1][0] else []
        assert any("analyze_visual_needs.py" in a for a in args1)
        # 不应该有 extract
        for call in calls:
            args = call[0][0] if call[0] else []
            assert not any("extract_target_frames.py" in a for a in args), \
                "extract_target_frames should NOT be called when needs_visual=false"


# ── 输出汇总 ────────────────────────────────────────────

class TestOutputSummary:
    """测试 stdout 输出汇总信息。"""

    def test_summary_contains_transcript_path(self, tmp_path, capsys):
        """验证汇总输出包含转录文本路径。"""
        from transcribe_single import print_summary
        result = {
            "transcript_path": "/tmp/work/transcripts.txt",
            "needs_visual": True,
            "reason": "含图表数据",
            "frames_dir": "/tmp/work/frames",
            "frame_count": 5,
            "title": "测试视频",
            "date": "2026-07-01",
            "aweme_id": "1234567890123456789",
        }
        print_summary(result)
        captured = capsys.readouterr()
        assert "/tmp/work/transcripts.txt" in captured.out
        assert "needs_visual" in captured.out.lower() or "画面需求" in captured.out

    def test_summary_skip_judge(self, tmp_path, capsys):
        """验证 skip_judge 模式的汇总。"""
        from transcribe_single import print_summary
        result = {
            "transcript_path": "/tmp/work/transcripts.txt",
            "needs_visual": None,
            "reason": "",
            "frames_dir": "",
            "frame_count": 0,
            "title": "口播视频",
            "date": "2026-07-01",
            "aweme_id": "1234567890123456789",
        }
        print_summary(result)
        captured = capsys.readouterr()
        assert "已跳过" in captured.out or "skip" in captured.out.lower()


# ── 工作目录清理 ────────────────────────────────────────

class TestWorkDirCleanup:
    """测试工作目录清理逻辑。"""

    def test_cleanup_removes_work_dir(self):
        """验证默认清理工作目录（合法 /tmp 下 douyin 前缀子目录）。"""
        from transcribe_single import cleanup_work_dir
        work_dir = os.path.join("/tmp", f"douyin_test_cleanup_{os.getpid()}")
        os.makedirs(work_dir, exist_ok=True)
        try:
            with open(os.path.join(work_dir, "test.txt"), "w") as f:
                f.write("hello")
            cleanup_work_dir(work_dir, keep=False)
            assert not os.path.exists(work_dir)
        finally:
            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    def test_keep_work_preserves_dir(self):
        """验证 --keep-work 保留目录。"""
        from transcribe_single import cleanup_work_dir
        work_dir = os.path.join("/tmp", f"douyin_test_keep_{os.getpid()}")
        os.makedirs(work_dir, exist_ok=True)
        try:
            with open(os.path.join(work_dir, "test.txt"), "w") as f:
                f.write("hello")
            cleanup_work_dir(work_dir, keep=True)
            assert os.path.exists(work_dir)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


class TestWorkDirSafety:
    """RED 测试：rmtree 安全边界 — 拒绝删除危险路径（/、~、仓库根），绝不 rmtree。"""

    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_rejects_root(self):
        from transcribe_single import _is_safe_work_dir
        assert _is_safe_work_dir("/") is False

    def test_rejects_home(self):
        from transcribe_single import _is_safe_work_dir
        assert _is_safe_work_dir(os.path.expanduser("~")) is False

    def test_rejects_repo_root(self):
        """仓库根路径禁止删除（basename 虽以 douyin 开头，但等于仓库根本身）。"""
        from transcribe_single import _is_safe_work_dir
        assert _is_safe_work_dir(self.REPO_ROOT) is False

    def test_accepts_tmp_douyin_subdir(self):
        """/tmp 下 douyin 前缀子目录是合法工作目录。"""
        from transcribe_single import _is_safe_work_dir
        assert _is_safe_work_dir("/tmp/douyin_single_work") is True

    def test_rejects_root_without_rmtree(self):
        """cleanup_work_dir('/') 必须抛 ValueError 且绝不调用 rmtree。"""
        from transcribe_single import cleanup_work_dir
        with mock.patch("transcribe_single.shutil.rmtree") as m_rm:
            with pytest.raises(ValueError):
                cleanup_work_dir("/", keep=False)
            m_rm.assert_not_called()

    def test_rejects_home_without_rmtree(self):
        from transcribe_single import cleanup_work_dir
        with mock.patch("transcribe_single.shutil.rmtree") as m_rm:
            with pytest.raises(ValueError):
                cleanup_work_dir(os.path.expanduser("~"), keep=False)
            m_rm.assert_not_called()

    def test_rejects_repo_root_without_rmtree(self):
        from transcribe_single import cleanup_work_dir
        with mock.patch("transcribe_single.shutil.rmtree") as m_rm:
            with pytest.raises(ValueError):
                cleanup_work_dir(self.REPO_ROOT, keep=False)
            m_rm.assert_not_called()

    def test_cleanup_allows_tmp_douyin_dir(self):
        """合法 /tmp 下 douyin 前缀目录正常清理。"""
        from transcribe_single import cleanup_work_dir
        work_dir = os.path.join("/tmp", f"douyin_test_cleanup_safe_{os.getpid()}")
        os.makedirs(work_dir, exist_ok=True)
        try:
            cleanup_work_dir(work_dir, keep=False)
            assert not os.path.exists(work_dir)
        finally:
            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)


# ── 输出持久化（P0-2）──────────────────────────────────────

class TestPersistOutputs:
    """RED→GREEN: 默认清理 work_dir 前，产物必须复制到持久 out-dir（防路径幽灵）。"""

    def test_persist_copies_outputs_and_updates_paths(self, tmp_path):
        """persist_outputs 把转录/判断/帧文件复制到 out-dir，并更新 result 路径。"""
        from transcribe_single import persist_outputs
        work_dir = tmp_path / "work"; work_dir.mkdir()
        out_dir = tmp_path / "out"
        (work_dir / "transcripts.txt").write_text("T", encoding="utf-8")
        (work_dir / "needs.json").write_text("{}", encoding="utf-8")
        frames = work_dir / "frames"; frames.mkdir()
        (frames / "f1.jpg").write_bytes(b"x")

        result = {
            "transcript_path": str(work_dir / "transcripts.txt"),
            "needs_visual": True,
            "reason": "含图表",
            "frames_dir": str(frames),
            "frame_count": 1,
            "title": "测试",
            "date": "2026-07-01",
            "aweme_id": "1234567890123",
        }
        new = persist_outputs(str(work_dir), str(out_dir), result)

        assert (out_dir / "transcripts.txt").exists()
        assert (out_dir / "needs.json").exists()
        assert (out_dir / "frames" / "f1.jpg").exists()
        assert new["transcript_path"] == str(out_dir / "transcripts.txt")
        assert new["frames_dir"] == str(out_dir / "frames")

    def test_main_persists_outputs_work_dir_cleaned(self, tmp_path, capsys):
        """跑通 pipeline（mock）后：产物落 out-dir；work_dir 被清理但 out-dir 产物在。"""
        import transcribe_single
        mp4_path = str(tmp_path / "douyin_5555555555555555555.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = f"/tmp/douyin_test_persist_{os.getpid()}"
        out_dir = str(tmp_path / "out")

        def side_effect(cmd, **kwargs):
            if any("transcribe_only.py" in a for a in cmd):
                os.makedirs(work_dir, exist_ok=True)
                make_dummy_transcript(os.path.join(work_dir, "transcripts.txt"))
                with open(os.path.join(work_dir, "processed.json"), "w") as f:
                    json.dump([], f)
            elif any("analyze_visual_needs.py" in a for a in cmd):
                make_dummy_needs_json(os.path.join(work_dir, "needs.json"),
                                      needs_visual=True)
            elif any("extract_target_frames.py" in a for a in cmd):
                frames = os.path.join(work_dir, "frames")
                os.makedirs(frames, exist_ok=True)
                with open(os.path.join(frames, "f1.jpg"), "wb") as f:
                    f.write(b"x")
            return mock.MagicMock(returncode=0)

        with mock.patch("subprocess.run", side_effect=side_effect):
            with mock.patch.object(sys, "argv", [
                "transcribe_single.py", "--mp4", mp4_path,
                "--title", "持久化测试", "--date", "2026-07-01",
                "--work-dir", work_dir, "--out-dir", out_dir,
            ]):
                try:
                    transcribe_single.main()
                except SystemExit:
                    pass

        # out-dir 产物在（转录/判断/帧）
        assert os.path.exists(os.path.join(out_dir, "transcripts.txt")), \
            "转录产物应落 out-dir"
        assert os.path.exists(os.path.join(out_dir, "needs.json")), "判断产物应落 out-dir"
        assert os.path.exists(os.path.join(out_dir, "frames", "f1.jpg")), \
            "帧产物应落 out-dir"
        # work_dir 被清理
        assert not os.path.exists(work_dir), "work_dir 应被清理"
        # 汇总打印的是持久路径
        captured = capsys.readouterr().out
        assert os.path.join(out_dir, "transcripts.txt") in captured, \
            "汇总应打印持久化后的转录路径"

    def test_default_out_dir_is_repo_output(self):
        """默认 --out-dir 为仓库根下 output/。"""
        from transcribe_single import parse_args
        with mock.patch.object(sys, "argv", [
            "transcribe_single.py", "--mp4", "/tmp/douyin_123.mp4",
        ]):
            args = parse_args()
        assert args.out_dir == os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


# ── 环境变量 ────────────────────────────────────────────

class TestEnvironment:
    """测试环境变量设置。"""

    def test_hf_hub_offline_set_in_main(self, tmp_path):
        """验证 main() 入口设置 HF_HUB_OFFLINE=1。"""
        import transcribe_single
        mp4_path = str(tmp_path / "douyin_4444444444444444444.mp4")
        make_dummy_mp4(mp4_path)
        work_dir = f"/tmp/douyin_test_hf_{os.getpid()}"

        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("subprocess.run") as mock_run:
                mock_run.return_value = mock.MagicMock(returncode=0)
                with mock.patch.object(sys, "argv", [
                    "transcribe_single.py",
                    "--mp4", mp4_path,
                    "--title", "环境测试",
                    "--date", "2026-07-01",
                    "--work-dir", work_dir,
                    "--skip-judge",
                ]):
                    transcribe_single.main()
            assert os.environ.get("HF_HUB_OFFLINE") == "1", \
                "HF_HUB_OFFLINE must be set to '1' in main()"


# ── CLI 参数解析 ────────────────────────────────────────

class TestCliArgs:
    """测试命令行参数解析。"""

    def test_default_values(self):
        """验证默认参数值。"""
        from transcribe_single import parse_args
        with mock.patch.object(sys, "argv", [
            "transcribe_single.py",
            "--mp4", "/tmp/douyin_123.mp4",
        ]):
            args = parse_args()
        assert args.mp4 == "/tmp/douyin_123.mp4"
        assert args.title is None
        assert args.date is not None  # 默认为今天
        assert args.work_dir == "/tmp/douyin_single_work"
        assert args.skip_judge is False
        assert args.fps == 2

    def test_full_args(self):
        """验证全部显式参数。"""
        from transcribe_single import parse_args
        with mock.patch.object(sys, "argv", [
            "transcribe_single.py",
            "--mp4", "/tmp/douyin_456.mp4",
            "--title", "自定义标题",
            "--date", "2026-07-15",
            "--work-dir", "/tmp/custom_work",
            "--skip-judge",
            "--fps", "3",
        ]):
            args = parse_args()
        assert args.mp4 == "/tmp/douyin_456.mp4"
        assert args.title == "自定义标题"
        assert args.date == "2026-07-15"
        assert args.work_dir == "/tmp/custom_work"
        assert args.skip_judge is True
        assert args.fps == 3
