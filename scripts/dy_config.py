"""统一配置加载模块（纯 stdlib，优先 pyyaml）。

用法:
    from scripts.dy_config import load_config, get_asr, get_vision
    cfg = load_config()          # 读仓库根 douyin_agent_kit.config.yaml；缺失时返回全默认 + 警告
    asr = get_asr(cfg)           # asr 配置段
    vision = get_vision(cfg)     # vision 配置段

结构定义见仓库根 config.schema.json；本模块内置同一套枚举与默认值做运行时校验。
"""
import copy
import json
import os
import sys

# ── 枚举（与 config.schema.json 保持一致）───────────────────────────────
AGENT_CHOICES = ["hermes", "openclaw", "workbuddy", "claude-code", "codex", "generic"]
ASR_PROVIDERS = ["mlx-whisper", "faster-whisper", "whisper.cpp",
                 "external-command", "none"]
VISION_JUDGE_PROVIDERS = ["ollama", "openai-compatible", "none"]
OCR_PROVIDERS = ["agent-vision", "tesseract", "paddleocr", "qwen-vl",
                 "gemini", "openai-compatible", "none"]

# ── 默认值（与 config.schema.json 保持一致）─────────────────────────────
DEFAULTS = {
    "agent": "generic",
    "asr": {
        "provider": "mlx-whisper",
        "model": "mlx-community/whisper-large-v3-turbo",
        "language": "zh",
        "offline": True,
        "external_command": "",
    },
    "vision": {
        "judge_provider": "ollama",
        "judge_model": "qwen2.5:7b",
        "ollama_url": "http://127.0.0.1:11434",
        "ocr_provider": "agent-vision",
        "fallback_ocr": "tesseract",
        "max_chars": 6000,
        "verify_rounds": 2,
    },
    "archive": {
        "vault_inbox": None,
        "enabled": True,
    },
    "features": {
        "single_extract": True,
        "favorites_sync": False,
        "creator_distill": False,
    },
}

# 默认配置文件位置：仓库根（本文件位于 scripts/ 下，上级即仓库根）
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "douyin_agent_kit.config.yaml",
)

_CONFIG_NAME = os.path.basename(DEFAULT_CONFIG_PATH)


def _deep_merge(base, override):
    """递归合并 dict：override 覆盖 base，未覆盖的键保留 base 值。"""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _load_yaml_text(path):
    """读取并解析配置文件：优先 pyyaml，不可用时 JSON 兜底。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml  # 可选依赖
    except ImportError:
        # JSON 是 YAML 子集，先试 json 兜底
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise ImportError(
                f"{_CONFIG_NAME} 需要 pyyaml 解析（当前未安装），"
                f"请运行: pip install pyyaml"
            )
    try:
        data = yaml.safe_load(text)
    except Exception as e:
        raise ValueError(
            f"{_CONFIG_NAME} 解析失败: {e}\n"
            f"请检查 {path} 的 YAML 语法"
        )
    return data or {}


def _validate(cfg):
    """校验关键枚举字段，非法值抛 ValueError 并列出合法值。"""
    agent = cfg.get("agent", DEFAULTS["agent"])
    if agent not in AGENT_CHOICES:
        raise ValueError(
            f"agent 非法: '{agent}'，合法值: {', '.join(AGENT_CHOICES)}")
    asr = cfg.get("asr", {})
    provider = asr.get("provider", DEFAULTS["asr"]["provider"])
    if provider not in ASR_PROVIDERS:
        raise ValueError(
            f"asr.provider 非法: '{provider}'，合法值: {', '.join(ASR_PROVIDERS)}")
    vision = cfg.get("vision", {})
    judge = vision.get("judge_provider", DEFAULTS["vision"]["judge_provider"])
    if judge not in VISION_JUDGE_PROVIDERS:
        raise ValueError(
            f"vision.judge_provider 非法: '{judge}'，"
            f"合法值: {', '.join(VISION_JUDGE_PROVIDERS)}")
    ocr = vision.get("ocr_provider", DEFAULTS["vision"]["ocr_provider"])
    if ocr not in OCR_PROVIDERS:
        raise ValueError(
            f"vision.ocr_provider 非法: '{ocr}'，合法值: {', '.join(OCR_PROVIDERS)}")
    return cfg


def load_config(path=None):
    """加载配置：读 path（默认仓库根 douyin_agent_kit.config.yaml）。

    文件缺失时返回全默认值并打印警告；文件存在时深合并默认值后校验。
    非法 provider 抛 ValueError。
    """
    path = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        print(
            f"WARN: 未找到配置文件 douyin_agent_kit.config.yaml（{path}），"
            f"使用全默认配置。\n"
            f"      可参考 douyin_agent_kit.config.example.yaml 创建，"
            f"或运行 python setup/setup_douyin_agent_kit.py 交互式生成。",
            flush=True,
        )
        return copy.deepcopy(DEFAULTS)
    user_cfg = _load_yaml_text(path)
    if not isinstance(user_cfg, dict):
        raise ValueError(f"{_CONFIG_NAME} 顶层应为映射（dict），实际: {type(user_cfg).__name__}")
    cfg = _deep_merge(DEFAULTS, user_cfg)
    return _validate(cfg)


def get_asr(cfg=None):
    """返回 asr 配置段（dict）。"""
    cfg = cfg if cfg is not None else load_config()
    return cfg.get("asr", dict(copy.deepcopy(DEFAULTS["asr"])))


def get_vision(cfg=None):
    """返回 vision 配置段（dict）。"""
    cfg = cfg if cfg is not None else load_config()
    return cfg.get("vision", dict(copy.deepcopy(DEFAULTS["vision"])))


def select_asr_engine(cfg=None):
    """返回当前 ASR provider 名（转录引擎分发点）。

    当前已实现: mlx-whisper。其余 provider 为接口预留，
    由调用方对非 mlx-whisper 抛 NotImplementedError 明确提示。
    """
    asr = get_asr(cfg)
    return asr.get("provider", DEFAULTS["asr"]["provider"])
