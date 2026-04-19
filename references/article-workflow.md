# Article Workflow

Convert web articles and social posts into Obsidian markdown notes with local image storage.

## Supported Sources

| Source | Tool | Notes |
|--------|------|-------|
| Web articles/blogs | defuddle / Jina Reader | Clean markdown extraction |
| 微信公众号 | defuddle | Full article + images |
| 小红书 | xhs-cli | Text + images |
| 抖音 | mcporter (douyin) | Video info + cover image |
| B站专栏 | defuddle / Jina Reader | Article content |

## Directory Structure

```text
raw/
  articles/
    <article_id>/              # e.g., xhs_69db0b4e000000001d01a2b8
      article.md               # Main article markdown
      images/                  # Local image storage
        01_cover.png
        02_screenshot.jpg
      metadata.json            # Optional
```

## Article ID Convention

Format: `<platform>_<content_id>`

Examples:
- `xhs_65a1b2c3d4e5f6` - Xiaohongshu note
- `wechat_mp123456789` - WeChat article
- `douyin_7123456789` - Douyin video
- `web_example.com_slug` - Web article

## Step-by-Step Process

### Step 1: Identify Source

Determine platform from URL:
- `xiaohongshu.com` / `xhslink.com` → Xiaohongshu
- `mp.weixin.qq.com` → WeChat
- `douyin.com` / `v.douyin.com` → Douyin
- `bilibili.com/read` → Bilibili article
- Other → Web article

### Step 2: Extract Content

**Xiaohongshu:**
```bash
# macOS/Linux
PYTHONIOENCODING=utf-8 xhs read "<note_id>" --json
```

```powershell
# Windows PowerShell
$env:PYTHONIOENCODING='utf-8'; xhs read "<note_id>" --json
```

**WeChat / Web Article:**
```bash
defuddle parse "<url>" --md
```

**Douyin:**
```bash
mcporter call 'douyin.parse_douyin_video_info(share_link: "...")'
```

**Bilibili Article:**
```bash
defuddle parse "https://www.bilibili.com/read/cv..." --md
# Or Jina Reader
curl -s "https://r.jina.ai/https://www.bilibili.com/read/cv..."
```

### Step 3: Download Images

Create `images/` subdirectory and download with sequential naming:

```bash
curl -H "User-Agent: Mozilla/5.0" -o "images/01_image.png" "<image_url>"
```

**Naming convention:**
```
01_cover.png        # Cover image
02_screenshot.jpg   # Screenshot
03_diagram.png      # Diagram
...
```

**Supported formats:** PNG, JPEG, WebP, GIF

**Anti-hotlinking:** Always include User-Agent header

### Step 4: Create article.md

**Invoke `obsidian-markdown` skill before writing to ensure correct syntax.**

Write to `raw/articles/<article_id>/article.md`:

```yaml
---
title: 文章标题
source: https://original-url.com/article
platform: xhs/wechat/douyin/web
date_saved: 2026-04-19
author: 作者名
tags:
  - tag1
  - tag2
---

# 文章标题

正文内容...

![[images/01_cover.png]]
![[images/02_screenshot.jpg]]

> 来源：[@作者](https://...) | 平台互动数据
```

### Step 5: Convert Image Links

Replace external URLs with local embeds:

Before:
```markdown
![](https://example.com/image.png)
```

After:
```markdown
![[images/01_image.png]]
```

### Step 6: Metadata (Optional)

Create `metadata.json`:

```json
{
  "id": "xhs_65a1b2c3d4e5f6",
  "source_url": "https://...",
  "platform": "xiaohongshu",
  "author": "作者",
  "published_date": "2026-04-19",
  "images_count": 3,
  "saved_date": "2026-04-19T15:00:00"
}
```

## Path and Link Rules

From `raw/articles/<article_id>/article.md`:

```markdown
![[images/01_cover.png]]                    # 图片在同级 images/ 目录
[相关视频](../../videos/video_id.mp4)       # 链接到视频
```

> 基础 Obsidian 语法（wikilinks, embeds）遵循 `obsidian-markdown` skill。

## Quality Standards

1. **Clean markdown** - Remove navigation, ads, clutter
2. **Local images** - Download and embed locally when possible
3. **Proper frontmatter** - Include title, source, date, tags
4. **Readable structure** - Use headings, lists, callouts appropriately
5. **Working links** - All image embeds and internal links should resolve

## Platform-Specific Notes

### Xiaohongshu (Windows)

xhs-cli requires UTF-8 encoding on Windows:

```powershell
$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json
```

Or set globally in PowerShell:
```powershell
$env:PYTHONIOENCODING = "utf-8"
```

### WeChat

- Images have anti-hotlinking, always use User-Agent
- defuddle works well for content extraction
- May need to download many images (20+)

### Douyin

- Returns video info, not full content
- Useful for cover image and metadata
- Pair with video workflow if full video processing needed
