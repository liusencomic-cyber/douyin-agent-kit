"""RED 测试：.gitignore 必须忽略 config*.yml 与 douyin-downloader/。

背景（WorkBuddy 审查 P0-1）：
- qr_login.py 会把 douyin-downloader/config.yml 写入仓库子目录；
- 博主蒸馏会写 config_<博主>.yml；
- README 指导 clone 上游 douyin-downloader 到本仓库子目录。
这些若不忽略，真实凭据/上游代码会被误提交。
"""
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_gitignore():
    with open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8") as f:
        return f.read()


class TestGitignoreSafety:

    def test_ignores_douyin_downloader(self):
        content = _read_gitignore()
        assert "douyin-downloader/" in content, (
            ".gitignore 应忽略 douyin-downloader/（README 指导 clone 上游到本仓库子目录）"
        )

    def test_ignores_config_yml(self):
        content = _read_gitignore()
        assert "config*.yml" in content, (
            ".gitignore 应忽略 config*.yml（qr_login.py 写 douyin-downloader/config.yml，"
            "博主蒸馏写 config_<博主>.yml）"
        )

    def test_keeps_example_config_tracked(self):
        """config*.yml 模式不得误忽略 douyin_agent_kit.config.example.yaml。"""
        r = subprocess.run(
            ["git", "check-ignore", "-q", "douyin_agent_kit.config.example.yaml"],
            cwd=REPO_ROOT, capture_output=True)
        assert r.returncode != 0, (
            "douyin_agent_kit.config.example.yaml 不应被 .gitignore 忽略"
        )
