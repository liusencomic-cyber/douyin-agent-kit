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


@pytest.fixture(scope="session")
def _preflight_fake_model(tmp_path_factory):
    """session 级：模拟 mlx 模型缓存中的 weights.safetensors 路径。

    形态对齐 ~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/
    snapshots/<hash>/weights.safetensors。[RED] 阶段仅返回路径（文件不存在，
    模拟 CI 干净环境模型缺失）；[GREEN] 阶段创建文件（模型检查通过）。
    """
    weights = (
        tmp_path_factory.mktemp("fake-mlx-model")
        / "models--mlx-community--whisper-large-v3-turbo"
        / "snapshots"
        / "abc123"
        / "weights.safetensors"
    )
    return weights


@pytest.fixture(autouse=True)
def mock_model_cache(_preflight_fake_model, monkeypatch):
    """为所有测试注入 PREFLIGHT_MOCK_MODEL，避免 preflight_check.sh 依赖真实模型缓存。

    背景：test_preflight.py 的“全通过”场景未设置 PREFLIGHT_MOCK_MODEL，CI 干净环境
    （无 ~/.cache/huggingface 模型缓存）下 check_model_cache 返回 FAIL → exit 1 →
    断言失败（GitHub Actions 实测）。测试经 subprocess.run env=os.environ.copy() 传
    环境变量，本 fixture 用 monkeypatch.setenv 注入 PREFLIGHT_MOCK_MODEL；显式传
    PREFLIGHT_MOCK_MODEL 的测试（test_model_cache_missing/present、
    test_multiple_failures_reported）经 env.update(env_overrides) 覆盖本值，不受影响。
    """
    monkeypatch.setenv("PREFLIGHT_MOCK_MODEL", str(_preflight_fake_model))
