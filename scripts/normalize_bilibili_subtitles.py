#!/usr/bin/env python3
"""Normalize a downloaded Bilibili subtitle JSON; no network or credentials."""
import argparse
import json
import math
from pathlib import Path


def clock(seconds, srt=False):
    total = round(seconds * 1000)
    s, ms = divmod(total, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f'{h:02}:{m:02}:{s:02}' + (f',{ms:03}' if srt else '')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--overwrite', action='store_true')
    args = ap.parse_args()
    original = json.loads(args.input.read_text(encoding='utf-8'))
    body = original.get('body')
    if not isinstance(body, list) or not body:
        raise ValueError('字幕 body 必须是非空列表；弹幕或空响应不能作为字幕。')
    segments = []
    previous = -1
    for i, row in enumerate(body, 1):
        start, end, text = row['from'], row['to'], row['content']
        if (not all(isinstance(t, (int, float)) and not isinstance(t, bool)
                    and math.isfinite(t) for t in (start, end))
                or start < 0 or end <= start or start < previous
                or not isinstance(text, str) or not text.strip()):
            raise ValueError(f'字幕 {i} 的时间或文字无效。')
        previous = start
        segments.append(dict(id=i, start=start, end=end, text=text))
    outputs = {
        '字幕-规范.json': json.dumps({'segments': segments}, ensure_ascii=False, indent=2) + '\n',
        '字幕-中文.srt': '\n\n'.join(
            f"{r['id']}\n{clock(r['start'], True)} --> {clock(r['end'], True)}\n{r['text']}"
            for r in segments) + '\n',
        '字幕-中文.txt': '\n'.join(r['text'] for r in segments) + '\n',
        '字幕-中文-带时间.txt': '\n'.join(
            f"[{clock(r['start'])}] {r['text']}" for r in segments) + '\n',
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = [args.output_dir / name for name in outputs]
    if args.input.resolve() in [f.resolve() for f in targets]:
        raise ValueError('输出路径不得覆盖原始输入字幕。')
    if not args.overwrite and any(f.exists() for f in targets):
        raise FileExistsError('输出已存在；确认需要更新后使用 --overwrite。')
    for name, content in outputs.items():
        (args.output_dir / name).write_text(content, encoding='utf-8')
    print(f"已转换 {len(segments)} 段字幕，{clock(segments[0]['start'])}—{clock(segments[-1]['end'])}。")


if __name__ == '__main__':
    main()
