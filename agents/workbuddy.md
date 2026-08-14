# WorkBuddy 接入说明

本文件说明 WorkBuddy 如何接入 douyin-skills。通用能力契约见
[adapter-contract.md](adapter-contract.md)。

## 视觉调用

- `vision.ocr_provider: agent-vision` 对应 WorkBuddy 的视觉能力；
  若 WorkBuddy 未启用视觉模型，改用 `tesseract` / `none`。
- 语义判断（judge）走本地 Ollama（`vision.judge_provider: ollama`），
  与 WorkBuddy 的 LLM 相互独立。

## 确认交互

- 下载、登录、归档等有副作用的操作，执行前向用户确认。
- 收藏同步每次最多一次/天；出现验证码或限流信号即停。

## 定时

- 使用 WorkBuddy 的定时任务能力做低频批量同步；不具备则手动运行。

## 投递

- 归档笔记写入 `archive.vault_inbox`。
- 其余产物（转录汇总、判断 JSON、截帧）按脚本输出路径落盘。

## 脚本运行

- 系统 `python3` + `requirements.txt`；环境检查先行：
  `python3 setup/checks.py`。
