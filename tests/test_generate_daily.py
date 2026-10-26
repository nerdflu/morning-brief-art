from datetime import date
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_daily as g
from fixture_store import Store
from PIL import Image

def request(date, concept):
    concept = {'garden': 'A garden of oversized flowers', 'lighthouse': 'A lighthouse made from folded paper'}.get(concept, concept)
    return {'date': date, 'concept': concept, 'style': 'linocut', 'layout': 'school', 'public_safe': True}
PILOT = {'test_id': 'flare-access-2026-10-26', 'reserved_aud': 5, 'run_id': 'fixture'}

class Transport:

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def call(self, path, body):
        self.calls.append((path, body))
        if self.fail:
            raise TimeoutError()
        out = io.BytesIO()
        Image.new('RGB', (1024, 1024), 'white').save(out, format='PNG')
        self.raw = out.getvalue()
        return ({'data': [{'b64_json': base64.b64encode(self.raw).decode()}], 'usage': {'input_tokens': 30, 'output_tokens': 196}}, None)

class Tests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        self.transport = Transport()
        self.published = []

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, day, original, display, metadata):
        self.published.append((original, display))
        self.assertEqual(original, self.transport.raw)
        self.assertEqual(Image.open(io.BytesIO(display)).size, (960, 480))
        base = 'https://raw.githubusercontent.com/nerdflu/morning-brief-art/main/'
        return {'date': day, 'image_url': base + 'display.png', 'original_url': base + 'original.png', 'manifest_url': base + 'manifest.json', 'verified': True}

    def run_request(self, day='2026-11-01', concept='lighthouse', publisher=None):
        return g.generate(request(date=day, concept=concept), store=self.store, transport=self.transport, publisher=publisher or self.publish, pilot=PILOT, clock=lambda: date(2026, 11, 1))

    def test_complete_preserves_bytes_and_idempotent(self):
        result = self.run_request()
        self.assertEqual(self.run_request(), result)
        self.assertEqual(len(self.transport.calls), 1)

    def test_pilot_blocks_october(self):
        with self.assertRaisesRegex(g.Stopped, 'budget'):
            g.generate(request(date='2026-10-27', concept='garden'), store=self.store, transport=self.transport, publisher=self.publish, pilot=PILOT, clock=lambda: date(2026, 10, 26))
        self.assertEqual(self.transport.calls, [])

    def test_second_date_blocked_by_full_reservation(self):
        self.run_request()
        with self.assertRaisesRegex(g.Stopped, 'budget'):
            self.run_request('2026-11-02')
        self.assertEqual(len(self.transport.calls), 1)

    def test_unknown_outcome_never_retried_even_after_reopen(self):
        self.transport.fail = True
        with self.assertRaisesRegex(g.Stopped, 'no_retry'):
            self.run_request()
        self.store = Store(self.tmp.name)
        with self.assertRaisesRegex(g.Stopped, 'no_retry'):
            self.run_request()
        self.assertEqual(len(self.transport.calls), 1)

    def test_conflicting_concept_cannot_regenerate(self):
        self.run_request()
        with self.assertRaisesRegex(g.Stopped, 'conflict'):
            self.run_request(concept='garden')

    def test_publication_failure_blocks_regeneration(self):
        with self.assertRaises(g.Stopped):
            self.run_request(publisher=lambda *args: {})
        with self.assertRaises(g.Stopped):
            self.run_request()
        self.assertEqual(len(self.transport.calls), 1)

    def test_rejects_raw_private_text_and_bad_dates(self):
        for request in [{'date': '2026-02-30', 'concept': 'garden'}, {'date': '2026-11-01', 'concept': 'private medical info'}, {'date': '2026-11-01', 'concept': 'garden', 'brief': 'private'}]:
            with self.assertRaises(g.Stopped):
                g.generate(request, store=self.store, transport=self.transport, publisher=self.publish, pilot=PILOT, clock=lambda: date(2026, 11, 1))
        self.assertEqual(self.transport.calls, [])

    def test_reconciled_october_can_generate_and_settles_conservatively(self):
        import reconcile_budget
        pilot = json.loads((Path(__file__).resolve().parents[1] / '.pipeline-tests/flare-access-2026-10-26.json').read_text())
        reconcile_budget.reconcile(self.store, pilot, 'fixture-approval', True)
        result = g.generate(request(date='2026-10-27', concept='garden'), store=self.store, transport=self.transport, publisher=self.publish, pilot=pilot, clock=lambda: date(2026, 10, 26))
        self.assertTrue(result['verified'])
        with self.store.locked() as db:
            self.assertEqual(g.get(db, '2026-10-27')['reserved_cents'], 3)
            self.assertEqual(g.get(db, '2026-10-27')['original_reserved_cents'], 50)
            self.assertFalse(g.get(db, '2026-10-27')['invoice_verified'])
            self.assertEqual(g.get(db, 'pilot:2026-10-26')['reserved_cents'], 10)

    def test_uncertain_after_reconciliation_freezes_other_dates(self):
        import reconcile_budget
        pilot = json.loads((Path(__file__).resolve().parents[1] / '.pipeline-tests/flare-access-2026-10-26.json').read_text())
        reconcile_budget.reconcile(self.store, pilot, 'fixture-approval', True)
        self.transport.fail = True
        with self.assertRaises(g.Stopped):
            g.generate(request(date='2026-10-27', concept='garden'), store=self.store, transport=self.transport, publisher=self.publish, pilot=pilot, clock=lambda: date(2026, 10, 26))
        with self.assertRaisesRegex(g.Stopped, 'budget'):
            g.generate(request(date='2026-10-28', concept='garden'), store=self.store, transport=self.transport, publisher=self.publish, pilot=pilot, clock=lambda: date(2026, 10, 26))
        self.assertEqual(len(self.transport.calls), 1)

    def test_31_observed_usage_images_fit_reviewed_monthly_policy(self):
        import reconcile_budget
        pilot = json.loads((Path(__file__).resolve().parents[1] / '.pipeline-tests/flare-access-2026-10-26.json').read_text())
        reconcile_budget.reconcile(self.store, pilot, 'fixture-approval', True)
        for day in range(1, 32):
            g.generate(request(date=f'2026-10-{day:02}', concept='garden'), store=self.store, transport=self.transport, publisher=self.publish, pilot=pilot, clock=lambda: date(2026, 10, 26))
        with self.store.locked() as db:
            total = sum((r['reserved_cents'] for r in db.records.values() if r.get('month') == '2026-10'))
        self.assertEqual(total, 103)
        self.assertEqual(len(self.transport.calls), 31)

    def test_reservation_or_submission_failure_prevents_paid_call(self):
        for failed_state in ('reserved', 'submitted'):
            with tempfile.TemporaryDirectory() as directory:
                store = Store(directory)
                original = store.save

                def failing_save(key, value):
                    if value.get('state') == failed_state:
                        raise RuntimeError('fixture persistence failure')
                    return original(key, value)
                store.save = failing_save
                with self.assertRaises(RuntimeError):
                    g.generate(request(date='2026-11-01', concept='garden'), store=store, transport=self.transport, publisher=self.publish, pilot=PILOT, clock=lambda: date(2026, 11, 1))
        self.assertEqual(self.transport.calls, [])

    def test_submission_durable_before_call(self):
        original = self.transport.call

        def check(path, body):
            with Store(self.tmp.name).locked() as db:
                state = g.get(db, '2026-11-01')
                self.assertEqual(state['state'], 'submitted')
                self.assertEqual(state['reserved_cents'], 500)
            return original(path, body)
        self.transport.call = check
        self.run_request()
if __name__ == '__main__':
    unittest.main()
