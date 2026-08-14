# OpenClaw 接入说明

本文件说明 OpenClaw 如何接入 douyin-agent-kit。通用能力契约见
[adapter-contract.md](adapter-contract.md)。

## 视觉调用

- 配置 `vision.ocr_provider: agent-vision` 时，使用 OpenClaw 的视觉工具
  （若你的 OpenClaw 配置了视觉模型）。OpenClaw 无视觉或未配置视觉模型时，
  将 `ocr_provider` 改为 `tesseract`（本地 OCR）或 `none`。
- `vision.judge_provider` 的语义判断走 Ollama 等本地 LLM 服务，
  不占用 OpenClaw 的上下文窗口。

## 确认交互

- 下载与登录（`qr_login.py` 扫码）涉及账号安全，执行前向用户确认；
  二维码图片投递给用户扫码。
- 批量同步遵循低频原则，遇风控（滑块/验证）立即停止并通知用户。

## 定时

- OpenClaw 有调度/循环能力时，可为批量任务配置每日定时；否则手动触发。

## 投递

- 归档笔记写入 `archive.vault_inbox`。
- 判断/截帧结果写入脚本输出路径。

## 脚本运行

- 以系统 `python3` 运行仓库脚本；依赖按 `requirements.txt` 安装。
