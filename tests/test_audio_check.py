"""RED 测试：audio_check.py 静音配对（P3-5）。

现状 `next((x for x in ends if x > s))` 是 O(n²)，且同一 end 可能被多个
start 重复匹配（重复计数）。应改为排序后双指针，每个 end 至多配一次。
"""
import os
import pytest
from unittest import mock


class FakeResult:
    def __init__(self, stderr):
        self.stderr = stderr


def test_silent_ratio_pairs_starts_ends():
    """交错 start/end 正常配对累计。"""
    import audio_check
    stderr = (
        "[silencedetect @ 0x0] silence_start: 0.5\n"
        "[silencedetect @ 0x0] silence_end: 1.5\n"
        "[silencedetect @ 0x0] silence_start: 3.0\n"
        "[silencedetect @ 0x0] silence_end: 4.0\n"
        "  Duration: 00:00:10.00, start: 0.000000, bitrate: 0 kb/s\n"
    )
    with mock.patch("subprocess.run", return_value=FakeResult(stderr)):
        ratio = audio_check.silent_ratio("/fake.mp4")
    assert ratio == pytest.approx(0.2), f"两段静音共 2.0s / 10s = 0.2，实际 {ratio}"


def test_silent_ratio_no_duplicate_end_counting():
    """同一 end 不应被多个 start 重复计数（旧 O(n²) 缺陷）。"""
    import audio_check
    stderr = (
        "[silencedetect @ 0x0] silence_start: 1.0\n"
        "[silencedetect @ 0x0] silence_start: 2.0\n"
        "[silencedetect @ 0x0] silence_end: 5.0\n"
        "  Duration: 00:00:10.00, start: 0.000000, bitrate: 0 kb/s\n"
    )
    with mock.patch("subprocess.run", return_value=FakeResult(stderr)):
        ratio = audio_check.silent_ratio("/fake.mp4")
    # 旧实现: (5-1)+(5-2)=7.0 → 0.7（end=5.0 被重复计数）
    # 正确:    (5-1)=4.0 → 0.4
    assert ratio == pytest.approx(0.4), f"end 不应重复计数，实际 {ratio}"


def test_silent_ratio_out_of_order_ends():
    """ends 乱序时排序后仍正确配对。"""
    import audio_check
    stderr = (
        "[silencedetect @ 0x0] silence_start: 0.0\n"
        "[silencedetect @ 0x0] silence_end: 8.0\n"
        "[silencedetect @ 0x0] silence_start: 2.0\n"
        "[silencedetect @ 0x0] silence_end: 3.0\n"
        "  Duration: 00:00:10.00, start: 0.000000, bitrate: 0 kb/s\n"
    )
    with mock.patch("subprocess.run", return_value=FakeResult(stderr)):
        ratio = audio_check.silent_ratio("/fake.mp4")
    # 排序后: start=0.0→end=3.0 (+3.0)；start=2.0→end=8.0 (+6.0) = 9.0 → 0.9
    assert ratio == pytest.approx(0.9), f"排序双指针应累计 9.0s，实际 {ratio}"
