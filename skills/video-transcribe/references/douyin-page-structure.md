# 抖音网页结构与技术细节

## URL 类型判断

| URL路径 | 类型 | 内容形态 |
|---|---|---|
| `/video/<ID>` | 视频 | video标签 + 音频轨 |
| `/note/<ID>` | 图文作品 | 多张img + 正文文字 |
| `/user/<ID>` | 用户主页 | 不处理 |

短链解析：`curl -s -L -o /dev/null -w "%{url_effective}" "https://v.douyin.com/XXXX/"`

## 页面结构 — 图文作品 (/note/)

### 图片元素
- 正文图片：`<img>` 标签，`src` 含 `douyinpic.com`，`naturalWidth` ≥ 1916px
- 封面图：与正文图URL前缀相同，但含 `noop.jpeg?biz_tag=pcweb_cover`
- 推荐图：`naturalWidth` ≤ 440px，含 `image-cut-tos` 路径
- UI图标：`douyinstatic.com` 域名，小尺寸，过滤掉

### 去重规则
同一张图在DOM中可能出现两次（懒加载占位 + 实际图），URL以 `~` 分隔签名参数前为唯一key：
```javascript
const key = src.split('~')[0];
```

### 反盗链机制
- curl直接下载图片 → 403 Forbidden（Tengine返回）
- 必须在Playwright页面上下文内用 `fetch()` 下载，浏览器自动携带cookie和Referer
- fetch → blob → FileReader.readAsDataURL → base64编码传出页面上下文 → 解码保存

### 页面文本
- 正文可能被登录墙遮挡，`document.body.innerText` 获取不完整
- 主要依赖图片OCR，页面文本仅作补充
- 有展开按钮：`[class*="expand"]`, `[class*="show-more"]`, `[class*="unfold"]` — 先点击再取文本

## 页面结构 — 视频 (/video/)

### 视频元素
- `<video>` 标签，`src` 属性含视频直链（douyinvod.com域名）
- 部分情况src为空，需用 `page.evaluate()` JS执行获取
- 视频URL含签名参数，有时效性（约数小时），获取后立即下载

### 获取标题
- `page.title()` 返回格式：`"视频标题 - 抖音"`
- img alt属性也含标题（封面图的alt）

## 截图问题

`page.screenshot(full_page=True)` 在抖音页面经常超时（等待字体加载），不可靠。
- 视口截图也可能超时
- 不依赖截图，优先用DOM提取 + fetch下载

## Cookie机制

- 必须先访问 `https://www.douyin.com/` 首页获取 `s_v_web_id` 等cookie
- 首页等待至少5秒让JS完成cookie设置
- 反webdriver检测：`Object.defineProperty(navigator, 'webdriver', {get: () => undefined});`
