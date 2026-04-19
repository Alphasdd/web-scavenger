---
name: web-scavenger
description: Collect and curate web content into Obsidian-ready notes. Automatically detects content type (video/article/social post) and routes to the appropriate workflow. Requires obsidian-markdown skill for proper Obsidian syntax. Use when user provides a URL to save or process.
---

# Web Scavenger

网络拾荒者 - 从互联网采集有价值的内容到知识库。

## Supported Content Types

| Type | Platforms | Workflow |
|------|-----------|----------|
| **Video** | Bilibili, YouTube, local video | `video-workflow.md` |
| **Xiaohongshu** | 小红书笔记 | `article-workflow.md` |
| **WeChat** | 微信公众号文章 | `article-workflow.md` |
| **Douyin** | 抖音视频（封面+信息） | `article-workflow.md` |
| **Web Article** | 博客、新闻、文档 | `article-workflow.md` |

## Auto-Detection Logic

From URL pattern:

```
bilibili.com/video     → Video
youtube.com/watch      → Video
youtu.be               → Video
youtube.com/shorts     → Video
b23.tv                 → Video (Bilibili short link)

xiaohongshu.com        → Xiaohongshu Article
xhslink.com            → Xiaohongshu Article

mp.weixin.qq.com       → WeChat Article

douyin.com/video       → Douyin (video info)
v.douyin.com           → Douyin (video info)

Other URLs             → Web Article
Local video/audio file → Video
Local .srt file        → Video (skip transcription)
```

## Vault Layout

```text
raw/
  videos/                     # 视频文件
    <video_id>_<slug>.mp4

  video_processing/           # 视频处理中间文件
    <video_id>/
      srt/
      compressed/
      chunks/
      metadata/

  video_summaries/            # 视频笔记
    <video_id>/
      transcript.md
      summary.md

  articles/                   # 图文笔记
    <article_id>/
      article.md
      images/
```

## ID Convention

- Video: `<platform>_<content_id>` (e.g., `BV1RkFAznESD`)
- Article: `<platform>_<content_id>` (e.g., `xhs_69db0b4e000000001d01a2b8`, `wechat_0CTwb4aEr5mWwsdRdwzwkw`)

## Main Workflow

### Step 1: Detect Content Type

From URL or file path, determine:
- Video → follow `references/video-workflow.md`
- Article/Social → follow `references/article-workflow.md`

### Step 2: Extract Content

Use appropriate tools based on platform:

```bash
# Video
python scripts/videocaptioner-stage.py --url "<url>" --work-dir "<dir>" --language zh --model medium --device cpu

# Xiaohongshu (macOS/Linux)
PYTHONIOENCODING=utf-8 xhs read "<note_id>" --json

# Xiaohongshu (Windows PowerShell)
$env:PYTHONIOENCODING='utf-8'; xhs read "<note_id>" --json

# WeChat / Web Article
defuddle parse "<url>" --md

# Douyin
mcporter call 'douyin.parse_douyin_video_info(share_link: "...")'
```

### Step 3: Process and Save

- Video: SRT → compress → transcript.md → calibrate → summary.md
- Article: Extract → download images → article.md

**Important:** Before writing any `.md` file, invoke the `obsidian-markdown` skill to ensure correct Obsidian Flavored Markdown syntax (wikilinks, embeds, callouts, properties).

### Step 4: Quality Check

- All image embeds resolve correctly
- Timestamp links are present for video notes
- For clickable timestamp playback inside Obsidian, tell the user to install and enable [Media Extended](https://github.com/aidenlx/media-extended) through Obsidian's own plugin marketplace. This is an Obsidian-side plugin, not an AI tool dependency.
- Frontmatter complete

## Dependencies

### Required Skill

- **obsidian-markdown** - Obsidian Flavored Markdown syntax (wikilinks, embeds, callouts, properties)

Install from: `kepano/obsidian-skills`

### External Tools

Check tool availability:

```bash
# Video
python scripts/videocaptioner-stage.py --help
yt-dlp --version
ffmpeg -version

# Article
defuddle --version
xhs --version           # Xiaohongshu
mcporter list           # MCP tools
curl --version          # Image download
```

Install if needed:

```bash
# Video tools
pip install videocaptioner
pip install faster-whisper

# Article tools
npm install -g defuddle
pipx install xiaohongshu-cli

# MCP tools (for Douyin, WeChat search)
pip install agent-reach
agent-reach install --env=auto

# Douyin MCP via Agent-Reach
pipx install douyin-mcp-server
mcporter config add douyin --command douyin-mcp-server --scope home

# Windows CUDA runtime for GPU transcription
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## Platform-Specific Notes

### Windows: xhs-cli Encoding

On Windows, xhs-cli may fail with Chinese text. Use PowerShell syntax:

```powershell
$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json
```

### ASR Transcription Time

Faster Whisper transcription takes ~1-2 minutes per 10 minutes of video. Always inform user of progress.

## References

- `references/video-workflow.md` - Detailed video processing workflow
- `references/article-workflow.md` - Detailed article processing workflow
- `references/platforms.md` - Platform-specific extraction guides
