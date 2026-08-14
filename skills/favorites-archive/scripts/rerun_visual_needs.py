#!/usr/bin/env python3
"""补跑 analyze_visual_needs.py 的 judge_failed 条目（截断输入后重判画面需求）。

背景：analyze_visual_needs.py 无输入截断，超长时间戳分段（>8K token）传给
qwen2.5:7b-8k 会触发上下文截断 → 输出非 JSON → 3 次重试失败 → judge_failed 降级 false
（2026-08-10 某量化博主 112 条实测：39 条失败，截断重跑后 36/39 实为需要画面）。

用法:
  python3 rerun_visual_needs.py --src <转录汇总txt> --needs <原始判断json> --out <修复json> [--max-chars 6000] [--model qwen2.5:7b]

输出：合并修复后的完整 items 数组 JSON；每条打 verification=rerun_fixed / rerun_failed。
"""
import argparse, json, re, time, urllib.request

def log(msg):
    print(msg, flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="transcribe_only 汇总 txt（含时间戳分段）")
    ap.add_argument("--needs", required=True, help="analyze_visual_needs 原始输出 json")
    ap.add_argument("--out", required=True, help="修复后 json 输出路径")
    ap.add_argument("--max-chars", type=int, default=6000)
    ap.add_argument("--model", default="qwen2.5:7b")
    args = ap.parse_args()

    txt = open(args.src).read()
    d = json.load(open(args.needs))
    items = d["items"]

    entries = re.split(r"^===== ", txt, flags=re.M)[1:]
    entry_map = {}
    for e in entries:
        first = e.split("\n", 1)[0]
        core = first.split("] ", 1)[-1][:20] if "] " in first else first[:20]
        entry_map[core] = e

    failed = [i for i, it in enumerate(items) if it.get("reason") == "judge_failed"]
    log(f"待补跑: {len(failed)} 条")

    done = 0
    for idx in failed:
        it = items[idx]
        title = it["title"]
        core = title.split("_", 1)[-1][:20] if "_" in title else title[:20]
        m = entry_map.get(core)
        if not m:
            it["needs_visual"] = False
            it["reason"] = "not_found"
            it["verification"] = "rerun_failed"
            log(f"  [skip] not_found {title[:30]}")
            done += 1
            continue
        ts = re.search(r"时间戳分段:\n(.*?)(?=\n\n|\Z)", m, re.S)
        ts_text = (ts.group(1)[:args.max_chars] + "\n[注: 长度限制仅展示前段]") if ts else "无分段"

        payload = {
            "model": args.model,
            "messages": [
                {"role": "system", "content": "你是一个视频内容分析助手。判断视频画面是否含口述未覆盖的增量信息（表格/图表/数据/代码/演示截图）。只输出JSON: {\"needs_visual\":true/false,\"reason\":\"...\",\"confidence\":0.0-1.0,\"segments\":[{\"start\":秒,\"end\":秒,\"text\":\"\",\"hint\":\"图表/表格/数据对比/要点展示/代码/演示/实物/其他\"}]}"},
                {"role": "user", "content": f"视频标题: {title}\n\n时间戳分段文本:\n{ts_text}\n\n请判断这条视频哪些时间段需要看画面。只输出JSON。"},
            ],
            "stream": False,
            "options": {"num_predict": 300},
        }
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read().decode())
            content = resp.get("message", {}).get("content", "")
            jm = re.search(r'\{[\s\S]*"needs_visual"[\s\S]*\}', content)
            if jm:
                raw = re.sub(r"(\d+\.?\d*)s([,\s}\]])", r"\1\2", jm.group(0))
                parsed = json.loads(raw)
                it["needs_visual"] = parsed.get("needs_visual", False)
                it["reason"] = parsed.get("reason", "")
                it["confidence"] = parsed.get("confidence", None)
                it["segments"] = [{"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", ""), "hint": s.get("hint", "")} for s in parsed.get("segments", [])]
                it["verification"] = "rerun_fixed"
                log(f"  {'TRUE ' if it['needs_visual'] else 'false'} | {title[:36]} | {str(it['reason'])[:36]}")
            else:
                it["needs_visual"] = False
                it["reason"] = "no_json_in_response"
                it["verification"] = "rerun_failed"
                log(f"  [warn] no_json {title[:30]}")
        except Exception as e:
            it["needs_visual"] = False
            it["reason"] = f"err:{type(e).__name__}"
            it["verification"] = "rerun_failed"
            log(f"  [err] {title[:30]} | {e}")
        done += 1
        if done % 5 == 0:
            json.dump(d, open(args.out, "w"), ensure_ascii=False, indent=1)
            log(f"  ... checkpoint {done}/{len(failed)}")
        time.sleep(0.3)

    json.dump(d, open(args.out, "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(i["needs_visual"] for i in items)
    log(f"DONE 合并后: True={c[True]}, False={c[False]}, 共{len(items)}")

if __name__ == "__main__":
    main()
