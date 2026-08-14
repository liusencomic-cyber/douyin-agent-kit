"""RED 测试：collect_notes_to_transcripts.py 死代码（P3-2）。

第 59 行 `have_ids = set(...) if False else set()`：if False 分支永不可达，
且 have_ids 变量从未被使用。
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCollectNotesDeadCode:

    def test_no_if_false_dead_branch(self):
        with open(os.path.join(REPO_ROOT, "collect_notes_to_transcripts.py"),
                  encoding="utf-8") as f:
            src = f.read()
        assert "if False" not in src, "死代码分支（if False）应删除"
