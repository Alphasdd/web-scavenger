# Platform-Specific Extraction Guide

## 平台工具速查表

| 平台 | 内容类型 | 主工具 | 备选方案 |
|------|----------|--------|----------|
| 小红书 | 图文笔记 | xhs-cli | agent-reach (mcporter) |
| 微信公众号 | 图文文章 | defuddle | agent-reach (camoufox) |
| 抖音 | 视频信息 | mcporter (douyin) | agent-reach |
| B站 | 视频 | yt-dlp + VideoCaptioner | agent-reach |
| B站 | 图文专栏 | defuddle | Jina Reader |
| YouTube | 视频 | yt-dlp + VideoCaptioner | agent-reach |
| 通用网页 | 图文 | defuddle | Jina Reader / agent-reach |

## 风控应对策略

各平台可能因风控更新导致工具失效，按以下优先级尝试：

```
主工具失效 → 备选方案 → agent-reach 更新 → 手动复制
```

**agent-reach 更新**：
```bash
# 更新 agent-reach 以获取最新风控应对
pip install -U agent-reach
agent-reach install --env=auto
```

> 关注 agent-reach 项目更新，以应对平台风控变化。

---

## 小红书 (Xiaohongshu)

### URL Pattern
- `https://www.xiaohongshu.com/explore/<note_id>`
- `https://www.xiaohongshu.com/discovery/item/<note_id>`
- `https://xhslink.com/<short_code>` (短链接)

### 主工具：xhs-cli

```bash
# 安装
pipx install xiaohongshu-cli

# 登录（从浏览器提取 Cookie）
xhs login

# 读取笔记（macOS/Linux）
PYTHONIOENCODING=utf-8 xhs read "NOTE_ID" --json
```

```powershell
# 读取笔记（Windows PowerShell）
$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json
```

**返回内容**：
- Title (标题)
- Desc (正文内容)
- Image_list (图片列表)
- User info (作者信息)
- Interact_info (点赞、收藏、评论数)

**Windows 注意**：必须使用 PowerShell 环境变量写法：`$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json`。

### 备选方案：agent-reach (mcporter)

```bash
# 通过 mcporter MCP 调用
mcporter call 'xiaohongshu.get_feed_detail(note_id: "...")'
```

### 图片处理
- 从 `url_default` 字段下载图片
- 命名：`01_image.webp`, `02_image.webp`...
- 嵌入：`![[images/01_image.webp]]`

---

## 微信公众号 (WeChat MP)

### URL Pattern
- `https://mp.weixin.qq.com/s/<article_id>`

### 主工具：defuddle

```bash
defuddle parse "https://mp.weixin.qq.com/s/<article_id>" --md
```

**优点**：
- 直接解析，无需登录
- 自动清理导航和广告
- 输出干净 Markdown

**注意**：
- 图片有防盗链，下载时需带 User-Agent
- 建议下载图片到本地

### 备选方案：agent-reach (camoufox)

适用于 defuddle 解析失败或需要 JavaScript 渲染的页面：

```bash
# 使用 Camoufox 浏览器渲染后提取
agent-reach web read "<url>"
```

### 图片下载

```bash
# 带防盗链处理
curl -H "User-Agent: Mozilla/5.0" -o "images/01.png" "<image_url>"
```

---

## 抖音 (Douyin)

### URL Pattern
- `https://www.douyin.com/video/<video_id>`
- `https://v.douyin.com/<short_code>/` (分享链接)

### 主工具：mcporter (douyin channel)

安装：

```bash
pipx install douyin-mcp-server
mcporter config add douyin --command douyin-mcp-server --scope home
mcporter list douyin --schema
```

```bash
mcporter call 'douyin.parse_douyin_video_info(share_link: "分享链接")'
```

**返回内容**：
- Video title (标题)
- Description (描述)
- Author (作者)
- Cover image (封面)
- Video URL 无水印 (视频链接)
- Like/Comment/Share count (互动数据)

### 备选方案：agent-reach

```bash
# 通过 agent-reach 调用抖音解析
agent-reach douyin parse "<share_link>"
```

> `extract_douyin_text` 需要 `DASHSCOPE_API_KEY`。本 skill 默认只用 Douyin MCP 获取下载链接，再使用本地 Faster Whisper 走视频 workflow 转录。

### 使用场景
- 提取视频元信息和封面
- 获取无水印视频链接
- 配合 video workflow 处理完整视频

---

## B站 (Bilibili)

### 视频内容

#### URL Pattern
- `https://www.bilibili.com/video/<video_id>`
- `https://b23.tv/<short_code>` (短链接)

#### 主工具：yt-dlp + VideoCaptioner

```bash
# 下载视频和字幕
python scripts/videocaptioner-stage.py --url "<url>" --work-dir "<dir>" --language zh --model medium --device cpu
```

**流程**：
1. yt-dlp 下载视频和字幕
2. Faster Whisper ASR 转录（如无字幕）
3. 生成 SRT 字幕文件

#### 备选方案：agent-reach

```bash
# 通过 agent-reach 获取 B站视频
agent-reach bilibili download "<url>"
```

### 图文专栏

#### URL Pattern
- `https://www.bilibili.com/read/cv<article_id>`

#### 主工具：defuddle

```bash
defuddle parse "https://www.bilibili.com/read/cv..." --md
```

#### 备选方案：Jina Reader

```bash
curl -s "https://r.jina.ai/<url>"
```

---

## YouTube

### URL Pattern
- `https://www.youtube.com/watch?v=<video_id>`
- `https://youtu.be/<video_id>`
- `https://www.youtube.com/shorts/<video_id>`

### 主工具：yt-dlp + VideoCaptioner

```bash
python scripts/videocaptioner-stage.py --url "<url>" --work-dir "<dir>" --language en --model medium --device cpu
```

### 备选方案：agent-reach

适用于地区限制或网络问题：

```bash
agent-reach youtube download "<url>"
```

---

## 通用网页 (General Web)

### 工具选择

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| 博客/文章 | defuddle | 清理导航、广告，输出干净 |
| 技术文档 | Jina Reader | 简单快速，保留结构 |
| 需要 JS 渲染 | agent-reach (camoufox) | 浏览器渲染 |
| 需要登录 | agent-reach | 支持认证 |
| 动态加载内容 | agent-reach (camoufox) | 完整渲染 |

### defuddle (推荐)

```bash
defuddle parse "<url>" --md -o output.md
```

### Jina Reader

```bash
curl -s "https://r.jina.ai/<url>"
```

### agent-reach

```bash
agent-reach web read "<url>"
```

---

## Image Download Best Practices

### 支持格式
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- WebP (`.webp`)
- GIF (`.gif`)

### 命名规范
```
01_cover.png        # 封面图
02_screenshot.jpg   # 截图
03_diagram.png      # 图表
...
```

### 下载命令

```bash
# 带 User-Agent 避免防盗链
curl -H "User-Agent: Mozilla/5.0" -o "images/01.png" "<image_url>"

# 或使用 wget
wget --header="User-Agent: Mozilla/5.0" -O "images/01.png" "<image_url>"
```

### 转换为 Obsidian 嵌入

Before:
```markdown
![](https://example.com/image.png)
```

After:
```markdown
![[images/01_image.png]]
```

---

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| xhs-cli 返回空 | Cookie 过期 | 重新 `xhs login` |
| xhs-cli 编码错误 | Windows UTF-8 问题 | PowerShell 使用 `$env:PYTHONIOENCODING='utf-8'; xhs read "NOTE_ID" --json` |
| defuddle 解析失败 | 页面需要 JS 渲染 | 使用 agent-reach (camoufox) |
| 抖音解析失败 | 风控更新 | 更新 agent-reach 或尝试新分享链接 |
| 微信图片下载失败 | 防盗链 | 添加 User-Agent 头 |
| B站视频下载失败 | 地区限制 | 使用 agent-reach |
