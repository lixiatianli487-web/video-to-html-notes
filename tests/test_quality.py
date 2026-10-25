"""Regression checks for real failure modes, using only standard-library fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def module(name):
    file=Path(__file__).resolve().parents[1]/'scripts'/f'{name}.py'
    spec=importlib.util.spec_from_file_location(name,file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


review=module('review_asr');coverage=module('check_coverage')


class QualityTests(unittest.TestCase):
    def test_short_tail_and_low_probability_never_autocorrect(self):
        rows=[dict(start=0,end=2,text='Hello.'),dict(start=8,end=8.04,text='All.',avg_logprob=-2.7)]
        original=copy.deepcopy(rows);r=review.scan(rows,8.1)
        self.assertEqual(rows,original)
        self.assertIn('very_short_text',[i['kind'] for i in r['issues']])
        self.assertIn('gap_candidate',[i['kind'] for i in r['issues']])
        self.assertTrue(all(i['status']=='pending' for i in r['issues']))
        self.assertTrue(all(0<=w['start']<w['end']<=8.1 for w in r['windows']))

    def test_plain_subtitles_report_missing_metrics(self):
        r=review.scan([dict(start=0,end=2,text='Not 12 but 20.')],2)
        self.assertFalse(r['metrics_available'])
        self.assertTrue(r['critical_tokens'])
        self.assertFalse(r['issues'])

    def fixture(self,root):
        source=root/'source.json';source.write_text(json.dumps({'segments':[{'id':1,'start':0,'end':2,'text':'Load 12. Not the process.'}]}))
        md=root/'notes.md';md.write_text('# Title\n\n## Step\n\n00:00—00:02\n\n把12装入R0。PCB不是进程本身。\n\n![原视频](image.jpg)\n')
        (root/'image.jpg').write_bytes(b'image fixture')
        ledger=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),content_units=[dict(id='U1',source_ids=[1],point='加载12；否定PCB等同于进程',note_evidence=[{'quote':'把12装入R0。PCB不是进程本身。'}],review_status='text_checked')],visual_units=[dict(id='V1',image='image.jpg',point='寄存器中间状态',note_evidence=[{'quote':'把12装入R0。'}],review_status='preview_checked')],exclusions=[])
        return source,md,ledger

    def test_valid_evidence_is_not_semantic_certificate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s,m,l=self.fixture(root);r=coverage.validate(s,m,l,root)
            self.assertTrue(r['structural_pass']);self.assertFalse(r['semantic_accuracy_certified'])
            self.assertIn('V1',r['pending_items'])

    def test_deleted_step_changed_number_and_negation_are_detected(self):
        for changed in ['PCB不是进程本身。','把13装入R0。PCB不是进程本身。','把12装入R0。PCB就是进程本身。']:
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as d:
                root=Path(d);s,m,l=self.fixture(root);m.write_text(m.read_text().replace('把12装入R0。PCB不是进程本身。',changed))
                self.assertFalse(coverage.validate(s,m,l,root)['structural_pass'])

    def test_heading_only_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s,m,l=self.fixture(root);l['content_units'][0]['note_evidence']=[{'quote':'Step'}]
            self.assertFalse(coverage.validate(s,m,l,root)['structural_pass'])

    def test_unreferenced_source_and_missing_picture_are_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s,m,l=self.fixture(root);l['content_units'][0]['source_ids']=[99];(root/'image.jpg').unlink()
            self.assertGreaterEqual(len(coverage.validate(s,m,l,root)['errors']),3)


if __name__=='__main__':unittest.main()
