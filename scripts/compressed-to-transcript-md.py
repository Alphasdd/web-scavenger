#!/usr/bin/env python3
"""Convert compressed subtitle text to an Obsidian review transcript.

Input format:
    HH:MM:SS|subtitle text

Output format:
    # Title
    > Purpose
    - [HH:MM:SS](../../videos/video.mp4#t=HH:MM:SS)
      - subtitle text
"""

import argparse
from pathlib import Path


def read_entries(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "|" not in line:
            raise SystemExit(f"Invalid compressed subtitle line {line_no}: {raw_line!r}")
        timestamp, text = line.split("|", 1)
        timestamp = timestamp.strip()
        text = text.strip()
        if timestamp and text:
            entries.append((timestamp, text))
    if not entries:
        raise SystemExit("No valid compressed subtitle entries found")
    return entries


def build_markdown(
    entries: list[tuple[str, str]],
    title: str,
    video_rel: str,
    purpose: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"> {purpose}",
        "",
    ]
    for timestamp, text in entries:
        lines.append(f"- [{timestamp}]({video_rel}#t={timestamp})")
        lines.append(f"  - {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create transcript.md from compressed subtitle text."
    )
    parser.add_argument("input", help="Compressed subtitle text in HH:MM:SS|text format.")
    parser.add_argument("-o", "--output", required=True, help="Output transcript Markdown path.")
    parser.add_argument(
        "--video-rel",
        required=True,
        help="Relative video path from transcript.md folder, for example ../../videos/video.mp4.",
    )
    parser.add_argument("--title", required=True, help="Markdown title.")
    parser.add_argument(
        "--purpose",
        default="用途：本稿由压缩字幕生成；Claude 需先完成术语和明显错字校验，再交给用户对照视频精修。",
        help="Blockquote purpose text.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries = read_entries(input_path)
    markdown = build_markdown(entries, args.title, args.video_rel, args.purpose)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
