# analyze_visual_needs.py 超长输入缺陷（judge_failed 批量漏判）

2026-08 某量化博主 112 条全量蒸馏实测发现（独立真实 E2E 审计，单元测试未能捕获）。

## 现象

- 112 条中 **39 条（35%）judge_failed**，全部降级 `needs_visual=false`
- 失败集中在转录文本较长的条目；短条目（<8K token）全部正常
- judge_failed 条目特征：`segments=[]`，`reason='judge_failed'`，`heuristic=true` 但 `llm_verdict=false`（冲突可见）

## 根因

- 脚本把完整时间戳分段文本直接拼进 user_prompt 传给 Ollama（无截断）
- 本机 qwen2.5:7b 是 **8K 上下文版本**（`OLLAMA_CONTEXT_LENGTH=8192` 省内存优化）
- 超长输入（实测最长 44530 字符 ≈ 2万+ token）触发 Ollama 内部截断
- 截断后模型输出变成自然语言总结而非 JSON → 正则取 JSON 失败 → ValueError → 重试 3 次同样失败 → 降级 judge_failed
- 手动复现对比：不截断传 44530 字符返回自然语言总结（11.35s）；截断到 1500/6000 字符返回正确 JSON（~4s）

## 修复（修复前临时绕行）

```python
# _call_ollama 内，拼 user_prompt 前截断：
if len(segments_text) > 6000:
    segments_text = segments_text[:6000] + "\n[注: 长度限制仅展示前6000字符]"
```

## 验证数据

- 截断重跑 39 条：**36 条翻转 needs_visual=true（92% 实际需要画面）**，3 条 JSONDecodeError（模型输出格式问题，`_sanitize_json` 未覆盖，影响小）
- 最终 112 条：True=108, False=4（4 条 false 中 1 条为合法 heuristic_conflict 降级）
- 结论：修复前批量蒸馏的 needs_visual 统计不可信；修复后与人工抽样 OCR 一致（抽样帧均含口述未覆盖的图表/代码/数据）

## 通用教训

- 判断类功能（LLM 语义判断）必须用**真实长文本样本**验证；短样本全绿 = 没测到截断路径
- 小上下文模型（8K）配长文本输入是隐藏炸弹；**脚本侧必须显式截断**，不要依赖模型端行为
- 补跑工具：`scripts/rerun_visual_needs.py`（按标题前 20 字符匹配汇总条目，截断后重判 judge_failed 条目）
