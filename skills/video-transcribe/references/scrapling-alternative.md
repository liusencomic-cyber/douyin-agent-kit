# Scrapling DynamicFetcher 替代方案

2026-06-06 实测：Scrapling v0.4.8 的 DynamicFetcher 可替代手写 Playwright 脚本下载抖音视频。

## 安装

```bash
pip install "scrapling[all]"
# 浏览器依赖由 DynamicFetcher 首次使用时自动安装（基于 playwright + patchright）
```

## 核心用法

```python
from scrapling import DynamicFetcher
import base64

VIDEO_ID = "7634829030205689138"

def download_video(page):
    """page_action: 先首页拿cookie → 跳视频页 → evaluate获取src → fetch下载"""
    # 1. 先访问首页获取cookie
    page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    
    # 2. 跳转视频页
    page.goto(f"https://www.douyin.com/video/{VIDEO_ID}", wait_until="domcontentloaded")
    page.wait_for_timeout(15000)  # 等视频加载
    
    # 3. 获取非blob的video src
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
    
    # 4. 在页面上下文内fetch下载（自带cookie和正确headers）
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
        path = f"/tmp/douyin_{VIDEO_ID}.mp4"
        with open(path, 'wb') as f:
            f.write(base64.b64decode(result['b64']))

# 调用
page = DynamicFetcher.fetch(
    "https://www.douyin.com/",
    headless=True,
    timeout=120000,
    page_action=download_video,
)
```

## 对比现有 Playwright 方案

| 方面 | 现有脚本 (douyin_download.py) | Scrapling DynamicFetcher |
|---|---|---|
| 代码量 | ~300行 | ~50行 |
| cookie管理 | 手动获取+注入 | page_action 自动继承 |
| 代理降级 | 手动 try/except 双策略 | 内置 proxy 参数 |
| 反检测 | add_init_script 隐藏 webdriver | 内置 browserforge 指纹 |
| 浏览器路径 | 手动 find_chromium() | 自动 |

## 已知限制

- DynamicFetcher 基于 Playwright，音视频分离场景（抖音经常把 video 和 audio 分成两个独立文件）的 `media-audio-und-mp4a` 下载逻辑已集成到 `douyin_download.py` 中
- page_action 参数是关键：必须先在 action 内手动导航首页→视频页，不能依赖 fetch() 的自动导航
- DynamicFetcher 首次连接可能因 `about:blank` 失败（retry 3次后抛异常），直接用抖音首页 URL 作为 fetch() 入口即可避免

## 2026-06-06 实测补充

### DynamicFetcher vs StealthyFetcher

| 场景 | DynamicFetcher | StealthyFetcher |
|---|---|---|
| 视频1 (7634829030205689138) | ✅ video src 直接获取，4.8MB 下载成功 | ✅ 同样成功 |
| 视频2 (7622332123072023848) | ❌ video src 为 blob:，performance entries 无 douyinvod 资源 | ✅ 从 performance 拿到 2 个 douyinvod URL，4.2MB+657KB 下载成功 |

**结论：** StealthyFetcher 在某些视频上表现更好（能捕获 performance 资源），DynamicFetcher 在其他视频上更稳定。`douyin_download.py` 使用 DynamicFetcher，遇到 blob: 时 fallback 到 performance entries 兜底。

### 关键修复

1. **performance entries 过滤条件不要加 `mime_type=video_mp4`** — douyinvod URL 不包含此参数，只过滤 `u.includes('douyinvod.com')` 即可
2. **`page.context.browser._proxy` 不存在** — Scrapling 的 browser 对象没有 `_proxy` 属性，不要用此方式判断是否走代理
3. **视频可能无音频轨** — 视频2 的 mp4 经 ffprobe 检查无 audio stream，但独立 `_audio.mp4` 文件包含 HE-AACv2 音频（44100Hz, stereo, 50kb/s），转录时直接使用该文件
