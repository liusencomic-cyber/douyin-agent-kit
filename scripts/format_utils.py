"""时间戳格式化公共模块（消除 transcribe_only/transcribe_archive 重复实现）。"""


def format_timestamp(seconds):
    """秒 → MM:SS.mmm 或 HH:MM:SS.mmm（当 ≥1h 时）"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    return f"{minutes:02d}:{secs:06.3f}"


def segments_to_timestamps(segments):
    """将 mlx_whisper segments 列表转为时间戳分段文本。"""
    if not segments:
        return ""
    lines = []
    for seg in segments:
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        lines.append(f"[{start} --> {end}] {seg['text']}")
    return "\n".join(lines)
