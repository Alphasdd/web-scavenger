#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

TIME_RE = re.compile(
    r'(?P<start>\d{2}:\d{2}:\d{2})(?P<ms>,\d{3})?\s*-->\s*'
    r'(?P<end>\d{2}:\d{2}:\d{2})(?P<endms>,\d{3})?'
)

HTML_TAG_RE = re.compile(r'<[^>]+>')
ASS_TAG_RE = re.compile(r'\{\\.*?\}')

# 默认句末标点：句号、问号、感叹号、省略号、英文句点
SENT_END_RE = re.compile(r'[。！？!?…\.](?:["”’\')\]]*)$')

# 如果开启 --comma-as-end，则逗号、分号、冒号也算断句
SENT_END_WITH_COMMA_RE = re.compile(r'[，,；;：:。！？!?…\.](?:["”’\')\]]*)$')


def normalize_newlines(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n')


def clean_text(text: str, remove_all_spaces: bool = False) -> str:
    text = text.replace('\ufeff', '')
    text = HTML_TAG_RE.sub('', text)
    text = ASS_TAG_RE.sub('', text)

    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    text = ' '.join(line for line in lines if line)
    text = re.sub(r'\s+', ' ', text).strip()

    # 注意：这里已经去掉了默认中文压缩
    # 也就是说不会再自动把 “你 好” 改成 “你好”

    if remove_all_spaces:
        text = re.sub(r'\s+', '', text)

    return text.strip()


def parse_srt(content: str, keep_ms: bool = False, remove_all_spaces: bool = False):
    content = normalize_newlines(content).strip()
    if not content:
        return []

    blocks = re.split(r'\n\s*\n+', content)
    entries = []

    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue

        time_index = None
        match = None

        for i, line in enumerate(lines):
            match = TIME_RE.search(line)
            if match:
                time_index = i
                break

        if time_index is None or match is None:
            continue

        start_time = match.group('start')
        if keep_ms and match.group('ms'):
            start_time += match.group('ms')

        subtitle_text = clean_text(
            '\n'.join(lines[time_index + 1:]),
            remove_all_spaces
        )

        if subtitle_text:
            entries.append((start_time, subtitle_text))

    return entries


def merge_by_sentence(
    entries,
    remove_all_spaces: bool = False,
    max_merge_len: int = 120,
    comma_as_end: bool = False
):
    """
    合并字幕，但避免无限合成一大段。

    断开条件：
    1. 当前文本以句末标点结尾
    2. 当前文本长度达到 max_merge_len
    3. 如果开启 comma_as_end，则逗号、分号、冒号也算句末
    """
    if not entries:
        return []

    end_re = SENT_END_WITH_COMMA_RE if comma_as_end else SENT_END_RE

    merged = []
    cur_start, cur_text = entries[0]

    for start, text in entries[1:]:
        # 当前文本已经是完整句子，或者已经太长，就先收尾
        if end_re.search(cur_text) or len(cur_text) >= max_merge_len:
            merged.append((cur_start, cur_text))
            cur_start, cur_text = start, text
        else:
            sep = '' if remove_all_spaces else ' '
            cur_text = (cur_text + sep + text).strip()

    merged.append((cur_start, cur_text))
    return merged


def format_entries(entries, delimiter='|'):
    return '\n'.join(f'{start}{delimiter}{text}' for start, text in entries)


def main():
    parser = argparse.ArgumentParser(
        description='Convert .srt subtitles to a compact AI-friendly format.'
    )

    parser.add_argument(
        'input',
        nargs='?',
        help='Input .srt file. Omit to read from stdin.'
    )

    parser.add_argument(
        '-o',
        '--output',
        help='Output file. Omit to write to stdout.'
    )

    parser.add_argument(
        '-d',
        '--delimiter',
        default='|',
        help='Delimiter between time and text. Default: |'
    )

    parser.add_argument(
        '--keep-ms',
        action='store_true',
        help='Keep milliseconds in the start time.'
    )

    parser.add_argument(
        '--remove-all-spaces',
        action='store_true',
        help='Remove all whitespace in subtitle text. Good for Chinese, not recommended for English.'
    )

    parser.add_argument(
        '--merge-sentences',
        action='store_true',
        help='Merge consecutive subtitle blocks until sentence-ending punctuation appears.'
    )

    parser.add_argument(
        '--max-merge-len',
        type=int,
        default=100,
        help='Maximum text length when merging subtitles. Default: 100.'
    )

    parser.add_argument(
        '--comma-as-end',
        action='store_true',
        help='Treat comma, semicolon and colon as sentence endings when merging.'
    )

    args = parser.parse_args()

    if args.input:
        content = Path(args.input).read_text(encoding='utf-8-sig')
    else:
        content = sys.stdin.read()

    entries = parse_srt(
        content,
        keep_ms=args.keep_ms,
        remove_all_spaces=args.remove_all_spaces
    )

    if not entries:
        raise SystemExit('No valid SRT entries found')

    if args.merge_sentences:
        entries = merge_by_sentence(
            entries,
            remove_all_spaces=args.remove_all_spaces,
            max_merge_len=args.max_merge_len,
            comma_as_end=args.comma_as_end
        )

    result = format_entries(entries, delimiter=args.delimiter)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result, encoding='utf-8')
    else:
        sys.stdout.write(result)


if __name__ == '__main__':
    main()
