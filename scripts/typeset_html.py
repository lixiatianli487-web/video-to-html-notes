"""Pre-render TeX in plain paragraphs, embedding KaTeX CSS and WOFF2 fonts."""
import base64
import html
import json
from pathlib import Path
import re
import subprocess


def typeset(document, node='node'):
    formulas = []
    marker = '\ue000MATH'
    if marker in document:
        raise ValueError('正文含保留的数学排版占位符。')

    def formula(tex, display):
        formulas.append(dict(tex=tex, display=display))
        return marker + str(len(formulas)-1) + '\ue001'

    def paragraph(match):
        raw = match.group(1)
        text = html.unescape(raw)
        block = re.fullmatch(r'\s*\\\[(.*?)\\\]\s*', text, re.S)
        if block:
            return '<div class="formula">' + formula(block.group(1), True) + '</div>'
        rendered = []
        for fragment in re.split(r'(<[^>]+>)', raw):
            if fragment.startswith('<'):
                rendered.append(fragment)
                continue
            pieces = re.split(r'(\\\(.*?\\\))', html.unescape(fragment), flags=re.S)
            for part in pieces:
                if part.startswith(r'\(') and part.endswith(r'\)'):
                    rendered.append(formula(part[2:-2], False))
                else:
                    if any(x in part for x in (r'\(', r'\)', r'\[', r'\]')):
                        raise ValueError('TeX 定界符不完整，或独立公式没有单独成段。')
                    rendered.append(html.escape(part))
        return '<p>' + ''.join(rendered) + '</p>'

    document = re.sub(r'<p>(.*?)</p>', paragraph, document, flags=re.S)
    if not formulas:
        return document
    base = Path(__file__).resolve().parent.parent / 'assets/katex'
    code = """const fs=require('fs');const katex=require(process.argv[1]);
const x=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(x.map(f=>katex.renderToString(f.tex,{displayMode:f.display,throwOnError:true,strict:'error',trust:false,output:'htmlAndMathml'}))));"""
    result = subprocess.run([node, '-e', code, str(base/'katex.js')],
                            input=json.dumps(formulas), text=True, capture_output=True)
    if result.returncode:
        raise ValueError('公式排版失败：' + result.stderr[:1500])
    rendered = json.loads(result.stdout)
    document = re.sub(re.escape(marker)+r'(\d+)\ue001',
                      lambda m: rendered[int(m.group(1))], document)
    css = (base/'katex.min.css').read_text(encoding='utf-8')
    css = re.sub(r'src:([^;}]+)', lambda m: 'src:'+','.join(
        item for item in m.group(1).split(',') if '.woff2' in item), css)

    def font_url(match):
        name = match.group(1).strip('\"\'')
        font = (base/name).resolve()
        if not font.is_relative_to(base.resolve()):
            raise ValueError('字体路径超出随附资源目录。')
        return 'url(data:font/woff2;base64,'+base64.b64encode(font.read_bytes()).decode()+')'

    css = re.sub(r'url\((fonts/[^)]+\.woff2)\)', font_url, css)
    css += '\n.katex{font-size:1.08em}.formula .katex{font-size:1.08em}'
    license_text = (base/'LICENSE').read_text(encoding='utf-8').replace('--', '- -')
    return document.replace('</head>', '<style id="embedded-katex">'+css+'</style>'
                            '<!-- KaTeX license\n'+license_text+'\n--></head>')
