---
name: douyin-video-transcribe
version: 5.0
description: 抖音内容提取→总结→意图判断→自动行动。支持视频(Whisper转录)和图文作品(视觉OCR)。Scrapling DynamicFetcher下载，GPU转录+智能画面判断，根据内容类型自动归档到Obsidian或添加待办。
trigger: 用户发送抖音链接（含 douyin.com、iesdouyin.com、v.douyin.com 等短链）
---

> **Agent 无关声明**：本技能与具体 Agent 解耦，可在 Hermes / OpenClaw / WorkBuddy /
> Claude Code / Codex / 任意本地 Agent 上运行。文中提到的 `vision_analyze` 等工具名
> 仅为示例：**如你的 Agent 无此能力，请按 `agents/adapter-contract.md` 适配，视觉/OCR
> 走 `douyin_agent_kit.config.yaml` 的 `vision.ocr_provider` / `vision.fallback_ocr`**。
> 各 Agent 接入方式见 `agents/<你的agent>.md`（设置向导生成的 `AGENT_SETUP.md` 会指向对应文档）。

# 抖音内容提取与智能归档

将抖音视频/图文 → 提取文字 → 归纳总结 → 判断意图 → 自动执行后续动作。

> **脚本速查**：下载统一用 `scripts/douyin_download.py`（Scrapling 版，视频+图文双类型，直连→DynamicFetcher→StealthyFetcher 自动降级）。必须用安装了 scrapling 的 Python 运行（系统 Python 可能无 scrapling，需 pip install scrapling）。

## 环境依赖

| 环节 | 工具 | 说明 |
|---|---|---|
| 浏览器自动化 | Scrapling DynamicFetcher/StealthyFetcher | 访问抖音页面，获取cookie、视频URL、图片 |
| 下载视频/图片 | 页面内fetch() | 利用浏览器cookie绕过防盗链 |
| 提取音频 | `ffmpeg` | 提取音频轨为 wav |
| 语音转文字 | `whisper` (homebrew) | turbo 模型，首次下载 ~1.5GB |
| 视频截帧 | `ffmpeg` | 每3秒截一帧用于画面OCR |
| 视频画面OCR | 视觉模型 (vision_analyze) | 识别店铺招牌、店名、路标、字幕标注 |
| 图片OCR | 视觉模型 (vision_analyze) | 识别图文作品中的文字 |
| 归纳总结 | LLM | 基于原文生成结构化总结 |
| 意图判断 | LLM | 分析内容类型，决定后续动作 |
| 归档 | Obsidian / Todo | 根据意图写入对应位置 |

## 工作流程总览

```
用户发链接 → 解析短链 → 判断类型(视频/图文)
  ├─ 视频: douyin_download.py下载 → whisper转录 + 截帧OCR
  └─ 图文: douyin_download.py下载 → 页面文字 + 图片OCR
→ 合并文字 → LLM归纳总结 → **在聊天中展示完整结果**
  ├─ 工具类/策略类 → 意图判断 → 归档/待办
  └─ 知识/方法论类 → **深度分析（理论映射）** → 展示分析 → 归档
```

---

## Step 1: 解析链接 & 判断类型

短链格式 `v.douyin.com/XXXX` 先解析重定向获取真实URL：

```bash
curl -s -L -o /dev/null -w "%{url_effective}" "https://v.douyin.com/XXXX/"
```

根据URL路径判断类型：
- `/video/<ID>` → 视频类型
- `/note/<ID>` → 图文作品
- 其他路径 → 按视频流程处理

### ⚠️ 短链解析可能因设备/账号/地区而异

同一个 `v.douyin.com/XXXX` 短链，在不同环境（抖音 APP vs 浏览器、登录 vs 未登录、不同地区/IP）下，服务器可能返回不同的最终视频。**这是抖音服务器的正常行为，不是用户给错链接。**

如果按服务器端解析到的视频ID下载后，内容标题/作者与 用户 描述不一致：
- **不要反复争辩 "链接解析没问题" 或 "你那边打开不对"** — 这会让 用户 烦躁。
- **直接说明事实**：服务器端抓取到的内容是什么，标题/作者是什么，与描述不一致。
- **提供选项**：
  1. 按服务器端实际内容归档（注明是抖音短链重定向导致的差异）
  2. 请 用户 在抖音 APP 内打开视频后复制**长链接**（`https://www.douyin.com/video/<ID>` 或 `https://www.douyin.com/note/<ID>`）再发一次
  3. 请 用户 直接录屏/下载视频文件发过来
- 不要尝试超过两次不同的抓取方式后继续纠缠同一个短链。

详见 `references/douyin-shortlink-redirect-pitfall.md`。

---

## Step 2A: 视频类型 — 下载视频

统一用 `scripts/douyin_download.py`：

```bash
python3（安装 scrapling 的环境） douyin_download.py <视频ID或URL>
```

- 输出：`/tmp/douyin_<ID>.mp4`，音视频分离时输出 `_video.mp4` + `_audio.mp4`（**转录优先用 `_audio.mp4`**）。
- 网络策略：直连优先 → 失败自动降级 DynamicFetcher → StealthyFetcher（覆盖两种场景：有的视频 DynamicFetcher 能拿 video src，有的只能拿 blob: 且 performance 为空，换 StealthyFetcher 从 performance 拿 douyinvod 资源）。
- **网络连通性**：用户 已改代理规则，抖音直连不走代理，但 HK IP 会被封锁（ERR_CONNECTION_CLOSED）。运行时检测：直连失败→走代理；代理可能加载错误页面→必须校验标题。

**关键点：**
- 必须先访问首页获取cookie，再访问视频页（脚本已内置）
- video元素src可能为空或blob:开头，脚本会自动从 `performance.getEntriesByType('resource')` / response 筛选 `douyinvod.com` 真实资源（**过滤条件只查 `u.includes('douyinvod.com')`，不要加 `mime_type=video_mp4` 参数**——douyinvod URL 不包含此参数）
- 视频URL有时效性，获取后应立即下载
- 下载到 `media-video` 文件可能实际只含音频流（无 video stream）——见 Pitfall 13

---

## Step 0: Playwright 启动（图文和视频共用）

`douyin_download.py` 基于 Scrapling 已内置浏览器启动逻辑。若需手动写 Playwright 脚本：
- **Playwright 1.59+ 默认用 `chromium_headless_shell`，安装可能不完整**。必须先用 `find_chromium()` 探测实际路径（`~/Library/Caches/ms-playwright/` 下 `Google Chrome for Testing.app` 或 `Chromium.app`），通过 `executable_path` 参数启动。
- 不要浪费时间 `playwright install`（经常超时）。若 executable_path 不存在，可创建符号链接指向已装 Chrome，但优先 executable_path。
- 详见 `references/playwright-chromium-path.md`。

---

## Step 2B: 图文作品 — 提取图片与文字

统一用 `scripts/douyin_download.py`（传完整 `/note/<ID>` URL，**不要只传数字ID**——脚本检测 `INPUT.isdigit()` 会默认成 video 类型）。

- 输出：`/tmp/douyin_note_imgs/note_<ID>_img*.webp` + `pagetext.txt` + `meta.json`
- **页面正文是主要信息来源**：大部分图文作品的文字在页面 `body.innerText` 中即可完整提取（标题、正文、#标签、发布时间）。图片OCR只是补充图表数据。先提取页面文字，再决定是否需要OCR图片。

**关键点：**
- curl直接下载图片会403（防盗链），必须在页面上下文内用 `fetch()` 下载
- **图片域名不限于 `douyinpic`**：可能来自 `douyinpic.com`、`p3-pc-sign.douyinpic.com` 等CDN。用 `naturalWidth >= 400` 过滤内容图、文件大小 `> 5KB` 过滤装饰图，不依赖域名判断
- 图片去重：同一张图可能有封面URL和正文URL（`src.split('~')[0]` 去重）
- 截图(`page.screenshot`)在抖音页面经常超时，不要依赖

### OCR识别

逐张图片调用 `vision_analyze`，但**不要假设扩展名**。先读 `meta.json` 或列目录拿真实路径（抖音可能混用 `.webp` / `.jpeg`）：

```
vision_analyze(image_url="/tmp/douyin_note_imgs/note_XXXX_img0.webp",
               question="请完整提取这张图片中的所有中文文字内容，逐字逐句，不要遗漏不要概括；如你需要描述版面，请放在最后，优先输出OCR原文。")
```

**视觉OCR整理注意：** 部分视觉模型即使被要求"不要概括"，仍会输出图片描述/解释。归档时把"原文提取"与"模型描述"分开：正文总结可吸收描述信息，但"原文/OCR"区只保留可识别文字。

---

## Step 3A: 视频类型 — 提取音频 + Whisper转录

> **2026-08-10 升级：转录引擎已切 mlx GPU + 智能转录判断（与博主蒸馏技能对齐）。**
> 单条视频完整链路：下载 → **`transcribe_single.py`（GPU转录→语义判断→定向截帧）** → vision OCR → 总结归档。

### 推荐：单条智能转录（GPU + 语义判断 + 定向截帧）

```bash
# 1. 下载（Scrapling）
python3（安装 scrapling 的环境） douyin_download.py <视频URL或ID>

# 2. GPU 转录 + 语义判断 + 定向截帧（一条命令完成，系统 python3）
python3 transcribe_single.py --mp4 /tmp/douyin_<ID>.mp4 [--title "标题"]
```

- 输出：转录文本（带时间戳）、`needs_visual` 判断、若需要画面则自动按标记时间段截帧到工作目录。
- 语义判断走本地 Ollama qwen2.5:7b（回环 127.0.0.1，零云端）；三重校验（置信度/双重确认/实义词）防漏判+防误报。
- 若只想要转录不做画面判断：`--skip-judge`。
- ⚠️ 脚本在仓库根（批量管线同目录，已 git 管理、测试覆盖）。工作目录可用环境变量 `DOUYIN_SYNC_DIR` 覆盖。

### 备用：手动 Whisper（CPU，仅当 GPU 管线不可用时）

**⚠️ 先检查视频是否有音频轨**（抖音经常音视频分离成两个文件）：

```bash
ffprobe -v error -show_entries stream=codec_type /tmp/douyin_XXXX_video.mp4
```

- **有音频轨**：`ffmpeg -i /tmp/douyin_XXXX.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/douyin_XXXX.wav -y`
- **无音频轨**：用单独下载的 `_audio.mp4` 转录（`ffmpeg -i /tmp/douyin_XXXX_audio.mp4 ...`）
- **反向情况**：下载的"视频"文件可能实际只有音频（codec_type=audio 无 video stream）→ ffmpeg 截帧会报错，跳过截帧OCR，用音频转录即可

```bash
KMP_DUPLICATE_LIB_OK=TRUE whisper /tmp/douyin_XXXX.wav --model turbo --language zh --output_format txt --output_dir /tmp/
```

- **必须**设置 `KMP_DUPLICATE_LIB_OK=TRUE`（macOS PyTorch OpenMP冲突）
- `turbo` 模型精度与 large 相当，速度快4-5倍；长音频（>5分钟）CPU-only 超时 → 降级 `--model base --device cpu --threads 8`（提速4-5倍，中文质量仍可用）
- 首次运行自动下载模型（~1.5GB）

### 视频画面文字提取（必做 ⭐）

**视频中经常包含音频未提及的店铺招牌、店名、路标、字幕标注等关键信息。** 转录完成后必须截帧 OCR，不能跳过。

- **优先用智能管线**（transcribe_single.py 已按语义判断定向截帧，只截"讲图表/代码/演示/表格"的段落，不再整段瞎截）。
- 手动模式（无智能判断时）按下方旧策略：

```bash
# 每3秒截一帧（2分钟视频≈40帧）
ffmpeg -i /tmp/douyin_XXXX.mp4 -vf "fps=1/3" /tmp/douyin_XXXX_frame_%03d.jpg -y
```

**OCR策略（分批并行，每批5帧）：**
- 逐帧调用 `vision_analyze`，问题模板：`"识别这张抖音视频截图中的所有文字，特别是店铺招牌、店名、日文标识、路标、字幕标注。逐字逐句提取，不要遗漏。"`
- 优先识别含店招/文字的画面帧（画面变化大的帧信息量高）
- OCR 结果中的店铺名、地址等结构化信息单独列出，补充到归纳总结
- vision_analyze 可能超时，超时的帧跳过即可，不要重试阻塞

**采样密度：** 默认 `fps=1/3`（每3秒1帧）；快剪风格视频对变化剧烈区间补 `fps=1` 帧（相邻帧文件大小差 >30% 说明画面变化大）；实际按内容密度控制每8-12秒一帧即可覆盖产品分段。

**本地 OCR 方案（已测试，不可用）：** Tesseract 对自然场景视频帧全部返回空（文档扫描 OCR 不适合店招）；EasyOCR 待测；**当前唯一可用方案是 vision_analyze**。

---

## ⚠️ 铁律：必须先展示完整结果，再问归档

**这条规则在 Step 4 和 Step 5 之间执行，不可跳过、不可颠倒顺序。**

### Step 4a: 在聊天中展示完整提取结果

**必须在聊天中输出完整内容，让 用户 看到结果。** 格式：

```
📝 【归纳总结】
一、核心主题：xxx
二、要点提炼：
  1. xxx
  2. xxx
  3. xxx
三、关键信息/数据：xxx

📜 【原文转录/OCR文字】
（完整逐字稿，不删不减）
```

**总结原则：** 归纳总结忠实于原文，不添加视频未提及的信息；原文转录绝对不删减；优先提取核心观点、关键数据、行动建议。

### 知识/方法论类内容的深度分析

如果内容属于知识/方法论类（自我认知、心理学、学习方法等），展示完标准总结后，**必须追加理论溯源分析**：①拆解底层逻辑结构；②映射到现有理论体系（Adler 个体心理学、Ikigai、心流理论等）；③判断是重新发现/直接引用/混合创新；④推荐关联书籍并说明原因。详见 `references/content-analysis-deep-dive.md`。

### Step 4b: 附带要点说明

展示完完整结果后，附带 2-3 句话的关键要点说明，让 用户 一眼知道内容价值。不要只贴总结然后直接跳到归档。

### Step 4c: 再问归档

展示完之后，再询问 用户 是否需要归档/行动。**不要先问归档再展示。** 顺序必须是：展示结果 → 要点说明 → 询问归档。

**常见错误（禁止）：** 先问"确认文件名"再展示；直接说"已归档"不展示；只展示总结不展示原文转录；展示完直接归档不询问。

---

## Step 5: 意图判断与自动行动 ⭐

根据内容判断 用户 的意图，自动执行对应动作：

### 意图类型与行动映射：

| 内容类型 | 意图判断 | 自动行动 |
|---|---|---|
| 炒股/投资经验、市场分析 | 知识归档 | 生成Obsidian笔记，存入 `_inbox/赫尔墨斯_inbox/`（归档规则见 obsidian 技能） |
| 量化因子/交易策略/回测策略 | 策略报告归档 | 生成供 用户 专业回测系统使用的结构化报告/规格书并写入 Obsidian；不要默认由 Hermes 执行实际回测 |
| GitHub项目/开源工具/软件推荐 | 工具待测 | 添加到待办事项，提醒用户测试；也可直接生成 Obsidian 工具笔记后添加待办测试 |
| 读书/学习/方法论 | 知识归档 | 生成Obsidian笔记 |
| 好物推荐/产品测评 | 消费决策 | 添加到待办事项，附链接和要点 |
| 新闻/热点/时事 | 资讯了解 | 仅展示总结，不归档；但 用户 明确说"所有链接都要归档"时，生成简洁笔记归档 |
| 生活技巧/教程 | 技能学习 | 生成Obsidian笔记 |
| 其他 | 视情况 | 先展示，询问用户是否需要归档；若 用户 明确规则"所有链接都要归档"，则直接归档 |

**归档到 Obsidian 的规则（2026-08-10 解耦，全局规则归 `obsidian` 技能）：**
- ⚠️ 写入路径/命名/inbox 约定等**全局规则已上移 obsidian 技能**（note-taking/obsidian），本技能直接引用，不再自行维护。
- 唯一真实 Vault（2026-08-05 用户 确认）：`<OBSIDIAN_VAULT>`，写 `_inbox/赫尔墨斯_inbox/`。⚠️ 只写配置指定的 Vault，其余目录只读。
- 文件命名：`YYYY-MM-DD_主题.md`
- 普通文档写入前仍需确认文件名；**量化因子/交易策略类内容例外：按命名规则自动生成文件名并直接写入，无需每次确认**
- **当 用户 明确规则"所有我分享给你的链接都要归档"时，所有链接直接写入 Obsidian，无需逐条询问**。仅在内容属于量化策略/投资类时触发结构化策略报告流程
- 笔记内容必须附上抖音原始链接
- 服务器端抓取内容与 用户 描述不一致（短链重定向）时，笔记注明："该短链在服务器端解析到的内容为 X，可能与用户描述不一致，建议用长链接复核。"
- 笔记格式：
```markdown
# 标题

🔗 来源：[抖音](原始链接)
📅 日期：YYYY-MM-DD
🏷️ 标签：#类型标签

---

## 归纳总结
（结构化总结内容）

## 原文内容
（完整文字，不删减）
```

**添加待办的规则：**
- 用 todo 工具添加待办事项；内容包含：工具名/策略名、要点、抖音链接
- GitHub/开源工具推荐 → `测试 <工具名> ...`；不要只展示总结后结束
- **量化因子/交易策略例外边界**：用户 已明确这类内容默认只需要报告/规格书，供其专业回测系统使用；Hermes 不应默认创建"执行回测/实现回测"的 todo 或 Kanban 任务。只有 用户 明确说"帮我回测/实现/跑一下"时，才进入 Hermes 回测执行队列
- 需要提醒 用户 后续验证，只能措辞 `专业系统验证 <策略名> ...` 或在报告内写"验证清单"，不要写成 Hermes 的 `待回测/执行回测` 任务

**量化因子/交易策略的额外规则：**
- 不能只总结；必须完成：①结构化统计整理；②写入 Obsidian 策略报告/规格书。默认不执行实际回测
- Obsidian 笔记必须包含：策略名称、来源链接、适用股票池/市场、因子定义、选股规则、入场规则、退出规则、仓位/持仓数量、风控/空仓规则、视频宣称绩效、风险点、供专业回测系统验证清单、完整转录/原文
- 写入位置固定为 iCloud Vault 的 `_inbox/赫尔墨斯_inbox/`；文件名 `YYYY-MM-DD_主题.md`
- 标签优先使用 `#策略报告`；避免用 `#待回测` 触发 Hermes 自己去回测

**判断流程：** ①分析归纳总结核心主题和关键词；②判断意图类型；③执行对应动作；④向 用户 汇报执行结果。

---

## Step 6: 清理临时文件

所有临时文件必须全部清理，包括mp4：

```bash
# 视频类型
rm -f /tmp/douyin_XXXX.mp4 /tmp/douyin_XXXX.wav /tmp/douyin_XXXX.txt
# 图文类型
rm -rf /tmp/douyin_note_imgs/
```

---

## 页面结构参考

- [references/douyin-shortlink-redirect-pitfall.md](references/douyin-shortlink-redirect-pitfall.md) — 短链服务器端与客户端解析不同视频；处理流程与归档标注方式。
- [references/blob-video-performance-capture.md](references/blob-video-performance-capture.md) — 播放器只暴露 blob URL 时，从 performance/response 捕获 `douyinvod.com` 真实音视频资源并下载。
- [references/playwright-chromium-path.md](references/playwright-chromium-path.md) — Playwright 1.59+ macOS Chromium 路径探测与修复。
- [references/local-ocr-evaluation.md](references/local-ocr-evaluation.md) — 本地 OCR 方案（Tesseract/EasyOCR）在抖音视频帧上的实测评估。
- [references/scrapling-alternative.md](references/scrapling-alternative.md) — Scrapling DynamicFetcher 替代方案（精简 Playwright 脚本至 ~50 行），2026-06-06 实测可用。
- [references/content-analysis-deep-dive.md](references/content-analysis-deep-dive.md) — 知识/方法论类内容的深度分析流程，含理论映射表（Adler/Ikigai/Jung等），归档前执行。

## Pitfalls（2026-08-10 重构重新编号）

### 下载类
1. **脚本必须用 Hermes venv Python 运行** — `douyin_download.py` 依赖 scrapling（在 Hermes venv，`python3（安装 scrapling 的环境）`），系统 Python 3.14 找不到。显式指定 venv Python：`python3（安装 scrapling 的环境） douyin_download.py <URL>`。不要直接 `python3 douyin_download.py`。
2. **Script defaults to "video" when given numeric ID** — `douyin_download.py` 检查 `INPUT.isdigit()` 默认 `content_type = "video"`。`/note/` 内容必须传完整 URL（或 `https://www.douyin.com/note/<ID>`），否则走错分支。
3. **curl下载视频不可靠** — URL截断、403、超时频发。**优先用页面内fetch()下载**（脚本已内置），curl仅作fallback。
4. **图文图片403防盗链** — curl直接下载图片返回403，必须在页面上下文内用 `fetch()` 下载（脚本已内置）。
5. **video元素src为空或blob:** — 先 `page.evaluate()` 取非blob src；仍 blob 则从 `performance.getEntriesByType('resource')`/response 筛选 `douyinvod.com`（只过滤 `u.includes('douyinvod.com')`，**不要加 `mime_type=video_mp4`**——URL 不含此参数），提取 `media-audio`/`media-video` 后页面内 `fetch()` 下载。脚本已内置此逻辑；下载的是分离音视频两个文件（`_video.mp4` + `_audio.mp4`），转录优先用 `_audio.mp4`。
6. **视频URL有时效** — 获取后应立即下载。
7. **yt-dlp 对抖音不可用** — 唯一可靠方案是浏览器自动化（Scrapling/Playwright）。
8. **StealthyFetcher vs DynamicFetcher 互补** — 有的视频 DynamicFetcher 能直接拿 video src，有的只能返回 blob: 且 performance entries 为空；换 StealthyFetcher 可能从 performance 拿到 douyinvod 资源。当前脚本用 DynamicFetcher + performance entries fallback 覆盖两种场景。

### 转录类
9. **KMP_DUPLICATE_LIB_OK** — 不设此环境变量 whisper 会 abort。
10. **视频可能无音频轨（音视频分离）** — 抖音常把视频和音频分成两个独立文件（`media-video-avc1` + `media-audio-und-mp4a`）。下载后必须 `ffprobe` 检查音频流；无音频轨则单独下载 `media-audio-und-mp4a` 用于转录。不要假设视频 mp4 一定有音频。
11. **"视频"文件可能实际只有音频** — 从 performance entries 下载的 `media-video` 可能只含音频流（codec_type=audio 无 video stream）。`ffprobe -v error -show_entries stream=codec_type` 检查，只有 audio 则跳过截帧OCR直接用音频转录。若两条文件大小完全相同，说明抓到同一音频，需另起会话从 performance entries 分别抓真正的 media-video（hevc/h264）用于截帧。
12. **Whisper base 模型作为 turbo 超时降级方案** — CPU-only 长音频（>5分钟）turbo 可能超时（300s+）。降级 `--model base --device cpu --threads 8` 数分钟完成，中文质量仍可用。
13. **brew whisper 可能因 numpy 崩坏** — `whisper` CLI 报 `No module named 'numpy._core._multiarray_umath'` 时不要折腾 brew 重装。Hermes venv 有 `faster_whisper`，用 PATH+PYTHONPATH wrapper 跑：`WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")`，2.5 分钟中文音频约 1-2 分钟出稿（VIX/VXN 会误写 VAX/VSM，整理时校正术语）。批量场景优先 mlx GPU（见 douyin-favorites-archive）。

### OCR类
14. **视频画面OCR是必做步骤，不是可选** — 抖音视频经常在画面上标注店铺招牌、店名、地址等音频没有的信息。转录完成后必须截帧OCR，不能跳过。
15. **视觉模型 provider 必须显式配置** — `auxiliary.vision.provider` 默认 `auto` 时 `vision_analyze` 可能报 `No LLM provider configured for task=vision` 或 `unknown variant image_url`。**本机可靠配置（2026-08-10 实测）**：
   ```bash
   hermes config set auxiliary.vision.provider openai-codex
   hermes config set auxiliary.vision.model gpt-5.6-sol
   ```
   ⚠️ **kimi-coding 是纯文本 coding 端点，不支持视觉**（旧 pitfall 写"kimi-coding 支持 vision"已过时作废）。设置后无需重启，新调用立即生效。
16. **Vision OCR 的 prompt 必须限定只返回文字** — kimi-for-coding 视觉识别易混入图片描述/解释。用强约束 prompt（"只输出图片中的文字，不要描述图片。"）；收到结果后过滤"图片描述/含义解释"，只保留 OCR 文字；归档时不要把模型解释当原文。
17. **批量 OCR 时单张图片单独调用** — 不要一次上传多张图片，逐张调用更易识别小字、表格和复杂排版。
18. **OCR 完成后优先读取页面文字而非图片 OCR** — 图文主体文案在 `body.innerText` 通常已完整。图片 OCR 仅补充图表、清单、数字等。归档时页面文字与 OCR 文字合并去重。
19. **页面文字是图文作品的主要来源** — 大部分图文在 `body.innerText` 可提取完整正文（标题、描述、#标签、发布时间）。图片OCR仅补充图表数据。不要跳过页面文字提取直接依赖OCR。
20. **图片域名多样，不要只过滤 douyinpic** — 图文内容图可能来自 `douyinpic.com`、`p3-pc-sign.douyinpic.com` 等CDN。用 `naturalWidth >= 400` + 文件大小 `> 5KB` 识别内容图，不依赖域名。
21. **图片去重** — 同一张图可能有封面URL和正文URL（`src.split('~')[0]` 去重）。
22. **OCR路径必须来自实际保存结果** — 图文图片扩展名可能是 `.webp`/`.jpeg`，先读 `meta.json` 或列目录拿真实路径，不手猜。
23. **视觉模型会混入解释性文字** — OCR prompt 即使写"不要概括"，模型仍可能返回版面描述/解释（kimi-for-coding 更明显）。归档时"OCR原文"与"模型理解"分层，只抽取 `图中所有文字提取`/`代码块`/`表格` 区域的字面内容。
24. **不要把帧 OCR 委派给 delegate_task 子Agent** — 实测子Agent 对 vision_analyze 帧 OCR 会整段编造结果（虚构字幕/品牌/谎称无文字），与主Agent亲自 OCR 完全矛盾。帧 OCR 必须由主Agent亲自调用，分批并行（每批5帧），按视频长度控制采样密度（每8-12秒一帧）。
25. **Tesseract 本地 OCR 视频帧不可用** — 文档扫描 OCR 不适合自然场景（店招占比小+复杂背景全返回空）。当前唯一可用方案是 vision_analyze。

### 网络与代理类
26. **抖音IP封锁动态变化** — HK IP(103.135.100.200)被抖音拒绝连接(ERR_CONNECTION_CLOSED)。直连和本地代理可能走同一IP，都需要非HK代理节点。**策略：直连优先→代理降级**；两种都失败则告知 用户 在 Clash 中配置 douyin.com 走非HK节点。
27. **代理导致加载错误页面** — 走代理时 Playwright 可能跳转到不相关视频（标题完全不同）。必须校验页面标题是否匹配预期。
28. **网络连通性动态变化** — 代理规则和出口IP会变，之前能直连不代表现在也能，运行时检测。
29. **GitHub/HK网络** — raw.githubusercontent.com 从HK访问被墙或极慢，git clone 需走代理。
31. **execute_code 沙箱无 playwright 模块** — 必须在 `terminal` 中运行 Playwright/Scrapling 脚本，不能用 `execute_code`。

### 流程与归档类
32. **短链在服务器端与 用户 端可能解析到不同视频** — 平台行为，不是用户给错链接。不要反复争辩，直接说明服务器端抓到的实际内容，给三个选项（按实际归档/长链接重发/直接发视频文件）。不要尝试超过两种抓取方式后继续纠缠。详见 `references/douyin-shortlink-redirect-pitfall.md`。
33. **Obsidian写入规则（2026-08-10 解耦）** — 只能写 `_inbox/赫尔墨斯_inbox/`（iCloud 唯一真实 Vault），其他目录只读；写入前确认文件名（量化策略类例外自动命名）。**全局规则以 obsidian 技能为准**。
34. **意图判断边界** — 内容类型不明确时，宁可先展示再询问，不要误判。
35. **图文vs视频混合** — 短链解析后检查URL路径，`/note/` 是图文，`/video/` 是视频，走不同分支。
36. **流程必须一次跑完** — 收到抖音链接后，必须从解析到归档/待办一气呵成。不能停在转录/OCR就停下来汇报。每条链接处理完必须走到 Step 5（意图判断+自动行动），除非真实阻塞。
37. **普通知识图文"存一下"也要先完整处理** — 用户说"存一下/收藏/保存"时，不要只展示总结；应完成下载、OCR、结构化 Markdown 草稿。非自动写入类别先写到 `/tmp/` 草稿并向 用户 确认文件名/路径后再写入 Vault。确认前不丢草稿、不清理草稿文件。
38. **知识/方法论类内容必须先做理论溯源分析再归档** — 不能只做表面总结+归档，展示完标准总结后追加底层逻辑拆解和理论体系映射。详见 `references/content-analysis-deep-dive.md`。

## 已尝试但失败的方案（不要重试）

| 方案 | 失败原因 |
|---|---|

| 方案 | 失败原因 |
|---|---|
| `yt-dlp` 直接下载 | 需要 s_v_web_id cookie，API返回空JSON |
| `yt-dlp --cookies-from-browser safari/chrome` | Cookie不满足抖音验证要求 |
| Playwright 不走代理 (HK IP) | 被抖音拒绝连接(ERR_CONNECTION_CLOSED) |
| Playwright 走代理加载错误页面 | 代理节点导致跳转到不相关视频，标题与目标不符 |
| video.src返回blob:URL | 无法直接下载，需用请求拦截或等待加载获取真实URL |
| Cookie转移策略(代理获取cookie→直连访问) | 直连也被封锁时同样ERR_CONNECTION_CLOSED，不可靠 |
| `f2` 工具 | HTTP代理配置不生效，ConnectError |
| curl 直接下载图片 | 403 Forbidden（防盗链） |
| curl 直接访问抖音API | 无有效cookie，返回空或403 |
| page.screenshot(full_page=True) | 抖音页面字体加载导致超时 |
| 第三方解析站(douyin.wtf/tikhub) | 返回404/Not Found |
| Tesseract 本地 OCR 视频帧 | 纯文字测试图完美，但真实视频帧（720×1280竖屏，店招占比小+复杂背景）全部返回空；Tesseract 是文档扫描 OCR，不适合自然场景文字识别 |
