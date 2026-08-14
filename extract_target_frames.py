#!/usr/bin/env python3
"""定向截帧：根据 analyze_visual_needs.py 的 JSON 输出，按标记时间段截帧。
用法: python3 extract_target_frames.py --video-dir <post目录> --needs <analyze的json> --out <帧输出目录>
"""
import argparse
import json
import os
import re
import subprocess
import sys


def log(msg):
    print(msg, flush=True)


def find_video_dir(video_base, item_title):
    """在 video_base 下匹配条目目录，返回 mp4 路径或 None。
    条目标题格式: YYYY-MM-DD_标题，目录格式: YYYY-MM-DD_标题_aweme_id。
    标题非法字符处理与 transcribe_single.sanitize_title 对齐；
    同名前缀歧义时精确匹配（目录标题部分完全一致）优先。
    """
    if not os.path.isdir(video_base):
        return None
    clean = re.sub(r'[/:?*<>|\\\t\n\r]+', '_', item_title).strip()
    folders = sorted(os.listdir(video_base))
    # 精确匹配优先：目录 日期_标题_aweme_id 的标题部分完全一致
    for folder in folders:
        fpath = os.path.join(video_base, folder)
        if not os.path.isdir(fpath):
            continue
        m = re.match(r"(.+)_(\d{10,})$", folder)
        if m and m.group(1) == clean:
            mp4s = [f for f in os.listdir(fpath) if f.endswith(".mp4")]
            if mp4s:
                return os.path.join(fpath, mp4s[0])
    # 前缀匹配兜底（原行为）
    for folder in folders:
        fpath = os.path.join(video_base, folder)
        if not os.path.isdir(fpath):
            continue
        if folder.startswith(clean):
            mp4s = [f for f in os.listdir(fpath) if f.endswith(".mp4")]
            if mp4s:
                return os.path.join(fpath, mp4s[0])
    return None


def extract_frames(mp4_path, segments, fps, out_dir, item_name):
    """对 segments 用 ffmpeg 截帧，返回成功帧数。
    - 每个 segment 独立调用 ffmpeg（-ss 在 -i 之前快速定位）。
    - 帧命名: <条目名>_<seg序号>_%03d.jpg
    """
    total = 0
    for idx, seg in enumerate(segments):
        start = seg["start"]
        end = seg["end"]
        if start < 0 or start >= end or end - start <= 0:
            continue
        out_pattern = os.path.join(out_dir, f"{item_name}_{idx}_%03d.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-ss", str(start), "-i", mp4_path,
                 "-to", str(round(end - start, 3)), "-vf", f"fps={fps}", out_pattern,
                 "-y", "-loglevel", "error"],
                check=True, capture_output=True, timeout=120,
            )
            # 统计生成的帧文件数
            existing = [f for f in os.listdir(out_dir)
                        if f.startswith(f"{item_name}_{idx}_") and f.endswith(".jpg")]
            total += len(existing)
        except (subprocess.CalledProcessError, FileNotFoundError,
                subprocess.TimeoutExpired) as e:
            log(f"    ✗ 截帧失败 seg#{idx} [{start}-{end}]: {e}")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-dir", required=True, help="作品目录（含日期_标题_id 子文件夹）")
    ap.add_argument("--needs", required=True, help="analyze_visual_needs.py 输出的 JSON")
    ap.add_argument("--out", required=True, help="帧输出目录")
    ap.add_argument("--fps", type=float, default=2, help="时间段内每秒截帧数")
    args = ap.parse_args()

    with open(args.needs, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    needs_items = [it for it in items if it.get("needs_visual") and it.get("segments")]

    log(f"需截帧: {len(needs_items)}/{len(items)} 条")

    total_frames = 0
    errors = []
    for item in needs_items:
        mp4 = find_video_dir(args.video_dir, item["title"])
        if not mp4:
            msg = f"未找到视频: {item['title']}"
            errors.append(msg)
            log(f"  ✗ {msg}")
            continue
        out_dir = os.path.join(args.out, item["title"])
        os.makedirs(out_dir, exist_ok=True)
        n = extract_frames(mp4, item["segments"], args.fps, out_dir, item["title"])
        total_frames += n
        log(f"  ✓ {item['title'][:40]}: {n} 帧")

    if errors:
        log(f"错误 ({len(errors)}):")
        for e in errors:
            log(f"  - {e}")

    log(f"Done: {total_frames} 帧 → {args.out}")


if __name__ == "__main__":
    main()
