#!/usr/bin/env python3
"""Recheck selected contextual ASR windows with one local model; never replace originals."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('media',type=Path)
    ap.add_argument('--queue',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--window',action='append',required=True,help='Explicit W001 etc.; repeat to select more')
    ap.add_argument('--model',default='medium')
    ap.add_argument('--download-root',type=Path,required=True)
    ap.add_argument('--language',required=True)
    ap.add_argument('--max-audio-seconds',type=float,default=180)
    ap.add_argument('--allow-download',action='store_true')
    args=ap.parse_args()
    if args.output.exists():ap.error('复核输出已存在，请另取文件名')
    q=json.loads(args.queue.read_text())
    source=Path(q['source_file'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=q['source_sha256']:ap.error('原始转写已变化，重新生成队列')
    windows=[w for w in q['windows'] if w['id'] in set(args.window)]
    if len(windows)!=len(set(args.window)):ap.error('复核区间不存在')
    if any(w.get('requires_manual_scope') for w in windows):ap.error('存在超过 60 秒的候选，先明确更小复核范围')
    if sum(w['end']-w['start'] for w in windows)>args.max_audio_seconds:ap.error('超出本轮音频复核预算')
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    audio=decode_audio(str(args.media),sampling_rate=16000)
    model=WhisperModel(args.model,device='cpu',compute_type='int8',cpu_threads=8,
                       download_root=str(args.download_root),local_files_only=not args.allow_download)
    raw=json.loads(source.read_text());raw=raw['segments'] if isinstance(raw,dict) else raw
    results=[];started=time.perf_counter()
    for window in windows:
        a,b=window['start'],window['end']
        sample=audio[round(a*16000):round(b*16000)]
        if not len(sample):raise ValueError('空复核片段')
        it,info=model.transcribe(sample,language=args.language,beam_size=5,vad_filter=True,word_timestamps=True)
        segments=[]
        for segment in it:
            row=asdict(segment);row['start']+=a;row['end']+=a
            for word in row.get('words') or []:word['start']+=a;word['end']+=a
            segments.append(row)
        original=[r for r in raw if r['end']>a and r['start']<b]
        results.append(dict(window=window,original_context=original,second_model_segments=segments,
                            status='pending_adjudication',note='上下文边缘文字可能被截断；不能将整窗差异都判作错误。'))
        print(f"{window['id']}: {len(segments)} segments",flush=True)
    result=dict(schema_version=1,source_sha256=q['source_sha256'],model=args.model,language=args.language,
                media_file=args.media.name,transcribe_seconds=time.perf_counter()-started,
                automatic_replacement=False,windows=results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
