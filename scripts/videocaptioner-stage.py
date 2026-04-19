#!/usr/bin/env python3
"""Prepare a video and SRT for the video-note-summary skill.

This script intentionally stops at mechanical work:
- optional online video download through VideoCaptioner
- local transcription through VideoCaptioner with Faster Whisper medium on CPU
- JSON output describing the produced files

The AI summary is done by Claude from compressed subtitle chunks, not
inside this script.
"""

import argparse
import json
import os
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
