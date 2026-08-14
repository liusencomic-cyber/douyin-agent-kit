# douyin-agent-kit

[中文](README.md) | [English](README.en.md)

**Agent 无关的抖音内容提取与博主蒸馏技能包** —— GPU 转录 + 智能画面判断 + 定向截帧 + 博主全量蒸馏，适配 Hermes / OpenClaw / WorkBuddy / Claude Code / Codex / 任意本地 Agent。

> [!IMPORTANT]
> 本项目是 **Agent Skills 技能包**（SKILL.md 标准），不是独立 App。用户把仓库交给本地 Agent 后，运行设置向导即可自动完成选择与配置。

---

## 特性

| 能力 | 说明 |
|---|---|
| **GPU 转录** | mlx-whisper（Apple Metal），比 faster-whisper CPU 快 ~12x，CPU 占用从 300%+ 降至个位数 |
| **完全离线** | 模型本地缓存 + `HF_HUB_OFFLINE=1`，无网络依赖 |
| **智能画面判断** | 转录后本地 Ollama 判断哪些时间段画面有增量信息（图表/代码/表格/演示），三重校验防漏判 + 防误报 |
| **定向截帧** | 按语义标记的时间段截帧，不整段瞎截 |
| **博主蒸馏** | 全量转录 → 观点浓缩（滑动窗口法）→ 七段式报告 |
| **风控保护** | 启动前检查残留进程/并发下载器/模型缓存/Ollama |
| **Agent 无关** | 不绑定单一 Agent 的工具名/路径，六项能力契约适配任意本地 Agent |
| **模型可配置** | ASR 五档、Vision judge 三档、OCR 七档，设置向导一键选择 |

## 快速开始（4 步）

### 1. Clone

```bash
git clone https://github.com/liusencomic-cyber/douyin-agent-kit
cd douyin-agent-kit
```

### 2. 运行设置向导

```bash
# 交互式（逐项选择 Agent / 机器类型 / ASR / Vision / 功能 / 归档）
python3 setup/setup_douyin_agent_kit.py

# 或非交互（参数注入，供无人值守/测试）
python3 setup/setup_douyin_agent_kit.py --non-interactive --agent hermes --machine apple-silicon
```

向导会生成 `douyin_agent_kit.config.yaml` + `AGENT_SETUP.md`（按所选 Agent 生成专属接入说明）。

### 3. 环境检查

```bash
python3 setup/checks.py
```

输出 OK / WARN / MISSING 分级报告，MISSING 项会给出修复提示。

### 4. 接入你的 Agent

按 `AGENT_SETUP.md`（或 `agents/<你的agent>.md`）接入。核心能力契约见 [`agents/adapter-contract.md`](agents/adapter-contract.md)。

## 配置

所有行为由 `douyin_agent_kit.config.yaml` 驱动（schema 见 [`config.schema.json`](config.schema.json)，完整示例见 [`douyin_agent_kit.config.example.yaml`](douyin_agent_kit.config.example.yaml)）。

```yaml
agent: hermes            # hermes / openclaw / workbuddy / claude-code / codex / generic
asr:
  provider: mlx-whisper  # mlx-whisper / faster-whisper / whisper.cpp / external-command / none
  model: mlx-community/whisper-large-v3-turbo
  language: zh
  offline: true
vision:
  judge_provider: ollama       # 画面需求语义判断
  judge_model: qwen2.5:7b
  ocr_provider: agent-vision   # agent-vision / tesseract / paddleocr / qwen-vl / gemini / none
  fallback_ocr: tesseract
  max_chars: 6000              # 超长输入截断（防止 8K 上下文溢出）
  verify_rounds: 2             # 双重确认防误报
archive:
  vault_inbox: ""              # Obsidian 收件箱路径（启用归档时填）
  enabled: false
features:
  single_extract: true         # 单条链接提取
  favorites_sync: false        # 收藏批量同步
  creator_distill: false       # 博主蒸馏
```

> [!NOTE]
> 未实现的 provider（如 faster-whisper / paddleocr）为**接口预留**：配置可选、分发点已留，调用会抛 `NotImplementedError` 明确提示，不会假装支持。

## 环境要求

- **macOS（Apple Silicon M1+）**：转录用 mlx-whisper（Metal GPU）。Linux/NVIDIA 可选 faster-whisper（接口预留）。
- Python 3.10+（系统 `/opt/homebrew/bin/python3` 或 venv）
- [Ollama](https://ollama.com) 本地服务（语义判断，可选——设 `vision.judge_provider: none` 可跳过）
- [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT，clone 到 `douyin-downloader/` 子目录，用于收藏同步/博主批量下载）

```bash
# 依赖（PEP 668 环境需 --break-system-packages）
python3 -m pip install --break-system-packages mlx mlx-whisper filelock scipy packaging json5 pyyaml

# Ollama 模型（语义判断）
ollama pull qwen2.5:7b

# 转录模型（首次运行自动下载 ~1.6GB 到 ~/.cache/huggingface）
```

## 安全说明

> [!CAUTION]
> 本项目涉及**抖音自动化**，使用前请阅读并遵守：

- **账号风险**：批量下载/收藏同步使用本人 Cookie，存在限流/滑块/Cookie 失效风险。任何工具都无法承诺零封号——只读自己的收藏列表属最低风险画像。
- **风控铁律**：单线程、低频（每天最多一次）、同 IP 直连；遇风控（滑块/验证）立即停止，**绝不自动重试硬闯**。
- **批量规模**：弹窗选择批量大小时，超时 = 停止等待你的确认，**绝不自动全量**（除非显式配置 `auto_proceed_on_timeout: true`）。
- **隐私**：Cookie/凭据只存本地（`qr_login.py` 登录流程），**严禁提交到仓库**（含 git 历史）。
- **提示注入**：转录文本视为不可信数据，LLM 调用内置数据边界声明防护。
- **漏洞报告**：见 [SECURITY.md](SECURITY.md)（GitHub Security Advisory 私密渠道）。

## 已知限制

- Whisper 同音错字（如"美债→每战"）需整理时校正。
- 语义判断用 7B 模型，判断有轻微波动；三重校验（置信度/双重确认/实义词）已显著降低漏判与误报。
- 视频下载依赖上游 [douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT），需自行 clone。
- CI 的 mlx 依赖仅在 macOS runner 有 wheel。

## 测试

```bash
env -u PYTHONPATH python3 -m pytest tests/ -q -p no:cacheprovider   # 212 项
```

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)（开发设置、测试、隐私要求、PR 流程）。

## 许可证

[MIT](LICENSE)。上游 `douyin-downloader` 为 MIT（用户自行 clone，不随本仓库分发）。
