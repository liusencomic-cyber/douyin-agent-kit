# 贡献指南（Contributing）

欢迎贡献！本仓库是 **Agent 无关** 的抖音内容提取技能集，遵守 MIT 许可证。
在提 PR 前请阅读本指南。

## 开发环境设置

```bash
# 1. 克隆并进入仓库
git clone <仓库地址> douyin-agent-kit && cd douyin-agent-kit

# 2. 创建虚拟环境（建议 venv）
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. 安装依赖
python3 -m pip install -r requirements.txt

# 4. 可选：生成本地配置（供功能验证）
python3 setup/setup_douyin_agent_kit.py --non-interactive \
    --agent generic --machine apple-silicon --skip-checks
```

> 依赖中含 Apple Silicon 专用项（mlx / mlx-whisper）。在非 macOS 环境贡献时，
> 测试不受影响（测试对转录引擎做了 mock），但请勿在 PR 中依赖这些包的平台行为。

## 运行测试

```bash
python3 -m pytest tests/ -q
```

- 所有测试必须全绿再提交（当前全量测试约 200+ 项）；
- 新增功能必须有对应测试（建议 TDD：先 RED 测试 → 再 GREEN 实现）；
- 提交信息可标注 `[RED]`（失败测试）与 `[GREEN]`（通过实现），便于审阅节奏。

## 隐私要求（重要）

- **不得提交**真实 Cookie、账号、会话凭据（`config/cookies.json`、
  `douyin-downloader/config*.yml` 等），相关文件已在 `.gitignore` 中；
- **严禁提交**本机绝对路径、用户名、个人 Vault 路径、真实视频文件；
- 新增示例/文档请使用占位符（如 `<OBSIDIAN_VAULT>`、`<博主>`）；
- 提交前自查：`git status` 无凭据/本机路径文件。

## 提交规范

- 提交信息用中文或英文均可，但需说明**做了什么**与**为什么**；
- 修复缺陷建议标注 `[RED]` / `[GREEN]` 成对提交（可选但推荐）；
- 不要修改 git 历史（已发布分支禁 force-push）；
- 一个 PR 只做一件事（改名 / 修复 / 文档 / 测试分开）。

## PR 流程

1. Fork 本仓库，从 `main` 创建特性分支（`fix/xxx` 或 `feat/xxx`）；
2. 实现 + 测试 + 更新 `CHANGELOG.md`（如有用户可见变化）；
3. 运行 `python3 -m pytest tests/ -q` 全绿；
4. 提交 PR，填写 `.github/PULL_REQUEST_TEMPLATE.md` 模板内容；
5. 维护者 review 后合并（可能要求补充测试或文档）。

## 文档改动

- 中文为主文档（`README.md`），英文为 `README.en.md`，两处保持一致；
- 技能文档（`skills/*/SKILL.md`）是 Agent 的运行时指令，措辞需精确；
- 改动配置结构时同步 `config.schema.json` 与 `scripts/dy_config.py` 的枚举/默认值。
