# douyin-agent-kit

> **[中文](README.md) | [English](README.en.md)**

An **agent-agnostic** toolkit for Douyin (抖音) content extraction and creator distillation:
**GPU transcription + smart visual-needs judgment + targeted frame extraction + creator
distillation reports**. Works with Hermes / OpenClaw / WorkBuddy / Claude Code / Codex /
any local agent — not bound to any single agent.

- `skills/video-transcribe/` — single-link extraction (video / image-text post) → transcription → visual judgment → archiving
- `skills/favorites-archive/` — batch workflows: favorites sync, creator full-archive distillation, smart visual judgment
- `scripts/` — unified config loading (`dy_config.py`), transcription engine (mlx-whisper GPU), semantic judgment (Ollama), targeted frame extraction
- `setup/` — setup wizard + environment checks (entry point for new users)
- `agents/` — per-agent adapter docs (capability contract)
- `tests/` — 200+ pytest tests

## Quick Start (4 steps)

### 1. Clone

```bash
git clone <this-repo-url> douyin-agent-kit && cd douyin-agent-kit
```

### 2. Run the setup wizard

```bash
# Interactive (choose Agent / machine type / ASR / Vision / features / archive)
python3 setup/setup_douyin_agent_kit.py

# Or non-interactive (parameter injection, for unattended/test use)
python3 setup/setup_douyin_agent_kit.py --non-interactive \
    --agent hermes --machine apple-silicon
```

The wizard generates:

- `douyin_agent_kit.config.yaml` — unified config (ASR / Vision switchable)
- `AGENT_SETUP.md` — onboarding doc tailored to your chosen agent
- `archive_config.json` — only when Obsidian archiving is enabled

### 3. Environment checks

```bash
python3 setup/checks.py
```

Outputs an `OK` / `WARN` / `MISSING` summary. If anything is `MISSING`, follow the hints
to install it and re-run (dependencies in `requirements.txt`; `tesseract` is a system package).

### 4. Onboard your agent

Hand the repo to your local agent and let it follow `AGENT_SETUP.md`;
the generic capability contract lives in `agents/adapter-contract.md`, and per-agent
details in `agents/<your-agent>.md`. Agents without vision capabilities can still run
the full pipeline (OCR falls back to a configured local solution or is disabled).

## Features

| Capability | Description |
|---|---|
| **Agent-agnostic** | No hard dependency on any agent; capability contract + per-agent docs; vision optional and degradable |
| **Configurable ASR** | `asr.provider`: mlx-whisper / faster-whisper / whisper.cpp / external-command / none (mlx-whisper implemented; others are reserved interfaces with explicit errors) |
| **Configurable Vision** | `vision.judge_provider` (ollama / openai-compatible / none) + `vision.ocr_provider` (agent-vision / tesseract / paddleocr / qwen-vl / gemini / openai-compatible / none) |
| **GPU transcription** | mlx-whisper (Apple Metal), ~12x faster than faster-whisper CPU; CPU usage drops from ~300% to single digits |
| **Fully offline** | Models cached locally + `HF_HUB_OFFLINE=1`, no network dependency |
| **Smart visual judgment** | Local Ollama (qwen2.5:7b) decides which time ranges have on-screen info (charts/code/tables/demos); triple verification to reduce misses and false positives |
| **Targeted frame extraction** | Frames are extracted only for semantically marked timestamps, not the whole video |
| **Creator distillation** | Full transcription → viewpoint condensation (sliding-window) → 7-section report |
| **Setup wizard** | Interactive / non-interactive config generation; new users up and running in 4 steps |
| **Risk protection** | Preflight checks for leftover processes / concurrent downloaders / model cache / Ollama |

## Configuration

- `douyin_agent_kit.config.yaml`: ASR / Vision / archive / feature switches
  (structure defined in `config.schema.json`, commented example in
  `douyin_agent_kit.config.example.yaml`; or just run the wizard)
- Working directory: override with env var `DOUYIN_SYNC_DIR`; defaults to the script
  directory when unset (no hardcoded machine paths)
- Semantic judgment: `vision.judge_provider` (default ollama) + `vision.judge_model`
  (default qwen2.5:7b), `vision.max_chars` (truncate over-long input),
  `vision.verify_rounds` (double-check)
- Archive path: `archive.vault_inbox` (Obsidian vault inbox) or `archive_config.json`

## Requirements

- Python 3.10+ (developed and tested on 3.10–3.13)
- [ffmpeg](https://ffmpeg.org/) (audio extraction / frame extraction)
- Optional:
  - [Ollama](https://ollama.com) local service (semantic judgment; `ollama pull qwen2.5:7b`)
  - mlx-whisper (Apple Silicon transcription; `pip install mlx mlx-whisper`)
  - tesseract (local OCR fallback; macOS: `brew install tesseract`, Debian: `apt install tesseract-ocr`)
- Upstream downloader: [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader)
  (MIT), clone into the `douyin-downloader/` subdirectory (for favorites/batch scenarios)

```bash
# Dependencies (add --break-system-packages on PEP 668 environments)
python3 -m pip install --break-system-packages -r requirements.txt

# Ollama model (semantic judgment)
ollama pull qwen2.5:7b

# Transcription model (auto-downloaded on first run, ~1.6GB to ~/.cache/huggingface)
```

## Security notes

- **Never commit real cookies/credentials** — `config/cookies.json` and
  `douyin-downloader/config*.yml` hold sensitive login state and are gitignored.
- **Batch downloads carry platform risk controls** (sliders, rate limits, cookie
  expiry). Follow the account-safety rules: read only your own favorites, low-frequency
  increments, single-threaded, same IP, stop immediately on risk-control signals.
- **Prompt-injection hardened** — transcript text is declared as data (not instructions)
  in the judge prompt; suspicious injection/refusal replies are downgraded to `judge_failed`.
- **Safe work-dir cleanup** — `transcribe_single.py` refuses to remove `/`, `~`, or the
  repo root; only repo-internal or `/tmp` `douyin`/`tmp`-prefixed directories are cleaned.

## Known limitations

- The transcription engine currently implements `mlx-whisper` (Apple Silicon);
  `faster-whisper` / `whisper.cpp` / `external-command` are reserved interfaces that
  raise a clear `NotImplementedError` rather than pretending to work.
- Transcription quality matches faster-whisper (same model, same precision); Whisper's
  homophone errors (e.g. Chinese market terms) need manual correction when editing.
- Semantic judgment uses a 7B model and is slightly noisy; the triple verification
  (confidence / double-check / content keywords) substantially reduces misses and
  false positives.
- Video download depends on the upstream douyin-downloader (MIT); clone it yourself.
  Cookie login goes through `qr_login.py` (QR scan).

## Testing

```bash
python3 -m pytest tests/ -q
```

## License

MIT. Upstream `douyin-downloader` is MIT (cloned by the user; not distributed with this repo).
