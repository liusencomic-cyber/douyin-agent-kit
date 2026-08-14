"""抖音扫码登录 → 抓取 cookie 写入 config.yml
用法: python3 qr_login.py
流程: 打开抖音首页 → 截取登录二维码保存到 /tmp/dy_login_qr.png（过期自动更新）
      → 轮询检测登录成功 → 收集 cookie → 写入 config/cookies.json 并更新 config.yml
"""
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# 注意：playwright 在 main() 内延迟 import，保证模块可被安全 import（
# 不依赖目标环境已安装 playwright），也便于测试与配置检查。
# 可移植工作目录：优先环境变量 DOUYIN_SYNC_DIR，否则推断为脚本所在目录（仓库根）。
BASE = os.environ.get("DOUYIN_SYNC_DIR") or str(Path(__file__).resolve().parent)
QR_PATH = "/tmp/dy_login_qr.png"
COOKIES_JSON = os.path.join(BASE, "douyin-downloader/config/cookies.json")
CONFIG_YML = os.path.join(BASE, "douyin-downloader/config.yml")
SCAN_TIMEOUT = 900  # 15 分钟扫码窗口


def find_chromium():
    cache = os.path.expanduser("~/Library/Caches/ms-playwright/")
    for pattern in [
        "chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    ]:
        matches = sorted(glob.glob(os.path.join(cache, pattern)), reverse=True)
        if matches:
            return matches[0]
    return None


def main():
    from playwright.sync_api import sync_playwright
    chromium = find_chromium()
    if not chromium:
        print("FATAL: no playwright chromium found")
        sys.exit(1)

    observed_mstokens = []
    last_qr_hash = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chromium)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        def on_request(req):
            try:
                m = re.search(r"[?&]msToken=([^&]+)", req.url)
                if m and m.group(1).strip():
                    observed_mstokens.append(m.group(1).strip())
            except Exception:
                pass

        page.on("request", on_request)

        print("[1/4] 打开抖音首页...", flush=True)
        page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)

        # 点开登录弹窗（若未自动弹出）
        for selector in ['text=登录', 'button:has-text("登录")', '[class*="login"] >> text=登录']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    break
            except Exception:
                continue
        page.wait_for_timeout(4000)

        print("[2/4] 截取二维码...", flush=True)
        deadline = time.time() + SCAN_TIMEOUT
        qr_reported = False
        while time.time() < deadline:
            # 检测登录成功：出现 session 类 cookie
            cookies = {c["name"]: c["value"] for c in context.cookies("https://www.douyin.com")}
            if cookies.get("sid_guard") or cookies.get("sessionid"):
                print("[3/4] 检测到登录成功，收集 cookie...", flush=True)
                break

            # 截取/更新二维码
            try:
                qr_src = page.evaluate(
                    """() => {
                        const imgs = document.querySelectorAll('img');
                        for (const img of imgs) {
                            const src = img.src || '';
                            if (src.startsWith('data:image') && img.naturalWidth > 100
                                && img.naturalWidth <= 600) return src;
                        }
                        return null;
                    }"""
                )
                if qr_src:
                    import base64
                    b64 = qr_src.split(",", 1)[1]
                    h = hashlib.md5(b64.encode()).hexdigest()
                    if h != last_qr_hash:
                        with open(QR_PATH, "wb") as f:
                            f.write(base64.b64decode(b64))
                        last_qr_hash = h
                        if not qr_reported:
                            print("QR_READY", flush=True)
                            qr_reported = True
                        else:
                            print("QR_REFRESHED", flush=True)
            except Exception:
                pass
            page.wait_for_timeout(3000)
        else:
            print("TIMEOUT: 15 分钟内未检测到登录", flush=True)
            browser.close()
            sys.exit(2)

        cookies = {c["name"]: c["value"] for c in context.cookies("https://www.douyin.com")}
        if observed_mstokens:
            cookies["msToken"] = observed_mstokens[-1]

        picked = {
            k: cookies.get(k, "")
            for k in ["msToken", "ttwid", "odin_tt", "passport_csrf_token", "sid_guard",
                      "sessionid", "sid_tt", "s_v_web_id", "d_ticket", "UIFID"]
            if cookies.get(k)
        }
        missing = [k for k in ["msToken", "ttwid", "odin_tt", "passport_csrf_token"]
                   if not picked.get(k)]
        if missing:
            print(f"WARN: 缺少关键 cookie: {missing}", flush=True)

        os.makedirs(os.path.dirname(COOKIES_JSON), exist_ok=True)
        with open(COOKIES_JSON, "w") as f:
            json.dump(picked, f, ensure_ascii=False, indent=2)

        # 更新 config.yml 的 cookies 段（保注释，逐字段替换）
        with open(CONFIG_YML) as f:
            cfg = f.read()
        for k in ["msToken", "ttwid", "odin_tt", "passport_csrf_token", "sid_guard"]:
            v = picked.get(k, "")
            if v:
                cfg = re.sub(rf'(  {k}: ).*', rf'\g<1>"{v}"', cfg)
        with open(CONFIG_YML, "w") as f:
            f.write(cfg)

        browser.close()
        print(f"[4/4] cookie 已写入。LOGIN_OK keys={sorted(picked.keys())}", flush=True)


if __name__ == "__main__":
    main()
