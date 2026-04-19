# Web Scavenger

Web Scavenger 是一个面向 Obsidian + LLM Wiki 知识库工作流的内容采集 skill，目标是把互联网上值得保留的图文和视频，更快、更完整地沉淀到知识库的 `raw` 层。

在个人知识库里，LLM 适合做理解、总结和再组织，但前提是原始材料必须先被稳定地保存下来。现实中的输入源却很分散：微信公众号、小红书、普通网页、B 站、抖音、本地视频……每个平台的链接结构、图片防盗链、视频下载、字幕转录方式都不一样。Web Scavenger 解决的就是这一步：把分散的平台内容统一转成 Obsidian 友好的本地文件。

## What It Solves

- **图文内容入库**：支持小红书、微信公众号、普通网页等来源，将正文提取为 Markdown，并把图片下载到本地，通过 Obsidian embeds / wikilinks 尽量还原原文的图文结构。
- **视频内容入库**：支持本地视频或分享链接，自动下载、转录、压缩字幕，生成可审计的时间轴校对稿和结构化视频总结。
- **时间戳跳转**：视频笔记中的段落时间戳会链接到本地视频文件。需要通过 Obsidian 自身插件市场安装并启用 [Media Extended](https://github.com/aidenlx/media-extended)，之后即可在 Obsidian 中点击时间戳直接跳到视频对应时间点。
- **统一 raw 层结构**：把文章、图片、视频文件、字幕、中间处理产物和最终笔记按固定目录组织，方便后续用 LLM 做总结、检索、重写和知识库加工。

## Supported Inputs

| 类型 | 当前支持 | 产物 |
|------|----------|------|
| 图文 | 小红书、微信公众号、普通网页、B 站专栏 | `article.md` + 本地图片 |
| 视频 | 本地视频、B 站、抖音、小红书视频 | `transcript.md` + `summary.md` + 本地视频 |
| 其他媒体 | 只要能获得可下载视频/音频链接即可接入 | 走通用视频 workflow |

## Features

| 内容类型 | 支持平台 | 输出 |
|---------|---------|------|
| 视频 | Bilibili, YouTube, 本地视频 | 时间轴校对稿 + 树状总结 |
| 小红书 | xiaohongshu.com, xhslink.com | Markdown + 本地图片 |
| 微信公众号 | mp.weixin.qq.com | Markdown + 本地图片 |
| 抖音 | douyin.com, v.douyin.com | 视频信息 + 封面 |
| 网页文章 | 博客、新闻、文档 | 清理后的 Markdown |

## 平台工具一览

| 平台 | 内容类型 | 主工具 | 备选方案 |
|------|----------|--------|----------|
| 小红书 | 图文笔记 | xhs-cli | agent-reach |
| 微信公众号 | 图文文章 | defuddle | agent-reach (camoufox) |
| 抖音 | 视频信息 | mcporter (douyin) | agent-reach |
| B站 | 视频 | yt-dlp + VideoCaptioner | agent-reach |
| B站 | 图文专栏 | defuddle | Jina Reader |
| YouTube | 视频 | yt-dlp + VideoCaptioner | agent-reach |
| 通用网页 | 图文 | defuddle | Jina Reader / agent-reach |

### 风控应对策略

各平台可能因风控更新导致工具失效，按以下优先级尝试：

```
主工具失效 → 备选方案 → 更新 agent-reach → 手动复制
```

**保持工具更新**：
```bash
# 更新 agent-reach 以获取最新风控应对
pip install -U agent-reach
agent-reach install --env=auto
```

> 关注 agent-reach 项目更新，以应对平台风控变化。

## Installation

### 1. 安装依赖 Skill

```bash
# 安装 obsidian-markdown skill
npx skills add git@github.com:kepano/obsidian-skills.git
```

或手动安装 `kepano/obsidian-skills` 到你的 skills 目录。

### 2. 安装本项目

将本项目放置到 Claude Code skills 目录：

```bash
# Linux / macOS
~/.claude/skills/web-scavenger

# Windows
C:\Users\<用户名>\.claude\skills\web-scavenger
```

### 3. 安装外部工具依赖

#### 核心依赖（必需）

```bash
# Python 包
pip install videocaptioner faster-whisper

# Node.js 包
npm install -g defuddle

# 系统工具
# macOS
brew install ffmpeg yt-dlp

# Windows (使用 winget 或 scoop)
winget install ffmpeg yt-dlp
# 或
scoop install ffmpeg yt-dlp
```

#### 平台特定依赖（按需安装）

```bash
# 小红书 (pipx 推荐)
pipx install xiaohongshu-cli

# MCP 工具 (抖音、微信搜索等)
pip install agent-reach
agent-reach install --env=auto

# 抖音 MCP（Agent-Reach 的 douyin 方式）
pipx install douyin-mcp-server
mcporter config add douyin --command douyin-mcp-server --scope home
```

## Dependencies 详解

### Required Skills

| Skill | 用途 | 安装 |
|-------|------|------|
| **obsidian-markdown** | Obsidian 语法规范（wikilinks, embeds, callouts, frontmatter） | `kepano/obsidian-skills` |

本 skill 依赖 `obsidian-markdown` 提供 Obsidian 格式支持，请确保已安装。

### 目标应用与 Obsidian 插件

| 应用/插件 | 安装位置 | 用途 | 必需 |
|------|----------|------|------|
| **Obsidian** | 本地应用 | 知识库管理，查看生成的笔记 | ✅ |
| **[Media Extended](https://github.com/aidenlx/media-extended)** | 通过 Obsidian 自身插件市场安装 | 在 Obsidian 内点击视频时间戳，跳转到本地视频对应时间点 | 视频笔记 ✅ |

> 注意：Media Extended 是 **Obsidian 内插件**，不是 Python、Node.js 或 AI 工具依赖。只有通过 Obsidian 自身插件市场安装并启用该插件后，视频笔记里的时间戳链接才能实现点击跳转到对应视频节点。

### 外部软件依赖

| 工具 | 用途 | 安装方式 | 必需 |
|------|------|----------|------|
| **Python 3.8+** | 运行脚本 | 系统安装 | ✅ |
| **ffmpeg** | 音视频处理 | brew / winget / scoop | 视频 ✅ |
| **yt-dlp** | 视频下载 | brew / pip | 视频 ✅ |
| **Faster Whisper** | ASR 转录 | `pip install faster-whisper` | 视频 ✅ |
| **VideoCaptioner** | 视频字幕处理 | `pip install videocaptioner` | 视频 ✅ |
| **defuddle** | 网页内容提取 | `npm install -g defuddle` | 图文 ✅ |
| **Node.js 18+** | 运行 defuddle | 系统安装 | 图文 ✅ |
| **curl** | 图片下载 | 系统自带 | 图文 ✅ |
| **xhs-cli** | 小红书笔记提取 | `pipx install xiaohongshu-cli` | 小红书 |
| **agent-reach** | 增强平台访问 | `pip install agent-reach` | 可选 |
| **douyin-mcp-server** | 抖音解析/下载链接 | `pipx install douyin-mcp-server` + `mcporter config add douyin --command douyin-mcp-server --scope home` | 抖音 |
| **nvidia-cublas-cu12 / nvidia-cudnn-cu12** | Windows CUDA 转录运行时 | `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` | GPU 加速 |

### MCP 工具依赖

| MCP Server | 用途 | 安装方式 |
|------------|------|----------|
| **mcporter** | 提供 douyin, xiaohongshu 等 | 通过 agent-reach 配置 |

配置示例：
```bash
# 安装 agent-reach
pip install agent-reach
agent-reach install --env=auto

# 添加抖音、微信等频道
agent-reach channel add douyin
agent-reach channel add wechat

# 抖音 MCP server
pipx install douyin-mcp-server
mcporter config add douyin --command douyin-mcp-server --scope home
```

### 内部脚本依赖

位于 `scripts/` 目录，无需额外安装：

| 脚本 | 用途 |
|------|------|
| `videocaptioner-stage.py` | 视频字幕提取主流程 |
| `srt-compress.py` | SRT 字幕压缩合并 |
| `split-compressed-subtitles.py` | 压缩字幕分块 |
| `compressed-to-transcript-md.py` | 生成 transcript.md |
| `markdown-process.py` | 将 `@00:25@` 时间标签替换为视频时间戳链接 |

## Quick Start

### 视频处理

```
用户: 帮我处理这个视频 <视频链接>
```

流程：下载视频 → ASR 转录 → 生成时间轴校对稿 → 生成树状总结

### 图文处理

```
用户: 保存这篇小红书笔记 <笔记链接>
```

流程：提取内容 → 下载图片 → 生成 Markdown

## Obsidian Support

生成的笔记兼容 Obsidian 格式，基础语法遵循 `obsidian-markdown` skill。

### Frontmatter 字段约定

```yaml
---
title: 文章标题
source: <原始链接>
platform: xhs/wechat/douyin/web/bilibili
date_saved: 2026-04-19
author: 作者名
tags:
  - tag1
  - tag2
---
```

### 时间戳视频链接

视频笔记支持时间戳跳转（项目特有格式）：

```markdown
- [00:01:23](../../videos/video.mp4#t=00:01:23) 核心观点
```

要在 Obsidian 内点击时间戳并跳转到视频对应时间点，必须通过 Obsidian 自身插件市场安装并启用 [Media Extended](https://github.com/aidenlx/media-extended)。这是视频输出链路的 Obsidian 端必需插件，不需要安装到 Claude、Codex 或命令行环境里。

## Vault 目录结构

```text
raw/
  videos/                     # 视频文件
    <video_id>_<slug>.mp4

  video_processing/           # 视频处理中间文件
    <video_id>/
      srt/                    # 字幕文件
      compressed/             # 压缩字幕
      chunks/                 # 分块字幕
      metadata/               # 元数据

  video_summaries/            # 视频笔记
    <video_id>/
      transcript.md           # 时间轴校对稿
      summary.md              # 树状总结

  articles/                   # 图文笔记
    <article_id>/
      article.md              # 文章主体
      images/                 # 本地图片
```

## Platform Notes

### Windows: xhs-cli 编码问题

Windows 下 xhs-cli 输出中文需要设置 UTF-8：

```powershell
$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json
```

或在 PowerShell 中全局设置：
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### ASR 转录时间

Faster Whisper 转录约 1-2 分钟/10分钟视频（CPU medium 模型）。

加速方法：
- 使用 `small` 或 `base` 模型
- 使用 GPU：`--fw-device cuda`
- 预提取音频

Windows 下如果 CUDA 转录报 `cublas64_12.dll` 或 `cudnn*.dll` 缺失，可安装：

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## Configuration

### 环境变量

```bash
# 默认知识库路径（可在 SKILL.md 中修改）
VAULT_ROOT=<YOUR_OBSIDIAN_VAULT>
```

### xhs-cli 配置

首次使用需要登录：
```bash
xhs login
# 按提示从浏览器提取 Cookie
```

## Troubleshooting

| 问题 | 解决方案 |
|------|----------|
| ffmpeg not found | 安装 ffmpeg 并添加到 PATH |
| ASR 转录失败 | 检查 faster-whisper 是否正确安装 |
| xhs-cli 返回空 | 检查 Cookie 是否过期，重新 `xhs login` |
| defuddle 解析失败 | 尝试 Jina Reader 作为备选 |
| 图片下载失败 | 检查网络，部分图片有防盗链 |

## License

MIT

## Contributing

欢迎提交 Issue 和 PR！
