import base64
import copy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image
from fixture_store import Store
import stage_school_revision as s
from generate_daily import Stopped


class Transport:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        out = io.BytesIO()
        Image.new('RGB',(1024,1024),'white').save(out,format='PNG')
        self.raw=out.getvalue()
    def call(self, path, body):
        self.calls.append((path,body))
        if self.fail:
            raise TimeoutError()
        return {'data':[{'b64_json':base64.b64encode(self.raw).decode()}],
                'usage':{'input_tokens':300,'output_tokens':196}}, 'req_fixture'


class StagedRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(self.tmp.name)
        self.transport=Transport()
        self.original={'state':'complete','fingerprint':'original',
            'manifest':{'manifest_url':'https://raw.githubusercontent.com/nerdflu/morning-brief-art/old/manifests/2026-10-30.json'},
            'month':'2026-10','reserved_cents':3}
        with self.store.locked() as db:
            db.save(s.DAY,self.original)
            db.save('budget-policy',{'policy_id':'flare-low-v1-reviewed'})
            db.save('other',{'month':'2026-10','reserved_cents':72})
        self.archived=[]
    def tearDown(self):
        self.tmp.cleanup()
    def archive(self, raw, metadata):
        self.archived.append(raw)
        return {'url':'https://raw.githubusercontent.com/nerdflu/morning-brief-art/source/original.png',
                'sha256':hashlib.sha256(raw).hexdigest()}
    def run_stage(self, **kwargs):
        return s.stage(store=self.store,transport=self.transport,archive=kwargs.get('archive',self.archive),today=kwargs.get('today',s.DAY),run_id='fixture')
    def test_one_call_then_review_original_unchanged(self):
        result=self.run_stage()
        self.assertEqual(result['state'],'awaiting_visual_review')
        self.assertEqual(result['reserved_cents'],50)
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.transport.calls[0][1]['n'],1)
        self.assertEqual(self.transport.calls[0][1]['size'],'1024x1024')
        self.assertEqual(self.archived,[self.transport.raw])
        self.assertEqual(self.store.get(s.DAY),self.original)
        self.assertNotIn('manifest',result)
    def test_duplicate_stage_cannot_charge_again(self):
        self.run_stage()
        with self.assertRaisesRegex(Stopped,'no_retry'):
            self.run_stage()
        self.assertEqual(len(self.transport.calls),1)
    def test_conflicting_fingerprint_cannot_charge(self):
        self.run_stage()
        with self.store.locked() as db:
            record=db.get(s.KEY);record['fingerprint']='conflict';db.save(s.KEY,record)
        with self.assertRaisesRegex(Stopped,'fingerprint_conflict'):
            self.run_stage()
        self.assertEqual(len(self.transport.calls),1)
    def test_unknown_call_freezes_and_never_retries(self):
        self.transport.fail=True
        for _ in range(2):
            with self.assertRaisesRegex(Stopped,'no_retry'):
                self.run_stage()
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.store.get(s.KEY)['reserved_cents'],500)
    def test_known_usage_publication_failure_keeps_conservative_hold(self):
        def fail(raw,metadata):
            raise TimeoutError()
        with self.assertRaisesRegex(Stopped,'no_retry'):
            self.run_stage(archive=fail)
        self.assertEqual(self.store.get(s.KEY)['reserved_cents'],50)
        self.assertEqual(self.store.get(s.KEY)['result']['usage']['input_tokens'],300)
    def test_cap_prevents_call(self):
        with self.store.locked() as db:
            db.save('other',{'month':'2026-10','reserved_cents':450})
        with self.assertRaisesRegex(Stopped,'budget'):
            self.run_stage()
        self.assertEqual(self.transport.calls,[])
    def test_other_date_prevents_call(self):
        with self.assertRaisesRegex(Stopped,'current_date'):
            self.run_stage(today='2026-10-31')
        self.assertEqual(self.transport.calls,[])
    def test_recovery_keeps_original_pixels_and_usage(self):
        transport=s.CapturingTransport(Path(self.tmp.name),self.transport)
        transport.call('/images/generations',{})
        self.assertEqual((Path(self.tmp.name)/'.revision-recovery/original-0.png').read_bytes(),self.transport.raw)
