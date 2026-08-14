"""RED 测试：开源发布治理文件补齐。

验证仓库根的 SECURITY.md / CONTRIBUTING.md / CODE_OF_CONDUCT.md / CHANGELOG.md /
README.en.md，以及 .github/ 下的 Issue/PR 模板、CI 工作流、dependabot 配置存在且含关键内容。
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestGovernanceFiles:
    """开源治理文件必须存在。"""

    REQUIRED = [
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "CHANGELOG.md",
        "README.en.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/workflows/ci.yml",
        ".github/dependabot.yml",
    ]

    def test_required_files_exist(self):
        missing = [p for p in self.REQUIRED
                   if not os.path.exists(os.path.join(REPO_ROOT, p))]
        assert not missing, f"缺失治理文件: {missing}"

    def test_security_md_covers_disclosure_and_risks(self):
        text = _read(os.path.join(REPO_ROOT, "SECURITY.md"))
        assert "Security Advisory" in text or "security/advisories" in text, \
            "SECURITY.md 应说明 GitHub Security Advisory 私密报告渠道"
        assert "Cookie" in text, "SECURITY.md 应声明 Cookie 保存风险"
        assert "风控" in text or "批量" in text, \
            "SECURITY.md 应声明批量下载风控风险"

    def test_contributing_md_covers_setup_test_privacy(self):
        text = _read(os.path.join(REPO_ROOT, "CONTRIBUTING.md"))
        assert "venv" in text or "虚拟环境" in text, "应含开发环境设置说明"
        assert "pytest" in text, "应含测试命令 pytest"
        assert "Cookie" in text and "不得" in text, \
            "应声明不得提交真实 Cookie/账号 的隐私要求"
        assert "PR" in text or "Pull Request" in text, "应含 PR 流程"

    def test_code_of_conduct_contributor_covenant(self):
        text = _read(os.path.join(REPO_ROOT, "CODE_OF_CONDUCT.md"))
        assert "Contributor Covenant" in text, "应标注 Contributor Covenant"
        assert "2.1" in text, "应为 2.1 版本"

    def test_changelog_keep_a_changelog_and_0_1_0(self):
        text = _read(os.path.join(REPO_ROOT, "CHANGELOG.md"))
        assert "Keep a Changelog" in text, "应标注 Keep a Changelog 格式"
        assert "0.1.0" in text, "应记录 0.1.0 初始版本"

    def test_readme_language_switch(self):
        text = _read(os.path.join(REPO_ROOT, "README.md"))
        assert "README.en.md" in text, "README.md 顶部应有英文版链接"
        assert "English" in text, "语言切换链接应含 English"

    def test_issue_templates_valid_yaml_forms(self):
        import yaml
        for name in ("bug_report.yml", "feature_request.yml"):
            p = os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE", name)
            data = yaml.safe_load(_read(p))
            assert isinstance(data, dict) and data.get("name"), \
                f"{name} 应为 YAML form 且含 name"
            assert "body" in data and isinstance(data["body"], list), \
                f"{name} 应含 body 字段列表"

    def test_ci_matrix_and_commands(self):
        import yaml
        data = yaml.safe_load(_read(os.path.join(
            REPO_ROOT, ".github", "workflows", "ci.yml")))
        matrix = data["jobs"]["test"]["strategy"]["matrix"]
        py_versions = matrix.get("python-version") or matrix.get("python")
        assert "3.10" in py_versions and "3.13" in py_versions, \
            f"CI 矩阵应覆盖 Python 3.10–3.13，实际: {py_versions}"
        steps = data["jobs"]["test"]["steps"]
        cmds = " ".join(s.get("run", "") for s in steps)
        assert "pip install -r requirements.txt" in cmds, "CI 应安装 requirements.txt"
        assert "pytest" in cmds, "CI 应运行 pytest"

    def test_dependabot_pip_weekly(self):
        import yaml
        data = yaml.safe_load(_read(os.path.join(
            REPO_ROOT, ".github", "dependabot.yml")))
        updates = data["updates"]
        assert any(u.get("package-ecosystem") == "pip"
                   and u.get("schedule", {}).get("interval") == "weekly"
                   for u in updates), \
            "dependabot 应配置 pip 依赖每周检查"


class TestPythonVersionConsistency:
    """P3-4: requirements.txt / README.en.md 版本表述与 CI matrix 3.10-3.13 一致。"""

    def test_requirements_comment_matches_ci_matrix(self):
        text = _read(os.path.join(REPO_ROOT, "requirements.txt"))
        first = text.splitlines()[0]
        assert "3.10" in first and "3.13" in first, \
            f"requirements.txt 首行注释应与 CI matrix 一致，实际: {first}"
        assert "3.14" not in first, "不应声称依赖面向 Python 3.14"

    def test_readme_en_version_consistent(self):
        text = _read(os.path.join(REPO_ROOT, "README.en.md"))
        assert "3.14" not in text, "README.en.md 不应声称开发于 Python 3.14"
