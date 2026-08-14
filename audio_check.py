#!/usr/bin/env python3
"""蒸馏流程补丁：音频质量检测 + 对低质量音频视频截帧。
对每个视频用 ffmpeg volumedetect + silencedetect 判断是否有清晰语音；
筛出的视频截 3 帧（前/中/后）供 OCR，帧写入 <out_dir>/<aweme_id>_f*.jpg。
输出 JSON：{aweme_id: {mean_volume, max_volume, silent_ratio, verdict, frames: [...]}}
verdict: ok(语音清晰, 不截帧) / weak(语音弱, 截帧) / silent(近无声, 截帧) / music(纯BGM, 截帧)
"""
import argparse, json, os, re, subprocess, sys

def probe_audio(mp4):
    """返回 (mean_volume, max_volume, duration) 或 None"""
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", mp4, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120)
        stderr = r.stderr
        mv = re.search(r"mean_volume:\s*(-?[\d.]+) dB", stderr)
        xv = re.search(r"max_volume:\s*(-?[\d.]+) dB", stderr)
        dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", stderr)
        mean = float(mv.group(1)) if mv else -91.0
        maxv = float(xv.group(1)) if xv else -91.0
        d = (int(dur.group(1))*3600 + int(dur.group(2))*60 + float(dur.group(3))) if dur else 0
        return (mean, maxv, d)
    except Exception as e:
        return None

def silent_ratio(mp4):
    """用 silencedetect 估计静音占比"""
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", mp4, "-af", "silencedetect=noise=-35dB:d=0.8", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180)
        starts = re.findall(r"silence_start:\s*([\d.]+)", r.stderr)
        ends = re.findall(r"silence_end:\s*([\d.]+)", r.stderr)
        dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
        d = (int(dur.group(1))*3600 + int(dur.group(2))*60 + float(dur.group(3))) if dur else 0
        if d <= 0:
            return 0.0
        # 把 silence_start/end 配对累计
        total_silence = 0.0
        for s in starts:
            # 找第一个大于 s 的 end
            e = next((x for x in ends if x > s), None)
            if e:
                total_silence += (e - s)
        return min(1.0, total_silence / d)
    except Exception:
        return 0.0

def extract_frames(mp4, aweme_id, out_dir, n=3):
    """截 n 帧：前/中/后均匀分布，返回帧路径列表"""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", mp4], capture_output=True, text=True, timeout=30)
        d = float(r.stdout.strip() or 0)
        if d <= 1:
            return paths
        ts = [1.0, d/2, d-1.0] if d > 6 else [0.5]
        for i, t in enumerate(ts):
            out = os.path.join(out_dir, f"{aweme_id}_f{i}.jpg")
            subprocess.run(["ffmpeg", "-ss", str(max(0,t-0.2)), "-i", mp4, "-frames:v", "1",
                            "-q:v", "3", "-y", out], capture_output=True, text=True, timeout=60)
            if os.path.exists(out) and os.path.getsize(out) > 3000:
                paths.append(out)
    except Exception:
        pass
    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--threshold-weak", type=float, default=-28.0, help="mean_volume 低于此值视为弱语音")
    ap.add_argument("--threshold-silent", type=float, default=-45.0, help="mean_volume 低于此值视为近无声")
    args = ap.parse_args()

    results = {}
    for folder in sorted(os.listdir(args.src_dir)):
        fpath = os.path.join(args.src_dir, folder)
        if not os.path.isdir(fpath):
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)_(\d{10,})$", folder)
        if not m:
            continue
        date, title, aweme_id = m.groups()
        mp4s = [f for f in os.listdir(fpath) if f.endswith(".mp4")]
        if not mp4s:
            results[aweme_id] = {"verdict": "novideo", "frames": []}
            continue
        mp4 = os.path.join(fpath, mp4s[0])
        probe = probe_audio(mp4)
        if probe is None:
            results[aweme_id] = {"verdict": "probe_fail", "frames": []}
            continue
        mean, maxv, dur = probe
        sr = silent_ratio(mp4)
        if maxv < -60:
            verdict = "silent"
        elif mean < args.threshold_silent:
            verdict = "silent"
        elif mean < args.threshold_weak:
            verdict = "weak"
        elif sr > 0.6:
            verdict = "music_or_sparse"
        else:
            verdict = "ok"
        frames = []
        if verdict != "ok":
            frames = extract_frames(mp4, aweme_id, args.frames_dir)
        results[aweme_id] = {
            "date": date, "title": title[:40], "mean_volume": round(mean,1),
            "max_volume": round(maxv,1), "duration": round(dur,1),
            "silent_ratio": round(sr,2), "verdict": verdict, "frames": frames,
        }
        print(f"{aweme_id} {title[:15]:<15} mean={mean:>6.1f} max={maxv:>6.1f} sr={sr:.2f} -> {verdict} frames={len(frames)}", flush=True)

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(v["verdict"] for v in results.values())
    print("=== 判定汇总 ===", dict(c))

if __name__ == "__main__":
    main()
