# douyin-skills

抖音内容提取与博主蒸馏的 Hermes/Claude Agent 技能集：**GPU 转录 + 智能画面判断 + 定向截帧 + 博主蒸馏报告**。

- `skills/video-transcribe/` — 单条抖音链接（视频/图文）提取 → 转录 → 画面判断 → 归档
- `skills/favorites-archive/` — 批量工作流：收藏同步、博主全量蒸馏、智能画面判断
- `scripts/` — 转录引擎（mlx-whisper GPU）、语义判断（Ollama）、定向截帧、风控检查、浓缩脚本
- `tests/` — 137 项测试（pytest）

## 特性

| 能力 | 说明 |
|---|---|
| **GPU 转录** | mlx-whisper（Apple Metal），比 faster-whisper CPU 快 ~12x，CPU 占用从 300% 降到个位数 |
| **完全离线** | 模型本地缓存 + `HF_HUB_OFFLINE=1`，无网络依赖 |
| **智能画面判断** | 转录后本地 Ollama（qwen2.5:7b）判断哪些时间段画面有增量信息（图表/代码/表格/演示），三重校验防漏判+防误报 |
| **定向截帧** | 按语义标记的时间戳段落截帧，不整段瞎截 |
| **博主蒸馏** | 全量转录 → 观点浓缩（滑动窗口法）→ 七段式报告 |
| **风控保护** | 启动前检查残留进程/并发下载器/模型缓存/Ollama |

## 环境要求

- macOS（Apple Silicon，M1+）— mlx-whisper 依赖 Metal
- Python 3.14（系统 `/opt/homebrew/bin/python3`）
- [Ollama](https://ollama.com) 本地服务（语义判断，qwen2.5:7b）
- 上游下载器：[jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT），clone 到 `douyin-downloader/` 子目录

```bash
# 依赖（PEP 668 环境需 --break-system-packages）
python3 -m pip install --break-system-packages mlx mlx-whisper filelock scipy packaging json5

# Ollama 模型（语义判断）
ollama pull qwen2.5:7b

# 转录模型（首次运行自动下载 ~1.6GB 到 ~/.cache/huggingface）
```

## 快速开始

```bash
# 单条视频：GPU 转录 + 语义判断 + 定向截帧
/opt/homebrew/bin/python3 scripts/transcribe_single.py --mp4 /tmp/douyin_<ID>.mp4

# 批量蒸馏：转录汇总
/opt/homebrew/bin/python3 scripts/transcribe_only.py --src-dir <post目录> --out transcripts.txt --processed processed.json

# 语义判断画面需求
/opt/homebrew/bin/python3 scripts/analyze_visual_needs.py --src transcripts.txt --out needs.json

# 按判断结果定向截帧
/opt/homebrew/bin/python3 scripts/extract_target_frames.py --video-dir <post目录> --needs needs.json --out frames/

# 启动前风控检查
bash scripts/preflight_check.sh
```

## 配置

- 归档路径：`archive_config.json`（`{"vault_inbox": "/path/to/obsidian/inbox"}`）
- 工作目录：环境变量 `DOUYIN_SYNC_DIR` 覆盖
- 语义判断：`--ollama-url http://127.0.0.1:11434`（默认）、`--model qwen2.5:7b`（默认）、`--max-chars 6000`（超长输入截断）

## 已知限制

- 转录质量与 faster-whisper 一致（同模型同精度），Whisper 同音错字（如"美债→每战"）需整理时校正
- 语义判断用 7B 模型，判断有轻微波动；三重校验（置信度/双重确认/实义词）已显著降低漏判与误报
- 视频下载依赖上游 douyin-downloader（MIT），需自行 clone

## 许可证

MIT。上游 `douyin-downloader` 为 MIT（用户自行 clone，不随本仓库分发）。
