#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sys
from pathlib import Path

# 只匹配：
# @MM:SS@
# @HH:MM:SS@
# 例如：
# @00:25@
# @01:02:03@
TIME_TAG_PATTERN = re.compile(r'@((?:\d+:)?[0-5]\d:[0-5]\d)@')


def parse_seconds(time_text: str) -> int:
    parts = [int(part) for part in time_text.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def normalize_hms(time_text: str) -> str:
    parts = time_text.split(":")
    if len(parts) == 2:
        return f"00:{parts[0]}:{parts[1]}"
    return time_text


def replace_time_tags(
    content: str,
    video_url: str,
    link_format: str = "{url}#t={hms}{suffix}",
    suffix: str = "",
) -> str:
    def repl(match):
        time_text = match.group(1)
        hms = normalize_hms(time_text)
        url = link_format.format(
            url=video_url,
            raw=time_text,
            hms=hms,
            seconds=parse_seconds(time_text),
            suffix=suffix,
        )
        return f'[{hms}]({url})'

    return TIME_TAG_PATTERN.sub(repl, content)


def main():
    parser = argparse.ArgumentParser(
        description="将 Markdown 中的 @00:25@ / @01:02:03@ 替换为视频时间链接"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="视频链接，例如 file:///Z:/Jellyfin/xxx.mp4"
    )
    parser.add_argument(
        "--suffix",
        default="",
        help='可选时间后缀，例如 ".62"；默认空字符串'
    )
    parser.add_argument(
        "--link-format",
        default="{url}#t={hms}{suffix}",
        help=(
            "链接格式模板。可用占位符：{url}, {raw}, {hms}, {seconds}, {suffix}。"
            "默认：{url}#t={hms}{suffix}"
        )
    )
    parser.add_argument(
        "--file",
        help="直接修改这个 Markdown 文件"
    )
    parser.add_argument(
        "--text",
        help="直接处理这段文本，并输出到 stdout"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="修改文件前生成 .bak 备份（仅 --file 模式有效）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出处理结果，不写回文件（仅 --file 模式有效）"
    )

    args = parser.parse_args()

    # 模式1：直接修改文件
    if args.file:
        path = Path(args.file)
        content = path.read_text(encoding="utf-8")
        new_content = replace_time_tags(
            content,
            args.url,
            link_format=args.link_format,
            suffix=args.suffix,
        )

        if args.dry_run:
            sys.stdout.write(new_content)
            return
        if args.backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            backup_path.write_text(content, encoding="utf-8")

        path.write_text(new_content, encoding="utf-8")
        print(f"已修改文件：{path}")
        return

    # 模式2：直接处理命令行传入的文本
    if args.text is not None:
        result = replace_time_tags(
            args.text,
            args.url,
            link_format=args.link_format,
            suffix=args.suffix,
        )
        sys.stdout.write(result)
        return

    # 模式3：从 stdin 读取，输出到 stdout
    content = sys.stdin.read()
    result = replace_time_tags(
        content,
        args.url,
        link_format=args.link_format,
        suffix=args.suffix,
    )
    sys.stdout.write(result)


if __name__ == "__main__":
    main()
