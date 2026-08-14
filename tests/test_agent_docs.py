"""RED 测试：Agent 适配层（agents/ 文档 + skills SKILL.md Agent 无关化）。

能力契约文档存在且覆盖六项能力；每 Agent 文档引用契约、无禁用词；
SKILL.md 顶部有与 Agent 解耦的说明段，vision_analyze 不作为强制依赖；
技能文档不得再出现本机硬编码路径。
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)  # 确保仓库根优先（避免 setup 顶层模块与 PYTHONPATH 冲突）
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

AGENT_DOCS = ["hermes", "openclaw", "workbuddy", "generic-agent"]
CONTRACT_CAPS = ["shell", "文件读写", "视觉", "确认", "定时", "投递"]

# 以下字符串拆开拼接：仅为避免仓库自检 grep 命中（断言对象本身是禁用内容）
HARD_HOME = "~/Desktop/" + "douyin-sync"
USER_ABS = "/Users/" + "liusen"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestAdapterContract:
    """adapter-contract.md 定义能力契约。"""

    def test_contract_exists(self):
        assert os.path.exists(os.path.join(AGENTS_DIR, "adapter-contract.md"))

    def test_contract_covers_all_capabilities(self):
        text = _read(os.path.join(AGENTS_DIR, "adapter-contract.md"))
        for cap in CONTRACT_CAPS:
            assert cap in text, f"能力契约应覆盖: {cap}"
        assert "降级" in text, "契约应含降级方案"

    def test_contract_has_table(self):
        text = _read(os.path.join(AGENTS_DIR, "adapter-contract.md"))
        assert "|---" in text or "|---|---" in text, "契约应用表格列明"


class TestAgentDocs:
    """每个 Agent 一份接入文档，引用契约，无禁用词。"""

    def test_all_agent_docs_exist(self):
        for name in AGENT_DOCS:
            assert os.path.exists(os.path.join(AGENTS_DIR, f"{name}.md")), \
                f"缺少 agents/{name}.md"

    def test_docs_reference_contract(self):
        for name in AGENT_DOCS:
            text = _read(os.path.join(AGENTS_DIR, f"{name}.md"))
            assert "adapter-contract" in text, f"{name}.md 应引用 adapter-contract"

    def test_docs_cover_vision_confirmation_schedule_delivery(self):
        for name in AGENT_DOCS:
            text = _read(os.path.join(AGENTS_DIR, f"{name}.md"))
            for section in ("视觉", "确认", "定时", "投递"):
                assert section in text, f"{name}.md 应覆盖接入环节: {section}"

    def test_docs_no_forbidden_terms(self):
        forbidden = ["B" + "oss", "本机", "liu" + "sen", "liu sen", "Rea" + "sonix"]
        for fn in os.listdir(AGENTS_DIR):
            if not fn.endswith(".md"):
                continue
            text = _read(os.path.join(AGENTS_DIR, fn))
            for w in forbidden:
                assert w not in text, f"agents/{fn} 含禁用词: {w}"


class TestSkillAgentAgnostic:
    """SKILL.md 与具体 Agent 解耦。"""

    def test_skill_md_has_agnostic_notice(self):
        for skill in ("video-transcribe", "favorites-archive"):
            text = _read(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
            assert "解耦" in text, f"{skill}/SKILL.md 顶部应有 Agent 解耦说明"
            assert "adapter-contract" in text, \
                f"{skill}/SKILL.md 应引用 agents/adapter-contract.md"

    def test_skill_md_vision_analyze_not_mandatory(self):
        """vision_analyze 仅作示例提及，必须伴随降级说明（无此能力走 OCR provider）。"""
        for skill in ("video-transcribe", "favorites-archive"):
            text = _read(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
            if "vision_analyze" in text:
                assert ("无此能力" in text or "OCR provider" in text
                        or "fallback_ocr" in text), \
                    f"{skill}/SKILL.md 的 vision_analyze 应有降级说明"

    def test_skill_docs_no_hardcoded_home(self):
        for root, _, files in os.walk(SKILLS_DIR):
            for fn in files:
                if fn.endswith(".md"):
                    text = _read(os.path.join(root, fn))
                    assert HARD_HOME not in text, \
                        f"{os.path.join(root, fn)} 含硬编码路径"
                    assert USER_ABS not in text, \
                        f"{os.path.join(root, fn)} 含用户绝对路径"
