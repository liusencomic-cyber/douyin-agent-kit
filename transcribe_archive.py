"""收藏视频转译归档流水线
扫描 Downloaded/self_self/collect/ 下的新作品 → ffmpeg 提音频 → mlx_whisper 转录（GPU/Metal）
→ 生成 Obsidian 笔记（KnocksenVault/_inbox/赫尔墨斯_inbox/）→ 记录已处理 ID。
用法: python3 transcribe_archive.py [--limit N]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.asr_utils import ensure_asr_engine_supported
from scripts.format_utils import segments_to_timestamps

# 可移植工作目录：优先环境变量 DOUYIN_SYNC_DIR，否则推断为脚本所在目录（仓库根）。
BASE = os.environ.get("DOUYIN_SYNC_DIR") or str(Path(__file__).resolve().parent)
COLLECT_DIR = os.path.join(BASE, "Downloaded/self_self/collect")
PROCESSED_JSON = os.path.join(BASE, "processed.json")
VAULT_INBOX = None  # 从共享配置延迟加载（见 get_vault_inbox）


def get_vault_inbox():
    """延迟加载归档收件箱路径。

    模块可被安全 import（不依赖本机配置文件存在）；
    首次真正需要归档时读取 archive_config.json 并缓存。
    """
    global VAULT_INBOX
    if VAULT_INBOX is None:
        VAULT_INBOX = load_archive_config().get("vault_inbox")
    return VAULT_INBOX


def load_archive_config():
    """从 douyin-sync 根目录 archive_config.json 读取归档配置。
    配置缺失时抛 FileNotFoundError 并指引用户创建。"""
    cfg_path = os.path.join(BASE, "archive_config.json")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(
            f"共享配置文件缺失: {cfg_path}\n"
            f"请在 douyin-sync 根目录创建 archive_config.json，内容示例:\n"
            f'{{"vault_inbox": "你的 Obsidian Vault _inbox 路径"}}'
        )
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"


def log(msg):
    print(msg, flush=True)


def sanitize_filename(name, maxlen=40):
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:maxlen].rstrip() or "未命名"


def load_processed():
    if os.path.exists(PROCESSED_JSON):
        with open(PROCESSED_JSON) as f:
            return set(json.load(f))
    return set()


def save_processed(ids):
    with open(PROCESSED_JSON, "w") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=1)


def transcribe(mp4_path):
    """ffmpeg 提取音频 → mlx_whisper 转录，返回 (文本, segments列表)。"""
    ensure_asr_engine_supported()  # 非 mlx-whisper 的 provider 明确报错（接口预留）
    import mlx_whisper
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav, "-y"],
            check=True, capture_output=True, timeout=300)
        result = mlx_whisper.transcribe(
            wav,
            path_or_hf_repo=WHISPER_MODEL,
            language="zh",
            verbose=False,
        )
        segments = result.get("segments", [])
        text = "".join(s["text"] for s in segments).strip()
        return text, segments
    finally:
        if os.path.exists(wav):
            os.remove(wav)


def make_note(date, title, aweme_id, meta, transcript, segments=None, note_tag="抖音收藏"):
    desc = (meta.get("desc") or title).strip()
    author = (meta.get("author") or {}).get("nickname", "未知作者")
    tags = " ".join(f"#{t}" for t in (meta.get("text_extra") or [])
                    if isinstance(t, dict) and t.get("hashtag_name")
                    for t in [t["hashtag_name"]])
    create = meta.get("create_time", "")
    if str(create).isdigit():
        import datetime
        create = datetime.datetime.fromtimestamp(int(create)).strftime("%Y-%m-%d")
    src = f"https://www.douyin.com/video/{aweme_id}"
    ts_section = ""
    if segments:
        ts_text = segments_to_timestamps(segments)
        if ts_text:
            ts_section = f"\n## 时间戳分段\n\n{ts_text}\n"
    body = f"""# {title}

🔗 来源：[抖音 - {author}]({src})
📅 收藏同步日期：{date}（作品发布：{create}）
🏷️ 标签：#{note_tag} {tags}

---

## 视频文案（作者自述）

{desc}

## 原文转录（Whisper）

{transcript if transcript else "（图文作品或无声视频，无转录内容）"}
{ts_section}
---

> 本文由收藏自动归档流水线生成。深度总结可按需让 Hermes 补充。
"""
    fname = f"{date}_{sanitize_filename(title)}.md"
    path = os.path.join(VAULT_INBOX, fname)
    with open(path, "w") as f:
        f.write(body)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 条（0=不限）")
    ap.add_argument("--src-dir", default=COLLECT_DIR, help="作品目录（默认收藏目录）")
    ap.add_argument("--processed", default=PROCESSED_JSON, help="已处理 ID 记录文件")
    ap.add_argument("--tag", default="抖音收藏", help="笔记主标签")
    args = ap.parse_args()

    processed_path = args.processed
    src_dir = args.src_dir

    if os.path.exists(processed_path):
        with open(processed_path) as f:
            processed = set(json.load(f))
    else:
        processed = set()

    def save_processed(ids):
        with open(processed_path, "w") as f:
            json.dump(sorted(ids), f, ensure_ascii=False, indent=1)

    if not os.path.isdir(src_dir):
        log(f"FATAL: 目录不存在 {src_dir}")
        sys.exit(1)

    items = []
    for folder in sorted(os.listdir(src_dir)):
        fpath = os.path.join(src_dir, folder)
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
            except Exception as e:
                log(f"WARN: {aweme_id} 元数据读取失败 {e}")
        items.append((date, title, aweme_id,
                      os.path.join(fpath, mp4s[0]) if mp4s else None, meta))

    if args.limit:
        items = items[: args.limit]
    log(f"待处理: {len(items)} 条（已处理历史: {len(processed)} 条）")
    if not items:
        log("DONE: 无新内容")
        return

    # 延迟加载归档配置（模块可安全 import，运行时才要求配置存在）
    vault_inbox = get_vault_inbox()
    os.makedirs(vault_inbox, exist_ok=True)

    # 防御：避免 PYTHONPATH 污染导致 numpy 版本冲突
    os.environ.pop("PYTHONPATH", None)
    # 防御：避免 all_proxy socks 代理导致 huggingface_hub 连接失败（模型已缓存在本地）
    for k in ("all_proxy", "ALL_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(k, None)
    # 强制离线：中国大陆无代理时 huggingface_hub 直连会被墙挂死；模型已本地缓存，读取即可
    os.environ["HF_HUB_OFFLINE"] = "1"
    # mlx_whisper.transcribe 内部按 path_or_hf_repo 缓存模型，重复调用不重载

    ok, fail = 0, 0
    for i, (date, title, aweme_id, mp4, meta) in enumerate(items, 1):
        try:
            transcript = ""
            segments = []
            if mp4:
                if i == 1:
                    log("加载 Whisper 模型（首次较慢，mlx-whisper GPU/Metal）...")
                log(f"[{i}/{len(items)}] 转录 {aweme_id} {title[:20]}...")
                transcript, segments = transcribe(mp4)
            else:
                log(f"[{i}/{len(items)}] 图文/无视频 {aweme_id}，仅归档元数据")
            path = make_note(date, title, aweme_id, meta, transcript, segments, note_tag=args.tag)
            processed.add(aweme_id)
            save_processed(processed)
            ok += 1
            log(f"    ✓ 笔记: {os.path.basename(path)}")
        except Exception as e:
            fail += 1
            log(f"    ✗ 失败 {aweme_id}: {e}")
    log(f"DONE: 成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    main()
