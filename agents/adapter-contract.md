# Agent 接入能力契约（adapter-contract）

任何本地 Agent（Hermes / OpenClaw / WorkBuddy / Claude Code / Codex / 任意通用 Agent）
接入本仓库，只需满足下表能力。**视觉能力是可选的**：没有视觉的 Agent 也能跑完整流程，
由 `douyin_skills.config.yaml` 的 `vision.ocr_provider` / `vision.fallback_ocr` 决定降级方案。

| 能力 | 用途 | 是否必需 | 降级方案 |
|---|---|---|---|
| Shell 执行 | 运行 `setup/`、`scripts/` 下脚本（ffmpeg、转录、判断、截帧） | **必需** | 无降级；无 shell 的 Agent 无法使用本仓库 |
| 文件读写 | 读写 `douyin_skills.config.yaml`、转录汇总、判断结果、归档笔记 | **必需** | 无降级；至少需能读配置、写输出 |
| 视觉能力（可选） | 画面/图片 OCR：识别店招、字幕、图表文字等增量信息 | 可选 | `vision.ocr_provider=agent-vision` 时使用；无此能力则按 `fallback_ocr` 走本地 OCR（tesseract 等），或 `ocr_provider=none` 跳过 OCR |
| 用户确认 | 下载、Cookie 登录、批量同步、归档/投递前向用户确认 | **必需**（安全） | 无人值守场景在配置中显式声明（如定时任务），风险自担 |
| 定时（可选） | 收藏同步 / 博主蒸馏按计划低频执行（防风控） | 可选 | 无定时能力则手动触发；`features.favorites_sync/creator_distill` 保持 false |
| 投递 | 把转录/判断结果写入 Obsidian Vault（`archive.vault_inbox`）或输出文件 | **必需**（归档时） | 不启用归档时结果仅写仓库内输出文件 |

## 约定

1. **配置优先**：所有可配置项（ASR 引擎、视觉 provider、OCR 方案、归档路径、功能开关）
   读 `douyin_skills.config.yaml`，脚本不写死。
2. **路径可移植**：脚本工作目录取环境变量 `DOUYIN_SYNC_DIR`，未设置时推断为脚本所在目录，
   不依赖任何用户的固定路径。
3. **诚实口径**：未实现的 provider（如 `faster-whisper`、`whisper.cpp`）脚本会明确抛
   `NotImplementedError` 提示，不假装支持。
4. **先检查后运行**：接入前先跑 `python3 setup/checks.py`，MISSING 项补齐后再运行主流程。

## 各 Agent 接入文档

- [hermes.md](hermes.md)
- [openclaw.md](openclaw.md)
- [workbuddy.md](workbuddy.md)
- [generic-agent.md](generic-agent.md)（Claude Code / Codex 等通用编码 Agent 亦适用）
