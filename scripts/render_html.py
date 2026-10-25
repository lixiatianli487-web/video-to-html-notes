#!/usr/bin/env python3
"""Export authored lecture Markdown to HTML without rewriting its source."""
import argparse
import html
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit
from typeset_html import typeset


def link_url(value, root, require_file=False):
    parsed = urlsplit(value)
    if parsed.scheme:
        if require_file or parsed.scheme not in ('http', 'https'):
            raise ValueError('不支持的链接或远程图片：'+value)
        return html.escape(value, quote=True)
    file = (root/unquote(value)).resolve()
    if value.startswith('//') or not file.is_relative_to(root):
        raise ValueError('素材须在项目目录内：'+value)
    if require_file and not file.is_file():
        raise ValueError('图片不存在：'+value)
    return html.escape(quote(unquote(value), safe='/#'), quote=True)


def inline(text, root):
    # Escape all content, then restore only the Markdown markup we support.
    chunks=re.split(r'(\[[^\]]+\]\([^)]+\))', text)
    result=[]
    for chunk in chunks:
        link=re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)',chunk)
        if link:
            result.append(f'<a href="{link_url(link[2],root)}">{html.escape(link[1])}</a>')
        else:
            value=html.escape(chunk)
            value=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)
            value=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<em>\1</em>',value)
            result.append(value)
    return ''.join(result)


def render_document(source, node='node'):
    source=Path(source).resolve();root=source.parent
    if source.suffix.lower()!='.md':raise ValueError('输入必须是 Markdown 讲义。')
    text=source.read_text(encoding='utf-8')
    lines=text.splitlines();blocks=[];buf=[];toc=[];title=None;math_mode=False;image_count=0
    def flush():
        if buf:blocks.append('<p>'+inline(' '.join(buf),root)+'</p>');buf.clear()
    for line in lines:
        stripped=line.strip()
        if math_mode:
            buf.append(line)
            if stripped==r'\]':
                blocks.append('<p>'+html.escape('\n'.join(buf))+'</p>');buf.clear();math_mode=False
            continue
        if stripped==r'\[':
            flush();buf.append(line);math_mode=True;continue
        if not stripped:flush();continue
        if re.match(r'(```|~~~|[-+] |\* |\d+[.)] |\||>)',stripped):
            raise ValueError('发现辅助脚本尚不支持的 Markdown 结构，请扩展后再导出：'+stripped)
        heading=re.fullmatch(r'(#{1,3})\s+(.+)',line)
        if heading:
            flush();level=len(heading[1]);value=heading[2]
            if level==1:
                if title is not None:raise ValueError('只允许一个顶层标题。')
                title=value
            else:
                ident='s'+str(len(toc)+1)
                toc.append(f'<a href="#{ident}">{html.escape(value)}</a>')
                blocks.append(f'<h{level} id="{ident}">{html.escape(value)}</h{level}>')
            continue
        picture=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',stripped)
        if picture:
            flush();url=link_url(picture[2],root,True);alt=html.escape(picture[1],quote=True)
            blocks.append(f'<figure><a href="{url}"><img loading="lazy" src="{url}" alt="{alt}"></a></figure>')
            image_count+=1;continue
        if re.fullmatch(r'\d{2}(?::\d{2}){1,2}\s*[—–-]\s*\d{2}(?::\d{2}){1,2}',stripped):
            flush();blocks.append(f'<span class="time">{html.escape(stripped)}</span>');continue
        if re.fullmatch(r'\*原视频[^*]+\*',stripped):
            flush();blocks.append('<p class="image-caption">'+html.escape(stripped[1:-1])+'</p>');continue
        buf.append(line)
    if math_mode:raise ValueError('独立公式未闭合。')
    flush()
    if title is None:raise ValueError('Markdown 缺少顶层标题。')
    css=(Path(__file__).resolve().parent.parent/'assets/lecture.css').read_text()
    css+='\n.image-caption{text-align:center;color:#66776f;font-size:14px;margin-top:-25px}h3{color:#116b5a}.time{display:block;margin:20px 0 8px}'
    document=('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>'+html.escape(title)+'</title><style>'+css+'</style></head><body><main>'
              '<h1>'+html.escape(title)+'</h1><nav aria-label="目录">'+''.join(toc)+'</nav>'
              +''.join(blocks)+'</main></body></html>')
    document=typeset(document,node)
    return document,image_count


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('--node',default='node')
    ap.add_argument('--overwrite',action='store_true')
    args=ap.parse_args()
    source=args.input.resolve();output=source.with_suffix('.html')
    if output.exists() and not args.overwrite:raise FileExistsError('输出已存在；确认更新后使用 --overwrite。')
    document,image_count=render_document(source,args.node)
    output.write_text(document,encoding='utf-8')
    print(f'已从 Markdown 导出 HTML，图片 {image_count} 张；Markdown 原件未修改：{output}')


if __name__=='__main__':main()
