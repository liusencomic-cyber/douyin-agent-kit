# Hermes 接入说明

本文件说明 Hermes 如何接入 douyin-agent-kit。通用能力契约见
[adapter-contract.md](adapter-contract.md)；本文只写 Hermes 的具体做法。

## 视觉调用

- 配置 `vision.ocr_provider: agent-vision` 时，调用 Hermes 的原生视觉能力
  （`vision_analyze` 类工具）。**注意**：若 Hermes 的视觉 provider 未显式配置
  （`auxiliary.vision.provider` 为 `auto` 或所选端点不支持视觉），调用会失败——
  此时把 `vision.ocr_provider` 改为本地 OCR（如 `tesseract`）或 `none`，
  不要卡在视觉工具上。
- 帧 OCR 建议由主会话直接调用，分批并行，避免委派子会话（子会话对帧 OCR
  可能整段编造结果）。

## 确认交互

- 下载、Cookie 登录、批量同步、归档前，先向用户确认再执行。
- 收藏/博主批量同步每天最多一次（风控考虑）。

## 定时

- 有调度能力时，可对 `favorites_sync` / `creator_distill` 配置每日低频任务；
  无调度则手动触发，保持 `features.*` 开关如实。

## 投递

- 归档笔记写入 `archive.vault_inbox`（Obsidian Vault 收件箱）。
- 转录汇总与判断结果按脚本输出路径写入仓库。

## 脚本运行

- 仓库脚本以系统 Python 运行（`python3`）；个别技能脚本若依赖第三方包，
  按其 SKILL.md 说明使用对应环境。
