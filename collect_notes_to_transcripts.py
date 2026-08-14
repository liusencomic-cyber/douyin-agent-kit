#!/usr/bin/env python3
"""从已写入 Obsidian 的逐条笔记中按 aweme_id 提取转录文本，合并进汇总文件（用于终版蒸馏）。
用法: python3 collect_notes_to_transcripts.py --processed <json> --inbox <dir> --out <汇总txt>
"""
import argparse, json, os, re, datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", required=True, help="processed json（aweme_id 列表）")
    ap.add_argument("--inbox", required=True, help="Obsidian inbox 目录")
    ap.add_argument("--out", required=True, help="汇总转录文本输出（追加）")
    args = ap.parse_args()

    with open(args.processed) as f:
        ids = set(json.load(f))
    print(f"目标 aweme_id 数: {len(ids)}")

    # 建 id → (日期, 标题) 映射，从已有汇总文件或 post 目录获取（此处只依赖笔记本身）
    # 遍历 inbox 所有 md，按来源链接里的 /video/{id} 匹配
    found = {}
    for fn in os.listdir(args.inbox):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(args.inbox, fn)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        m = re.search(r"douyin\.com/video/(\d{10,})", content)
        if not m:
            continue
        aid = m.group(1)
        if aid not in ids:
            continue
        # 提取 视频文案 与 原文转录 段
        desc = ""
        tr = ""
        dm = re.search(r"## 视频文案（作者自述）\n\n(.*?)\n\n## 原文转录", content, re.S)
        if dm:
            desc = dm.group(1).strip()
        tm = re.search(r"## 原文转录（Whisper）\n\n(.*?)\n\n---", content, re.S)
        if tm:
            tr = tm.group(1).strip()
        date = fn[:10]
        title = fn[11:-3]
        found[aid] = (date, title, desc, tr)

    print(f"匹配到笔记: {len(found)}/{len(ids)}")
    missing = ids - set(found)
    if missing:
        print("未匹配（可能转录失败或无视频）:", sorted(missing)[:10], f"...共{len(missing)}")

    # 追加到汇总文件（若已存在同 id 则跳过——先读已有内容）
    existing = ""
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            existing = f.read()
    have_ids = set(re.findall(r"===== \[\d{4}-\d{2}-\d{2}\] .*?(\d{10,})?$", existing, re.M)) if False else set()
    # 简单去重：按标题行匹配
    existing_titles = set(re.findall(r"^===== \[([\d-]+)\] (.+) =====$", existing, re.M))

    with open(args.out, "a", encoding="utf-8") as out:
        n = 0
        for aid in sorted(found):
            date, title, desc, tr = found[aid]
            key = (date, title)
            if key in existing_titles:
                continue
            out.write(f"===== [{date}] {title} =====\n")
            out.write(f"视频文案: {desc}\n")
            out.write(f"原文转录: {tr if tr else '（无音频内容）'}\n\n")
            existing_titles.add(key)
            n += 1
    print(f"新增写入汇总: {n} 条")

if __name__ == "__main__":
    main()
