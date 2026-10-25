# douyin-agent-kit

[中文](README.md) | [English](README.en.md)

**抖音内容提取与博主蒸馏工具集**——把抖音视频变成可用的文字材料：GPU 转录、智能画面判断、定向截帧、博主全量蒸馏，一条龙完成。不绑定任何特定 Agent，Hermes、OpenClaw、WorkBuddy、Claude Code、Codex 以及各种本地 Agent 都能直接用。

> [!IMPORTANT]
> 这是一个 **Agent Skills 技能包**（遵循 SKILL.md 标准），不是一个独立 App。把仓库交给你的本地 Agent，运行一次设置向导，它就会自动帮你完成选择和配置。

---

## 它能做什么

| 能力 | 说明 |
|---|---|
| **GPU 转录** | 基于 mlx-whisper（Apple Metal），比 faster-whisper 的 CPU 方案快约 12 倍，CPU 占用从 300%+ 降到个位数 |
| **完全离线** | 模型本地缓存，配合 `HF_HUB_OFFLINE=1`，全程不联网 |
| **智能画面判断** | 转录之后，用本地 Ollama 判断视频哪些时间段画面里有口播没讲到的信息（图表、代码、表格、演示），三重校验减少漏判和误报 |
| **定向截帧** | 只截语义判断标记的时间段，不会整段视频无差别截图 |
| **博主蒸馏** | 全量转录 → 观点浓缩（滑动窗口法）→ 生成七段式报告 |
| **风控保护** | 启动前自动检查残留进程、并发下载器、模型缓存、Ollama 状态 |
| **适配任意 Agent** | 不依赖某个 Agent 专属的工具名或路径，通过六项能力契约对接 |
| **模型可配置** | 当前可用：mlx-whisper（转录）+ 本地 Ollama（判断）+ agent-vision/tesseract（OCR）；其余 provider（faster-whisper、whisper.cpp、paddleocr 等）为接口预留，调用时报 `NotImplementedError` 不假装支持 |

## 快速开始（4 步）

### 1. 克隆仓库

```bash
git clone https://github.com/senlib/douyin-agent-kit
cd douyin-agent-kit
```

### 2. 运行设置向导

```bash
# 交互式：逐项选择 Agent / 机器类型 / ASR / Vision / 功能 / 归档
python3 setup/setup_douyin_agent_kit.py

# 非交互式：参数注入，适合无人值守或测试
python3 setup/setup_douyin_agent_kit.py --non-interactive --agent hermes --machine apple-silicon
```

向导会生成 `douyin_agent_kit.config.yaml` 和 `AGENT_SETUP.md`（针对你选的 Agent 生成专属接入说明）。

### 3. 环境检查

```bash
python3 setup/checks.py
```

输出 OK / WARN / MISSING 三级报告，缺失项会给出修复提示。

### 4. 接入你的 Agent

按照 `AGENT_SETUP.md`（或 `agents/<你的agent>.md`）接入。能力契约见 [`agents/adapter-contract.md`](agents/adapter-contract.md)。

## 配置说明

所有行为都由 `douyin_agent_kit.config.yaml` 驱动（结构定义见 [`config.schema.json`](config.schema.json)，完整示例见 [`douyin_agent_kit.config.example.yaml`](douyin_agent_kit.config.example.yaml)）。

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
  max_chars: 6000              # 超长输入截断（防止超出 8K 上下文）
  verify_rounds: 2             # 双重确认，防误报
archive:
  vault_inbox: ""              # Obsidian 收件箱路径（启用归档时填写）
  enabled: false
features:
  single_extract: true         # 单条链接提取
  favorites_sync: false        # 收藏批量同步
  creator_distill: false       # 博主蒸馏
```

> [!NOTE]
> 部分 provider（如 faster-whisper、paddleocr）目前是**接口预留**：配置里可以选，分发点已经留好，但调用时会明确报 `NotImplementedError`，不会假装支持。

## 环境要求

- **macOS（Apple Silicon M1 及以上）**：转录用 mlx-whisper（Metal GPU）。Linux/NVIDIA 可选用 faster-whisper（接口预留）
- Python 3.10+（系统 `/opt/homebrew/bin/python3` 或 venv 均可）
- [Ollama](https://ollama.com) 本地服务（画面判断用，可选——设 `vision.judge_provider: none` 可跳过）
- [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT 协议，克隆到 `douyin-downloader/` 子目录，收藏同步和博主批量下载用）

```bash
# 安装依赖（PEP 668 环境需要加 --break-system-packages）
python3 -m pip install --break-system-packages mlx mlx-whisper filelock scipy packaging json5 pyyaml

# 拉取 Ollama 模型（画面判断用）
ollama pull qwen2.5:7b

# 转录模型首次运行会自动下载（约 1.6GB，存到 ~/.cache/huggingface）
```

## 安全说明

> [!CAUTION]
> 本项目涉及**抖音自动化**，使用前请务必阅读并遵守以下规则：

- **账号风险**：批量下载和收藏同步用的是你本人的 Cookie，存在限流、滑块验证、Cookie 失效等风险。任何工具都不敢保证"零封号"——只读自己的收藏列表属于最低风险的使用方式。
- **风控铁律**：单线程、低频（每天最多一次）、同 IP 直连；遇到风控（滑块/验证码）立即停止，**绝不自动重试硬闯**。
- **批量规模**：选择批量大小时如果弹窗超时，默认**停止并等待你的确认**，不会自动全量（除非显式配置 `auto_proceed_on_timeout: true`）。
- **隐私**：Cookie 和凭据只存本地（通过 `qr_login.py` 扫码登录），**严禁提交到仓库**（包括 git 历史）。
- **提示注入**：转录文本被当作不可信数据处理，调用 LLM 时内置了数据边界声明防护。
- **漏洞报告**：见 [SECURITY.md](SECURITY.md)（走 GitHub Security Advisory 私密渠道）。

## 已知限制

- Whisper 有同音错字问题（如"美债"可能写成"每战"），整理时需人工校正。
- 画面判断用的是 7B 模型，结果会有轻微波动；三重校验（置信度/双重确认/实义词）已经大幅降低了漏判和误报。
- 视频下载依赖上游 [douyin-downloader](https://github.com/jiji262/douyin-downloader)（MIT 协议），需要自己克隆。
- CI 中的 mlx 依赖只在 macOS runner 上有预编译 wheel。

## 测试

```bash
env -u PYTHONPATH python3 -m pytest tests/ -q -p no:cacheprovider   # 共 212 项
```

## 参与贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)（开发环境、测试要求、隐私约定、PR 流程）。

## 许可证

[MIT](LICENSE)。上游 `douyin-downloader` 为 MIT 协议（由用户自行克隆，不随本仓库分发）。
