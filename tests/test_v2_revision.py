import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fixture_store import Store
from test_v2_generation import Transport,PILOT,BASE
from art_contracts import POLICY
import generate_daily as g
import git_daily as adapter
class RevisionTests(unittest.TestCase):
 def test_v2_named_revision_archives_unique_source_and_never_repeats_call(self):
  with tempfile.TemporaryDirectory() as root:
   Path(root+'/store').mkdir()
   store=Store(root+'/store');transport=Transport();p=adapter.GitPublisher(root)
   canonical=BASE+'manifests/2026-11-01.json'
   with store.locked() as db:
    db.save('budget-policy',{'policy_id':'flare-low-v1-reviewed','settle_success':True})
    db.save('2026-11-01',{'state':'complete','month':'2026-11','reserved_cents':50,'manifest':{'manifest_url':canonical}})
   before=copy.deepcopy(store.get('2026-11-01'))
   sentinel=Path(root)/'images/2026/11/2026-11-01-solo-panorama-v2-original.png';sentinel.parent.mkdir(parents=True);sentinel.write_bytes(b'original unchanged')
   req={'date':'2026-11-01','concept':'A witty pumpkin captain steers a moon boat.','style':'ink','layout':'non-school','public_safe':True}
   rev={'id':'halloween-v1','supersedes_manifest_url':canonical,'max_reservation_cents':50,'approval_reference':'fixture explicit approval'}
   def fetch(url):return (Path(root)/url.split('/'+'a'*40+'/')[1]).read_bytes()
   def run():return g.generate(req,revision=rev,format_policy=POLICY,store=store,transport=transport,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1))
   with patch.object(adapter,'commit',lambda *args:'a'*40),patch.object(p,'fetch_bytes',fetch):
    result=run();self.assertEqual(run(),result);self.assertEqual(len(transport.calls),1)
    self.assertEqual((result['width'],result['height']),(1872,400))
    self.assertIn('-revision-halloween-v1-solo-panorama-v2-original.png',result['original_url'])
    self.assertEqual(result['framing'],'solo-panorama-v2')
    self.assertEqual(result['original_sha256'],hashlib.sha256(transport.raw).hexdigest())
    self.assertFalse((Path(root)/'manifests/current/2026-11-01.json').exists())
    self.assertEqual(store.get('2026-11-01'),before);self.assertEqual(sentinel.read_bytes(),b'original unchanged')
    req['concept']='A different pumpkin captain steers a moon boat.'
    with self.assertRaisesRegex(g.Stopped,'date_conflict'):run()
    self.assertEqual(len(transport.calls),1)
if __name__=='__main__':unittest.main()
