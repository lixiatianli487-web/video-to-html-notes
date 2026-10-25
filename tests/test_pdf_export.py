"""PDF regressions for print cascade, missing assets, source preservation, and captions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/'scripts'))
from render_pdf import prepare


class PdfTests(unittest.TestCase):
    def test_missing_or_remote_images_stop_export(self):
        with tempfile.TemporaryDirectory() as d:
            for url in ['missing.jpg','https://example.org/a.jpg','../outside.jpg']:
                with self.subTest(url=url),self.assertRaises(ValueError):
                    prepare(f'<html><head></head><body><img src="{url}"></body></html>',Path(d),'')

    def test_caption_moves_inside_figure_without_changing_text_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a.jpg').write_bytes(b'fixture')
            text='<html><head></head><body><p>First</p><figure><img src="a.jpg"></figure><p class="image-caption">Caption</p><p>Second</p></body></html>'
            result,inventory,count=prepare(text,root,'body{font-size:11pt}')
            self.assertIn('<figcaption>Caption</figcaption></figure>',result)
            self.assertEqual(len(inventory.images),1);self.assertEqual(count,1)
            self.assertLess(result.index('First'),result.index('Caption'))
            self.assertLess(result.index('Caption'),result.index('Second'))

    @unittest.skipUnless(importlib.util.find_spec('weasyprint'),'WeasyPrint not installed')
    def test_real_render_overrides_screen_css_and_preserves_input(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);Image.new('RGB',(128,72),'#116b5a').save(root/'image.png')
            source=root/'lecture.html';pdf=root/'lecture.pdf'
            source.write_text('<html lang="zh"><head><style>body{font-size:28pt;line-height:2.5}</style></head><body><main><h1>中文讲义</h1><p>把12装入R0，不能删除此步骤。</p><figure><img src="image.png"></figure><p class="image-caption">原视频 00:12</p></main></body></html>')
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            result=subprocess.run([sys.executable,str(SKILL/'scripts/render_pdf.py'),str(source)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(pdf.with_suffix('.检查.json').read_text())
            self.assertEqual(report['actual_body_font_sizes_pt'],[11.0])
            self.assertEqual(report['placed_images'],1)
            self.assertFalse(report['overflow_candidates'])
            self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
            again=subprocess.run([sys.executable,str(SKILL/'scripts/render_pdf.py'),str(source)],capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)


if __name__=='__main__':unittest.main()
