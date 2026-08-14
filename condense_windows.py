#!/usr/bin/env python3
"""观点浓缩脚本：读取 transcribe_only.py 输出的转录汇总文件，提取滑动窗口观点。
用法: python3 condense_windows.py --src <转录汇总txt> --out <condensed.json>
"""
import argparse
import json
import re
import sys

# ── 默认结论关键词 ────────────────────────────────────────────
CLAIM_KWS = ['结论', '所以', '看好', '看空', '风险', '估值', '溢价',
             '折价', '预期', '核心', '关键', '逻辑', '本质']

# ── 数字正则：整数/小数 + 可选中文单位后缀 ──────────────────────
NUM_RE = re.compile(r'\d+(?:\.\d+)?[%万亿倍元个只亿]?')

# ── 条目分隔正则 ──────────────────────────────────────────────
ENTRY_RE = re.compile(r'^===== \[(\d{4}-\d{2}-\d{2})\]\s+(.+?)\s+=====$')

# ── 原文转录起始行 ──────────────────────────────────────────────
TRANSCRIPT_START = '原文转录:'
TIMESTAMP_START = '时间戳分段:'
NO_AUDIO_MARKER = '（无音频内容）'

# ── 主题分类关键词 ─────────────────────────────────────────────
CATEGORY_RULES = [
    ('量化', ['量化', 'AI', '因子', '回测', '算法', '模型']),
    ('宏观', ['银行', '保险', '地产', '宏观', '利率', '央行', '通胀', 'CPI', 'GDP', '就业', '非农']),
    ('心态', ['心态', '情绪', '纪律', '贪婪', '恐惧', '耐心', '坚持']),
    ('公司分析', ['估值', '财报', 'SOTP', '基本面', '利润', '营收', '现金流', 'ROE', 'PE', 'PB']),
    ('方法论', ['方法论', '体系', '框架', '策略', '方法', '原则']),
    ('市场观点', ['市场', '走势', '行情', '趋势', '看多', '看空', '牛市', '熊市']),
]


def classify_title(title):
    """根据标题关键词进行主题分类。"""
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in title.lower():
                return cat
    return '其他'


def extract_windows(text, claim_kws=None, win=70, max_windows=5):
    """从转录文本中提取滑动窗口观点。

    Args:
        text: 转录原文（不含时间戳行）
        claim_kws: 结论关键词列表，默认 CLAIM_KWS
        win: 窗口半径（字符数）
        max_windows: 每条最多提取窗口数

    Returns:
        list of dict: [{"text": "...", "num": "7月2日"}, ...]
    """
    if claim_kws is None:
        claim_kws = CLAIM_KWS

    out = []
    seen = set()
    for m in NUM_RE.finditer(text):
        if len(out) >= max_windows:
            break
        start = max(0, m.start() - win)
        end = min(len(text), m.end() + win)
        ctx = text[start:end].strip()
        if any(k in ctx for k in claim_kws) and ctx not in seen:
            out.append({"text": ctx, "num": m.group()})
            seen.add(ctx)
    return out


def parse_transcript_file(content):
    """解析转录汇总文件，返回条目列表。

    每条目: {"date": str, "title": str, "transcript": str, "has_audio": bool}
    """
    lines = content.split('\n')
    items = []
    i = 0
    current = None

    while i < len(lines):
        line = lines[i]
        m = ENTRY_RE.match(line)
        if m:
            if current is not None:
                items.append(current)
            date, title = m.groups()
            current = {"date": date, "title": title, "transcript": "", "has_audio": False}
            i += 1
            continue

        if current is None:
            i += 1
            continue

        # 在条目内收集转录文本
        stripped = line.strip()

        if stripped.startswith(TRANSCRIPT_START):
            # 读到转录行
            transcript_text = stripped[len(TRANSCRIPT_START):].strip()
            if transcript_text and transcript_text != NO_AUDIO_MARKER:
                current["transcript"] = transcript_text
                current["has_audio"] = True
            # 时间戳分段行在我们读取 transcript 之后，不参与浓缩
            # 跳过时间戳分段直到下一个条目
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if ENTRY_RE.match(next_line) or next_line.startswith(TIMESTAMP_START):
                    # 再遇到时间戳分段行时也继续跳过其内容
                    if next_line.startswith(TIMESTAMP_START):
                        i += 1
                        continue
                    break
                # 跳过时间戳分段行（以 [ 开头的行是时间戳行）
                i += 1
            continue

        i += 1

    if current is not None:
        items.append(current)

    return items


def process_items(items, claim_kws=None, win=70, max_windows=5, title_scan=False, classify=False):
    """处理条目，提取窗口并生成输出结构。

    Returns:
        dict: {"items": [...], "stats": {...}}
    """
    result_items = []
    stats = {"total": len(items), "with_windows": 0, "title_only": 0, "empty": 0}

    for idx, item in enumerate(items, 1):
        entry = {
            "idx": idx,
            "date": item["date"],
            "title": item["title"],
            "windows": [],
            "type": "empty",
        }
        if classify:
            entry["category"] = classify_title(item["title"])

        if item["has_audio"] and item["transcript"]:
            windows = extract_windows(item["transcript"], claim_kws, win, max_windows)
            if windows:
                entry["windows"] = windows
                entry["type"] = "windows"
                stats["with_windows"] += 1
            elif title_scan:
                entry["type"] = "title_only"
                stats["title_only"] += 1
            else:
                stats["empty"] += 1
        elif not item["has_audio"]:
            # 无音频内容
            stats["empty"] += 1
        else:
            # 有音频但无转录文本（不应出现，但保险）
            stats["empty"] += 1

        result_items.append(entry)

    return {"items": result_items, "stats": stats}


def main():
    ap = argparse.ArgumentParser(description="观点浓缩脚本：从转录汇总中提取滑动窗口观点")
    ap.add_argument("--src", required=True, help="转录汇总文本文件路径（transcribe_only.py 输出）")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--window", type=int, default=70, help="窗口半径字符数（默认 70）")
    ap.add_argument("--max-windows", type=int, default=5, help="每条最多提取窗口数（默认 5）")
    ap.add_argument("--keywords", type=str, default=None,
                    help="自定义结论关键词，逗号分隔（覆盖默认 CLAIM_KWS）")
    ap.add_argument("--title-scan", action="store_true",
                    help="对未抽到窗口的条目输出 title_only 类型")
    ap.add_argument("--classify", action="store_true",
                    help="按标题关键词进行主题分类")
    args = ap.parse_args()

    # 读取转录文件
    try:
        with open(args.src, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在 -- {args.src}", file=sys.stderr)
        sys.exit(1)

    # 解析关键词
    claim_kws = None
    if args.keywords:
        claim_kws = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

    # 解析条目
    items = parse_transcript_file(content)

    # 处理条目
    result = process_items(
        items,
        claim_kws=claim_kws,
        win=args.window,
        max_windows=args.max_windows,
        title_scan=args.title_scan,
        classify=args.classify,
    )

    # 输出 JSON
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
