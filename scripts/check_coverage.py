#!/usr/bin/env python3
"""Validate authored content-to-paragraph evidence; do not certify semantic or audio accuracy."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def paragraphs(markdown):
    result=[]
    heading=None
    for match in re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*',markdown):
        text=match.group().strip()
        if text.startswith('#'):
            heading=text.lstrip('# ').strip();continue
        if (text.startswith(('![','*原视频','\\[')) or
            re.fullmatch(r'\d{2}(?::\d{2}){1,2}[—–-]\d{2}(?::\d{2}){1,2}',text)):
            continue
        result.append(dict(text=text,line=markdown.count('\n',0,match.start())+1,heading=heading))
    return result


def validate(source, markdown, ledger, root):
    errors=[];pending=[];locations=[]
    src=json.loads(source.read_text());rows=src['segments'] if isinstance(src,dict) else src
    ids=[r.get('id',i) for i,r in enumerate(rows,1)]
    if len(ids)!=len(set(ids)):errors.append('源字幕编号重复')
    if ledger.get('source_sha256')!=hashlib.sha256(source.read_bytes()).hexdigest():
        errors.append('源字幕指纹变化，不能沿用旧核对结论')
    md=markdown.read_text();paras=paragraphs(md);seen=set();excluded=set();unit_ids=[]
    def evidence(items, uid):
        if not items:errors.append(f'{uid} 缺少正文证据');return
        for item in items:
            quote=item.get('quote','')
            hits=[p for p in paras if quote and quote in p['text']]
            if not hits:errors.append(f'{uid} 正文引文不存在或只指向标题/时间/图注')
            else:
                for p in hits:locations.append(dict(unit_id=uid,markdown_line=p['line'],heading=p['heading'],quote=quote))
    for unit in ledger.get('content_units',[]):
        uid=unit.get('id');unit_ids.append(uid)
        sids=unit.get('source_ids',[])
        if not unit.get('point','').strip() or not sids:errors.append(f'{uid} 缺少具体讲解点或源编号')
        unknown=set(sids)-set(ids)
        if unknown:errors.append(f'{uid} 引用未知字幕 {sorted(unknown)}')
        seen.update(sids);evidence(unit.get('note_evidence'),uid)
        status=unit.get('review_status')
        if status not in ('text_checked','audio_checked','pending'):errors.append(f'{uid} 核对状态无效')
        if status=='audio_checked' and not unit.get('audio_review_note'):errors.append(f'{uid} 缺少听音依据记录')
        if status=='pending':pending.append(uid)
    for item in ledger.get('exclusions',[]):
        sids=item.get('source_ids',[])
        if not sids or not item.get('reason'):errors.append('排除项必须有编号和理由')
        excluded.update(sids)
        if item.get('status')!='confirmed_exclusion':pending.append('exclusion:'+str(sids))
    if seen&excluded:errors.append(f'同一字幕既覆盖又排除 {sorted(seen&excluded)}')
    if excluded-set(ids):errors.append('排除项引用未知字幕')
    missing=set(ids)-seen-excluded
    if missing:errors.append(f'未落实到讲解点的字幕 {sorted(missing)}')
    if len(unit_ids)!=len(set(unit_ids)):errors.append('讲解点编号重复')
    actual_images=set(re.findall(r'!\[[^\]]*\]\(([^)]+)\)',md));reviewed_images=set()
    for unit in ledger.get('visual_units',[]):
        uid=unit.get('id');image=unit.get('image','');reviewed_images.add(image)
        if image not in actual_images:errors.append(f'{uid} 引用了正文未使用的截图')
        file=(root/image).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():errors.append(f'{uid} 图片不存在或越出项目')
        if not unit.get('point'):errors.append(f'{uid} 未说明画面信息')
        evidence(unit.get('note_evidence'),uid)
        if unit.get('review_status') not in ('detail_checked','preview_checked','pending'):errors.append(f'{uid} 画面核对状态无效')
        if unit.get('review_status')!='detail_checked':pending.append(uid)
    if actual_images-reviewed_images:errors.append('缺少画面检查记录：'+','.join(sorted(actual_images-reviewed_images)))
    return dict(structural_pass=not errors,errors=errors,pending_items=pending,
                source_segments=len(ids),referenced_segments=len(seen),excluded_segments=len(excluded),
                content_units=len(unit_ids),visual_units=len(ledger.get('visual_units',[])),
                resolved_evidence=locations,semantic_accuracy_certified=False,
                audio_accuracy_certified=False,
                note='结构通过只说明编号、正文引文和图片有效；语义与原音仍需 Agent/人工核对，pending 不自动通过。')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--markdown',type=Path,required=True)
    ap.add_argument('--ledger',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--require-reviewed',action='store_true')
    ap.add_argument('--overwrite',action='store_true')
    args=ap.parse_args()
    if args.output.resolve() in [p.resolve() for p in [args.source,args.markdown,args.ledger]]:ap.error('输出不得覆盖输入')
    if args.output.exists() and not args.overwrite:ap.error('输出已存在')
    report=validate(args.source,args.markdown,json.loads(args.ledger.read_text()),args.markdown.parent)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='resolved_evidence'},ensure_ascii=False))
    if report['errors'] or (args.require_reviewed and report['pending_items']):raise SystemExit(1)


if __name__=='__main__':main()
