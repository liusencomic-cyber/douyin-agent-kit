# 本地 OCR 方案评估（2026-06-02）

## 测试环境
- macOS 26.3.1, Apple Silicon
- 测试视频：抖音竖屏 720×1280，东京探店（ID: 7646732760342914979）
- 目标：识别视频画面中的店铺招牌、店名、日文标识

## Tesseract

### 安装状态
已通过 Homebrew 安装，语言包完整（chi_sim, jpn, eng 等 163 种）。

### 纯文字测试图
- 3200×800 白底黑字，STHeiti 72pt
- 测试文字：浪花家総本店 / 成城石井 SUPERMARKET / 麻布十番 8-14 / 予約受付中
- 结果：✅ 完美识别，一字不差

### 真实视频帧测试
- 帧 008（浪花家総本店招牌）：全部 PSM 模式返回空
- 帧 028（成城石井招牌）：全部 PSM 模式返回空
- 帧 032（HISAYA 栗菓匠招牌）：全部 PSM 模式返回空

### 尝试过的预处理
- 3x 放大（LANCZOS）
- 灰度 + 对比度增强（2.5x）
- 二值化（阈值 128）
- 暗像素提取（阈值 80）
- 反色
- 区域裁剪 + 放大
- 所有 PSM 模式（0-13）

全部返回空。

### 结论
Tesseract 是文档扫描 OCR，不适合自然场景中的文字识别（复杂背景、光影变化、文字占比小）。不可用于抖音视频帧 OCR。

## EasyOCR

### 安装状态
未安装。尝试 import 时遇到 OpenMP 冲突（与 Whisper 相同的 libomp 重复加载问题）。

### 理论适用性
EasyOCR 专门做场景文字识别（Scene Text Recognition），对自然场景中的招牌、路标效果应该好于 Tesseract。

### 待测试
- 安装：`pip install easyocr`（首次运行下载检测+识别模型 ~100MB）
- 需要 `KMP_DUPLICATE_LIB_OK=TRUE` 绕过 OpenMP 冲突
- 如果 EasyOCR 可用，可替代 vision_analyze 做视频帧 OCR，大幅降低成本

## 当前可用方案
vision_analyze（API 视觉模型）—— 效果最好但受限于超时和并发。
