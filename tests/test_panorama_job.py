import base64
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import io
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from fixture_store import Store
from generate_daily import generate, Stopped
from git_panorama_test import REQUEST, TEST_ID
from test_panorama import fixture
from panorama import derive_panorama
import git_daily

PILOT = {'test_id': 'flare-access-2026-10-26', 'reserved_aud': 5, 'run_id': 'fixture'}


class Transport:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.raw = fixture()
    def call(self, path, body):
        self.calls.append(body)
        if self.fail:
            raise TimeoutError()
        return {'data': [{'b64_json': base64.b64encode(self.raw).decode()}],
                'usage': {'input_tokens': 300, 'output_tokens': 196}}, None


class PanoramaJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.transport = Transport()
        with self.store.locked() as db:
            db.save('budget-policy', {'policy_id': 'flare-low-v1-reviewed', 'settle_success': True})
            db.save('pilot:2026-10-26', {'month': '2026-10', 'reserved_cents': 10})
            db.save(REQUEST['date'], {'state': 'complete', 'fingerprint': 'original',
                'month': '2026-10', 'reserved_cents': 3, 'manifest': {'original': True}})
        self.original = self.store.get(REQUEST['date'])
    def tearDown(self):
        self.tmp.cleanup()
    def publisher(self, day, original, display, metadata):
        base = 'https://raw.githubusercontent.com/nerdflu/morning-brief-art/commit/'
        return dict(date=day, image_url=base+'images/tests/'+TEST_ID+'/panorama-v1.png',
            original_url=base+'original.png', manifest_url=base+'manifest.json', verified=True,
            test_id=TEST_ID, format_contract='panorama-v1', width=1872, height=380,
            original_sha256=hashlib.sha256(original).hexdigest(), display_sha256=hashlib.sha256(display).hexdigest())
    def run_test(self, request=None):
        return generate(request or REQUEST, store=self.store, transport=self.transport,
            publisher=self.publisher, pilot=PILOT, clock=lambda: date(2026,10,30), panorama_test=TEST_ID)
    def test_single_call_idempotent_original_date_immutable(self):
        result = self.run_test()
        self.assertEqual(self.run_test(), result)
        self.assertEqual(len(self.transport.calls), 1)
        self.assertEqual(self.transport.calls[0]['size'], '1872x624')
        self.assertEqual(self.store.get(REQUEST['date']), self.original)
    def test_conflicting_fingerprint_no_second_call(self):
        self.run_test()
        with self.assertRaisesRegex(Stopped, 'conflict'):
            self.run_test(dict(REQUEST, concept='A different impossible library above the clouds.'))
        self.assertEqual(len(self.transport.calls), 1)
    def test_uncertain_call_freezes_budget_no_retry(self):
        self.transport.fail = True
        for _ in range(2):
            with self.assertRaisesRegex(Stopped, 'no_retry'):
                self.run_test()
        self.assertEqual(len(self.transport.calls), 1)
        state = self.store.get('test:panorama-v1:'+TEST_ID)
        self.assertEqual(state['reserved_cents'], 500)
        self.assertEqual(state['state'], 'uncertain_or_needs_review')
        self.assertEqual(self.store.get(REQUEST['date']), self.original)

    def test_publication_uses_separate_immutable_paths_and_verifies_public_bytes(self):
        original = fixture()
        display, metadata = derive_panorama(original)
        metadata['test_id'] = TEST_ID
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            def public_get(url, timeout):
                relative = url.split('/commit/', 1)[1]
                return io.BytesIO((root/relative).read_bytes())
            with patch.object(git_daily, 'commit', return_value='commit'), patch.object(git_daily.urllib.request, 'urlopen', public_get):
                result = git_daily.GitPublisher(root)(REQUEST['date'], original, display, metadata)
                self.assertTrue(result['verified'])
                self.assertEqual(result['width'], 1872)
                self.assertEqual(result['height'], 380)
                self.assertIn('/images/tests/'+TEST_ID+'/panorama-v1.png', result['image_url'])
                self.assertTrue((root/'manifests/tests'/str(TEST_ID+'.json')).exists())
                self.assertFalse((root/'manifests'/str(REQUEST['date']+'.json')).exists())
                with self.assertRaisesRegex(Stopped, 'immutable_revision_manifest_conflict'):
                    git_daily.GitPublisher(root)(REQUEST['date'], original, display, metadata)

    def test_insufficient_monthly_budget_prevents_paid_call(self):
        with self.store.locked() as db:
            db.save('other', {'month': '2026-10', 'reserved_cents': 450})
        with self.assertRaisesRegex(Stopped, 'budget'):
            self.run_test()
        self.assertEqual(self.transport.calls, [])


    def test_failed_composition_retains_source_and_actual_usage_without_retry(self):
        self.transport.raw = fixture(outside=True)
        preserved = []
        with self.assertRaisesRegex(Stopped, 'no_retry'):
            generate(REQUEST, store=self.store, transport=self.transport,
                publisher=self.publisher, pilot=PILOT, clock=lambda: date(2026,10,30),
                panorama_test=TEST_ID, source_archiver=lambda raw, metadata: preserved.append(raw))
        self.assertEqual(preserved, [self.transport.raw])
        state = self.store.get('test:panorama-v1:'+TEST_ID)
        self.assertEqual(state['result']['reported_usage']['output_tokens'], 196)
        self.assertEqual(state['state'], 'uncertain_or_needs_review')
        self.assertEqual(self.store.get(REQUEST['date']), self.original)
