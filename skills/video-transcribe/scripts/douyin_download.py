#!/usr/bin/env python3
"""抖音内容下载脚本 — Scrapling版
用法: 
  ~/.hermes/hermes-agent/venv/bin/python3 douyin_download.py <视频/图文ID或短链URL>
  （⚠️ 必须用 Hermes venv 的 Python 运行，系统 Python 无 scrapling 模块）

支持:

支持:
  - 视频类型 (/video/): 下载mp4视频
  - 图文类型 (/note/): 下载图片(webp/jpeg) + 页面文本

输出: 
  - 视频: /tmp/douyin_<ID>.mp4 (或 _video.mp4 + _audio.mp4 音视频分离)
  - 图文: /tmp/douyin_note_imgs/note_<ID>_img*.webp + pagetext.txt + meta.json

网络策略: 直连优先 → DynamicFetcher → StealthyFetcher 逐级降级
"""
import sys, os, re, subprocess, base64, json
from scrapling import DynamicFetcher, StealthyFetcher

INPUT = sys.argv[1] if len(sys.argv) > 1 else None
PROXY = "http://127.0.0.1:7897"

if not INPUT:
    print("用法: python3 douyin_download.py <视频/图文ID或短链URL>")
    sys.exit(1)

# --- 解析输入 ---
content_id = None
content_type = "video"

if INPUT.isdigit():
    content_id = INPUT
elif "douyin.com" in INPUT:
    m_video = re.search(r'/video/(\d+)', INPUT)
    m_note = re.search(r'/note/(\d+)', INPUT)
    if m_video:
        content_id = m_video.group(1)
        content_type = "video"
    elif m_note:
        content_id = m_note.group(1)
        content_type = "note"
    else:
        print(f"解析短链: {INPUT}")
        result = subprocess.run(
            ["curl", "-s", "-L", "-o", "/dev/null", "-w", "%{url_effective}", INPUT],
            capture_output=True, text=True, timeout=15
        )
        resolved = result.stdout.strip()
        print(f"解析结果: {resolved}")
        m_video = re.search(r'/video/(\d+)', resolved)
        m_note = re.search(r'/note/(\d+)', resolved)
        if m_video:
            content_id = m_video.group(1)
            content_type = "video"
        elif m_note:
            content_id = m_note.group(1)
            content_type = "note"
        else:
            print(f"无法从链接提取ID: {resolved}")
            sys.exit(1)
else:
    print(f"无法识别输入: {INPUT}")
    sys.exit(1)

print(f"ID: {content_id}, 类型: {content_type}")

# --- 全局变量：记录下载结果 ---
download_result = {"success": False, "title": "", "files": []}


def fetch_video(page):
    """page_action: 访问首页→视频页→获取video src→fetch下载"""
    global download_result
    print("访问首页获取cookie...")
    page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    print(f"首页: {page.title()[:60]}")

    print(f"访问视频页: {content_id}")
    page.goto(f"https://www.douyin.com/video/{content_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(15000)

    title = page.title()
    print(f"标题: {title}")
    download_result["title"] = title

    # 获取video src（排除blob:）
    video_src = page.evaluate("""() => {
        const video = document.querySelector('video');
        if (!video) return null;
        if (video.src && !video.src.startsWith('blob:')) return video.src;
        const sources = video.querySelectorAll('source');
        for (const s of sources) {
            if (s.src && !s.src.startsWith('blob:')) return s.src;
        }
        return null;
    }""")

    # blob: 兜底：从performance entries获取真实媒体URL
    if not video_src or video_src.startswith('blob:'):
        print("video元素无直接URL，从performance entries获取媒体资源...")
        page.wait_for_timeout(5000)

        urls = page.evaluate("""() => performance.getEntriesByType('resource')
            .map(e => e.name)
            .filter(u => u.includes('douyinvod.com'))""")

        seen = set()
        unique_urls = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        video_url = next((u for u in unique_urls if 'media-video' in u), None)
        audio_url = next((u for u in unique_urls if 'media-audio' in u), None)

        if not video_url and unique_urls:
            video_url = unique_urls[0]

        if video_url:
            print(f"找到media-video URL，通过fetch()下载...")
            vpath = f"/tmp/douyin_{content_id}_video.mp4"
            result = page.evaluate(f"""async () => {{
                try {{
                    const response = await fetch(\"{video_url}\");
                    if (!response.ok) return {{ error: 'HTTP ' + response.status }};
                    const blob = await response.blob();
                    const reader = new FileReader();
                    const promise = new Promise((resolve) => {{
                        reader.onloadend = () => resolve(reader.result);
                    }});
                    reader.readAsDataURL(blob);
                    const dataUrl = await promise;
                    const parts = dataUrl.split(',', 2);
                    return {{ header: parts[0], size: parts[1].length, b64: parts[1] }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}""")
            if 'error' not in result:
                with open(vpath, 'wb') as f:
                    f.write(base64.b64decode(result['b64']))
                print(f"视频下载成功: {vpath} ({os.path.getsize(vpath)} bytes)")
                download_result["files"].append(vpath)
            else:
                print(f"视频fetch失败: {result['error']}")

        if audio_url:
            print(f"找到media-audio URL，通过fetch()下载...")
            apath = f"/tmp/douyin_{content_id}_audio.mp4"
            result = page.evaluate(f"""async () => {{
                try {{
                    const response = await fetch(\"{audio_url}\");
                    if (!response.ok) return {{ error: 'HTTP ' + response.status }};
                    const blob = await response.blob();
                    const reader = new FileReader();
                    const promise = new Promise((resolve) => {{
                        reader.onloadend = () => resolve(reader.result);
                    }});
                    reader.readAsDataURL(blob);
                    const dataUrl = await promise;
                    const parts = dataUrl.split(',', 2);
                    return {{ header: parts[0], size: parts[1].length, b64: parts[1] }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}""")
            if 'error' not in result:
                with open(apath, 'wb') as f:
                    f.write(base64.b64decode(result['b64']))
                print(f"音频下载成功: {apath} ({os.path.getsize(apath)} bytes)")
                download_result["files"].append(apath)
            else:
                print(f"音频fetch失败: {result['error']}")

        if download_result["files"]:
            download_result["success"] = True
            print("DONE (使用performance entries下载)")
            return
        else:
            print("WARN: 无法从performance entries获取媒体URL")
            return  # 不exit，让主流程fallback

    print(f"视频URL获取成功 ({len(video_src)} chars)")

    # fetch()下载
    output_path = f"/tmp/douyin_{content_id}.mp4"
    print("fetch() 下载视频...")
    result = page.evaluate(f"""async () => {{
        try {{
            const response = await fetch(\"{video_src}\");
            if (!response.ok) return {{ error: 'HTTP ' + response.status }};
            const blob = await response.blob();
            const reader = new FileReader();
            const promise = new Promise((resolve) => {{
                reader.onloadend = () => resolve(reader.result);
            }});
            reader.readAsDataURL(blob);
            const dataUrl = await promise;
            const parts = dataUrl.split(',', 2);
            return {{ header: parts[0], size: parts[1].length, b64: parts[1] }};
        }} catch(e) {{
            return {{ error: e.message }};
        }}
    }}""")

    if 'error' not in result:
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(result['b64']))
        size = os.path.getsize(output_path)
        if size > 10000:
            print(f"下载成功: {size} bytes → {output_path}")
            download_result["files"].append(output_path)
            download_result["success"] = True
        else:
            print(f"文件太小({size} bytes)，下载可能不完整")
    else:
        print(f"fetch失败: {result['error']}")


def fetch_note(page):
    """page_action: 访问首页→图文页→下载图片+提取文本"""
    global download_result
    print("访问首页获取cookie...")
    page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    print(f"首页: {page.title()[:60]}")

    print(f"访问图文页: {content_id}")
    page.goto(f"https://www.douyin.com/note/{content_id}", wait_until="domcontentloaded")
    page.wait_for_timeout(8000)

    title = page.title()
    print(f"标题: {title}")
    download_result["title"] = title

    # 下载图片
    img_data_list = page.evaluate("""async () => {
        const imgs = document.querySelectorAll('img');
        const results = [];
        const seen = new Set();
        for (const img of imgs) {
            const src = img.src || img.getAttribute('data-src');
            if (!src || src.startsWith('data:') || img.naturalWidth < 400) continue;
            if (seen.has(src)) continue;
            seen.add(src);
            try {
                const response = await fetch(src);
                const blob = await response.blob();
                const reader = new FileReader();
                const promise = new Promise((resolve) => {
                    reader.onloadend = () => resolve(reader.result);
                });
                reader.readAsDataURL(blob);
                const dataUrl = await promise;
                results.push({
                    dataUrl: dataUrl,
                    width: img.naturalWidth,
                    height: img.naturalHeight,
                    alt: img.alt || ''
                });
            } catch(e) {
                results.push({error: e.message});
            }
        }
        return results;
    }""")

    # 提取页面文本
    page_text = page.evaluate("""() => {
        const expandBtns = document.querySelectorAll('[class*="expand"], [class*="show-more"], [class*="unfold"]');
        expandBtns.forEach(btn => { try { btn.click(); } catch(e) {} });
        return document.body.innerText;
    }""")

    out_dir = "/tmp/douyin_note_imgs"
    os.makedirs(out_dir, exist_ok=True)
    saved_paths = []

    for i, item in enumerate(img_data_list):
        if 'error' in item:
            print(f"  img{i}: ERROR - {item['error']}")
            continue
        data_url = item['dataUrl']
        header, b64data = data_url.split(',', 1)
        ext = header.split('/')[1].split(';')[0]
        filepath = f"{out_dir}/note_{content_id}_img{i}.{ext}"
        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(b64data))
        size = os.path.getsize(filepath)
        if size > 5000:
            saved_paths.append(filepath)
            print(f"  img{i}: {size} bytes, {item['width']}x{item['height']}")
        else:
            os.remove(filepath)
            print(f"  img{i}: {size} bytes (too small, skipped)")

    text_path = f"{out_dir}/note_{content_id}_pagetext.txt"
    with open(text_path, 'w') as f:
        f.write(page_text)

    print(f"图片保存: {len(saved_paths)} 张 → {out_dir}/")
    print(f"页面文本: {text_path}")

    meta = {
        "id": content_id,
        "type": "note",
        "title": title,
        "images": saved_paths,
        "page_text_path": text_path,
    }
    meta_path = f"{out_dir}/note_{content_id}_meta.json"
    with open(meta_path, 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"元信息: {meta_path}")

    download_result["success"] = True
    download_result["files"] = saved_paths + [text_path, meta_path]


# --- 主流程：逐级降级 ---
action_fn = fetch_video if content_type == "video" else fetch_note

strategies = [
    ("DynamicFetcher 直连", lambda: DynamicFetcher.fetch(
        "https://www.douyin.com/", headless=True, timeout=120000, page_action=action_fn)),
    ("DynamicFetcher 代理", lambda: DynamicFetcher.fetch(
        "https://www.douyin.com/", headless=True, timeout=120000,
        proxy={"server": PROXY}, page_action=action_fn)),
    ("StealthyFetcher 直连", lambda: StealthyFetcher.fetch(
        "https://www.douyin.com/", headless=True, timeout=120000,
        solve_cloudflare=True, page_action=action_fn)),
    ("StealthyFetcher 代理", lambda: StealthyFetcher.fetch(
        "https://www.douyin.com/", headless=True, timeout=120000,
        solve_cloudflare=True, proxy={"server": PROXY}, page_action=action_fn)),
]

for name, fn in strategies:
    if download_result["success"]:
        break
    print(f"\n尝试 {name}...")
    try:
        download_result = {"success": False, "title": "", "files": []}
        fn()
    except Exception as e:
        print(f"  {name} 失败: {e}")

if not download_result["success"]:
    print("\nERROR: 所有下载策略均失败")
    sys.exit(1)

print(f"\n✅ 下载成功: {download_result['title']}")
print(f"   文件: {download_result['files']}")
