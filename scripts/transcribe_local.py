#!/usr/bin/env python3
"""Transcribe local media with faster-whisper; preserve raw output and provenance."""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
import math
from pathlib import Path
import resource
import time


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
    ap.add_argument('--model', default='large-v3-turbo')
    ap.add_argument('--download-root', type=Path)
    ap.add_argument('--device', default='cpu', choices=['cpu', 'cuda', 'auto'])
    ap.add_argument('--compute-type', default='int8')
    ap.add_argument('--threads', type=int, default=8)
    ap.add_argument('--language', default='auto')
    ap.add_argument('--prompt', default=None)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--word-timestamps', action='store_true')
    ap.add_argument('--overwrite', action='store_true')
    args = ap.parse_args()
    if not args.input.is_file():
        ap.error('输入媒体不存在')
    names = ['字幕-ASR原始.json', '字幕-规范.json', '字幕-ASR.srt',
             '字幕-ASR.txt', '字幕-ASR-带时间.txt', '转写来源.json']
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.input.resolve() in [(args.output_dir / n).resolve() for n in names]:
        ap.error('输出不得覆盖输入媒体')
    if not args.overwrite and any((args.output_dir / n).exists() for n in names):
        ap.error('已有同名输出；请使用新目录，或明确指定 --overwrite')
    from faster_whisper import WhisperModel
    import av
    with av.open(str(args.input)) as container:
        if not container.streams.audio:
            ap.error('媒体中没有音轨')
        duration = float(container.duration / av.time_base) if container.duration else None
    loaded = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type,
                         cpu_threads=args.threads, download_root=str(args.download_root) if args.download_root else None,
                         local_files_only=args.offline)
    load_seconds = time.perf_counter() - loaded
    start = time.perf_counter()
    iterator, info = model.transcribe(str(args.input), language=None if args.language == 'auto' else args.language,
                                     task='transcribe', beam_size=5, vad_filter=True,
                                     initial_prompt=args.prompt, word_timestamps=args.word_timestamps)
    raw = []
    issues = []
    last_end = 0
    for segment in iterator:
        row = asdict(segment)
        if not (math.isfinite(row['start']) and math.isfinite(row['end']) and 0 <= row['start'] < row['end']):
            raise ValueError('模型返回无效时间戳；不生成规范字幕')
        if row['start'] < last_end - 0.01:
            issues.append({'segment': len(raw)+1, 'kind': 'overlap'})
        if duration and row['end'] > duration + 0.1:
            issues.append({'segment': len(raw)+1, 'kind': 'beyond_media_end'})
        last_end = row['end']
        raw.append(row)
        print(f"[{clock(row['start'])}—{clock(row['end'])}] {row['text'].strip()}", flush=True)
    elapsed = time.perf_counter() - start
    if not raw:
        raise ValueError('没有识别到文字；不要把空结果当作可用字幕')
    segments = [dict(id=i, start=s['start'], end=s['end'], text=s['text'].strip()) for i,s in enumerate(raw,1)]
    provenance = dict(source_type='local_asr', engine='faster-whisper', model=args.model,
                      media_file=args.input.name, media_duration_seconds=duration,
                      device=args.device, compute_type=args.compute_type, cpu_threads=args.threads,
                      language=info.language, language_probability=info.language_probability,
                      language_requested=args.language, task='transcribe', initial_prompt=args.prompt,
                      beam_size=5, vad_filter=True, word_timestamps=args.word_timestamps,
                      offline=args.offline, model_load_seconds=load_seconds,
                      transcribe_seconds=elapsed, process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                      timing_issues=issues, human_audio_review_completed=False,
                      package_versions={p:importlib.metadata.version(p) for p in ['faster-whisper','ctranslate2','av']})
    outputs = {
        names[0]: json.dumps({'source_type':'local_asr','language':info.language,'segments':raw},ensure_ascii=False,indent=2),
        names[1]: json.dumps({'source_type':'local_asr','segments':segments},ensure_ascii=False,indent=2),
        names[2]: '\n\n'.join(f"{s['id']}\n{clock(s['start'],True)} --> {clock(s['end'],True)}\n{s['text']}" for s in segments),
        names[3]: '\n'.join(s['text'] for s in segments),
        names[4]: '\n'.join(f"[{clock(s['start'])}—{clock(s['end'])}] {s['text']}" for s in segments),
        names[5]: json.dumps(provenance,ensure_ascii=False,indent=2)
    }
    for name, content in outputs.items():
        (args.output_dir/name).write_text(content+'\n',encoding='utf-8')
    print(f'Completed: {len(raw)} segments, {elapsed:.1f}s, language={info.language}',flush=True)


if __name__ == '__main__':
    main()
