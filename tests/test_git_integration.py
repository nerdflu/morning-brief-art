"""Real local bare-Git round trip; fake API and fake public GET only."""
import base64
from datetime import date
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import git_daily as git
from generate_daily import generate, Stopped


def command(cwd, *args):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base/'remote.git'
        self.root = self.base/'working'
        command(self.base, 'init', '--bare', '--initial-branch=main', str(self.remote))
        command(self.base, 'clone', str(self.remote), str(self.root))
        (self.root/'README.md').write_text('fixture\n')
        command(self.root, 'add', '.')
        command(self.root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'initial')
        command(self.root, 'push', 'origin', 'main')
        self.pilot=json.loads((Path(__file__).resolve().parents[1]/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
    def tearDown(self):
        self.tmp.cleanup()
    def fake_public_get(self, url, timeout):
        # No actual public/network requests; read the committed immutable blob.
        components=url.split('/')
        sha=components[5]; path='/'.join(components[6:])
        raw=subprocess.run(['git','show',sha+':'+path],cwd=self.remote,capture_output=True,check=True).stdout
        return io.BytesIO(raw)
    def test_git_end_to_end_reserves_remotely_then_publishes_and_is_idempotent(self):
        outer=self
        class Transport:
            calls=0
            def call(self, path, body):
                self.calls+=1
                ledger=json.loads(command(outer.remote,'show','main:'+git.LEDGER))
                outer.assertEqual(ledger['2026-11-01']['state'],'submitted')
                buf=io.BytesIO();Image.new('RGB',(1024,1024),'white').save(buf,format='PNG')
                return {'data':[{'b64_json':base64.b64encode(buf.getvalue()).decode()}], 'usage':{'input_tokens':29,'output_tokens':196}},'fixture-request'
        transport=Transport()
        with patch.dict(git.os.environ, {'ART_GLOBAL_LOCK':'morning-brief-art-writer','GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'nerdflu/morning-brief-art','GITHUB_REF':'refs/heads/main'}), patch.object(git.urllib.request,'urlopen',self.fake_public_get):
            args=dict(store=git.GitStore(self.root),transport=transport,publisher=git.GitPublisher(self.root),pilot=self.pilot,clock=lambda:date(2026,11,1))
            result=generate({'date':'2026-11-01','concept':'A lighthouse with enormous origami sails.', 'style':'woodcut','layout':'non-school','public_safe':True},**args)
            self.assertTrue(result['verified'])
            result2=generate({'date':'2026-11-01','concept':'A lighthouse with enormous origami sails.', 'style':'woodcut','layout':'non-school','public_safe':True},**args)
            self.assertEqual(result,result2)
            self.assertEqual(transport.calls,1)
        ledger=json.loads(command(self.remote,'show','main:'+git.LEDGER))
        self.assertEqual(ledger['2026-11-01']['state'],'complete')
    def test_unreachable_remote_stops_before_paid_call(self):
        command(self.root,'remote','set-url','origin',str(self.base/'nonexistent.git'))
        class NoCalls:
            def call(*args):raise AssertionError('paid call must not happen')
        with patch.dict(git.os.environ, {'ART_GLOBAL_LOCK':'morning-brief-art-writer','GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'nerdflu/morning-brief-art','GITHUB_REF':'refs/heads/main'}):
            with self.assertRaises(Stopped):
                generate({'date':'2026-11-01','concept':'A lighthouse with enormous origami sails.', 'style':'woodcut','layout':'non-school','public_safe':True},store=git.GitStore(self.root),transport=NoCalls(),publisher=None,pilot=self.pilot,clock=lambda:date(2026,11,1))

if __name__=='__main__':unittest.main()
