#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

LINE_RE = re.compile(r"^(?P<time>\d{2}:\d{2}:\d{2})\|(?P<text>.*)$")


def parse_hms(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def format_hms(value: int) -> str:
    hours = value // 3600
    minutes = (value % 3600) // 60
    seconds = value % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def read_entries(path: Path):
    entries = []
    for line_no, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if not match:
            raise ValueError(
                f"Invalid compressed subtitle line {line_no}: {raw_line!r}"
            )
        start = match.group("time")
        text = match.group("text").strip()
        if text:
            entries.append((parse_hms(start), start, text))
    return entries


def build_chunks(entries, chunk_seconds: int, overlap_seconds: int):
    if not entries:
        return []

    first_time = entries[0][0]
    last_time = entries[-1][0]
    chunks = []
    chunk_start = first_time

    while chunk_start <= last_time:
        chunk_end = chunk_start + chunk_seconds
        selected = [entry for entry in entries if chunk_start <= entry[0] < chunk_end]

        if selected:
            chunks.append(
                {
                    "window_start_seconds": chunk_start,
                    "window_end_seconds": chunk_end,
                    "entries": selected,
                }
            )

        next_start = chunk_end - overlap_seconds
        if next_start <= chunk_start:
            next_start = chunk_end
        chunk_start = next_start

    return chunks


def write_chunks(chunks, output_dir: Path, stem: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for index, chunk in enumerate(chunks, start=1):
        entries = chunk["entries"]
        actual_start = entries[0][1]
        actual_end = entries[-1][1]
        chunk_name = f"{stem}.part{index:02d}.{actual_start.replace(':', '-')}_{actual_end.replace(':', '-')}.txt"
        chunk_path = output_dir / chunk_name
        chunk_text = "\n".join(f"{start}|{text}" for _, start, text in entries)
        chunk_path.write_text(chunk_text, encoding="utf-8")

        manifest.append(
            {
                "index": index,
                "path": str(chunk_path),
                "window_start": format_hms(chunk["window_start_seconds"]),
                "window_end": format_hms(chunk["window_end_seconds"]),
                "actual_start": actual_start,
                "actual_end": actual_end,
                "entry_count": len(entries),
            }
        )

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Split compressed subtitle text into timestamp-based chunks for long videos."
    )
    parser.add_argument(
        "input", help="Input compressed subtitle txt in HH:MM:SS|text format."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory for chunk files. Default: <input_stem>_chunks next to input.",
    )
    parser.add_argument(
        "--chunk-minutes",
        type=int,
        default=15,
        help="Chunk length in minutes. Default: 15.",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=45,
        help="Overlap between adjacent chunks in seconds. Default: 45.",
    )
    parser.add_argument(
        "--threshold-minutes",
        type=int,
        default=30,
        help="Only split when subtitle span exceeds this many minutes. Default: 30.",
    )
    parser.add_argument(
        "--manifest",
        help="Optional manifest json path. Default: <output-dir>/manifest.json",
    )

    args = parser.parse_args()

    if args.chunk_minutes <= 0:
        raise SystemExit("--chunk-minutes must be greater than 0")
    if args.overlap_seconds < 0:
        raise SystemExit("--overlap-seconds must be >= 0")
    if args.threshold_minutes < 0:
        raise SystemExit("--threshold-minutes must be >= 0")

    input_path = Path(args.input)
    entries = read_entries(input_path)
    if not entries:
        raise SystemExit(
            "Compressed subtitle file is empty or contains no valid entries"
        )

    total_span_seconds = entries[-1][0] - entries[0][0]
    should_split = total_span_seconds > args.threshold_minutes * 60

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else input_path.with_name(f"{input_path.stem}_chunks")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if should_split:
        chunks = build_chunks(entries, args.chunk_minutes * 60, args.overlap_seconds)
    else:
        chunks = [
            {
                "window_start_seconds": entries[0][0],
                "window_end_seconds": entries[-1][0],
                "entries": entries,
            }
        ]

    manifest = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "threshold_minutes": args.threshold_minutes,
        "chunk_minutes": args.chunk_minutes,
        "overlap_seconds": args.overlap_seconds,
        "total_span_seconds": total_span_seconds,
        "split_applied": should_split,
        "chunks": write_chunks(chunks, output_dir, input_path.stem),
    }

    manifest_path = (
        Path(args.manifest) if args.manifest else output_dir / "manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8"
    )

    json.dump(manifest, sys.stdout, ensure_ascii=True, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
