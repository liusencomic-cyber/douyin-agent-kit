"""conftest.py —— 共享 fixtures 与 mock 基础设施"""
import sys
import pytest
from unittest import mock


@pytest.fixture(autouse=True)
def fake_mlx_whisper():
    """在所有测试前注入假的 mlx_whisper 模块，避免 ModuleNotFoundError。
    测试可以用 mock.patch('mlx_whisper.transcribe', ...) 控制行为。
    """
    if "mlx_whisper" not in sys.modules:
        fake = mock.MagicMock()
        fake.transcribe = mock.MagicMock(return_value={
            "text": "", "segments": [], "language": "zh"
        })
        sys.modules["mlx_whisper"] = fake
    yield
    # 不清理 —— 测试间保持模块可用
