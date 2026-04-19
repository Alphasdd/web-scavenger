#!/usr/bin/env python3
"""Prepare a video and SRT for the video-note-summary skill.

This script intentionally stops at mechanical work:
- optional online video download through VideoCaptioner
- Bilibili official subtitle extraction (no auth required)
- local transcription through VideoCaptioner with Faster Whisper medium on CPU
- JSON output describing the produced files

The AI summary is done by Claude from compressed subtitle chunks, not
inside this script.
"""

import argparse
import json
import os
import re
import shutil
import site
import subprocess
import sys
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    ".flv",
    ".wmv",
    ".ts",
    ".m4v",
    ".mpg",
    ".mpeg",
}


EXTRA_PATH_DIRS: list[str] = []


def add_path_dir(path: Path | str) -> None:
    value = str(path)
    if value and value not in EXTRA_PATH_DIRS:
        EXTRA_PATH_DIRS.append(value)


def command_candidates(name: str) -> list[Path]:
    candidates: list[Path] = []
    if sys.platform == "win32":
        suffixes = [".exe", ".bat", ".cmd", ""]
        scripts = [
            Path(sys.executable).with_name("Scripts"),
            Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts",
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts",
        ]
        for directory in scripts:
            for suffix in suffixes:
                candidates.append(directory / f"{name}{suffix}")
    return candidates


def resolve_command(name: str) -> str:
    found = shutil.which(name)
    if found:
        add_path_dir(Path(found).parent)
        return found
    for candidate in command_candidates(name):
        if candidate.is_file():
            add_path_dir(candidate.parent)
            return str(candidate)
    raise SystemExit(f"Required command not found on PATH: {name}")


def add_videocaptioner_bin_to_path() -> None:
    try:
        import videocaptioner.config as vc_config

        add_path_dir(vc_config.BIN_PATH)
        add_path_dir(vc_config.FASTER_WHISPER_PATH)
    except Exception:
        return


def run_command(cmd: list[str]) -> None:
    env = os.environ.copy()
    if EXTRA_PATH_DIRS:
        env["PATH"] = os.pathsep.join(EXTRA_PATH_DIRS + [env.get("PATH", "")])
    result = subprocess.run(cmd, text=True, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_command_status(cmd: list[str]) -> int:
    env = os.environ.copy()
    if EXTRA_PATH_DIRS:
        env["PATH"] = os.pathsep.join(EXTRA_PATH_DIRS + [env.get("PATH", "")])
    return subprocess.run(cmd, text=True, env=env).returncode


def add_nvidia_wheel_dll_dirs() -> None:
    """Make CUDA DLLs installed from nvidia-* wheels visible on Windows."""
    if sys.platform != "win32":
        return

    candidates: list[Path] = []
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        nvidia_root = Path(base) / "nvidia"
        if nvidia_root.is_dir():
            candidates.extend(path for path in nvidia_root.glob("*/bin") if path.is_dir())

    for directory in candidates:
        add_path_dir(directory)
        current_path = os.environ.get("PATH", "")
        directory_text = str(directory)
        if directory_text not in current_path.split(os.pathsep):
            os.environ["PATH"] = os.pathsep.join([directory_text, current_path])
        try:
            os.add_dll_directory(str(directory))
        except (AttributeError, FileNotFoundError, OSError):
            pass


def format_srt_time(seconds: float) -> str:
    millis = int(round(max(seconds, 0) * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_with_python_faster_whisper(
    video_path: Path,
    output_srt: Path,
    language: str,
    model_name: str,
    device: str,
) -> None:
    add_nvidia_wheel_dll_dirs()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit(
            "VideoCaptioner transcription failed, and Python fallback requires "
            "`pip install faster-whisper`."
        ) from exc

    compute_type = "float16" if device == "cuda" else "int8"
    whisper = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _info = whisper.transcribe(
        str(video_path),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    output_srt.parent.mkdir(parents=True, exist_ok=True)
    with output_srt.open("w", encoding="utf-8") as handle:
        written = 0
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            written += 1
            handle.write(f"{written}\n")
            handle.write(
                f"{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n"
            )
            handle.write(text + "\n\n")

    if written == 0:
        raise SystemExit("Python faster-whisper fallback produced no SRT segments")


def newest_video(directory: Path, before: set[Path]) -> Path:
    candidates = [
        path
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and path.resolve() not in before
    ]
    if not candidates:
        candidates = [
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
    if not candidates:
        raise SystemExit(f"No downloaded video file found in {directory}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def snapshot_videos(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {
        path.resolve()
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    }


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def is_bilibili_url(url: str) -> bool:
    """Check if URL is a Bilibili video."""
    patterns = [
        r"bilibili\.com/video/",
        r"b23\.tv/",
    ]
    return any(re.search(p, url, re.IGNORECASE) for p in patterns)


def extract_bvid(url: str) -> str | None:
    """Extract BV ID from Bilibili URL."""
    match = re.search(r"/video/(BV[0-9A-Za-z]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"(BV[0-9A-Za-z]+)", url)
    if match:
        return match.group(1)
    return None


def try_bilibili_subtitle(url: str, output_srt: Path) -> dict | None:
    """
    Try to fetch Bilibili official subtitles.
    Returns metadata dict on success, None if no subtitles available.
    """
    try:
        import requests
    except ImportError:
        print("requests not installed, skipping Bilibili subtitle check", file=sys.stderr)
        return None

    bvid = extract_bvid(url)
    if not bvid:
        return None

    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        # Fetch video info
        info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        resp = session.get(info_url, timeout=10)
        resp.raise_for_status()
        info_data = resp.json()

        if info_data.get("code") != 0:
            print(f"Bilibili API error: {info_data.get('message')}", file=sys.stderr)
            return None

        video_info = info_data["data"]
        aid = video_info.get("aid", 0)
        cid = video_info.get("cid", 0)
        title = video_info.get("title", "")

        if not cid:
            return None

        # Fetch subtitle list
        player_url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
        resp = session.get(player_url, timeout=10)
        resp.raise_for_status()
        player_data = resp.json()

        if player_data.get("code") != 0:
            print(f"Player API error: {player_data.get('message')}", file=sys.stderr)
            return None

        subtitles = player_data.get("data", {}).get("subtitle", {}).get("subtitles", [])

        if not subtitles:
            print("No official subtitles found on Bilibili", file=sys.stderr)
            return None

        # Pick best subtitle (prefer Chinese, then English)
        def subtitle_priority(sub: dict) -> int:
            lan = str(sub.get("lan", "")).lower()
            if lan in ("zh-cn", "zh-hans"):
                return 0
            if lan == "zh":
                return 1
            if "zh" in lan:
                return 2
            if lan in ("en", "en-us"):
                return 10
            return 50

        subtitles.sort(key=subtitle_priority)
        best = subtitles[0]

        # Download subtitle JSON
        subtitle_url = best.get("subtitle_url", "")
        if subtitle_url.startswith("//"):
            subtitle_url = f"https:{subtitle_url}"

        resp = session.get(subtitle_url, timeout=30)
        resp.raise_for_status()
        subtitle_data = resp.json()

        body = subtitle_data.get("body", [])
        if not body:
            print("Subtitle file is empty", file=sys.stderr)
            return None

        # Convert to SRT
        def format_srt_time(seconds: float) -> str:
            total_ms = int(max(0, seconds) * 1000)
            hours = total_ms // 3_600_000
            total_ms %= 3_600_000
            minutes = total_ms // 60_000
            total_ms %= 60_000
            secs = total_ms // 1000
            millis = total_ms % 1000
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        srt_lines = []
        for i, item in enumerate(body, 1):
            text = str(item.get("content", "")).strip()
            if not text:
                continue
            start = float(item.get("from", 0))
            end = float(item.get("to", 0))
            srt_lines.append(str(i))
            srt_lines.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
            srt_lines.append(text)
            srt_lines.append("")

        srt_content = "\n".join(srt_lines)

        # Write SRT file
        output_srt.parent.mkdir(parents=True, exist_ok=True)
        output_srt.write_text(srt_content, encoding="utf-8")

        print(f"Bilibili official subtitle extracted: {len(body)} segments", file=sys.stderr)

        return {
            "bvid": bvid,
            "aid": aid,
            "cid": cid,
            "title": title,
            "subtitle_lan": best.get("lan", ""),
            "subtitle_lan_doc": best.get("lan_doc", ""),
            "is_ai": str(best.get("lan", "")).lower().startswith("ai-"),
            "segment_count": len(body),
            "available_subtitles": [
                {"lan": s.get("lan"), "lan_doc": s.get("lan_doc")}
                for s in subtitles
            ],
        }

    except Exception as e:
        print(f"Bilibili subtitle fetch failed: {e}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download/transcribe video with VideoCaptioner and emit JSON paths."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Online video URL supported by VideoCaptioner/yt-dlp.")
    source.add_argument("--video", help="Local video path.")
    parser.add_argument("--work-dir", required=True, help="Working directory for video/SRT outputs.")
    parser.add_argument("--output-srt", help="Explicit SRT output path.")
    parser.add_argument("--language", default="zh", help="Source language code. Default: zh.")
    parser.add_argument("--model", default="medium", help="Faster Whisper model. Default: medium.")
    parser.add_argument("--device", default="cpu", help="Faster Whisper device. Default: cpu.")
    parser.add_argument("--videocaptioner", default="videocaptioner", help="VideoCaptioner command.")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    add_videocaptioner_bin_to_path()
    videocaptioner_cmd = (
        str(Path(args.videocaptioner))
        if Path(args.videocaptioner).is_file()
        else resolve_command(args.videocaptioner)
    )
    video_path: Path
    original_url = args.url or ""

    if args.url:
        # Try Bilibili official subtitle first (no download needed for subtitle)
        bilibili_result = None
        if is_bilibili_url(args.url):
            print("Detected Bilibili URL, trying official subtitle...", file=sys.stderr)
            # Define output_srt early for Bilibili subtitle
            bvid = extract_bvid(args.url) or "video"
            bilibili_srt_path = work_dir / f"{bvid}.srt"
            bilibili_result = try_bilibili_subtitle(args.url, bilibili_srt_path)

        if bilibili_result:
            # Official subtitle obtained, no need for ASR
            # Still download video for local reference (optional)
            try:
                resolve_command("yt-dlp")
                before = snapshot_videos(work_dir)
                run_command([videocaptioner_cmd, "download", args.url, "-o", str(work_dir)])
                video_path = newest_video(work_dir, before)
            except Exception as e:
                print(f"Video download skipped (subtitle already obtained): {e}", file=sys.stderr)
                video_path = work_dir / f"{bilibili_result.get('bvid', 'video')}.mp4"

            result = {
                "video_path": str(video_path.resolve()) if video_path.exists() else "",
                "srt_path": str(bilibili_srt_path.resolve()),
                "video_link_url": file_uri(video_path) if video_path.exists() else "",
                "original_url": original_url,
                "work_dir": str(work_dir.resolve()),
                "subtitle_source": "bilibili_official",
                "bilibili": bilibili_result,
            }
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        # Fallback to download + ASR
        resolve_command("yt-dlp")
        before = snapshot_videos(work_dir)
        run_command([videocaptioner_cmd, "download", args.url, "-o", str(work_dir)])
        video_path = newest_video(work_dir, before)
    else:
        video_path = Path(args.video)
        if not video_path.is_file():
            raise SystemExit(f"Video file not found: {video_path}")

    output_srt = (
        Path(args.output_srt)
        if args.output_srt
        else work_dir / f"{video_path.stem}.srt"
    )
    if output_srt.resolve() == video_path.resolve():
        raise SystemExit("Refusing to overwrite the source video with subtitle output")
    output_srt.parent.mkdir(parents=True, exist_ok=True)

    transcribe_cmd = [
        videocaptioner_cmd,
        "transcribe",
        str(video_path),
        "--asr",
        "faster-whisper",
        "--fw-model",
        args.model,
        "--fw-device",
        args.device,
        "--language",
        args.language,
        "--format",
        "srt",
        "-o",
        str(output_srt),
    ]
    if run_command_status(transcribe_cmd) != 0:
        print(
            "VideoCaptioner transcription failed; falling back to Python "
            "faster-whisper.",
            file=sys.stderr,
        )
        transcribe_with_python_faster_whisper(
            video_path,
            output_srt,
            args.language,
            args.model,
            args.device,
        )

    result = {
        "video_path": str(video_path.resolve()),
        "srt_path": str(output_srt.resolve()),
        "video_link_url": file_uri(video_path),
        "original_url": original_url,
        "work_dir": str(work_dir.resolve()),
        "subtitle_source": "local_asr",
        "asr": {
            "engine": "faster-whisper",
            "model": args.model,
            "device": args.device,
            "language": args.language,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
