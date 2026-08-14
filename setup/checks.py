#!/usr/bin/env python3
"""环境检查（纯 stdlib）：python3 / ffmpeg / mlx_whisper / Ollama / douyin-downloader /
模型缓存 / tesseract（若配置）/ 归档路径（若配置）。

输出分级汇总：
  OK      正常
  WARN    缺失但可选/降级可用
  MISSING 必需项缺失 → 汇总后 exit 1

用法:
  python3 setup/checks.py [--config douyin_skills.config.yaml]
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 单个检查项：签名 fn(cfg=None) → (name, status, detail) ──────────

def check_python3(cfg=None):
    v = sys.version_info
    major_ok = v.major == 3 and v.minor >= 10
    status = "OK" if major_ok else "WARN"
    return ("python3", status,
            f"{v.major}.{v.minor}.{v.micro}" + ("" if major_ok else "（建议 Python 3.10+）"))


def check_ffmpeg(cfg=None):
    path = shutil.which("ffmpeg")
    if path:
        return ("ffmpeg", "OK", path)
    return ("ffmpeg", "MISSING", "未找到 ffmpeg（macOS: brew install ffmpeg）")


def check_mlx_whisper(cfg=None):
    if importlib.util.find_spec("mlx_whisper") is not None:
        return ("mlx_whisper", "OK", "可导入")
    return ("mlx_whisper", "WARN",
            "未安装 mlx-whisper（仅 Apple Silicon 转录需要；pip install mlx-whisper）")


def check_ollama(cfg=None):
    url = "http://127.0.0.1:11434"
    if cfg and cfg.get("vision", {}).get("judge_provider") == "none":
        return ("ollama", "SKIP", "vision.judge_provider=none，不需要 Ollama")
    if cfg and cfg.get("vision", {}):
        url = cfg["vision"].get("ollama_url", url)
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "3",
             f"{url}/api/tags"],
            capture_output=True, text=True, timeout=10)
        if r.stdout.strip() == "200":
            return ("ollama", "OK", f"{url}/api/tags 可达")
        return ("ollama", "WARN", f"{url} 未返回 200（服务未启动？）")
    except Exception as e:
        return ("ollama", "WARN", f"{url} 不可达: {e}")


def check_downloader(cfg=None):
    base = os.environ.get("DOUYIN_SYNC_DIR") or REPO_ROOT
    d = os.path.join(base, "douyin-downloader")
    if os.path.isdir(d):
        return ("douyin-downloader", "OK", d)
    return ("douyin-downloader", "MISSING",
            f"未找到 douyin-downloader/（{d}；请 clone jiji262/douyin-downloader）")


def check_model_cache(cfg=None):
    cache = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.isdir(cache):
        names = [n.lower() for n in os.listdir(cache)]
        if any("whisper" in n for n in names):
            return ("model_cache", "OK", cache)
        return ("model_cache", "WARN",
                f"{cache} 存在但未见 whisper 模型（首次转录会自动下载）")
    return ("model_cache", "WARN",
            "模型缓存目录不存在（首次转录自动下载 ~1.6GB）")


def check_tesseract(cfg=None):
    need = True  # 默认 fallback_ocr=tesseract
    if cfg:
        vision = cfg.get("vision", {})
        need = (vision.get("ocr_provider") == "tesseract"
                or vision.get("fallback_ocr") == "tesseract")
    if not need:
        return ("tesseract", "SKIP", "未配置 tesseract OCR")
    path = shutil.which("tesseract")
    if path:
        return ("tesseract", "OK", path)
    return ("tesseract", "WARN",
            "未安装 tesseract（vision 配置含 tesseract 时需要；可选）")


def check_archive_path(cfg=None):
    if not cfg or not cfg.get("archive", {}).get("enabled"):
        return ("archive_path", "SKIP", "归档未启用")
    vault = cfg.get("archive", {}).get("vault_inbox") or ""
    if not vault:
        return ("archive_path", "WARN", "archive.enabled=true 但 vault_inbox 为空")
    if os.path.isdir(vault):
        return ("archive_path", "OK", vault)
    return ("archive_path", "WARN", f"vault_inbox 不存在: {vault}（向导可创建）")


# ── 注册表 ────────────────────────────────────────────────────────
CHECK_FUNCTIONS = [
    ("python3", check_python3),
    ("ffmpeg", check_ffmpeg),
    ("mlx_whisper", check_mlx_whisper),
    ("ollama", check_ollama),
    ("douyin-downloader", check_downloader),
    ("model_cache", check_model_cache),
    ("tesseract", check_tesseract),
    ("archive_path", check_archive_path),
]


def run_checks(functions=None, config_path=None):
    """逐个执行检查函数，返回 [(name, status, detail), ...]。

    functions: 覆盖检查函数列表（默认 CHECK_FUNCTIONS 的 func）。
    config_path: 可选配置文件路径，供条件检查项（tesseract/archive）使用。
    """
    funcs = functions or [f for _, f in CHECK_FUNCTIONS]
    cfg = None
    if config_path and os.path.exists(config_path):
        try:
            sys.path.insert(0, REPO_ROOT)
            from scripts.dy_config import load_config
            cfg = load_config(config_path)
        except Exception as e:
            print(f"WARN: 配置文件 {config_path} 读取失败，按默认检查: {e}")
    results = []
    for fn in funcs:
        try:
            results.append(fn(cfg))
        except TypeError:
            results.append(fn())
        except Exception as e:
            results.append((getattr(fn, "__name__", "?"), "WARN", f"检查异常: {e}"))
    return results


def summarize(results):
    """返回 (OK 数, WARN 数, MISSING 数)；SKIP 不计入。"""
    ok = warn = missing = 0
    for _, status, _ in results:
        if status == "OK":
            ok += 1
        elif status == "WARN":
            warn += 1
        elif status == "MISSING":
            missing += 1
    return ok, warn, missing


def exit_code(results):
    """存在任何 MISSING → 1，否则 0。"""
    return 1 if any(status == "MISSING" for _, status, _ in results) else 0


def main():
    ap = argparse.ArgumentParser(description="douyin-skills 环境检查")
    ap.add_argument("--config", default=None,
                    help="douyin_skills.config.yaml 路径（条件检查项使用）")
    # parse_known_args：容忍被其它进程以额外参数调用（如 pytest 环境）
    args, _ = ap.parse_known_args()
    results = run_checks(config_path=args.config)
    ok, warn, missing = summarize(results)
    print("=" * 46)
    print("douyin-skills 环境检查报告")
    print("=" * 46)
    for name, status, detail in results:
        print(f"  [{status:<7}] {name}: {detail}")
    print("-" * 46)
    print(f"  汇总: OK={ok}  WARN={warn}  MISSING={missing}")
    if missing:
        print("  结论: 存在缺失项（MISSING），请按提示补齐后重跑。")
    else:
        print("  结论: 无缺失项。")
    sys.exit(exit_code(results))


if __name__ == "__main__":
    main()
