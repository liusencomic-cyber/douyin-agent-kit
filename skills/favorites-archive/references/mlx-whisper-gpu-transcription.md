# mlx-whisper GPU 转录完整配方（2026-08-10 实测验证，M1 Max / 32GB）

方向 A（转录引擎 GPU 化）的落地配方。用户 三原则：尽量本地化；在本地化基础上降低功耗和性能占用；尽量简洁不重但要满足全部需求。

## 为什么换
- 旧方案 faster_whisper `large-v3-turbo` + device="cpu" int8：模型加载 79s + 转录 17.6s（71.9s 视频）= 96.7s/条，CPU 300%+ 满载（8 性能核全烧）。
- mlx-whisper GPU：转录 ~8s（批处理 ~3s/条），CPU user 仅 ~4s（GPU/Metal 干活）——12x 提速，功耗大降，质量等价（同模型同精度，错字也一致）。
- 附带收益：mlx_whisper 输出**逐句时间戳**（`[00:08.66] ...`），是方向 G（智能转录判断：转录→语义判断→按时间戳定向截帧）的定位基础。

## 环境（本机已具备）
- 系统 python3：`/opt/homebrew/bin/python3`（3.14.3），已装 `mlx 0.31.2 + mlx-metal + mlx-whisper 0.4.3 + onnxruntime 1.24.4`。
- 模型：`mlx-community/whisper-large-v3-turbo`（~1.6GB）→ `~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/`。**与 faster-whisper 的 CTranslate2 格式（mobiuslabsgmbh 缓存）和 brew whisper 的 .pt（~/.cache/whisper/）互不通用，须单独下载**。
- 验证 GPU：`python3 -c "import mlx.core as mx; print(mx.metal.is_available())"` → True。

## 六个环境坑（全部实测踩过）
1. **PYTHONPATH 污染**：douyin-sync venv（3.11）site-packages 残留会话 → 3.14 的 mlx_whisper 加载 cp311 numpy 报 `_multiarray_umath` 错。`env -u PYTHONPATH mlx_whisper ...`。
2. **缺依赖**：filelock + scipy + packaging；brew python3.14 有 PEP 668 保护 → `python3 -m pip install --break-system-packages filelock scipy packaging`。
3. **会话 cwd 被 enclave 沙箱改写**：cd 后 cwd 可能跳到奇怪路径，命令一律用绝对路径。
4. **HF 下载走 SOCKS 代理炸**：`all_proxy=socks5://127.0.0.1:7890`，httpx 缺 socksio → ImportError。下载时 `env -u all_proxy -u ALL_PROXY`（保留 http_proxy 走 HTTP 代理）。
5. **⚠️ 会话 HOME 被 enclave 沙箱改写（严重）**：`$HOME` 可能指向 `<SANDBOX_HOME> 全解析到沙箱 → huggingface_hub 把模型下到沙箱缓存。**任何 HOME 操作前先 `echo $HOME`；需真用户路径时 `export HOME=~` 或写死绝对路径**。曾因此误删真模型缓存（教训：删除前确认路径归属）。
6. **mx.load 用 blob hash 路径报 "Unknown file format"**：blob 名无扩展名，mx.load 按扩展名识别格式。验证模型完整性用 snapshot 软链接路径（`snapshots/<hash>/weights.safetensors`），不是 blobs 下的 hash 文件。

## CLI / Python API
```bash
env -u PYTHONPATH -u all_proxy -u ALL_PROXY HF_HUB_OFFLINE=1 mlx_whisper \
  --model mlx-community/whisper-large-v3-turbo --language zh \
  --output-format txt --output-dir <dir> --output-name <name> <video或wav>
```
- 输出格式：txt/vtt/srt/tsv/json/all。
- Python：`mlx_whisper.transcribe(mp4, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="zh", verbose=False)` → `result["segments"]` 是 **dict 列表**（`s["text"]`，不是 faster_whisper 的对象属性 `s.text`）；**无 vad_filter 参数**（faster_whisper 有，别传）。

## 离线化（关键修复）
- 坑：脚本清掉代理变量后，huggingface_hub 仍尝试联网检查模型 → 直连 HF 被墙挂死（300s）。
- 正解：脚本在 import mlx_whisper 前设 `os.environ["HF_HUB_OFFLINE"] = "1"` → 只读本地缓存，秒级完成；模型缺失时快速失败（报错清晰）而非挂死。
- 这是 用户「尽量本地化」的正解形态：模型已缓存 = 完全离线转录。

