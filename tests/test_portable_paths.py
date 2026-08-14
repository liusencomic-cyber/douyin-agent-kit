"""RED 测试：脚本路径可移植化（去除本机硬编码 ~/Desktop/douyin-sync）。

开源用户 clone 仓库后，脚本应能通过环境变量 DOUYIN_SYNC_DIR 覆盖
工作目录，或在无环境变量时推断为脚本所在目录，而不是写死开发者本机路径。
"""
import importlib
from pathlib import Path


def _snapshot_transcribe():
    import transcribe_archive
    return {
        "BASE": transcribe_archive.BASE,
        "COLLECT_DIR": transcribe_archive.COLLECT_DIR,
        "PROCESSED_JSON": transcribe_archive.PROCESSED_JSON,
        "VAULT_INBOX": transcribe_archive.VAULT_INBOX,
    }


def _restore_transcribe(saved):
    import transcribe_archive
    transcribe_archive.BASE = saved["BASE"]
    transcribe_archive.COLLECT_DIR = saved["COLLECT_DIR"]
    transcribe_archive.PROCESSED_JSON = saved["PROCESSED_JSON"]
    transcribe_archive.VAULT_INBOX = saved["VAULT_INBOX"]


def _snapshot_qr_login():
    import qr_login
    return {
        "BASE": qr_login.BASE,
        "COOKIES_JSON": qr_login.COOKIES_JSON,
        "CONFIG_YML": qr_login.CONFIG_YML,
    }


def _restore_qr_login(saved):
    import qr_login
    qr_login.BASE = saved["BASE"]
    qr_login.COOKIES_JSON = saved["COOKIES_JSON"]
    qr_login.CONFIG_YML = saved["CONFIG_YML"]


class TestTranscribePortablePaths:
    """transcribe_archive.py 的 BASE 应支持环境变量覆盖与脚本目录推断。"""

    def test_base_env_override(self, monkeypatch):
        import transcribe_archive
        saved = _snapshot_transcribe()
        monkeypatch.setenv("DOUYIN_SYNC_DIR", "/tmp/fake")
        importlib.reload(transcribe_archive)
        try:
            assert transcribe_archive.BASE == "/tmp/fake", \
                f"环境变量 DOUYIN_SYNC_DIR 应覆盖 BASE，实际: {transcribe_archive.BASE}"
            assert transcribe_archive.COLLECT_DIR == "/tmp/fake/Downloaded/self_self/collect"
            assert transcribe_archive.PROCESSED_JSON == "/tmp/fake/processed.json"
        finally:
            _restore_transcribe(saved)

    def test_base_default_script_dir(self, monkeypatch):
        import transcribe_archive
        saved = _snapshot_transcribe()
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        importlib.reload(transcribe_archive)
        try:
            expected = str(Path(transcribe_archive.__file__).resolve().parent)
            assert transcribe_archive.BASE == expected, \
                f"无环境变量时 BASE 应推断为脚本目录 {expected}，实际: {transcribe_archive.BASE}"
        finally:
            _restore_transcribe(saved)

    def test_base_not_hardcoded_home(self):
        """RED: BASE 赋值行不应包含 ~/Desktop/douyin-sync 硬编码。"""
        import transcribe_archive
        src = open(transcribe_archive.__file__).read()
        for line in src.splitlines():
            if "BASE" in line and "=" in line and "expanduser" in line:
                assert "douyin-sync" not in line, \
                    f"BASE 不应硬编码 ~/Desktop/douyin-sync: {line.strip()}"


class TestQrLoginPortablePaths:
    """qr_login.py 的路径应支持环境变量覆盖与脚本目录推断。"""

    def test_paths_env_override(self, monkeypatch):
        import qr_login
        saved = _snapshot_qr_login()
        monkeypatch.setenv("DOUYIN_SYNC_DIR", "/tmp/fake")
        importlib.reload(qr_login)
        try:
            assert qr_login.BASE == "/tmp/fake", \
                f"环境变量 DOUYIN_SYNC_DIR 应覆盖 BASE，实际: {qr_login.BASE}"
            assert qr_login.COOKIES_JSON == "/tmp/fake/douyin-downloader/config/cookies.json"
            assert qr_login.CONFIG_YML == "/tmp/fake/douyin-downloader/config.yml"
        finally:
            _restore_qr_login(saved)

    def test_paths_default_script_dir(self, monkeypatch):
        import qr_login
        saved = _snapshot_qr_login()
        monkeypatch.delenv("DOUYIN_SYNC_DIR", raising=False)
        importlib.reload(qr_login)
        try:
            expected = str(Path(qr_login.__file__).resolve().parent)
            assert qr_login.BASE == expected, \
                f"无环境变量时 BASE 应推断为脚本目录 {expected}，实际: {qr_login.BASE}"
        finally:
            _restore_qr_login(saved)

    def test_paths_not_hardcoded_home(self):
        """RED: 路径赋值行不应包含 ~/Desktop/douyin-sync 硬编码。"""
        import qr_login
        src = open(qr_login.__file__).read()
        for line in src.splitlines():
            if "expanduser" in line and "douyin-sync" in line:
                assert False, \
                    f"路径不应硬编码 ~/Desktop/douyin-sync: {line.strip()}"
