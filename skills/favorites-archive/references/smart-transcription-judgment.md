# 智能转录判断（方向 G）—— 时间戳转录 + 语义判断画面需求 + 定向截帧

用户 需求（2026-08-10）：视频转文字不能只靠音频转录，很多博主口述不覆盖画面信息。要做**智能判断**：先转录并理解内容，再判断画面有没有口述未覆盖的信息、哪些时间段需要看画面——而不是无差别截帧。本文件记录完整实现、实测数据与核心坑（编码Agent 开发，Hermes 审计）。

## 架构链路（全部本地化）

```
转录（mlx-whisper GPU，segments 自带 start/end 时间戳）
  → 转录汇总文件新增「时间戳分段:」段，格式 [MM:SS.mmm --> MM:SS.mmm] 文本
  → analyze_visual_needs.py：调本地 Ollama qwen2.5:7b（http://127.0.0.1:11434 /api/chat）
      逐条判断 needs_visual + 标记需要画面的 segments（hint 分类）
  → extract_target_frames.py：按标记 segments 用 ffmpeg -ss/-to 定向截帧（fps=2 默认）
  → 帧 → vision_analyze OCR/理解 → 画面增量信息并入蒸馏报告
```

## 脚本（仓库根，可用 DOUYIN_SYNC_DIR 覆盖工作目录）

| 脚本 | 用法 | 输出 |
|---|---|---|
| `transcribe_only.py` / `transcribe_archive.py` | 不变（新增时间戳分段输出段，原格式保持） | 追加「时间戳分段:」每行 `[MM:SS.mmm --> MM:SS.mmm] 文本` |
| `analyze_visual_needs.py` | `--src <转录txt> --out <json> [--model qwen2.5:7b] [--ollama-url] [--max-items]` | `{"items":[{"title","needs_visual","reason","segments":[{"start","end","text","hint"}]}]}` |
| `extract_target_frames.py` | `--video-dir <post目录> --needs <json> --out <帧目录> [--fps 2]` | `条目名_序号_%03d.jpg`（目录匹配 `日期_标题_id`，-ss 前置快速定位） |

- 语义判断失败重试 3 次，仍失败降级 `{"needs_visual": false, "reason": "judge_failed"}` 不中断整体。
- Ollama 响应可能包 markdown 代码块，正则提取 JSON 容错。

## ⚠️ 核心坑：7B 语义判断漏判「内容类型→画面倾向」（2026-08-10 审计实锤）

**真实案例**：「2026-07-26_给大家整理数据做了一个机制对比」（79.7s，博主X）——口述内容是"98年纳指改革 vs 20年泡沫制度对比"，**画面全程配有 2000年 vs 2026年 规则对比表格**（7 维度：外资/ADR、新股纳入等待、市值计算口径、最低流通股要求、权重规则、权重调整频次、成分股更换周期；含具体数据如"单只权重上限15% vs 14%、前五龙头封顶38.5%"）。表格数据**口述完全未覆盖** = 典型画面增量信息。但 qwen2.5:7b 判 `needs_visual=false`，reason="全段均为口述观点"。

- **根因**：小模型不会推断"内容类型→画面倾向"；prompt 只列了直接线索（讲图表/K线/数据），缺推断规则。
- **修复**（编码Agent 合同）：① prompt 加推断规则——财经/知识类中制度/规则对比、历史演变、数据统计、机制原理、演示步骤、实物展示类口播，画面大概率配图表/表格/要点展示，即使口述看似完整也应标记；② 启发式关键词粗筛（对比/数据/机制/整理/演变/统计/表格/图/演示/教程）命中时把提示拼进 user prompt 强制 LLM 重点评估；③ 输出保留 `heuristic` + `llm_verdict` 审计字段（启发式命中但 LLM 判 false 时可见冲突）。
- **审计验证法**：对判断结果用 `vision_analyze` 抽帧做 ground truth（视觉模型确认表格在 24s/48s/首尾帧均出现），再对比 LLM 判断——**判断类功能必须用真视频验证 =true 路径**，只测 =false 路径会漏掉漏判。

## GPU 转录实测基准（M1 Max / 32GB）

- 71.9s 中文财经视频：mlx-whisper GPU **~8s**（模型已缓存） vs faster-whisper CPU **96.7s**（79.1s 模型加载 + 17.6s 转录）= **12x 提速**；CPU user 仅 ~4s（GPU 干活）。
- 批处理 2 条：31s 墙钟（25s 模型加载 + ~6s 转录 ≈ 3s/条；模型加载只发生一次，批处理摊薄）。
- 质量：与 faster-whisper **完全一致**（同模型同精度，连同音错字都一样）。
- **完全离线**：`HF_HUB_OFFLINE=1` + 清代理也能跑（模型本地缓存），符合 用户 本地化要求。

## ⚠️ ffmpeg -ss/-to 参数语义陷阱（2026-08-10 审计实锤，截帧脚本曾踩）

`extract_target_frames.py` 首版写 `["ffmpeg","-ss",str(start),"-i",mp4,"-to",str(end),"-vf","fps=2",...]`——**错**。

- **ffmpeg 语义**：`-ss` 在 `-i` 前 = 快速 seek 到 start；此时 `-to` 是**相对 seek 起点的时长**，不是绝对时间戳。传绝对 end 会每段多截 start 秒。
- **实测**：段 [8.8-11.5]（应 2.7s ≈ 5帧@2fps）截出 23 帧；整条视频 196 帧 vs 应有 ~60 帧，冗余 3-4 倍（批量蒸馏 = OCR 成本翻几倍）。
- **修复**：`"-to", str(round(end - start, 3))`；并跳过 `start < 0` / `end - start <= 0` 的段。修复后 60 帧与理论值（标记段总时长 × fps）完全吻合。
- **验收核对法**：任何 ffmpeg 截段命令后必须做"理论帧数 vs 实际帧数"核对（`段总时长 × fps ≈ 实际帧数`），偏差大 = 参数语义错误；再抽帧 vision_analyze 确认定位正确。

## 待办 / 未实现（截至 2026-08-10）

- L2：视频理解大模型接入（本地 Qwen3-VL 或 Gemini API）替代逐帧 OCR，问"画面里有哪些口述没讲的信息"。
- 批量并发调优（当前单线程串行调 Ollama，用户 低功耗要求下的保守选择）。
- 截帧内容 OCR 验证自动化；更强本地判断模型（gemma4:12b）对比评估。
- Obsidian 归档解耦（方向 F）：抖音技能只管内容格式，落盘规则上移独立 obsidian 技能。
