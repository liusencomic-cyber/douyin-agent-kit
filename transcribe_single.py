#!/usr/bin/env python3
"""单条视频智能转录适配器：mp4 → 日期_标题_id目录 → GPU转录 → 语义判断 → 定向截帧。
用法: python3 transcribe_single.py --mp4 <视频路径> [--title <标题>] [--date <YYYY-MM-DD>]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date as date_type
from pathlib import Path

# ── 脚本本尊所在目录，用于定位组件 ──
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHON = sys.executable  # 复用同一个解释器


def log(msg):
    print(msg, flush=True)


def extract_aweme_id_from_mp4(mp4_path):
    """从 /tmp/douyin_<ID>.mp4 提取 aweme_id；提取不到用毫秒时间戳兜底。"""
    basename = os.path.basename(mp4_path)
    # 去掉 .mp4 扩展名
    stem = re.sub(r"\.mp4$", "", basename, count=1, flags=re.IGNORECASE)
    m = re.search(r"douyin_(\d{10,})", stem)
    if m:
        return m.group(1)
    # 兜底：纳秒时间戳（保证唯一）
    return str(time.time_ns())


def sanitize_title(title):
    """清理标题中的文件名非法字符。"""
    # 替换 / : ? * < > | \ 以及换行/制表符
    return re.sub(r'[/:?*<>|\\\t\n\r]+', '_', title).strip()


def setup_video_dir(work_dir, mp4_path, title, date, aweme_id):
    """在 work_dir 下创建 日期_标题_aweme_id 子目录并复制 mp4 进去。
    返回视频目录路径。
    """
    clean_title = sanitize_title(title)
    dir_name = f"{date}_{clean_title}_{aweme_id}"
    video_dir = os.path.join(work_dir, dir_name)
    os.makedirs(video_dir, exist_ok=True)

    # 复制 mp4 到目标目录
    dest_mp4 = os.path.join(video_dir, os.path.basename(mp4_path))
    if not os.path.exists(dest_mp4):
        shutil.copy2(mp4_path, dest_mp4)
    return video_dir


def run_pipeline(work_dir, video_dir, mp4_path, title, date, aweme_id, skip_judge=False, fps=2):
    """执行转录 → 语义判断 → 定向截帧 管道。
    返回汇总 dict。
    """
    transcript_path = os.path.join(work_dir, "transcripts.txt")
    processed_path = os.path.join(work_dir, "processed.json")
    needs_path = os.path.join(work_dir, "needs.json")
    frames_dir = os.path.join(work_dir, "frames")

    result = {
        "transcript_path": transcript_path,
        "needs_visual": None,
        "reason": "",
        "frames_dir": "",
        "frame_count": 0,
        "title": title,
        "date": date,
        "aweme_id": aweme_id,
    }

    script_dir = _SCRIPT_DIR

    # ── 1. GPU 转录 ──
    log(f"[1/3] GPU 转录 (mlx_whisper)...")
    transcribe_script = os.path.join(script_dir, "transcribe_only.py")
    subprocess.run(
        [_PYTHON, transcribe_script,
         "--src-dir", work_dir,
         "--out", transcript_path,
         "--processed", processed_path],
        check=True,
    )
    log(f"  ✓ 转录完成: {transcript_path}")

    # ── 2. 语义判断 ──
    if skip_judge:
        log(f"[2/3] 跳过语义判断 (--skip-judge)")
        log(f"[3/3] 跳过定向截帧")
        return result

    log(f"[2/3] 语义判断 (Ollama)...")
    analyze_script = os.path.join(script_dir, "analyze_visual_needs.py")
    subprocess.run(
        [_PYTHON, analyze_script,
         "--src", transcript_path,
         "--out", needs_path],
        check=True,
    )

    # 读取判断结果
    needs_visual = False
    reason = ""
    try:
        with open(needs_path, encoding="utf-8") as f:
            needs_data = json.load(f)
        items = needs_data.get("items", [])
        if items:
            needs_visual = items[0].get("needs_visual", False)
            reason = items[0].get("reason", "")
    except Exception as e:
        log(f"  ⚠️ 读取 needs.json 失败: {e}")
        needs_visual = False

    result["needs_visual"] = needs_visual
    result["reason"] = reason
    log(f"  ✓ needs_visual={needs_visual}, reason={reason[:80] if reason else 'N/A'}")

    # ── 3. 定向截帧 ──
    if not needs_visual:
        log(f"[3/3] 无需截帧 (needs_visual=false)")
        return result

    log(f"[3/3] 定向截帧 (ffmpeg, fps={fps})...")
    extract_script = os.path.join(script_dir, "extract_target_frames.py")
    os.makedirs(frames_dir, exist_ok=True)
    subprocess.run(
        [_PYTHON, extract_script,
         "--video-dir", work_dir,
         "--needs", needs_path,
         "--out", frames_dir,
         "--fps", str(fps)],
        check=True,
    )

    # 统计帧数
    frame_count = 0
    if os.path.isdir(frames_dir):
        for root, dirs, files in os.walk(frames_dir):
            frame_count += sum(1 for f in files if f.endswith(".jpg"))
    result["frames_dir"] = frames_dir
    result["frame_count"] = frame_count
    log(f"  ✓ 截帧完成: {frame_count} 帧 → {frames_dir}")

    return result


def persist_outputs(work_dir, out_dir, result):
    """把 work_dir 中的转录/判断/帧产物复制到持久 out-dir，返回更新路径后的 result。

    work_dir 是中间目录（默认会被清理）；out_dir 是产物归宿。
    仅复制存在的产物，缺文件不报错。
    """
    os.makedirs(out_dir, exist_ok=True)
    for fname in ("transcripts.txt", "needs.json"):
        src = os.path.join(work_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, fname))
    frames_src = os.path.join(work_dir, "frames")
    frames_dst = os.path.join(out_dir, "frames")
    if os.path.isdir(frames_src):
        if os.path.isdir(frames_dst):
            shutil.rmtree(frames_dst)
        shutil.copytree(frames_src, frames_dst)
        result["frames_dir"] = frames_dst
    result["transcript_path"] = os.path.join(out_dir, "transcripts.txt")
    return result


def print_summary(result):
    """输出汇总信息到 stdout。"""
    print("\n" + "=" * 60, flush=True)
    print("📊 单条智能转录汇总", flush=True)
    print("=" * 60, flush=True)
    print(f"  标题: {result['title']}", flush=True)
    print(f"  日期: {result['date']}", flush=True)
    print(f"  aweme_id: {result['aweme_id']}", flush=True)
    print(f"  转录文本: {result['transcript_path']}", flush=True)

    if result["needs_visual"] is None:
        print(f"  画面需求: 已跳过 (--skip-judge)", flush=True)
    elif result["needs_visual"]:
        print(f"  画面需求: ✅ 需要", flush=True)
        print(f"  判断理由: {result['reason']}", flush=True)
        print(f"  截帧目录: {result['frames_dir']}", flush=True)
        print(f"  截帧数量: {result['frame_count']}", flush=True)
    else:
        print(f"  画面需求: ❌ 不需要（纯口播/闲聊）", flush=True)
        print(f"  判断理由: {result['reason']}", flush=True)

    print("=" * 60, flush=True)


def cleanup_work_dir(work_dir, keep=False):
    """清理工作目录。keep=True 时保留。

    删除前做安全边界校验：
    - 危险路径（/、~、仓库根等）抛 ValueError 拒绝删除并保留目录，绝不 rmtree；
    - 目录名不以 douyin/tmp 开头的自定义目录：警告并保留（不 rmtree），
      不 raise，保证运行不因清理失败崩溃。
    """
    if keep:
        log(f"保留工作目录: {work_dir}")
        return
    if _is_dangerous_work_dir(work_dir):
        log(f"⚠️ 拒绝清理不安全的工作目录（已保留）: {work_dir}")
        raise ValueError(f"拒绝删除不安全的工作目录: {work_dir}")
    if not os.path.basename(os.path.realpath(work_dir)).startswith(("douyin", "tmp")):
        log(f"⚠️ 工作目录名不以 douyin/tmp 开头，已保留（不删除）: {work_dir}")
        return
    if os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir)
            log(f"已清理工作目录: {work_dir}")
        except Exception as e:
            log(f"清理工作目录失败: {e}")


# 允许的工作目录安全父路径：用户主目录（仓库通常在其下）、系统临时目录
_SAFE_PARENTS = (os.path.expanduser("~"), "/tmp", "/private/tmp")


def _is_dangerous_work_dir(work_dir):
    """危险路径判定：等于仓库根、或不在安全父目录内（如 /、~ 自身）。

    前缀不匹配 douyin/tmp 的普通自定义目录不属于危险路径（降级保留即可）。
    """
    real = os.path.realpath(work_dir)
    repo_root = os.path.realpath(_SCRIPT_DIR)
    if real == repo_root:
        return True  # 仓库根本身禁止删除
    parents = _SAFE_PARENTS + (repo_root,)
    return not any(
        real.startswith(os.path.realpath(p) + os.sep) for p in parents
    )


def _is_safe_work_dir(work_dir):
    """校验 work_dir 是否处于安全边界内（仓库子目录或 /tmp 下 douyin/tmp 前缀目录）。

    规则：
    - realpath 后必须是某个安全父目录（~/、/tmp、/private/tmp、仓库根）的子路径；
    - 目录 basename 必须以 douyin 或 tmp 开头（防止误删任意目录）；
    - 仓库根本身（即使 basename 匹配）禁止删除。
    """
    real = os.path.realpath(work_dir)
    repo_root = os.path.realpath(_SCRIPT_DIR)
    if real == repo_root:
        return False  # 仓库根本身禁止删除
    parents = _SAFE_PARENTS + (repo_root,)
    in_safe_parent = any(
        real.startswith(os.path.realpath(p) + os.sep) for p in parents
    )
    basename_ok = os.path.basename(real).startswith(("douyin", "tmp"))
    return in_safe_parent and basename_ok


def parse_args():
    """解析命令行参数。"""
    ap = argparse.ArgumentParser(
        description="单条视频智能转录适配器：mp4 → GPU转录 → 语义判断 → 定向截帧"
    )
    ap.add_argument("--mp4", required=True, help="视频文件路径（如 /tmp/douyin_<ID>.mp4）")
    ap.add_argument("--title", default=None, help="视频标题（缺省用文件名）")
    ap.add_argument("--date", default=date_type.today().isoformat(), help="日期 YYYY-MM-DD（缺省今天）")
    ap.add_argument("--work-dir", default="/tmp/douyin_single_work", help="临时工作目录")
    ap.add_argument("--skip-judge", action="store_true", help="跳过语义判断和截帧，只转录")
    ap.add_argument("--fps", type=float, default=2, help="定向截帧帧率（默认2）")
    ap.add_argument("--keep-work", action="store_true", help="保留工作目录不清理")
    ap.add_argument("--out-dir", default=os.path.join(_SCRIPT_DIR, "output"),
                    help="持久产物输出目录（默认仓库根 output/）")
    return ap.parse_args()


def main():
    # 防御：避免 PYTHONPATH 污染和代理问题
    os.environ.pop("PYTHONPATH", None)
    for k in ("all_proxy", "ALL_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(k, None)
    os.environ["HF_HUB_OFFLINE"] = "1"

    args = parse_args()

    # 输入校验
    if not os.path.isfile(args.mp4):
        log(f"错误: 视频文件不存在: {args.mp4}")
        sys.exit(1)

    # 参数处理
    date = args.date
    aweme_id = extract_aweme_id_from_mp4(args.mp4)
    title = args.title or os.path.splitext(os.path.basename(args.mp4))[0]

    log(f"单条智能转录适配")
    log(f"  视频: {args.mp4}")
    log(f"  标题: {title}")
    log(f"  日期: {date}")
    log(f"  aweme_id: {aweme_id}")
    log(f"  工作目录: {args.work_dir}")
    log(f"  skip_judge: {args.skip_judge}")

    try:
        # 1. 建立目录结构
        video_dir = setup_video_dir(args.work_dir, args.mp4, title, date, aweme_id)
        log(f"  视频目录: {video_dir}")

        # 2. 执行管道
        result = run_pipeline(
            work_dir=args.work_dir,
            video_dir=video_dir,
            mp4_path=args.mp4,
            title=title,
            date=date,
            aweme_id=aweme_id,
            skip_judge=args.skip_judge,
            fps=args.fps,
        )

        # 3. 产物复制到持久 out-dir（work_dir 默认会被清理）
        result = persist_outputs(args.work_dir, args.out_dir, result)

        # 4. 输出汇总（打印持久路径）
        print_summary(result)

    except subprocess.CalledProcessError as e:
        log(f"管道执行失败: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"未预期错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 5. 清理中间目录（产物已复制到 out-dir）
        cleanup_work_dir(args.work_dir, keep=args.keep_work)


if __name__ == "__main__":
    main()
