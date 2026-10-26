import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import git_daily as g
import generate_daily as core
from fixture_store import Store
import reconcile_budget as budget

class Tests(unittest.TestCase):
    def test_git_save_confirms_push_before_return(self):
        with tempfile.TemporaryDirectory() as root:
            store=g.GitStore(root); store.records={}; calls=[]
            def cmd(root,*args):
                calls.append(args)
                if args[:1]==('rev-parse',): return 'abc'
                if args[:1]==('ls-remote',): return 'abc\trefs/heads/main'
                return ''
            with patch.object(g,'command',cmd): store.save('2026-11-01',{'state':'submitted'})
            self.assertEqual(calls[-2][0],'rev-parse'); self.assertEqual(calls[-1][0],'ls-remote')
            self.assertEqual(json.loads((Path(root)/g.LEDGER).read_text())['2026-11-01']['state'],'submitted')
    def test_remote_confirmation_mismatch_stops(self):
        def cmd(root,*args):
            return 'local' if args[0]=='rev-parse' else 'remote refs/heads/main'
        with patch.object(g,'command',cmd):
            with self.assertRaisesRegex(core.Stopped,'not_confirmed'): g.commit('.', ['file'], 'test')
    def test_missing_global_lock_fails(self):
        with patch.dict(g.os.environ,{},clear=True):
            with self.assertRaisesRegex(core.Stopped,'lock_required'):
                with g.GitStore('.').locked(): pass
    def test_pilot_reconcile_preview_does_not_touch_store(self):
        pilot=json.loads((Path(__file__).resolve().parents[1]/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
        result=budget.reconcile(None,pilot,'',False)
        self.assertEqual(result['pilot_hold_cents'],10)
        with self.assertRaisesRegex(core.Stopped,'approval'): budget.reconcile(None,pilot,'',True)
    def test_unknown_pilot_cost_fails_closed(self):
        with self.assertRaises(core.Stopped): budget.reconcile(None,{},'approval',False)
    def test_reconciled_policy_allows_bounded_calls(self):
        pilot=json.loads((Path(__file__).resolve().parents[1]/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            budget.reconcile(store,pilot,'fixture-approval',True)
            with store.locked() as db:
                self.assertEqual(core.get(db,'pilot:2026-10-26')['reserved_cents'],10)
                self.assertEqual(core.get(db,'budget-policy')['per_call_hold_cents'],50)

if __name__=='__main__':unittest.main()
