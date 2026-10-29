import io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import git_daily as g
from art_contracts import derive
class PublisherTests(unittest.TestCase):
 def test_publication_fetches_exact_bytes_and_selects_immutable_manifest(self):
  for layout,size in [('school',(1536,768)),('non-school',(1872,624))]:
   with self.subTest(layout=layout),tempfile.TemporaryDirectory() as root:
    im=Image.new('L',size,255)
    for x in range(40,size[0]-40): im.putpixel((x,300),0)
    buf=io.BytesIO();im.save(buf,'PNG');raw=buf.getvalue();display,metadata=derive(raw,layout)
    publisher=g.GitPublisher(root);calls=[]
    def commit(root,paths,message): calls.append(paths);return 'a'*40
    def fetch(url): return (Path(root)/url.split('/'+'a'*40+'/')[1]).read_bytes()
    with patch.object(g,'commit',commit),patch.object(publisher,'fetch_bytes',fetch):
     metadata['archived_original_url']=publisher.archive_original('2026-11-01',raw,metadata)
     result=publisher('2026-11-01',raw,display,metadata)
     selected=publisher.current_for('2026-11-01',{})
     self.assertEqual(selected['image_url'],result['image_url'])
     self.assertEqual(selected['display_sha256'],result['display_sha256'])
     before=(Path(root)/'manifests/current/2026-11-01.json').read_bytes()
     publisher.publish_current('2026-11-01',result['manifest_url'],result)
     self.assertEqual(before,(Path(root)/'manifests/current/2026-11-01.json').read_bytes())
     self.assertEqual(len(calls),4)
     with self.assertRaisesRegex(g.Stopped,'manifest_conflict'):publisher('2026-11-01',raw,display,metadata)
if __name__=='__main__':unittest.main()
