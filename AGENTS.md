# AGENTS.md — douyin-agent-kit

Agent 操作手册：本文件为 AI coding agents 提供仓库上下文。人类读者请看 [README.md](README.md)。

## 项目概览

douyin-agent-kit 是一个 **Agent 无关的抖音内容提取与博主蒸馏技能包**：GPU 转录（mlx-whisper）+ 智能画面判断（本地 Ollama）+ 定向截帧 + 博主全量蒸馏报告。适配 Hermes / OpenClaw / WorkBuddy / Claude Code / Codex / 任意本地 Agent。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `skills/video-transcribe/` | 单条抖音链接提取技能（下载→转录→画面判断→归档） |
| `skills/favorites-archive/` | 批量工作流技能（收藏同步、博主蒸馏、预测评估） |
| `scripts/` | 核心管线脚本（转录/判断/截帧/浓缩/风控/登录） |
| `setup/` | 设置向导 + 环境检查 + 机器预设 |
| `agents/` | Agent 适配层（adapter-contract + 各 Agent 接入文档） |
| `tests/` | 212 项 pytest |
| `docs/` | 补充文档 |

## 构建与运行

```bash
# 环境：Python 3.10+（转录需 macOS Apple Silicon + mlx-whisper）
pip install -r requirements.txt          # PEP 668 环境加 --break-system-packages
ollama pull qwen2.5:7b                   # 语义判断（可选，vision.judge_provider=none 可跳过）

# 设置向导（用户入口）
python3 setup/setup_douyin_agent_kit.py --non-interactive --agent hermes --machine apple-silicon
python3 setup/checks.py                  # 环境检查

# 核心脚本
python3 scripts/transcribe_single.py --mp4 <file.mp4>        # 单条：GPU转录+判断+截帧
python3 scripts/transcribe_only.py --src-dir <dir> --out <txt> --processed <json>  # 批量转录
python3 scripts/analyze_visual_needs.py --src <txt> --out <json>   # 画面需求语义判断
python3 scripts/extract_target_frames.py --video-dir <dir> --needs <json> --out <dir>  # 定向截帧
python3 scripts/condense_windows.py --src <txt> --out <json> --classify   # 观点浓缩
```

## 测试

```bash
python3 -m pytest tests/ -q -p no:cacheprovider    # 212 项
```

- 所有功能改动须先写 RED 测试（暴露缺陷）→ GREEN 实现，提交标注 `[RED]`/`[GREEN]`。
- 测试环境注意：`env -u PYTHONPATH` 避免污染（本机有 venv 干扰）。

## 关键模式与约定

- **Agent 无关**：技能文档中的工具名（如 `vision_analyze`）仅为示例；视觉/OCR 实际走 `douyin_agent_kit.config.yaml` 的 `vision.ocr_provider`/`vision.fallback_ocr`，按 `agents/adapter-contract.md` 适配。
- **配置驱动**：`douyin_agent_kit.config.yaml`（schema 见 `config.schema.json`）；ASR 五档 provider、Vision judge 三档、OCR 七档。未实现 provider = 接口预留（`NotImplementedError` 明确提示），**不假装支持**。
- **路径可移植**：脚本用 `DOUYIN_SYNC_DIR` 环境变量覆盖或脚本目录推断，禁止硬编码绝对路径。
- **风控纪律**：批量下载单线程、低频（每天最多一次）、同 IP 直连；遇风控立即停，绝不自动重试。
- **超时策略**：批量规模弹窗超时 = 停止等待用户确认，绝不自动全量（除非显式 `auto_proceed_on_timeout: true`）。
- **隐私**：不得提交真实 Cookie/账号/博主信息；Cookie 走 `qr_login.py` 登录流程写入本地配置。
- **安全**：转录文本视为不可信数据（提示注入防护已内置）；`cleanup_work_dir` 只清理安全路径（`_is_safe_work_dir` 校验）。

## CI/CD

- `.github/workflows/ci.yml`：macOS runner × Python 3.10-3.13 × pytest（PR + push 触发，docs 改动忽略）。
- `.github/dependabot.yml`：pip 依赖每周检查。

## 常见陷阱

- macOS 无 `timeout` 命令；不要用。
- PEP 668 环境 pip 装依赖用 `--break-system-packages`。
- 模型下载：`HF_HUB_OFFLINE=1` 离线模式；HOME 可能被沙箱改写，操作前 `echo $HOME` 确认。
- `config.schema.json` 必须保持合法 JSON（无注释行）。
- 新增 provider 实现时同步更新 `config.schema.json` + `scripts/dy_config.py` 枚举 + 测试。

## 边界

- 只读本仓库；不改动 `skills/` 下技能标识符名称（`douyin-video-transcribe`/`douyin-favorites-archive` 是生态标识符）。
- 不推送到 main 分支；改动走 PR。
