#!/usr/bin/env python3
"""Fetch Bilibili official subtitles without authentication.

This script extracts official/CC subtitles from Bilibili videos.
If no subtitle is available, it returns an error so the caller can
fallback to local ASR transcription.

API Reference:
- Video info: https://api.bilibili.com/x/web-interface/view?bvid=xxx
- Subtitle list: https://api.bilibili.com/x/player/v2?bvid=xxx&cid=xxx
- Subtitle JSON: https://*.hdslb.com/*.json

No login required. Only needs Referer header for anti-hotlinking.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("requests is required: pip install requests", file=sys.stderr)
    raise

HEADERS = {
    "Referer": "https://www.bilibili.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


class BilibiliSubtitleError(Exception):
    """Base error for Bilibili subtitle fetching."""
    pass


class NoSubtitleError(BilibiliSubtitleError):
    """Video has no available subtitles."""
    pass


class VideoNotFoundError(BilibiliSubtitleError):
    """Video not found or private."""
    pass


def extract_bvid(url_or_bvid: str) -> str:
    """Extract BV ID from URL or return as-is if already a BV ID."""
    text = url_or_bvid.strip()
    # Direct BV ID
    if text.startswith("BV") and len(text) >= 10:
        return text
    # URL patterns
    match = re.search(r"/video/(BV[0-9A-Za-z]+)", text)
    if match:
        return match.group(1)
    # Short URL or other patterns
    match = re.search(r"(BV[0-9A-Za-z]+)", text)
    if match:
        return match.group(1)
    raise BilibiliSubtitleError(f"Cannot extract BV ID from: {url_or_bvid}")


def fetch_video_info(bvid: str) -> dict[str, Any]:
    """Fetch video metadata including cid, aid, title, duration."""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    resp = SESSION.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        msg = data.get("message", "Unknown error")
        if data.get("code") == -400:
            raise VideoNotFoundError(f"Video not found: {bvid}")
        raise BilibiliSubtitleError(f"Bilibili API error: {msg} (code: {data.get('code')})")

    video_data = data["data"]
    return {
        "bvid": bvid,
        "aid": video_data.get("aid", 0),
        "title": video_data.get("title", ""),
        "description": video_data.get("desc", ""),
        "author": video_data.get("owner", {}).get("name", ""),
        "duration": video_data.get("duration", 0),
        "default_cid": video_data.get("cid", 0),
        "pages": [
            {
                "cid": p.get("cid", 0),
                "page": p.get("page", 1),
                "duration": p.get("duration", 0),
                "part": p.get("part", ""),
            }
            for p in video_data.get("pages", [])
        ],
        "pubdate": video_data.get("pubdate", 0),
    }


def fetch_subtitle_list(bvid: str, cid: int, aid: int = 0) -> list[dict[str, Any]]:
    """Fetch available subtitle tracks for a video."""
    # Prefer player/wbi/v2 endpoint with aid
    if aid:
        url = f"https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}&bvid={bvid}"
    else:
        url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"

    resp = SESSION.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        # Try fallback endpoint without aid
        if aid and data.get("code") in (-400, -404):
            url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
            resp = SESSION.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            msg = data.get("message", "Unknown error")
            raise BilibiliSubtitleError(f"Player API error: {msg} (code: {data.get('code')})")

    subtitle_data = data.get("data", {}).get("subtitle", {})
    subtitles = subtitle_data.get("subtitles", [])

    return [
        {
            "id": sub.get("id", ""),
            "lan": sub.get("lan", ""),
            "lan_doc": sub.get("lan_doc", ""),
            "subtitle_url": normalize_subtitle_url(sub.get("subtitle_url", "")),
            "is_ai": str(sub.get("lan", "")).lower().startswith("ai-"),
        }
        for sub in subtitles
        if sub.get("subtitle_url")
    ]


def normalize_subtitle_url(url: str) -> str:
    """Ensure subtitle URL has https scheme."""
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if not url.startswith("http"):
        return f"https://{url.lstrip('/')}"
    return url


def fetch_subtitle_body(url: str) -> list[dict[str, Any]]:
    """Download and parse subtitle JSON file."""
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("body", [])


def pick_cid(info: dict[str, Any], page_index: int = 1) -> int:
    """Pick the correct cid for a given page index (1-indexed)."""
    pages = info.get("pages", [])
    if not pages:
        return info.get("default_cid", 0)

    # Find by page number
    for p in pages:
        if p.get("page") == page_index:
            return p.get("cid", 0)

    # Fallback to index
    if 1 <= page_index <= len(pages):
        return pages[page_index - 1].get("cid", 0)

    return info.get("default_cid", 0)


def pick_duration(info: dict[str, Any], page_index: int = 1) -> int:
    """Pick the duration for a given page index."""
    pages = info.get("pages", [])
    if not pages:
        return info.get("duration", 0)

    for p in pages:
        if p.get("page") == page_index:
            return p.get("duration", 0)

    if 1 <= page_index <= len(pages):
        return pages[page_index - 1].get("duration", 0)

    return info.get("duration", 0)


def subtitle_priority(sub: dict[str, Any]) -> int:
    """Calculate priority for subtitle track selection (lower = better)."""
    lan = str(sub.get("lan", "")).lower()
    lan_doc = str(sub.get("lan_doc", "")).lower()

    # Chinese variants (highest priority)
    if lan in ("zh-cn", "zh-hans"):
        return 0
    if lan == "zh":
        return 1
    if "zh" in lan:
        return 2
    if "中文" in lan_doc:
        return 3

    # English
    if lan in ("en", "en-us", "en-gb"):
        return 10
    if "en" in lan:
        return 11
    if "英文" in lan_doc or "english" in lan_doc:
        return 12

    return 50


def pick_best_subtitle(subtitles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the best subtitle track (Chinese > English > others)."""
    if not subtitles:
        return None

    # Sort by priority, then by language name
    sorted_subs = sorted(subtitles, key=lambda s: (subtitle_priority(s), s.get("lan_doc", "")))
    return sorted_subs[0]


def validate_subtitle_duration(body: list[dict[str, Any]], video_duration: int) -> bool:
    """Check if subtitle duration roughly matches video duration."""
    if not body or video_duration <= 0:
        return True  # Skip validation if no data

    # Find max timestamp in subtitle
    max_to = 0
    for item in body:
        to = float(item.get("to", 0))
        from_time = float(item.get("from", 0))
        max_to = max(max_to, to, from_time)

    # Allow 15% tolerance
    upper_limit = video_duration + max(12, video_duration * 0.15)
    lower_limit = video_duration * 0.15  # At least 15% coverage

    if max_to > upper_limit:
        return False  # Subtitle too long (wrong track)
    if max_to < lower_limit:
        return False  # Subtitle too short (wrong track)

    return True


def json_to_srt(body: list[dict[str, Any]]) -> str:
    """Convert Bilibili subtitle JSON to SRT format."""
    if not body:
        return ""

    lines = []
    for i, item in enumerate(body, 1):
        text = str(item.get("content", "")).strip()
        if not text:
            continue

        start = float(item.get("from", 0))
        end = float(item.get("to", 0))

        lines.append(str(i))
        lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    total_ms = int(max(0, seconds) * 1000)
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def fetch_bilibili_subtitles(
    url_or_bvid: str,
    page_index: int = 1,
    language: str | None = None,
    prefer_ai: bool = False,
) -> dict[str, Any]:
    """
    Main function to fetch Bilibili subtitles.

    Args:
        url_or_bvid: Bilibili video URL or BV ID
        page_index: Page number for multi-part videos (1-indexed)
        language: Preferred language code (e.g., "zh-CN", "en-US")
        prefer_ai: Prefer AI-generated subtitles over human ones

    Returns:
        Dict with video info, subtitle metadata, and SRT content

    Raises:
        NoSubtitleError: No subtitles available for this video
        VideoNotFoundError: Video not found or private
        BilibiliSubtitleError: Other API errors
    """
    bvid = extract_bvid(url_or_bvid)

    # Fetch video info
    info = fetch_video_info(bvid)
    aid = info.get("aid", 0)
    cid = pick_cid(info, page_index)
    duration = pick_duration(info, page_index)

    if not cid:
        raise BilibiliSubtitleError(f"Cannot determine cid for page {page_index}")

    # Fetch subtitle list
    subtitles = fetch_subtitle_list(bvid, cid, aid)

    if not subtitles:
        raise NoSubtitleError(f"No subtitles available for {bvid}")

    # Filter by language if specified
    if language:
        subtitles = [
            s for s in subtitles
            if s.get("lan", "").lower() == language.lower()
            or s.get("lan_doc", "").lower() == language.lower()
        ]
        if not subtitles:
            raise NoSubtitleError(f"No subtitles found for language: {language}")

    # Filter by AI preference
    if prefer_ai:
        ai_subs = [s for s in subtitles if s.get("is_ai")]
        if ai_subs:
            subtitles = ai_subs
    else:
        human_subs = [s for s in subtitles if not s.get("is_ai")]
        if human_subs:
            subtitles = human_subs

    # Pick best subtitle
    best = pick_best_subtitle(subtitles)
    if not best:
        raise NoSubtitleError("No suitable subtitle track found")

    # Download subtitle body
    subtitle_url = best.get("subtitle_url", "")
    body = fetch_subtitle_body(subtitle_url)

    if not body:
        raise NoSubtitleError("Subtitle file is empty")

    # Validate duration
    if not validate_subtitle_duration(body, duration):
        # Try other subtitles if available
        for sub in subtitles:
            if sub == best:
                continue
            try:
                alt_body = fetch_subtitle_body(sub.get("subtitle_url", ""))
                if alt_body and validate_subtitle_duration(alt_body, duration):
                    body = alt_body
                    best = sub
                    break
            except Exception:
                continue

    # Convert to SRT
    srt_content = json_to_srt(body)

    return {
        "bvid": bvid,
        "aid": aid,
        "cid": cid,
        "page": page_index,
        "title": info.get("title", ""),
        "author": info.get("author", ""),
        "description": info.get("description", ""),
        "duration": duration,
        "subtitle": {
            "id": best.get("id"),
            "lan": best.get("lan"),
            "lan_doc": best.get("lan_doc"),
            "is_ai": best.get("is_ai"),
            "url": subtitle_url,
            "segment_count": len(body),
        },
        "srt": srt_content,
        "available_subtitles": [
            {"lan": s.get("lan"), "lan_doc": s.get("lan_doc"), "is_ai": s.get("is_ai")}
            for s in subtitles
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Bilibili official subtitles without authentication."
    )
    parser.add_argument("url_or_bvid", help="Bilibili video URL or BV ID")
    parser.add_argument("--page", type=int, default=1, help="Page number for multi-part videos")
    parser.add_argument("--language", help="Preferred language code (e.g., zh-CN, en-US)")
    parser.add_argument("--prefer-ai", action="store_true", help="Prefer AI-generated subtitles")
    parser.add_argument("--output-srt", "-o", type=Path, help="Output SRT file path")
    parser.add_argument("--output-json", type=Path, help="Output JSON metadata path")
    parser.add_argument("--list", action="store_true", help="List available subtitles only")
    args = parser.parse_args()

    try:
        if args.list:
            # Just list available subtitles
            bvid = extract_bvid(args.url_or_bvid)
            info = fetch_video_info(bvid)
            aid = info.get("aid", 0)
            cid = pick_cid(info, args.page)
            subtitles = fetch_subtitle_list(bvid, cid, aid)

            result = {
                "bvid": bvid,
                "title": info.get("title", ""),
                "subtitles": subtitles,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        result = fetch_bilibili_subtitles(
            args.url_or_bvid,
            page_index=args.page,
            language=args.language,
            prefer_ai=args.prefer_ai,
        )

        # Output SRT file
        if args.output_srt:
            args.output_srt.parent.mkdir(parents=True, exist_ok=True)
            args.output_srt.write_text(result["srt"], encoding="utf-8")
            print(f"SRT saved to: {args.output_srt}", file=sys.stderr)

        # Output JSON metadata
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            output_data = {k: v for k, v in result.items() if k != "srt"}
            args.output_json.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"JSON saved to: {args.output_json}", file=sys.stderr)

        # Output to stdout
        output = {
            "success": True,
            "video": {
                "bvid": result["bvid"],
                "aid": result["aid"],
                "title": result["title"],
                "author": result["author"],
                "duration": result["duration"],
            },
            "subtitle": result["subtitle"],
            "srt_path": str(args.output_srt) if args.output_srt else None,
            "available_subtitles": result["available_subtitles"],
        }

        if not args.output_srt:
            output["srt_preview"] = result["srt"][:500] + "..." if len(result["srt"]) > 500 else result["srt"]

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    except NoSubtitleError as e:
        output = {"success": False, "error": str(e), "error_type": "no_subtitle"}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1

    except VideoNotFoundError as e:
        output = {"success": False, "error": str(e), "error_type": "video_not_found"}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 2

    except BilibiliSubtitleError as e:
        output = {"success": False, "error": str(e), "error_type": "api_error"}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 3

    except Exception as e:
        output = {"success": False, "error": str(e), "error_type": "unknown"}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
