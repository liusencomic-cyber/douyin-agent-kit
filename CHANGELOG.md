# 更新日志（Changelog）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-08-14

初始版本：抖音内容提取与博主蒸馏的 **Agent 无关** 技能集。

### 新增

- **设置向导**：`setup/setup_douyin_agent_kit.py` 交互/非交互生成统一配置
  `douyin_agent_kit.config.yaml`（ASR / Vision 可配置开口）、`AGENT_SETUP.md`、`archive_config.json`；
  按所选 Agent（hermes / openclaw / workbuddy / claude-code / codex / generic）生成接入说明。
- **环境检查**：`setup/checks.py` 输出 OK / WARN / MISSING 分级汇总。
- **单条智能转录**：`transcribe_single.py` — mp4 → GPU 转录（mlx-whisper）→
  语义判断（本地 Ollama）→ 定向截帧；支持 `--skip-judge` / `--keep-work`。
- **语义判断**：`analyze_visual_needs.py` — 三重校验（置信度 / 双重确认 / 实义词）
  防漏判与误报；含提示注入防护（转录数据边界声明 + 注入回复降级）。
- **批量归档**：`transcribe_archive.py` — 收藏目录扫描 → 转录 → Obsidian 笔记
  （时间戳分段、作者文案、标签）；已处理 ID 去重。
- **扫码登录**：`qr_login.py`（headless Playwright 抓二维码，轮询 Cookie）。
- **统一配置**：`scripts/dy_config.py` + `config.schema.json`（JSON Schema draft-07）。
- **Agent 适配层**：`agents/` 能力契约 + 各 Agent 接入文档；SKILL.md Agent 无关声明。
- **治理文件**：SECURITY / CONTRIBUTING / CODE_OF_CONDUCT / CHANGELOG、
  Issue/PR 模板、CI（Python 3.10–3.13）、dependabot（pip 每周）。

### 安全

- 工作目录清理带安全边界校验：仅允许仓库内或 /tmp 下 douyin/tmp 前缀目录，
  拒绝删除 `/`、`~`、仓库根等危险路径（`transcribe_single.py`）。
- 批量下载遵守账号安全铁律：低频增量、单线程、同 IP、遇风控立即停；
  弹窗超时**绝不自动推进全量**，需显式配置 `auto_proceed_on_timeout: true`。

### 已知限制

- 转录引擎当前实现 `mlx-whisper`（Apple Silicon）；faster-whisper / whisper.cpp /
  external-command 为接口预留，调用时明确抛 `NotImplementedError`。
- 视频下载依赖上游 [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)
  （MIT），需自行 clone 到 `douyin-downloader/` 子目录。
- 语义判断用 7B 模型，判断有轻微波动；Whisper 同音错字需整理时校正。
