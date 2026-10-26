import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import git_daily as g

class Tests(unittest.TestCase):
    def setUp(self):
        self.event={'ref':'refs/heads/main','repository':{'full_name':g.REPO},'before':'a'*40,'after':'b'*40}
        self.request={'date':'2026-10-27','concept':'A geometric olive parade','style':'ink','layout':'school','public_safe':True}
        self.calls=[]
    def cmd(self,root,*args):
        self.calls.append(args)
        if args[0]=='diff': return 'requests/2026-10-27.json\0'
        if args[0]=='show': return json.dumps(self.request)
        return ''
    def test_resolves_only_event_added_modified_request(self):
        with patch.object(g,'command',self.cmd):
            self.assertEqual(g.resolve_request('.', 'push', self.event),self.request)
        self.assertIn('--diff-filter=AM',self.calls[2])
        self.assertEqual(self.calls[-1],('show','b'*40+':requests/2026-10-27.json'))
    def test_no_reprocessing_historical_or_multiple_requests(self):
        for diff in ('','requests/2026-10-27.json\0requests/2026-10-28.json\0'):
            with patch.object(g,'command',lambda root,*args: diff if args[0]=='diff' else ''):
                with self.assertRaisesRegex(g.Stopped,'exactly_one'): g.resolve_request('.','push',self.event)
    def test_filename_date_must_match(self):
        self.request['date']='2026-10-28'
        with patch.object(g,'command',self.cmd):
            with self.assertRaisesRegex(g.Stopped,'mismatch'):g.resolve_request('.','push',self.event)
    def test_invalid_sha_no_git(self):
        self.event['after']='main; echo dangerous'
        with patch.object(g,'command',self.cmd):
            with self.assertRaises(g.Stopped):g.resolve_request('.','push',self.event)
        self.assertEqual(self.calls,[])
    def test_manual_contract_is_bounded(self):
        self.assertEqual(g.resolve_request('.','workflow_dispatch',{},json.dumps(self.request)),self.request)
        with self.assertRaises(g.Stopped):g.resolve_request('.','workflow_dispatch',{},'x'*2001)

if __name__=='__main__':unittest.main()
