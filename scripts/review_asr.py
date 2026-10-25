#!/usr/bin/env python3
"""Locate ASR review candidates without correcting or approving the transcript."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan(rows, duration=None, terms=(), padding=8, logprob=-0.8, wordprob=0.45, gap=4):
    issues = []
    critical = []
    previous = None
    def flag(ids, start, end, kind, detail, priority='normal'):
        issues.append(dict(id=f'R{len(issues)+1:03}', segment_ids=ids,
                           start=start, end=end, kind=kind, detail=detail,
                           priority=priority, status='pending'))
    for index, row in enumerate(rows, 1):
        sid = row.get('id', index)
        start, end = row['start'], row['end']
        text = row['text'].strip()
        if not (all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start,end)) and 0 <= start < end):
            raise ValueError(f'无效时间戳：{sid}')
        if previous and start < previous['start']:
            raise ValueError('输入分段必须按开始时间排序')
        if duration is not None and end > duration+0.1:
            flag([sid],start,end,'out_of_bounds','结束时间超出媒体范围','high')
        if end-start < 0.3 and text:
            flag([sid],start,end,'very_short_text','小于 0.3 秒的非空文字，可能是残片或对齐问题','high')
        if end-start > 20:
            flag([sid],start,end,'long_segment','超过 20 秒；检查长段覆盖与断句')
        if row.get('avg_logprob', 0) < logprob:
            flag([sid],start,end,'low_logprob',f"avg_logprob={row['avg_logprob']:.3f}",'high')
        if row.get('no_speech_prob', 0) > 0.6:
            flag([sid],start,end,'no_speech_candidate',f"no_speech_prob={row['no_speech_prob']:.3f}；不能仅据此删句")
        low = [w for w in (row.get('words') or []) if w.get('probability',1) < wordprob]
        if low:
            flag([sid],start,end,'low_word_probability',
                 '; '.join(f"{w['word'].strip()}={w['probability']:.3f}" for w in low))
        for term in terms:
            for variant in term.get('variants',[]):
                pattern = re.escape(variant)
                if variant.isascii() and variant[0].isalnum() and variant[-1].isalnum():
                    pattern = r'(?<!\w)'+pattern+r'(?!\w)'
                if re.search(pattern,text,re.I):
                    flag([sid],start,end,'term_variant',f"发现候选写法 {variant}；核对是否为 {term['canonical']}",'high')
        tokens = re.findall(r'\b\d+(?:\.\d+)?\b|\b(?:not|no|never|without|only|except)\b|不能|不再|没有|仅|只有',text,re.I)
        if tokens:
            critical.append(dict(segment_id=sid,start=start,end=end,tokens=tokens,text=text))
        if previous:
            prev_id = previous.get('id', index-1)
            if start < previous['end']-0.02:
                flag([prev_id,sid],start,previous['end'],'overlap','分段时间重叠')
            if start-previous['end'] > gap:
                flag([prev_id,sid],previous['end'],start,'gap_candidate','分段间空隙；可能是真实停顿，不代表漏句')
            normalized = lambda s: re.sub(r'\W+','',s.lower())
            if len(normalized(text)) >= 12 and normalized(text)==normalized(previous['text']):
                flag([prev_id,sid],previous['start'],end,'repeated_text','相邻段文字相同；检查是否原片重复')
        previous = {**row,'id':sid}
    windows = []
    for issue in sorted(issues,key=lambda x:x['start']):
        start = max(0,issue['start']-padding)
        end = issue['end']+padding
        if duration is not None:
            end = min(end,duration)
        if end <= start:
            continue
        if windows and start <= windows[-1]['end']+1 and end-windows[-1]['start'] <= 60:
            windows[-1]['end']=max(windows[-1]['end'],end)
            windows[-1]['issue_ids'].append(issue['id'])
        else:
            windows.append(dict(id=f'W{len(windows)+1:03}',start=start,end=end,issue_ids=[issue['id']]))
    for window in windows:
        window['segment_ids']=[r.get('id',i) for i,r in enumerate(rows,1)
                               if r['end']>window['start'] and r['start']<window['end']]
        window['requires_manual_scope']=window['end']-window['start']>60
    return dict(issues=issues,windows=windows,critical_tokens=critical,
                metrics_available=any('avg_logprob' in r for r in rows),
                word_metrics_available=any(r.get('words') for r in rows))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--duration',type=float)
    ap.add_argument('--terms',type=Path)
    ap.add_argument('--padding',type=float,default=8)
    ap.add_argument('--overwrite',action='store_true')
    args=ap.parse_args()
    if args.padding<0 or (args.duration is not None and args.duration<=0):ap.error('时长必须为正，前后文不能为负')
    obj=json.loads(args.input.read_text());rows=obj.get('segments',[]) if isinstance(obj,dict) else obj
    if not rows:ap.error('分段不能为空')
    terms=json.loads(args.terms.read_text()) if args.terms else []
    report=scan(rows,args.duration,terms,args.padding)
    report.update(schema_version=1,source_sha256=fingerprint(args.input),source_file=str(args.input.resolve()),
                  duration=args.duration,threshold_note='阈值仅用于定位候选，不是准确率；未命中不等于无错。',
                  automatic_corrections=False,semantic_approval=False)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    targets=[args.output_dir/'复核候选.json',args.output_dir/'待核对清单.md']
    if not args.overwrite and any(p.exists() for p in targets):ap.error('输出已存在')
    if args.input.resolve() in [p.resolve() for p in targets]:ap.error('不得覆盖输入')
    targets[0].write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# 待核对清单','','这里只列候选，不自动纠错或确认内容正确。数字和否定词另见 JSON 的 critical_tokens。',
           '',f"候选 {len(report['issues'])} 项，合并为 {len(report['windows'])} 个含前后文的复核区间。",'']
    for w in report['windows']:
        lines.extend([f"## {w['id']}：{w['start']:.2f}–{w['end']:.2f} 秒",''])
        for item in report['issues']:
            if item['id'] in w['issue_ids']:
                lines.append(f"- {item['id']}，字幕 {item['segment_ids']}：{item['detail']}（待核对）。")
        lines.append('')
    if not report['metrics_available']:lines.append('输入缺少置信相关字段，本轮没有执行相应检查。')
    targets[1].write_text('\n'.join(lines)+'\n')
    print(f"{len(report['issues'])} candidates; {len(report['windows'])} contextual windows; no transcript changed")


if __name__=='__main__':main()
