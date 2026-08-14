# douyin-agent-kit

抖音内容提取与博主蒸馏的 **Agent 无关** 技能集：**GPU 转录 + 智能画面判断 + 定向截帧 + 博主蒸馏报告**。
适配 Hermes / OpenClaw / WorkBuddy / Claude Code / Codex / 任意本地 Agent —— 不绑定任何单一 Agent。

- `skills/video-transcribe/` — 单条抖音链接（视频/图文）提取 → 转录 → 画面判断 → 归档
- `skills/favorites-archive/` — 批量工作流：收藏同步、博主全量蒸馏、智能画面判断
- `scripts/` — 统一配置加载（dy_config.py）、转录引擎（mlx-whisper GPU）、语义判断（Ollama）、定向截帧
- `setup/` — 设置向导 + 环境检查（新用户入口）
- `agents/` — 各 Agent 接入适配文档（能力契约）
- `tests/` — 186 项测试（pytest）

## 快速开始（4 步）

### 1. Clone

```bash
git clone <本仓库地址> douyin-agent-kit && cd douyin-agent-kit
```

### 2. 运行设置向导

```bash
# 交互式（逐项选择 Agent / 机器类型 / ASR / Vision / 功能 / 归档）
python3 setup/setup_douyin_agent_kit.py

# 或非交互（参数注入，供无人值守/测试）
python3 setup/setup_douyin_agent_kit.py --non-interactive \
    --agent hermes --machine apple-silicon
```

向导生成：
- `douyin_agent_kit.config.yaml` — 统一配置（ASR / Vision 可配置开口）
- `AGENT_SETUP.md` — 按所选 Agent 生成的接入说明
- `archive_config.json` — 启用 Obsidian 归档时生成

### 3. 环境检查

```bash
python3 setup/checks.py
```

输出 `OK` / `WARN` / `MISSING` 分级汇总；存在 `MISSING` 时按提示补齐后重跑（依赖见
`requirements.txt`，tesseract 为系统包）。

### 4. 接入你的 Agent

把仓库交给你的本地 Agent，让它按 `AGENT_SETUP.md` 执行；
通用能力契约见 `agents/adapter-contract.md`，各 Agent 具体做法见 `agents/<你的agent>.md`。
不启用视觉的 Agent 也能跑通全流程（OCR 走配置的本地方案或关闭）。

## 特性

| 能力 | 说明 |
|---|---|
| **Agent 无关** | 不绑定具体 Agent；能力契约 + 每 Agent 接入文档，视觉能力可选、可降级 |
| **ASR 可配置** | `asr.provider` 可选 mlx-whisper / faster-whisper / whisper.cpp / external-command / none（当前实现 mlx-whisper，其余接口预留并明确报错） |
| **Vision 可配置** | `vision.judge_provider`（ollama / openai-compatible / none）+ `vision.ocr_provider`（agent-vision / tesseract / paddleocr / qwen-vl / gemini / openai-compatible / none） |
| **GPU 转录** | mlx-whisper（Apple Metal），比 faster-whisper CPU 快 ~12x，CPU 占用从 300% 降到个位数 |
| **完全离线** | 模型本地缓存 + `HF_HUB_OFFLINE=1`，无网络依赖 |
| **智能画面判断** | 转录后本地 Ollama（qwen2.5:7b）判断哪些时间段画面有增量信息（图表/代码/表格/演示），三重校验防漏判+防误报 |
| **定向截帧** | 按语义标记的时间戳段落截帧，不整段瞎截 |
| **博主蒸馏** | 全量转录 → 观点浓缩（滑动窗口法）→ 七段式报告 |
| **设置向导** | 交互/非交互生成完整配置，新用户 4 步上手 |
| **风控保护** | 启动前检查残留进程/并发下载器/模型缓存/Ollama |

## 配置

- `douyin_agent_kit.config.yaml`：ASR / Vision / 归档 / 功能开关（结构定义见 `config.schema.json`，
  中文注释示例见 `douyin_agent_kit.config.example.yaml`；也可直接跑向导生成）
- 工作目录：环境变量 `DOUYIN_SYNC_DIR` 覆盖，未设置时推断为脚本所在目录（无本机硬编码路径）
- 语义判断：`vision.judge_provider`（默认 ollama）+ `vision.judge_model`（默认 qwen2.5:7b）、
  `vision.max_chars`（超长输入截断）、`vision.verify_rounds`（双重确认）
- 归档路径：`archive.vault_inbox`（Obsidian Vault 收件箱）或 `archive_config.json`

## 环境要求

- Python 3.10+（在 3.14 上开发测试）
- [ffmpeg](https://ffmpeg.org/)（音频提取/截帧）
- 按需：
  - [Ollama](https://ollama.com) 本地服务（语义判断；`ollama pull qwen2.5:7b`）
  - mlx-whisper（Apple Silicon 转录；`pip install mlx mlx-whisper`）
  - tesseract（本地 OCR 兜底；macOS: `brew install tesseract`，Debian: `apt install tesseract-ocr`）
- 上游下载器：[jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT），clone 到 `douyin-downloader/` 子目录（收藏/批量场景）

```bash
# 依赖（PEP 668 环境需 --break-system-packages）
python3 -m pip install --break-system-packages -r requirements.txt

# Ollama 模型（语义判断）
ollama pull qwen2.5:7b

# 转录模型（首次运行自动下载 ~1.6GB 到 ~/.cache/huggingface）
```

## 已知限制

- 转录引擎当前实现 `mlx-whisper`（Apple Silicon）；`faster-whisper` / `whisper.cpp` /
  `external-command` 为接口预留，脚本会明确抛 `NotImplementedError`，不假装支持
- 转录质量与 faster-whisper 一致（同模型同精度），Whisper 同音错字（如"美债→每战"）需整理时校正
- 语义判断用 7B 模型，判断有轻微波动；三重校验（置信度/双重确认/实义词）已显著降低漏判与误报
- 视频下载依赖上游 douyin-downloader（MIT），需自行 clone；Cookie 登录走 `qr_login.py`（扫码）

## 测试

```bash
python3 -m pytest tests/ -q
```

## 许可证

MIT。上游 `douyin-downloader` 为 MIT（用户自行 clone，不随本仓库分发）。
