# 博主全量蒸馏 → 单篇报告工作流

约定：博主蒸馏 = **一篇超详细 Obsidian 报告**，不是每支视频一篇笔记。
本文件是 230 条全量蒸馏的完整可复用路径（35 万字符转录 → 单篇报告）。

## 0. 关键脚本（仓库根，可用 DOUYIN_SYNC_DIR 覆盖工作目录）

| 脚本 | 用途 |
|---|---|
| `transcribe_only.py` | 纯转录汇总：`--src-dir <post目录> --out /tmp/<博主>_all_transcripts.txt --processed processed_<博主>.json`。不写 Obsidian，只 append 汇总文件。格式：`===== [日期] 标题 =====\n视频文案: ...\n原文转录: ...` |
| `collect_notes_to_transcripts.py` | 从误写的逐条 Obsidian 笔记按 aweme_id 回收转录文本（`--processed --inbox --out`），用于纠正旧模式产物 |
| `audio_check.py` | 音频质量检测（ffmpeg volumedetect + silencedetect）→ ok/weak/silent/music_or_sparse，非 ok 截前/中/后 3 帧供 OCR |
| `transcribe_archive.py` | 旧版（逐条写 Obsidian），**博主蒸馏不要再用**；仅收藏流水线用 |

## 1. 转录完整性校验（必做）

- 下载 N 条 ≠ 转录 N 条：`grep -c '^=====' 汇总文件` vs `python3 -c "json.load(processed)"` vs post 目录 mp4 数
- 缺条原因：转录进程被中断/排序未轮到 → 重跑 `transcribe_only.py`（processed json 自动跳过已处理）
- 重复条目：两个实例并发写同一文件 → 按条目首行 `===== [日期] 标题`（前 60 字符）去重
- **启动任务前 `ps aux | grep [t]ranscribe_only` 确认无残留进程**（poll not_found 不可靠）

## 2. 音频质检 + 截帧（用户 要求"蒸馏不能只转录音频"）

- 全量跑 audio_check.py：语音清晰（ok）免截帧；weak/silent/music 截帧 3 张
- 截帧逐张 vision_analyze（强约束 prompt："只输出图片中的文字"），OCR 结果并入素材
- 实测 230 条：228 ok / 2 weak（截 6 帧），成本可控

## 3. 观点浓缩（35 万字符 → 可通读规模）

Whisper 转录**无标点**，不能按句切分。用滑动窗口法：

```python
CLAIM_KWS = ['结论','所以','看好','看空','风险','估值','溢价','折价','预期','核心','关键','逻辑','本质']
NUM_RE = re.compile(r'\d+(\.\d+)?[%万亿倍元个只亿]?')
def extract_windows(tr, win=70):
    out = []
    for m in NUM_RE.finditer(tr):
        ctx = tr[max(0,m.start()-win): min(len(tr), m.end()+win)]
        if any(k in ctx for k in CLAIM_KWS) and ctx.strip() not in out:
            out.append(ctx.strip())
        if len(out) >= 5: break
    return out
```

- 存 `/tmp/<博主>_condensed.json`（idx/date/title/wins）
- 主题分类（标题关键词 → 公司分析/方法论/心态/宏观/市场观点/量化），统计分布定报告结构
- 未抽到窗口的条目做**标题级扫描**确认无遗漏（多为感悟/闲聊类）
- 与你体系相关的关键条目（量化/银行/中国资产等）**补读全文**，不只看窗口

## 4. 报告七段式模板（单篇，只此一篇进 Obsidian）

```markdown
# 博主蒸馏报告：<博主>（全量 N 条）
🔗 主页：抖音号 xxx（sec_uid: ...） 📅 蒸馏日期 🏷️ 标签
## 一、博主画像（粉丝/获赞/定位/内容形式/更新频率/一句话总结）
## 二、内容构成（类型|数量|占比|说明 表格 + 覆盖行业）
## 三、核心方法论体系（估值框架/财务拆解/分析套路/投资哲学）
## 四、市场观点汇总（日期|观点 表格——观点必须带日期可追溯）
## 五、专项（量化/AI 相关内容详解——若有）
## 六、可信度评估（优点/局限/评级）
## 七、与 用户 体系的映射（具体到持仓/审计线/观察清单）
## 八、原文转录（注明全文暂存路径）
```

- 文件名：`YYYY-MM-DD_博主蒸馏_<博主>.md` → 走 `obsidian` 技能写入 `_inbox/赫尔墨斯_inbox/`（归档规则全局上移，2026-08-10 解耦）
- Whisper 错字校正后再引用（实测示例：申数=升数、驾驶博=嘉士伯、鱼漆=逾期、实化=石化）
- 内容方向与 用户 研究强相关（财经/量化）时，评级要诚实（无自证实绩 → B- 档，不因内容扎实抬高分）

## 5. 交付清单

1. 单篇报告入 Obsidian ✅
2. 逐条笔记（旧模式误产物）→ 给 用户 清单确认处置（删/留/归档）
3. 聊天中展示精华版（画像/最相关三块/评级）
4. skill 记录本次实测（博主/条数/新教训）
