# 通用 Agent 接入说明（generic-agent）

适用于任意本地 Agent，包括 Claude Code / Codex / 其他 CLI 编码 Agent。
通用能力契约见 [adapter-contract.md](adapter-contract.md)。

若你的 Agent 不在 `agents/` 单独成文，按本文接入即可；设置向导
（`setup/setup_douyin_skills.py`）选择 `agent: generic` 或 `claude-code` / `codex`
时生成的 AGENT_SETUP.md 也指向本文。

## 视觉调用

- 默认配置 `vision.ocr_provider: agent-vision` 意为"由 Agent 提供视觉"。
  你的 Agent 有视觉工具（能读图/识别文字）就用它；**如你的 Agent 无此能力**，
  把 `ocr_provider` 改为 `tesseract`（本地 OCR，需安装 tesseract）或 `none`。
- 语义判断走本地 Ollama（`vision.judge_provider: ollama`，
  `ollama pull qwen2.5:7b`），与你的 Agent 无关。

## 确认交互

- 下载、扫码登录、批量同步、归档/投递前，先向用户确认。
- 收藏/博主批量操作低频执行（每天最多一次），遇风控即停。

## 定时（可选）

- 你的 Agent 支持定时/后台任务时，可为批量同步配置每日任务；
  否则手动触发，并把 `features.favorites_sync` / `features.creator_distill`
  如实设为 `false`。

## 投递

- 归档笔记写入 `archive.vault_inbox`（Obsidian Vault 收件箱路径）。
- 未启用归档时，转录汇总/判断结果写入脚本输出路径。

## 脚本运行

- 系统 `python3`；依赖：`python3 -m pip install -r requirements.txt`
  （PEP 668 环境加 `--break-system-packages`）。
- 先跑 `python3 setup/checks.py`，确认无 MISSING 再运行主流程。
