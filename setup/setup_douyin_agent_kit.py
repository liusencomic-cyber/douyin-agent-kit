#!/usr/bin/env python3
"""设置向导：为任意本地 Agent 生成 douyin-agent-kit 配置。

交互式（默认）由 input() 驱动；非交互式用 --non-interactive + 参数注入（便于测试/无人值守）。

生成物（写到 --wizard-dir，默认仓库根）:
  douyin_agent_kit.config.yaml   统一配置（ASR/Vision 可配置开口）
  archive_config.json         归档配置（启用归档时）
  AGENT_SETUP.md              按所选 Agent 生成的接入说明

结束时自动运行 python setup/checks.py 输出环境检查报告（--skip-checks 跳过）。

用法:
  python3 setup/setup_douyin_agent_kit.py                          # 交互式
  python3 setup/setup_douyin_agent_kit.py --non-interactive \
      --agent hermes --machine apple-silicon --skip-checks      # 非交互
"""
import argparse
import copy
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from scripts.dy_config import (  # noqa: E402
    DEFAULTS,
    AGENT_CHOICES,
    ASR_PROVIDERS,
    VISION_JUDGE_PROVIDERS,
    OCR_PROVIDERS,
    _deep_merge,
    _load_yaml_text,
)

MACHINE_CHOICES = ["apple-silicon", "nvidia", "cpu-only", "existing-service"]
PRESETS_DIR = os.path.join(REPO_ROOT, "setup", "presets")
MACHINE_PRESETS = {
    "apple-silicon": "mac-mlx-local.yaml",
    "nvidia": "linux-cuda.yaml",
    "cpu-only": "cpu-only.yaml",
    "existing-service": None,  # 已有转录服务：不加载预设，手动选择
}
# 各机器类型的 ASR provider 推荐排序（交互选择时展示）
MACHINE_ASR_RECOMMEND = {
    "apple-silicon": ["mlx-whisper", "faster-whisper", "whisper.cpp",
                      "external-command", "none"],
    "nvidia": ["faster-whisper", "whisper.cpp", "external-command",
               "mlx-whisper", "none"],
    "cpu-only": ["faster-whisper", "whisper.cpp", "external-command",
                 "mlx-whisper", "none"],
    "existing-service": ["external-command", "none", "faster-whisper",
                         "whisper.cpp", "mlx-whisper"],
}
FEATURE_CHOICES = ["single_extract", "favorites_sync", "creator_distill"]


# ── 交互原语 ──────────────────────────────────────────────────────

def ask(question, choices, default=None):
    """单选：输入编号或值；空输入用默认值。"""
    print(f"\n{question}")
    for i, c in enumerate(choices, 1):
        print(f"  {i}) {c}")
    if default:
        print(f"  （默认: {default}）")
    while True:
        raw = input("> ").strip().lower()
        if not raw and default:
            return default
        if raw in choices:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        print("  无效选择，请重新输入编号或选项名。")


def ask_multi(question, choices, default=None):
    """多选：逗号分隔编号或名字；空输入用默认。"""
    print(f"\n{question}")
    print("  （逗号分隔多个，如: 1,2 或 single_extract,favorites_sync）")
    for i, c in enumerate(choices, 1):
        print(f"  {i}) {c}")
    if default:
        print(f"  （默认: {', '.join(default)}）")
    raw = input("> ").strip().lower()
    if not raw and default:
        return list(default)
    selected = []
    for part in raw.split(","):
        p = part.strip()
        if p in choices:
            selected.append(p)
        elif p.isdigit() and 1 <= int(p) <= len(choices):
            selected.append(choices[int(p) - 1])
    return selected


def ask_yes_no(question, default="n"):
    ans = ask(question, ["y", "n"], default=default)
    return ans == "y"


# ── 预设加载 ──────────────────────────────────────────────────────

def load_preset(machine):
    """按机器类型加载预设（无预设返回空 dict）。"""
    fname = MACHINE_PRESETS.get(machine)
    if not fname:
        return {}
    path = os.path.join(PRESETS_DIR, fname)
    if not os.path.exists(path):
        return {}
    data = _load_yaml_text(path)
    return data if isinstance(data, dict) else {}


# ── 配置构建 ──────────────────────────────────────────────────────

def build_config_noninteractive(args):
    """非交互：参数注入 + 机器预设 + 默认值。"""
    machine = args.machine or "apple-silicon"
    preset = load_preset(machine)
    cfg = _deep_merge(DEFAULTS, preset)

    cfg["agent"] = args.agent or "generic"
    cfg["asr"]["provider"] = args.asr or preset.get("asr", {}).get(
        "provider") or MACHINE_ASR_RECOMMEND[machine][0]
    if args.asr_model:
        cfg["asr"]["model"] = args.asr_model
    if args.language:
        cfg["asr"]["language"] = args.language

    cfg["vision"]["judge_provider"] = args.judge or preset.get(
        "vision", {}).get("judge_provider", "ollama")
    if args.judge_model:
        cfg["vision"]["judge_model"] = args.judge_model
    if args.ollama_url:
        cfg["vision"]["ollama_url"] = args.ollama_url
    cfg["vision"]["ocr_provider"] = args.ocr or preset.get(
        "vision", {}).get("ocr_provider", "agent-vision")
    if args.fallback_ocr:
        cfg["vision"]["fallback_ocr"] = args.fallback_ocr
    if args.max_chars is not None:
        cfg["vision"]["max_chars"] = args.max_chars
    if args.verify_rounds is not None:
        cfg["vision"]["verify_rounds"] = args.verify_rounds

    if args.features:
        selected = [f.strip() for f in args.features.split(",") if f.strip()]
        for feat in FEATURE_CHOICES:
            cfg["features"][feat] = feat in selected
    else:
        # 默认只启用 single_extract
        cfg["features"]["single_extract"] = True
        cfg["features"]["favorites_sync"] = False
        cfg["features"]["creator_distill"] = False

    if args.vault_inbox:
        cfg["archive"]["enabled"] = True
        cfg["archive"]["vault_inbox"] = args.vault_inbox
    else:
        cfg["archive"]["enabled"] = False
        cfg["archive"]["vault_inbox"] = ""
    return cfg


def build_config_interactive(args):
    """交互：input() 逐项询问（每步编号选项）。"""
    print("\n===== douyin-agent-kit 设置向导（交互模式）=====")
    print("Ctrl-C 随时取消；直接回车使用默认值。")

    agent = ask("1) 你的 Agent 类型", AGENT_CHOICES, default="generic")
    machine = ask("2) 机器类型", MACHINE_CHOICES, default="apple-silicon")
    asr_recommend = MACHINE_ASR_RECOMMEND[machine]
    asr = ask(f"3) ASR provider（按 {machine} 推荐排序）",
              asr_recommend, default=asr_recommend[0])
    judge = ask("4) Vision judge provider（画面需求语义判断）",
                VISION_JUDGE_PROVIDERS, default="ollama")
    ocr = ask("5) OCR provider（画面/图片文字识别）",
              OCR_PROVIDERS, default="agent-vision")
    feats = ask_multi(
        "6) 启用哪些功能（multi-select）",
        FEATURE_CHOICES, default=["single_extract"])
    archive_on = ask_yes_no("7) 启用 Obsidian 归档？", default="n")
    vault = ""
    if archive_on:
        print("   输入 Obsidian Vault 收件箱路径（可直接回车跳过）:")
        vault = input("> ").strip()

    cfg = copy.deepcopy(DEFAULTS)
    preset = load_preset(machine)
    cfg = _deep_merge(cfg, preset)
    # 用户答案必须覆盖预设
    cfg["agent"] = agent
    cfg["asr"]["provider"] = asr
    cfg["vision"]["judge_provider"] = judge
    cfg["vision"]["ocr_provider"] = ocr
    for feat in FEATURE_CHOICES:
        cfg["features"][feat] = feat in feats
    cfg["archive"]["enabled"] = archive_on and bool(vault)
    cfg["archive"]["vault_inbox"] = vault
    return cfg


# ── AGENT_SETUP.md 生成 ───────────────────────────────────────────

# claude-code / codex 等通用编码 Agent 共用 generic-agent 适配文档
AGENT_DOC_MAP = {"claude-code": "generic-agent", "codex": "generic-agent"}


def generate_agent_setup_md(agent, cfg):
    """按所选 Agent 生成专属接入说明（引用 agents/<agent>.md）。"""
    doc_name = AGENT_DOC_MAP.get(agent, agent)
    asr = cfg["asr"]
    vision = cfg["vision"]
    archive = cfg["archive"]
    feats = cfg["features"]
    vault = archive.get("vault_inbox") or "（未启用）"
    ocr_style = (
        "调用你的原生视觉能力识别画面文字；如你的 Agent 无此能力，"
        "脚本会按 vision.fallback_ocr 走本地 OCR（tesseract 等）"
        if vision["ocr_provider"] == "agent-vision"
        else f"本地/远端 OCR 方案: {vision['ocr_provider']}"
    )
    return f"""# AGENT_SETUP —— douyin-agent-kit 接入说明（{agent}）

本文件由设置向导根据你的选择生成，是 {agent} 接入本仓库的操作手册。
能力契约与通用约定见 `agents/adapter-contract.md`；本 Agent 的详细适配见 `agents/{doc_name}.md`。

## 1. 当前环境（来自 douyin_agent_kit.config.yaml）

| 项目 | 值 |
|---|---|
| Agent 类型 | {agent} |
| ASR provider | {asr['provider']}（模型: {asr['model']}，语言: {asr['language']}） |
| Vision judge | {vision['judge_provider']}（{vision['judge_model']}） |
| OCR | {vision['ocr_provider']}（兜底: {vision['fallback_ocr']}） |
| 功能开关 | single_extract={feats['single_extract']}, favorites_sync={feats['favorites_sync']}, creator_distill={feats['creator_distill']} |
| 归档 | {archive['enabled']} → {vault} |

## 2. 四个接入环节

### 2.1 视觉调用
- {ocr_style}
- 语义判断（judge）: 调 {vision['judge_provider']}（{vision['judge_model']}，{vision['ollama_url']}）判断哪些时间段画面有增量信息。

### 2.2 用户确认
- 涉及下载、Cookie 登录、归档写入、投递前，先向用户确认再执行。
- 批量同步每天最多一次（收藏/博主全量有风控风险，见 skills/favorites-archive/SKILL.md）。

### 2.3 定时（可选）
- `features.favorites_sync=true` 或 `features.creator_distill=true` 时建议配置每日定时（低频增量）。

### 2.4 投递
- 归档笔记写入: {vault}
- 转录汇总/画面判断结果写入仓库内由脚本指定的输出路径。

## 3. 运行入口
- 单条提取: `skills/video-transcribe/`（含脚本与说明）
- 批量归档: `skills/favorites-archive/`
- 环境检查: `python3 setup/checks.py`
"""


# ── 写出文件 ──────────────────────────────────────────────────────

def write_yaml(cfg, path):
    """写 YAML；pyyaml 不可用时 JSON 兜底（JSON 是 YAML 子集）。"""
    try:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    except ImportError:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    return path


def run_wizard(args):
    """生成配置并写出全部产物；返回生成的 cfg dict。"""
    cfg = (build_config_noninteractive(args)
           if args.non_interactive else build_config_interactive(args))

    # 校验：复用 dy_config 的枚举校验（非法值抛 ValueError）
    from scripts.dy_config import load_config
    out_path = args.config_out or os.path.join(REPO_ROOT, "douyin_agent_kit.config.yaml")
    write_yaml(cfg, out_path)
    load_config(out_path)  # 校验通过才继续

    wizard_dir = args.wizard_dir or REPO_ROOT
    os.makedirs(wizard_dir, exist_ok=True)

    if cfg["archive"]["enabled"] and cfg["archive"].get("vault_inbox"):
        acfg = {"vault_inbox": cfg["archive"]["vault_inbox"]}
        with open(os.path.join(wizard_dir, "archive_config.json"), "w",
                  encoding="utf-8") as f:
            json.dump(acfg, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(wizard_dir, "AGENT_SETUP.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_agent_setup_md(cfg["agent"], cfg))

    print(f"\n✓ 配置已生成: {out_path}")
    print(f"✓ AGENT_SETUP.md: {md_path}")
    if cfg["archive"]["enabled"]:
        print(f"✓ archive_config.json: {os.path.join(wizard_dir, 'archive_config.json')}")
    print("下一步: python setup/checks.py 环境检查，然后按 AGENT_SETUP.md 接入 Agent。")

    if not args.skip_checks:
        checks = os.path.join(REPO_ROOT, "setup", "checks.py")
        subprocess.run([sys.executable, checks], cwd=REPO_ROOT)
    return cfg


def main():
    ap = argparse.ArgumentParser(description="douyin-agent-kit 设置向导")
    ap.add_argument("--non-interactive", action="store_true",
                    help="非交互模式（参数注入，供测试/无人值守）")
    ap.add_argument("--agent", choices=AGENT_CHOICES, default=None,
                    help="Agent 类型（默认 generic）")
    ap.add_argument("--machine", choices=MACHINE_CHOICES, default=None,
                    help="机器类型（默认 apple-silicon）")
    ap.add_argument("--asr", choices=ASR_PROVIDERS, default=None,
                    help="ASR provider（默认按机器预设推荐）")
    ap.add_argument("--asr-model", default=None, help="ASR 模型名")
    ap.add_argument("--language", default=None, help="转录语言（默认 zh）")
    ap.add_argument("--judge", choices=VISION_JUDGE_PROVIDERS, default=None,
                    help="Vision judge provider（默认 ollama）")
    ap.add_argument("--judge-model", default=None, help="judge 模型名")
    ap.add_argument("--ollama-url", default=None, help="Ollama API 地址")
    ap.add_argument("--ocr", choices=OCR_PROVIDERS, default=None,
                    help="OCR provider（默认 agent-vision）")
    ap.add_argument("--fallback-ocr", default=None, help="OCR 兜底方案")
    ap.add_argument("--max-chars", type=int, default=None, help="judge 输入最大字符数")
    ap.add_argument("--verify-rounds", type=int, default=None, help="验证轮数")
    ap.add_argument("--features", default=None,
                    help="功能开关（逗号分隔，如 single_extract,favorites_sync）")
    ap.add_argument("--vault-inbox", default=None,
                    help="Obsidian Vault 收件箱路径（提供即启用归档）")
    ap.add_argument("--config-out", default=None,
                    help="配置输出路径（默认仓库根 douyin_agent_kit.config.yaml）")
    ap.add_argument("--wizard-dir", default=None,
                    help="产物目录（默认仓库根；AGENT_SETUP.md/archive_config.json 写此处）")
    ap.add_argument("--skip-checks", action="store_true",
                    help="结束后跳过环境检查（setup/checks.py）")
    args = ap.parse_args()
    run_wizard(args)


if __name__ == "__main__":
    main()
