# 抖音 blob 播放器真实媒体资源捕获

## 触发场景

视频页加载成功，标题/页面文本正确，但：

- `document.querySelector('video').src` 返回 `blob:https://www.douyin.com/...`
- 原下载脚本报 `ERROR: 未找到视频URL`
- 页面实际已经在播放，说明真实媒体请求存在于浏览器资源列表中

## 稳定做法

1. Playwright 访问首页拿 cookie。
2. 访问 `https://www.douyin.com/video/<ID>`，等待 15–25 秒让播放器发起请求。
3. 从 performance resources 或 response 事件中筛选：
   - 域名包含 `douyinvod.com`
   - URL 包含 `mime_type=video_mp4`
4. 通常得到两类 URL：
   - `media-video-avc1`：无声视频轨
   - `media-audio-und-mp4a`：音频轨
5. 在页面上下文内 `fetch(url)`，利用当前 cookie/header 绕过 403，保存 base64 为本地 mp4。
6. 转录时优先对 `media-audio` 保存的 mp4 做 ffmpeg → wav → whisper。

## 核心代码片段

```python
urls = page.evaluate("""
    () => performance.getEntriesByType('resource')
        .map(e => e.name)
        .filter(u => u.includes('douyinvod.com') && u.includes('mime_type=video_mp4'))
""")
seen = []
for u in urls:
    if u not in seen:
        seen.append(u)

audio_url = next((u for u in seen if 'media-audio' in u), None)
video_url = next((u for u in seen if 'media-video' in u), None)

result = page.evaluate("""async (url) => {
  try {
    const r = await fetch(url);
    const blob = await r.blob();
    const reader = new FileReader();
    const p = new Promise(resolve => reader.onloadend = () => resolve(reader.result));
    reader.readAsDataURL(blob);
    const dataUrl = await p;
    return {header: dataUrl.split(',')[0], b64: dataUrl.split(',')[1]};
  } catch(e) {
    return {error: e.message};
  }
}""", audio_url)
```

## 注意

- 不要把 `video.src is blob` 当成最终失败。
- 媒体 URL 有时效，提取后立即下载。
- 音频和视频常是分离轨；做转录只需要音频轨。
- 若要给用户返回完整视频，需用 ffmpeg mux 音视频轨。