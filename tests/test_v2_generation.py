import base64
import copy
from datetime import date
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fixture_store import Store
import generate_daily as g
from art_contracts import POLICY

BASE='https://raw.githubusercontent.com/nerdflu/morning-brief-art/'+'a'*40+'/'
PILOT={'test_id':'flare-access-2026-10-26','reserved_aud':5,'run_id':'fixture'}


class Transport:
    def __init__(self):self.calls=[];self.failure=None;self.tall=False
    def call(self,path,body):
        self.calls.append(body)
        if self.failure:raise self.failure
        size=tuple(map(int,body['size'].split('x')));im=Image.new('RGB',size,'white')
        if size==(1872,624):ImageDraw.Draw(im).rectangle((70,10 if self.tall else 115,1800,610 if self.tall else 495),fill='black')
        b=io.BytesIO();im.save(b,format='PNG');self.raw=b.getvalue()
        return {'data':[{'b64_json':base64.b64encode(self.raw).decode()}],'usage':{'input_tokens':300,'output_tokens':196}},None


class Publisher:
    def __init__(self):self.sources=[];self.manifests=[];self.selected=None
    def archive_original(self,day,raw,metadata):
        self.sources.append(raw);return BASE+'images/'+day[:4]+'/'+day[5:7]+'/'+day+'-original.png'
    def current_for(self,day,fallback):return self.selected or fallback
    def __call__(self,day,raw,display,metadata):
        suffix='school-v2' if metadata['layout']=='school' else 'solo-panorama-v2'
        m={'date':day,'image_url':BASE+'images/'+day[:4]+'/'+day[5:7]+'/'+day+'-'+suffix+'.png',
           'original_url':metadata['archived_original_url'],'manifest_url':BASE+'manifests/'+day+'.json',
           'verified':True,'display_sha256':hashlib.sha256(display).hexdigest(),
           **{k:metadata[k] for k in ('format_contract','layout','width','height')}}
        self.manifests.append(m);return m


class V2GenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name);self.t=Transport();self.p=Publisher()
        with self.store.locked() as db:db.save('budget-policy',{'policy_id':'flare-low-v1-reviewed','settle_success':True})
    def tearDown(self):self.tmp.cleanup()
    def run_request(self,day='2026-11-01',layout='school'):
        r={'date':day,'concept':'A large expressive paper bird shelters a small moon creature.',
           'style':'ink','layout':layout,'public_safe':True}
        return g.generate(r,store=self.store,transport=self.t,publisher=self.p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=POLICY)
    def test_modes_and_duplicate_no_second_call(self):
        first=self.run_request();self.assertEqual(first['width'],960);self.assertEqual(len(self.p.sources),1)
        self.assertEqual(self.run_request(),first);self.assertEqual(len(self.t.calls),1)
        solo=self.run_request('2026-11-02','non-school');self.assertEqual((solo['width'],solo['height']),(1872,400))
    def test_completed_date_returns_selected_revision_without_call(self):
        original=self.run_request();record=self.store.get('2026-11-01');self.p.selected=dict(original,revision_id='approved',image_url=BASE+'approved.png')
        self.assertEqual(self.run_request(),self.p.selected)
        self.assertEqual(self.store.get('2026-11-01'),record);self.assertEqual(len(self.t.calls),1)
    def test_unknown_call_freezes_and_cannot_repeat(self):
        self.t.failure=TimeoutError()
        for _ in range(2):
            with self.assertRaises(g.Stopped):self.run_request()
        self.assertEqual(self.store.get('2026-11-01')['reserved_cents'],500);self.assertEqual(len(self.t.calls),1)
    def test_cancel_leaves_durable_unknown_hold_before_call(self):
        self.t.failure=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.run_request()
        self.assertEqual(self.store.get('2026-11-01')['state'],'submitted')
        self.assertEqual(self.store.get('2026-11-01')['reserved_cents'],500)
        with self.assertRaises(g.Stopped):self.run_request()
        self.assertEqual(len(self.t.calls),1)
    def test_known_framing_failure_preserves_source_usage_and_headroom(self):
        self.t.tall=True
        with self.assertRaises(g.Stopped):self.run_request(layout='non-school')
        self.assertEqual(len(self.p.sources),1);self.assertEqual(self.p.manifests,[])
        record=self.store.get('2026-11-01');self.assertEqual(record['reserved_cents'],50)
        self.assertEqual(record['result']['usage']['output_tokens'],196)
        self.t.tall=False;self.run_request('2026-11-02')
        self.assertEqual(len(self.t.calls),2)
    def test_missing_source_archiver_or_invalid_policy_prevents_call(self):
        request={'date':'2026-11-01','concept':'A large paper bird with a moon.','style':'ink','layout':'school','public_safe':True}
        for policy in (POLICY,'unreviewed'):
            with self.assertRaises(g.Stopped):g.generate(request,store=self.store,transport=self.t,publisher=lambda *a:None,pilot=PILOT,format_policy=policy)
        self.assertEqual(self.t.calls,[])
