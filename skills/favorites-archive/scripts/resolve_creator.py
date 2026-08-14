"""博主身份解析：抖音号/视频链接 → sec_uid + 主页信息核对（免登录）
用法:
  python3 resolve_creator.py --video-url https://www.douyin.com/video/<ID>
  python3 resolve_creator.py --sec-uid MS4wLjABAAAA...
输出: 作者 sec_uid、昵称、抖音号、粉丝/作品数（用于核对是否目标博主）
运行: 须用 PATH+PYTHONPATH wrapper（见 SKILL.md），playwright 在 douyin-sync venv。
"""
import argparse
import glob
import os
import re

from playwright.sync_api import sync_playwright


def find_chromium():
    cache = os.path.expanduser("~/Library/Caches/ms-playwright/")
    for pattern in [
        "chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    ]:
        matches = sorted(glob.glob(os.path.join(cache, pattern)), reverse=True)
        if matches:
            return matches[0]
    raise RuntimeError("no playwright chromium found")


def extract_author_uid(page):
    """视频页 DOM 中第一条无文本的 /user/ 链接（头像链接）即作者。"""
    links = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[href*="/user/"]').forEach(a => {
            const m = a.href.match(/\\/user\\/([A-Za-z0-9_-]+)/);
            if (m && m[1] !== 'self')
                out.push({sec_uid: m[1], text: (a.innerText || '').trim()});
        });
        return out;
    }""")
    for l in links:  # 作者头像链接通常无 innerText 且排在最前
        if not l["text"]:
            return l["sec_uid"]
    return links[0]["sec_uid"] if links else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url")
    ap.add_argument("--sec-uid")
    args = ap.parse_args()
    if not args.video_url and not args.sec_uid:
        ap.error("需要 --video-url 或 --sec-uid")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=find_chromium())
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page.goto("https://www.douyin.com/", wait_until="domcontentloaded",
                  timeout=60000)
        page.wait_for_timeout(5000)

        sec_uid = args.sec_uid
        if args.video_url:
            page.goto(args.video_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)
            sec_uid = extract_author_uid(page)
            if not sec_uid:
                print("FAIL: 视频页未找到作者链接")
                return
            print("AUTHOR_SEC_UID:", sec_uid)

        page.goto(f"https://www.douyin.com/user/{sec_uid}",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        body = page.evaluate("() => document.body.innerText")
        print("PROFILE_TITLE:", page.title())
        m = re.search(r"抖音号[：:]\s*(\S+)", body)
        print("DOUYIN_ID:", m.group(1) if m else "未显示")
        for label in ["粉丝", "作品", "获赞"]:
            m = re.search(rf"{label}\s*\n?([\d.万w]+)", body)
            if m:
                print(f"{label}:", m.group(1))
        browser.close()


if __name__ == "__main__":
    main()
