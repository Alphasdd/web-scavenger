# Video Workflow

Convert videos into Obsidian notes with timestamped transcript and tree-shaped summary.

## Workflow Overview

```
video URL / local video / existing SRT
  → create or choose SRT
  → compress SRT
  → split compressed subtitles
  → create transcript.md draft
  → Claude calibrates transcript.md
  → create summary.md from transcript.md
```

## Core Principle

1. `transcript.md` is the auditable source for summary
2. `transcript.md` must be calibrated (fix ASR errors, terminology) while preserving timestamps
3. User can edit transcript.md, then regenerate summary.md
4. `summary.md` should be insight-dense and tree-shaped

## Directory Structure

```text
raw/
  videos/
    <video_id>_<ascii_slug>.mp4

  video_processing/
    <video_id>/
      srt/
        faster_whisper_medium_cpu.srt
        provided_bilingual.srt
      compressed/
        faster_whisper_medium_cpu.txt
      chunks/
        chunk_001.txt
        manifest.json
      metadata/
        video_note_metadata.json

  video_summaries/
    <video_id>/
      transcript.md
      summary.md
```

## Step-by-Step Process

### Step 1: Prepare Paths

Resolve:
- `vault_root` (from `VAULT_ROOT`, or ask the user for their Obsidian vault path)
- `video_id` (prefer platform ID like Bilibili BV id)
- `ascii_slug` (short ASCII title, lowercase, no spaces)
- Create directories

### Step 2: Create or Select SRT

**From URL:**
```bash
python scripts/videocaptioner-stage.py --url "<video_url>" --work-dir "<work_dir>" --language zh --model medium --device cpu
```

**B站视频优化**：脚本自动检测B站URL，优先获取官方字幕（秒级），无字幕时fallback到Whisper ASR。

**单独获取B站字幕**：
```bash
# 只获取字幕，不下载视频
python scripts/bilibili-subtitle.py "<bilibili_url>" -o subtitle.srt

# 列出可用字幕轨道
python scripts/bilibili-subtitle.py "<bilibili_url>" --list
```

**From local video:**
```bash
python scripts/videocaptioner-stage.py --video "<video_path>" --work-dir "<work_dir>" --language zh --model medium --device cpu
```

**From existing SRT:**
- Use provided SRT if higher quality than ASR output
- Copy to `raw/video_processing/<video_id>/srt/`

**字幕来源标识**：输出JSON中的 `subtitle_source` 字段标识字幕来源：
- `bilibili_official`：B站官方字幕（含CC字幕、AI字幕）
- `local_asr`：本地Whisper ASR转录

### Step 3: Compress SRT

```bash
python scripts/srt-compress.py "<srt_path>" -o "<compressed_txt>" --merge-sentences
```

Store in `raw/video_processing/<video_id>/compressed/`

### Step 4: Split Compressed Subtitles

```bash
python scripts/split-compressed-subtitles.py "<compressed_txt>" -o "<chunk_dir>"
```

Store in `raw/video_processing/<video_id>/chunks/`

### Step 5: Create transcript.md Draft

**Invoke `obsidian-markdown` skill before writing to ensure correct syntax.**

The helper script creates a mechanical draft with frontmatter and timestamp links. The agent must still load and follow `obsidian-markdown` rules before writing or updating the final `transcript.md`.

```bash
python scripts/compressed-to-transcript-md.py "<compressed_txt>" -o "<summary_dir>/transcript.md" --video-rel "../../videos/<video_id>_<slug>.mp4" --title "<title> 时间轴校对稿" --source "<original_url>" --platform "<platform>"
```

Format:
```markdown
---
title: "<title> 时间轴校对稿"
type: video_transcript
video: ../../videos/<video>.mp4
platform: <platform>
date_saved: 2026-04-19
status: draft_from_compressed_subtitles
source: <original_url>
tags:
  - web-scavenger
  - video
  - transcript
---

# <title> 时间轴校对稿

> 用途：本稿已完成 Claude 第一轮术语和明显错字校验

- [00:00:00](../../videos/<video>.mp4#t=00:00:00)
  - subtitle text
```

### Step 6: Calibrate transcript.md

Before showing to user, Claude must calibrate:

**Calibration rules:**
- Preserve every timestamp link
- Correct obvious ASR errors (platform names, model names, people, libraries, commands, English terms)
- Fix broken word splits and punctuation
- Do NOT summarize, delete content, or invent details
- Keep raw machine outputs in `video_processing/` directory

Mark status in metadata:
```json
{
  "transcript_status": "claude_first_pass_calibrated"
}
```

### Step 7: Create summary.md

**Invoke `obsidian-markdown` skill before writing to ensure correct syntax.**

The agent writes `summary.md`, so it must load and follow `obsidian-markdown` rules before creating or updating the file.

Generate from calibrated or user-edited transcript.md.

`summary.md` must also include Obsidian frontmatter:

```yaml
---
title: "<title>"
type: video_summary
source: <original_url>
platform: <platform>
video: ../../videos/<video>.mp4
transcript: transcript.md
date_saved: 2026-04-19
tags:
  - web-scavenger
  - video
  - summary
---
```

**Summary Style Requirements:**

Main node format:
```markdown
- [00:00:00](../../videos/video.mp4#t=00:00:00) 核心命题：精炼的判断句
  - 机制解释：为什么是这样
  - 案例/证据：具体例子支撑
  - 提炼：关键洞察
```

**Requirements:**
- Timestamp + core claim (judgment sentence, not just title)
- Sub-nodes: mechanism, evidence, reusable conclusion
- Use `提炼：` or `可迁移结论：` to mark insights
- Tree-shaped for easy folding and mindmap conversion

**Avoid:**
- Pure outline (titles without content)
- Title-style nodes (e.g., "效果演示" instead of "效果演示证明 XX 可行")
- Long paragraphs
- Too many timestamps (interfere with reading)

### Step 8: Metadata

Write to `raw/video_processing/<video_id>/metadata/video_note_metadata.json`:

```json
{
  "id": "<video_id>",
  "title": "<title>",
  "original_url": "<url>",
  "video_file": "raw/videos/<video_id>_<slug>.mp4",
  "summary_dir": "raw/video_summaries/<video_id>",
  "transcript": "raw/video_summaries/<video_id>/transcript.md",
  "summary": "raw/video_summaries/<video_id>/summary.md",
  "link_format": "../../videos/<video_id>_<slug>.mp4#t={hms}",
  "summary_source": "raw/video_summaries/<video_id>/transcript.md",
  "transcript_status": "claude_first_pass_calibrated"
}
```

## ASR Time Notice

Faster Whisper takes ~1-2 minutes per 10 minutes of video. Inform user:

```
正在加载 Whisper medium 模型...
正在转录音频（视频约 13 分钟，预计需要 2-3 分钟）...
转录完成，正在保存字幕文件...
```

For faster transcription:
- Use `small` or `base` model
- Use GPU with `--fw-device cuda`
- Pre-extract audio

### Windows CUDA Runtime

If CUDA transcription fails with missing `cublas64_12.dll` or `cudnn*.dll`, install the CUDA runtime wheels:

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

`scripts/videocaptioner-stage.py` adds these wheel DLL directories automatically when they are present.

## Path and Link Rules

From `raw/video_summaries/<video_id>/`:

```markdown
[00:00:00](../../videos/<video_id>_<slug>.mp4#t=00:00:00)
```

Relative path: `video_summaries/<id>/` → `videos/<file>.mp4`

## Obsidian Playback Requirement

Timestamp links are written for Obsidian playback. To click a timestamp in Obsidian and jump to the matching point in the local video, the user must install and enable [Media Extended](https://github.com/aidenlx/media-extended) through Obsidian's own plugin marketplace.

This is an Obsidian-side plugin requirement, not a Python, Node.js, Claude, or Codex dependency.
