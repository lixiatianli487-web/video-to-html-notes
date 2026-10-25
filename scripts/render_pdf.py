#!/usr/bin/env python3
"""Export lecture Markdown (or explicitly supplied offline HTML) to a self-contained PDF."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
import tempfile
from urllib.parse import urljoin, urlsplit, unquote


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__();self.images=[];self.headings=0;self.scripts=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='img':self.images.append(attrs.get('src',''))
        if tag in ('h1','h2','h3'):self.headings+=1
        if tag=='script':self.scripts+=1


def prepare(document, root, css):
    inventory=Inventory();inventory.feed(document)
    base=root.resolve().as_uri()+'/'
    for src in inventory.images:
        url=urlsplit(urljoin(base,src))
        if url.scheme=='data':continue
        path=Path(unquote(url.path)).resolve()
        if (url.scheme!='file' or url.netloc not in ('','localhost') or
            not path.is_relative_to(root.resolve()) or not path.is_file()):
            raise ValueError('图片缺失、远程图片或超出讲义目录：'+src)
    if 'katex-error' in document:raise ValueError('HTML 包含公式排版错误')
    # Only join adjacent captions; preserve all prose, formula and image ordering.
    document,count=re.subn(r'</figure>\s*<p class="image-caption">(.*?)</p>',
                           r'<figcaption>\1</figcaption></figure>',document,flags=re.S)
    if re.search(r'<p class="image-caption">',document):
        raise ValueError('有无法关联到前一张图片的图注，请先核对 HTML')
    if '</head>' not in document:raise ValueError('输入 HTML 缺少 head')
    # Author rules appended after screen CSS actually override it in print media.
    document=document.replace('</head>','<style media="print">'+css+'</style></head>',1)
    return document,inventory,count


def layout_report(doc):
    pages=[];images=0;overflow=[];body_fonts=set()
    for index,page in enumerate(doc.pages,1):
        box=page._page_box
        top=box.margin_top;bottom=page.height-box.margin_bottom
        content_bottom=top;fonts=[];placed=[]
        for child in box.descendants():
            name=type(child).__name__
            if child.element_tag=='body':body_fonts.add(round(float(child.style['font_size'])*.75,2))
            if name=='TextBox' and getattr(child,'text','').strip():
                # Margin boxes (page numbers) sit below the content boundary.
                if top-1<=child.position_y<bottom:
                    content_bottom=max(content_bottom,child.position_y+child.height)
                    fonts.append(round(float(child.style['font_size'])*.75,2))
            if child.element_tag=='img' and name.endswith('ReplacedBox'):
                images+=1;placed.append(dict(top=round(child.position_y,2),bottom=round(child.position_y+child.height,2)))
                content_bottom=max(content_bottom,child.position_y+child.height)
                if child.position_y<top-1 or child.position_y+child.height>bottom+1:
                    overflow.append(dict(page=index,kind='image_outside_print_area'))
            if name=='TextBox' and top-1<=child.position_y<bottom:
                if child.position_x<box.margin_left-2 or child.position_x+child.width>page.width-box.margin_right+2:
                    overflow.append(dict(page=index,kind='text_outside_print_area',text=child.text[:80]))
        pages.append(dict(page=index,fill_fraction=round((content_bottom-top)/(bottom-top),3),
                          text_font_sizes_pt=sorted(set(fonts)),images=placed))
    return dict(pages=pages,placed_images=images,actual_body_font_sizes_pt=sorted(body_fonts),overflow_candidates=overflow,
                sparse_pages=[p['page'] for p in pages if p['fill_fraction']<.5])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--node',default='node')
    ap.add_argument('--font-size',type=float,default=11)
    ap.add_argument('--overwrite',action='store_true')
    args=ap.parse_args()
    source=args.input.resolve();output=(args.output or source.with_suffix('.pdf')).resolve()
    report_path=output.with_suffix('.检查.json')
    if source.suffix.lower() not in ('.md','.html'):ap.error('输入须为讲义 Markdown 或离线 HTML')
    if not source.is_file():ap.error('输入不存在')
    if output.suffix.lower()!='.pdf' or output==source:ap.error('输出须为独立 PDF 文件')
    if not 8<=args.font_size<=18:ap.error('字号须在 8–18 磅之间')
    if not args.overwrite and (output.exists() or report_path.exists()):ap.error('输出已存在；更新请加 --overwrite')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if source.suffix.lower()=='.md':
        from render_html import render_document
        document,_=render_document(source,args.node)
    else:document=source.read_text(encoding='utf-8')
    css=(Path(__file__).resolve().parent.parent/'assets/lecture-print.css').read_text()
    css+='\n@media print {body {font-size:'+str(args.font_size)+'pt;}}'
    document,inventory,captions=prepare(document,source.parent,css)
    from weasyprint import HTML, __version__
    from weasyprint.urls import URLFetcher
    class OfflineFetcher(URLFetcher):
        def fetch(self,url,headers=None):
            parsed=urlsplit(url)
            if parsed.scheme=='file':
                path=Path(unquote(parsed.path)).resolve()
                if parsed.netloc not in ('','localhost') or not path.is_relative_to(source.parent):
                    raise ValueError('资源超出讲义目录')
            return super().fetch(url,headers)
    errors=[]
    class Errors(logging.Handler):
        def emit(self,record):
            if record.levelno>=logging.ERROR:errors.append(record.getMessage())
    logger=logging.getLogger('weasyprint');handler=Errors();logger.addHandler(handler)
    try:
        doc=HTML(string=document,base_url=source.parent.as_uri()+'/',
                 url_fetcher=OfflineFetcher(allowed_protocols={'file','data'},fail_on_errors=True)).render()
        layout=layout_report(doc)
        if layout['actual_body_font_sizes_pt']!=[args.font_size]:
            raise ValueError('打印字号仍被源样式覆盖，请核对 HTML 的高优先级样式')
        if layout['placed_images']!=len(inventory.images):
            raise ValueError('排版后的图片数与源文档不一致；可能存在隐藏或分页异常')
        if errors:raise ValueError('排版发生错误：'+str(errors))
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent,suffix='.pdf',delete=False) as temp:
            temporary=Path(temp.name)
        try:
            doc.write_pdf(temporary)
            if errors:raise ValueError('PDF 写入发生错误：'+str(errors))
            if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('源文件在导出时发生变化')
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        logger.removeHandler(handler)
    report=dict(source_name=source.name,source_sha256=digest,source_kind=source.suffix[1:],
                renderer='WeasyPrint',renderer_version=__version__,page_count=len(doc.pages),
                paper='A4',body_font_size_pt=args.font_size,source_images=len(inventory.images),
                headings=inventory.headings,captions_joined=captions,remote_resources_allowed=False,
                scripts_executed=False,browser_used=False,visual_review_completed=False,
                note='布局检测不是视觉验收；稀疏页只提示，不通过删内容或压小截图强行消除。',**layout)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(doc.pages)} pages; {len(inventory.images)} images; {output}')


if __name__=='__main__':main()
