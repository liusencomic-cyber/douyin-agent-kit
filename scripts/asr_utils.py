"""ASR 引擎分发公共模块（消除 transcribe_only/transcribe_archive 重复实现）。

复用 scripts/dy_config.select_asr_engine；配置不可读时回落 mlx-whisper
（与原两脚本行为一致）。
"""


def select_asr_engine():
    """返回当前 ASR provider 名（来自 douyin_agent_kit.config.yaml）。

    配置不可读/未配置时回落默认 mlx-whisper。其他 provider 为接口预留。
    """
    try:
        from scripts.dy_config import select_asr_engine as _select
        return _select()
    except Exception:
        return "mlx-whisper"


def ensure_asr_engine_supported():
    """校验当前 ASR provider 已实现；未实现时抛 NotImplementedError 明确提示。"""
    engine = select_asr_engine()
    if engine != "mlx-whisper":
        raise NotImplementedError(
            f"ASR provider '{engine}' 尚未实现完整转录：当前仅支持 mlx-whisper。\n"
            f"可在 douyin_agent_kit.config.yaml 的 asr.provider 选择: "
            f"mlx-whisper / faster-whisper / whisper.cpp / external-command / none"
        )
    return engine
