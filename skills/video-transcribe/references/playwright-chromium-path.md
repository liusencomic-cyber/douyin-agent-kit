# Playwright 1.59+ Chromium Path Resolution (macOS)

## Problem

Playwright 1.59+ changed the default browser from `chromium` to `chromium_headless_shell`. On macOS, `playwright install chromium` downloads the regular Chromium but the headless_shell binary is often missing, causing:

```
BrowserType.launch: Executable doesn't exist at
/Users/.../chromium_headless_shell-1217/chrome-headless-shell-mac-arm64/chrome-headless-shell
```

## Why not `playwright install chromium-headless-shell`?

The download often times out (120s+). The binary is ~150MB and network conditions vary.

## Solution: Find and use `executable_path`

### 1. Locate the actual Chromium binary

```python
import os, glob

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
```

### 2. Launch with explicit path

```python
CHROMIUM_PATH = find_chromium()
browser = p.chromium.launch(headless=True, executable_path=CHROMIUM_PATH)
```

### 3. Symbolic link fallback (less reliable)

```bash
CHROMIUM=$(find ~/Library/Caches/ms-playwright/chromium-*/ -name "Google Chrome for Testing" -type f 2>/dev/null | head -1)
SHELL_DIR=~/Library/Caches/ms-playwright/chromium_headless_shell-1217/chrome-headless-shell-mac-arm64/
mkdir -p "$SHELL_DIR"
ln -sf "$CHROMIUM" "$SHELL_DIR/chrome-headless-shell"
```

Note: Playwright may still reject the symlink due to executable validation. Prefer `executable_path`.

## Notes

- This applies to Playwright 1.59.0+ on macOS (arm64 and x86_64)
- `execute_code` sandbox does NOT have `playwright` installed — must use `terminal` 
- The `chromium-1217` version may change; the glob pattern handles version drift
