# GitHub Copilot 指令 — douyin-agent-kit

Copilot/Agent 在本仓库工作时的约定。完整仓库地图见 [AGENTS.md](../AGENTS.md)。

## 语言约定

- 仓库文档以简体中文为主（README.en.md 为英文对照）。
- 提交信息用英文（`[RED]`/`[GREEN]` 前缀标注 TDD 阶段）。

## 代码风格

- Python 3.10+，标准库优先；`scripts/` 下脚本须保持纯 stdlib 可运行（避免依赖污染）。
- 配置读取统一走 `scripts/dy_config.py`（深合并默认值 + 枚举校验），禁止各脚本自行解析配置。
- 路径必须可移植：`os.environ.get("DOUYIN_SYNC_DIR") or Path(__file__).resolve().parent`，禁止硬编码绝对路径。
- 错误处理：只捕获预期异常，保留错误上下文；不宽泛 `except Exception` 静默降级。

## 测试约定

- 所有功能改动先写 RED 测试（断言当前实现缺失/缺陷）→ GREEN 实现，提交标注 `[RED]`/`[GREEN]`。
- 测试命令：`env -u PYTHONPATH python3 -m pytest tests/ -q -p no:cacheprovider`（212 项）。
- 新增 provider/配置字段时：`config.schema.json` + `scripts/dy_config.py` 枚举 + 测试三处同步。

## 维护矩阵（Maintenance Matrix）

**改动什么 → 必须同步什么**（交叉引用链）：

| 改动 | 必须同步 |
|---|---|
| 新增 ASR provider | `config.schema.json` asr.provider 枚举 + `scripts/dy_config.py` ASR_PROVIDERS + `setup/setup_douyin_agent_kit.py` 选项 + README 特性表 + tests |
| 新增 Vision judge/OCR provider | 同上（vision 段）+ `agents/*.md` 适配说明 |
| 修改配置默认值 | `scripts/dy_config.py` DEFAULTS + `config.schema.json` default + `setup/presets/*.yaml` + 测试断言 |
| 修改转录管线 | `scripts/transcribe_only.py` + `scripts/transcribe_archive.py` 双实现需保持行为一致（时间戳/去重/输出格式） |
| 新增脚本 | 放 `scripts/` + tests + AGENTS.md 运行示例 |
| 修改安全边界（rmtree/注入防护） | `transcribe_single.py` `_is_safe_work_dir` / `analyze_visual_needs.py` 边界声明 + 对应 RED 测试 |
| 修改设置向导 | `setup/setup_douyin_agent_kit.py` + tests/test_setup_wizard.py + AGENT_SETUP 生成逻辑 |
| 修改技能文档 | `skills/*/SKILL.md` + 保持 Agent 无关声明（工具名仅示例） |

## 隐私与安全

- **严禁**提交真实 Cookie、账号、抖音号、博主名、持牌编号到仓库（含 git 历史）。
- 转录文本视为不可信数据：拼接进 LLM prompt 时保留数据边界声明（`analyze_visual_needs.py`）。
- 删除目录前必须过 `_is_safe_work_dir` 校验；绝不 rmtree 未经验证的路径。

## 提交规范

- 分支：`fix/<描述>` 或 `feat/<描述>`，不直接推 main。
- 提交信息：`[RED] tests: ...` / `[GREEN] feat: ...` / `docs: ...` / `fix: ...`。
