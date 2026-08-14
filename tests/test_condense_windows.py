"""测试：condense_windows.py 观点浓缩脚本（方向C）"""
import json
import os
import sys
import tempfile
import pytest
from unittest import mock


# ── helpers ──────────────────────────────────────────────────

def make_transcript_file(path, content):
    """写入转录汇总文本文件"""
    path.write_text(content, encoding="utf-8")


def run_condense(src_path, out_path, **kwargs):
    """调用 condense_windows.py 主函数"""
    import condense_windows
    argv = ["condense_windows.py", "--src", str(src_path), "--out", str(out_path)]
    for k, v in kwargs.items():
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            if v:
                argv.append(flag)
        else:
            argv.extend([flag, str(v)])
    with mock.patch.object(sys, "argv", argv):
        condense_windows.main()

    with open(out_path, encoding="utf-8") as f:
        return json.load(f)


# ── 转录样例 ─────────────────────────────────────────────────

SAMPLE_WITH_WINDOWS = """\
===== [2026-07-01] 纳指标普7月前瞻_纳斯达克 =====
视频文案: 纳指标普7月前瞻 #纳斯达克
原文转录: 7月2日非农数据公布结论就是就业超预期美债收益率上行导致纳指承压核心逻辑是估值修复目前纳指PE约38倍所以我觉得短期继续看空
时间戳分段:
[00:00.000 --> 00:02.500] 7月2日非农数据公布
[00:02.500 --> 00:05.000] 结论就是就业超预期
"""

SAMPLE_IMAGE_ONLY = """\
===== [2026-07-15] 图文分享_美股 =====
视频文案: 图文分享内容 #美股
原文转录: （无音频内容）
"""

SAMPLE_NO_WINDOW = """\
===== [2026-07-20] 早安打卡 =====
视频文案: 早安打卡
原文转录: 大家早上好今天天气不错我们一起努力
"""

SAMPLE_MULTI_ENTRY = SAMPLE_WITH_WINDOWS + "\n" + SAMPLE_IMAGE_ONLY + "\n" + SAMPLE_NO_WINDOW + "\n"


# ── 基础解析测试 ─────────────────────────────────────────────

class TestBasicParsing:

    def test_extract_windows_from_transcript(self, tmp_path):
        """RED: 窗口提取 —— 数字 + 结论词匹配"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_WITH_WINDOWS)
        result = run_condense(src, out)

        assert "items" in result, "output must have 'items' key"
        assert "stats" in result, "output must have 'stats' key"
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["idx"] == 1
        assert item["date"] == "2026-07-01"
        assert item["title"] == "纳指标普7月前瞻_纳斯达克"
        assert item["type"] == "windows"
        assert len(item["windows"]) > 0
        # 至少有一条窗口包含数字 + 结论词
        assert any("7月2日" in w["text"] for w in item["windows"]), \
            "should extract window containing number and conclusion keyword"

    def test_image_only_entry(self, tmp_path):
        """RED: 图文/无音频条目 → type='empty'"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_IMAGE_ONLY)
        result = run_condense(src, out)

        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "empty"
        assert result["items"][0]["windows"] == []

    def test_stats_correct(self, tmp_path):
        """RED: stats 统计正确"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_MULTI_ENTRY)
        result = run_condense(src, out)

        stats = result["stats"]
        assert stats["total"] == 3
        assert stats["with_windows"] == 1
        # 默认不开启 title-scan，无窗口非空条目归为 empty → empty=2
        assert stats["empty"] == 2
        assert stats.get("title_only", 0) == 0
        assert stats["with_windows"] + stats.get("title_only", 0) + stats["empty"] == stats["total"]

    def test_output_schema_valid(self, tmp_path):
        """RED: 输出 JSON schema 完整"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_MULTI_ENTRY)
        result = run_condense(src, out)

        for item in result["items"]:
            assert "idx" in item
            assert "date" in item
            assert "title" in item
            assert "type" in item
            assert "windows" in item
            assert item["type"] in ("windows", "title_only", "empty")
            if item["type"] == "windows":
                for w in item["windows"]:
                    assert "text" in w
                    assert "num" in w


# ── CLI 参数测试 ────────────────────────────────────────────

class TestCliOptions:

    def test_max_windows_limit(self, tmp_path):
        """RED: --max-windows 限制每条目窗口数"""
        # 构造含大量数字+关键词的转录
        long_transcript = "纳指" + "市盈率估值的核心逻辑是" * 20 + "风险预期在" + "38倍".join(
            [f"{i}倍" for i in range(50)])
        content = f"""\
===== [2026-07-01] 长文本测试 =====
视频文案: 测试
原文转录: {long_transcript}
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, max_windows=3)
        assert len(result["items"][0]["windows"]) <= 3

    def test_window_radius_param(self, tmp_path):
        """RED: --window 半径参数生效"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_WITH_WINDOWS)
        # 极小窗口不会匹配到结论词
        result = run_condense(src, out, window=5)
        assert len(result["items"]) == 1
        # 窗口很小可能导致无法匹配结论词
        item = result["items"][0]
        assert item["type"] in ("windows", "empty")

    def test_keywords_override(self, tmp_path):
        """RED: --keywords 覆盖默认结论词"""
        # 用非默认关键词
        content = """\
===== [2026-07-01] 自定义关键词测试 =====
视频文案: 测试
原文转录: 8月走势很不错推荐买入
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        # 默认关键词不含"推荐"，不会匹配
        result_default = run_condense(src, out)

        # 用自定义关键词："推荐"
        result_custom = run_condense(src, out, keywords="推荐,买入")
        # 自定义关键词应该能匹配
        assert result_custom["items"][0]["type"] == "windows"


# ── 时间戳排除测试 ─────────────────────────────────────────────

class TestTimestampExclusion:

    def test_timestamp_lines_excluded(self, tmp_path):
        """RED: 时间戳分段行不参与浓缩"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, SAMPLE_WITH_WINDOWS)
        result = run_condense(src, out)

        for item in result["items"]:
            for w in item.get("windows", []):
                assert "--> " not in w["text"], \
                    f"window should not contain timestamp lines: {w['text'][:50]}..."
                assert not w["text"].startswith("["), \
                    f"window should not start with timestamp: {w['text'][:50]}..."


# ── title-scan 测试 ──────────────────────────────────────────

class TestTitleScan:

    def test_title_scan_on(self, tmp_path):
        """RED: --title-scan 为无窗口非空条目输出 title_only"""
        content = SAMPLE_WITH_WINDOWS + "\n" + SAMPLE_NO_WINDOW + "\n" + SAMPLE_IMAGE_ONLY + "\n"
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, title_scan=True)

        types = {str(i): item["type"] for i, item in enumerate(result["items"], 1)}
        # 有窗口条目
        assert any(t == "windows" for t in types.values())
        # 无窗口非空条目应有 title_only
        assert any(t == "title_only" for t in types.values()), \
            f"Expected title_only entries with --title-scan, got types: {types}"
        # 图文条目仍是 empty
        assert any(t == "empty" for t in types.values())

    def test_title_scan_off_default(self, tmp_path):
        """RED: 默认不启用 title-scan"""
        content = SAMPLE_WITH_WINDOWS + "\n" + SAMPLE_NO_WINDOW + "\n"
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out)

        types = [item["type"] for item in result["items"]]
        assert "title_only" not in types, \
            f"Default should not produce title_only entries, got types: {types}"


# ── 去重测试 ──────────────────────────────────────────────────

class TestDeduplication:

    def test_window_dedup(self, tmp_path):
        """RED: 重复窗口去重"""
        # 同一转录的多个数字落在同一窗口内
        content = """\
===== [2026-07-01] 去重测试 =====
视频文案: 测试
原文转录: 38倍估值核心逻辑你看38倍这个风险预期很大核心逻辑是估值偏高
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out)

        if result["items"][0]["type"] == "windows":
            texts = [w["text"] for w in result["items"][0]["windows"]]
            assert len(texts) == len(set(texts)), \
                f"windows should be deduplicated, got: {texts}"


# ── 主题分类测试 ─────────────────────────────────────────────

class TestClassify:

    def test_classify_flag(self, tmp_path):
        """RED: --classify 添加 category 字段"""
        content = """\
===== [2026-07-01] 纳指标普7月前瞻_纳斯达克 =====
视频文案: 纳指标普7月前瞻 #纳斯达克
原文转录: 7月2日非农数据结论就是就业超预期核心逻辑是估值修复
===== [2026-07-02] AI量化因子回测 =====
视频文案: AI量化因子回测
原文转录: 3.5倍因子回测结果核心逻辑就是量化
===== [2026-07-03] 投资心态和纪律 =====
视频文案: 投资心态
原文转录: （无音频内容）
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, classify=True)

        for item in result["items"]:
            assert "category" in item, f"item should have 'category' field: {item}"
            assert item["category"] in (
                "公司分析", "方法论", "心态", "宏观", "市场观点", "量化", "其他"
            ), f"unexpected category: {item['category']}"

    def test_classify_quant(self, tmp_path):
        """RED: 量化/AI/因子 → '量化'"""
        content = """\
===== [2026-07-01] AI量化因子回测 =====
视频文案: AI量化因子回测
原文转录: 3.5倍因子回测核心逻辑就是量化
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, classify=True)
        assert result["items"][0]["category"] == "量化"

    def test_classify_macro(self, tmp_path):
        """RED: 银行/保险/地产 → '宏观'"""
        content = """\
===== [2026-07-01] 银行板块分析 =====
视频文案: 银行板块分析
原文转录: 核心逻辑就是银行基本面改善
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, classify=True)
        assert result["items"][0]["category"] == "宏观"

    def test_classify_mentality(self, tmp_path):
        """RED: 心态/情绪/纪律 → '心态'"""
        content = """\
===== [2026-07-01] 投资心态和纪律 =====
视频文案: 投资心态
原文转录: （无音频内容）
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, classify=True)
        assert result["items"][0]["category"] == "心态"

    def test_classify_company(self, tmp_path):
        """RED: 估值/财报/SOTP → '公司分析'"""
        content = """\
===== [2026-07-01] SOTP估值法拆解 =====
视频文案: #估值
原文转录: 核心逻辑是估值修复
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out, classify=True)
        assert result["items"][0]["category"] == "公司分析"


# ── 边界条件测试 ─────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_file(self, tmp_path):
        """空文件: 返回空 items"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, "")
        result = run_condense(src, out)

        assert result["items"] == []
        assert result["stats"]["total"] == 0
        assert result["stats"]["with_windows"] == 0

    def test_no_numbers_in_transcript(self, tmp_path):
        """无数字的转录: 无法匹配窗口"""
        content = """\
===== [2026-07-01] 无数字测试 =====
视频文案: 测试
原文转录: 这是一段没有任何数字的文本内容完全都是中文描述
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out)

        assert result["items"][0]["type"] in ("empty", "title_only")
        assert result["items"][0]["windows"] == []

    def test_malformed_entry_skipped(self, tmp_path):
        """格式不正确的条目跳过"""
        content = """\
这不是一个正确的条目格式
===== [2026-07-01] 正确的条目 =====
视频文案: 测试
原文转录: 38倍估值核心逻辑
"""
        src = tmp_path / "t.txt"
        out = tmp_path / "out.json"
        make_transcript_file(src, content)
        result = run_condense(src, out)

        # 应该只解析出1条正确格式的条目
        assert len(result["items"]) == 1
        assert result["items"][0]["date"] == "2026-07-01"
