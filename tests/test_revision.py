import copy
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from fixture_store import Store
import generate_daily as g
import git_daily as git
import git_revision
import revision_switch as switch
import test_generate_daily as daily
from test_generate_daily import request
from display_image import derive_display

class RevisionTests(unittest.TestCase):
    run_request = daily.Tests.run_request
    publish = daily.Tests.publish
    tearDown = daily.Tests.tearDown
    def setUp(self):
        daily.Tests.setUp(self)
        import reconcile_budget
        self.pilot = json.loads((Path(__file__).resolve().parents[1]/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
        reconcile_budget.reconcile(self.store, self.pilot, 'fixture-approval', True)
        self.original = self.run_request()
        self.original_record = json.loads(self.store.path.read_text())['2026-11-01']
        self.rev = {'id': 'gravity-v1', 'supersedes_manifest_url': self.original['manifest_url'],
                    'max_reservation_cents': 50, 'approval_reference': 'fixture-one-call'}
    # Inherit setup helpers, not the baseline test methods (run separately).
    def revision_publish(self, day, original, display, metadata):
        result = self.publish(day, original, display, metadata)
        result.update(revision_id=metadata['revision']['id'], supersedes_manifest_url=self.original['manifest_url'],
                      original_sha256=hashlib.sha256(original).hexdigest(), display_sha256=hashlib.sha256(display).hexdigest())
        return result
    def revision(self, **kwargs):
        args = dict(store=self.store, transport=self.transport, publisher=self.revision_publish, pilot=self.pilot,
                    clock=lambda: date(2026, 11, 1), revision=self.rev)
        args.update(kwargs)
        return g.generate(request('2026-11-01', 'garden'), **args)
    def test_revision_duplicate_and_original_immutable(self):
        result = self.revision()
        self.assertEqual(self.revision(), result)
        self.assertEqual(len(self.transport.calls), 2)
        self.assertEqual(json.loads(self.store.path.read_text())['2026-11-01'], self.original_record)
        self.assertEqual(self.run_request(), self.original)
    def test_revision_conflict_before_call(self):
        self.revision()
        with self.assertRaisesRegex(g.Stopped, 'conflict'):
            self.rev['approval_reference'] = 'changed'
            self.revision()
        self.assertEqual(len(self.transport.calls), 2)
    def test_revision_uncertain_freezes_and_never_retries(self):
        self.transport.fail = True
        with self.assertRaisesRegex(g.Stopped, 'no_retry'): self.revision()
        self.store = Store(self.tmp.name)
        with self.assertRaisesRegex(g.Stopped, 'no_retry'): self.revision()
        self.rev['id'] = 'another-id'
        with self.assertRaisesRegex(g.Stopped, 'budget'): self.revision()
        self.assertEqual(len(self.transport.calls), 2)
    def test_revision_bad_hash_freezes(self):
        def bad(*args):
            result = self.revision_publish(*args); result['display_sha256'] = 'wrong'; return result
        with self.assertRaisesRegex(g.Stopped, 'no_retry'): self.revision(publisher=bad)
        with self.assertRaisesRegex(g.Stopped, 'no_retry'): self.revision()
        self.assertEqual(len(self.transport.calls), 2)
    def test_revision_requires_original_and_sufficient_approval(self):
        self.rev['supersedes_manifest_url'] = 'different'
        with self.assertRaisesRegex(g.Stopped, 'completed_original'): self.revision()
        self.rev['supersedes_manifest_url'] = self.original['manifest_url']
        self.rev['max_reservation_cents'] = 2
        with self.assertRaisesRegex(g.Stopped, 'below_required'): self.revision()
        self.assertEqual(len(self.transport.calls), 1)

    def test_revision_persistence_failure_prevents_call(self):
        original_save=self.store.save
        def fail(key,value):
            if ':revision:' in key and value['state']=='submitted':raise RuntimeError('fixture-save')
            return original_save(key,value)
        self.store.save=fail
        with self.assertRaises(RuntimeError):self.revision()
        self.assertEqual(len(self.transport.calls),1)

    def test_revision_does_not_expand_monthly_budget(self):
        with self.store.locked() as db:
            db.save('fixture-hold',{'month':'2026-11','reserved_cents':498})
        with self.assertRaisesRegex(g.Stopped,'monthly_budget'):self.revision()
        self.assertEqual(len(self.transport.calls),1)

class FitTests(unittest.TestCase):
    def test_revision_fill_and_default_unchanged(self):
        image=Image.new('RGB',(1024,1024),'white')
        from PIL import ImageDraw
        ImageDraw.Draw(image).rectangle((100,300,900,700),fill='black')
        raw=io.BytesIO(); image.save(raw,format='PNG')
        def bounds(data):
            img=Image.open(io.BytesIO(data)); return img.point(lambda v:255 if v<250 else 0).getbbox()
        default=derive_display(raw.getvalue(),'non-school')
        self.assertEqual(default,derive_display(raw.getvalue(),'non-school','contain-v1'))
        old=bounds(default); new=bounds(derive_display(raw.getvalue(),'non-school','band-fill-v1'))
        self.assertLess(old[2]-old[0],400)
        self.assertGreater(new[2]-new[0],920)
        self.assertGreaterEqual(new[1],154); self.assertLessEqual(new[3],326)
        self.assertEqual(derive_display(raw.getvalue(),'school'),derive_display(raw.getvalue(),'school','band-fill-v1'))
    def test_null_revision_cannot_fall_through_to_daily(self):
        with self.assertRaisesRegex(g.Stopped,'named_revision'):
            git_revision.resolve_revision(json.dumps({'request':{'date':'2026-10-28'},'revision':None}),'2026-10-28')
    def test_revision_envelope_current_date_only(self):
        with self.assertRaises(g.Stopped): git_revision.resolve_revision(json.dumps({'request':{'date':'2026-10-27'},'revision':{}}),'2026-10-28')

class SwitchTests(unittest.TestCase):
    def setUp(self):
        base='https://raw.githubusercontent.com/nerdflu/morning-brief-art/'+'a'*40+'/'
        self.original={'date':'2026-10-28','manifest_url':base+'manifests/2026-10-28.json','image_url':base+'images/2026/10/2026-10-28-flare.png'}
        self.blobs={}
        self.result={'date':'2026-10-28','revision_id':'gravity-v1','supersedes_manifest_url':self.original['manifest_url'],'framing':'band-fill-v1'}
        for field,hash_field,size in [('original_url','original_sha256',(1024,1024)),('image_url','display_sha256',(960,480))]:
            raw=io.BytesIO();Image.new('RGB',size,'white').save(raw,format='PNG');raw=raw.getvalue()
            self.result[field]=base+'images/2026/10/2026-10-28-revision-gravity-v1-'+field.replace('_','-')+'.png'
            self.result[hash_field]=hashlib.sha256(raw).hexdigest();self.blobs[self.result[field]]=raw
        self.result['manifest_url']=base+'manifests/2026-10-28-revision-gravity-v1.json'
        self.blobs[self.result['manifest_url']]=json.dumps({k:v for k,v in self.result.items() if k!='manifest_url'}).encode()
        self.result['verified']=True
        self.row={'image_url':self.original['image_url'],'payload_json':json.dumps({'schema_version':1,'hero_image':self.original['image_url'],'briefing':{'headline':'Synthetic only'}}),'status':'ready'}
        outer=self
        class Adapter:
            calls=[]
            def compare_and_swap(self,row_id,expected,replacement):
                self.calls.append(row_id)
                if outer.row != expected:return False
                outer.row=copy.deepcopy(replacement);return True
            def read(self,row_id):return copy.deepcopy(outer.row)
        self.adapter=Adapter()
    def run_switch(self,expected=None):
        return switch.switch_same_row(self.adapter,50,expected or copy.deepcopy(self.row),self.original,self.result,fetch=self.blobs.__getitem__)
    def test_same_row_only_after_hash_verification(self):
        result=self.run_switch()
        self.assertEqual(self.adapter.calls,[50]);self.assertEqual(result['status'],'ready')
        self.assertEqual(json.loads(result['payload_json'])['briefing'],{'headline':'Synthetic only'})
        self.assertEqual(json.loads(result['payload_json'])['hero_image'],self.result['image_url'])
    def test_bad_bytes_never_switch(self):
        self.blobs[self.result['image_url']]=b'bad'
        with self.assertRaisesRegex(g.Stopped,'hash_mismatch'):self.run_switch()
        self.assertEqual(self.adapter.calls,[])
    def test_changed_row_fails_closed(self):
        expected=copy.deepcopy(self.row);self.row['status']='changed'
        with self.assertRaisesRegex(g.Stopped,'row_changed'):self.run_switch(expected)
        self.assertEqual(self.row['status'],'changed')
    def test_different_hero_never_switches(self):
        self.row['payload_json']=json.dumps({'hero_image':'other'})
        with self.assertRaisesRegex(g.Stopped,'different_image'):self.run_switch()
        self.assertEqual(self.adapter.calls,[])
