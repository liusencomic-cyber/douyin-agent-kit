#!/usr/bin/env python3
"""博主蒸馏纯转录模式：只转录 mp4 → 汇总到单文本文件，不写逐条 Obsidian 笔记。
用法: python3 transcribe_only.py --src-dir <post目录> --out <汇总txt> --processed <json>
"""
import argparse, json, os, re, subprocess, sys, tempfile

from scripts.asr_utils import ensure_asr_engine_supported
from scripts.format_utils import segments_to_timestamps

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"


def log(msg):
    print(msg, flush=True)


def main():
    # 防御：避免 PYTHONPATH 污染导致 numpy 版本冲突
    os.environ.pop("PYTHONPATH", None)
    # 防御：避免 all_proxy socks 代理导致 huggingface_hub 连接失败（模型已缓存在本地）
    for k in ("all_proxy", "ALL_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(k, None)
    # 强制离线：中国大陆无代理时 huggingface_hub 直连会被墙挂死；模型已本地缓存，读取即可
    os.environ["HF_HUB_OFFLINE"] = "1"
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", required=True, help="作品目录（含日期_标题_id 子文件夹）")
    ap.add_argument("--out", required=True, help="汇总转录文本输出路径")
    ap.add_argument("--processed", required=True, help="已处理 ID 记录 json")
    ap.add_argument("--append", action="store_true",
                    help="追加写 --out（默认覆盖写，防跨运行残留）")
    args = ap.parse_args()

    processed_path = args.processed
    if os.path.exists(processed_path):
        with open(processed_path) as f:
            processed = set(json.load(f))
    else:
        processed = set()

    def save_processed(ids):
        with open(processed_path, "w") as f:
            json.dump(sorted(ids), f, ensure_ascii=False, indent=1)

    items = []
    for folder in sorted(os.listdir(args.src_dir)):
        fpath = os.path.join(args.src_dir, folder)
        if not os.path.isdir(fpath):
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)_(\d{10,})$", folder)
        if not m:
            continue
        date, title, aweme_id = m.groups()
        if aweme_id in processed:
            continue
        mp4s = [f for f in os.listdir(fpath) if f.endswith(".mp4")]
        jsons = [f for f in os.listdir(fpath) if f.endswith("_data.json")]
        meta = {}
        if jsons:
            try:
                with open(os.path.join(fpath, jsons[0])) as f:
                    meta = json.load(f)
            except Exception:
                pass
        items.append((date, title, aweme_id, os.path.join(fpath, mp4s[0]) if mp4s else None, meta))

    log(f"待处理: {len(items)} 条（已处理历史: {len(processed)}）")
    if not items:
        log("DONE: 无新内容")
        return

    import mlx_whisper
    log("加载 Whisper 模型（首次较慢，mlx-whisper GPU/Metal）...")
    # mlx_whisper.transcribe 内部按 path_or_hf_repo 缓存模型，重复调用不重载
    ensure_asr_engine_supported()  # 非 mlx-whisper 的 provider 明确报错（接口预留）

    ok, fail = 0, 0
    with open(args.out, "a" if args.append else "w", encoding="utf-8") as out:
        for i, (date, title, aweme_id, mp4, meta) in enumerate(items, 1):
            try:
                transcript = ""
                segments = []
                if mp4:
                    log(f"[{i}/{len(items)}] 转录 {aweme_id} {title[:20]}...")
                    result = mlx_whisper.transcribe(
                        mp4,
                        path_or_hf_repo=WHISPER_MODEL,
                        language="zh",
                        verbose=False,
                    )
                    segments = result.get("segments", [])
                    transcript = "".join(s["text"] for s in segments).strip()
                else:
                    log(f"[{i}/{len(items)}] 图文/无视频 {aweme_id}，仅记文案")
                desc = (meta.get("desc") or title).strip()
                out.write(f"===== [{date}] {title} =====\n")
                out.write(f"视频文案: {desc}\n")
                out.write(f"原文转录: {transcript if transcript else '（无音频内容）'}\n")
                if segments:
                    out.write(f"时间戳分段:\n{segments_to_timestamps(segments)}\n")
                out.write("\n")
                out.flush()
                processed.add(aweme_id)
                save_processed(processed)
                ok += 1
                log(f"    ✓ 已汇总 {aweme_id}（{len(transcript)}字）")
            except Exception as e:
                fail += 1
                log(f"    ✗ 失败 {aweme_id}: {e}")
    log(f"DONE: 成功 {ok}，失败 {fail}")

if __name__ == "__main__":
    main()
