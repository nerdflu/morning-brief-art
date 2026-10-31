import base64,copy,hashlib,io,json,sys,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw,ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import art_contracts as c
import git_daily as gd
import generate_daily as g
from fixture_store import Store
from test_v2_generation import Transport,Publisher,PILOT,BASE

def png(size,blank=False):
 im=Image.new('RGB',size,'white')
 if not blank:ImageDraw.Draw(im).rectangle((20,20,size[0]-20,size[1]-20),fill=(130,100,170))
 b=io.BytesIO();im.save(b,'PNG');return b.getvalue()

class NativePublisher(Publisher):
 def __call__(self,day,raw,display,metadata):
  m=super().__call__(day,raw,display,metadata)
  m['image_url']=m['image_url'].replace('solo-panorama-v2','landscape-cover-v3')
  return m

class LandscapeTests(unittest.TestCase):
 def test_native_and_off_ratio_scenes_keep_all_pixels_without_canvas_padding(self):
  for size in [(1872,624),(1536,768),(1600,1000),(1000,800),(1600,400)]:
   raw=png(size);before=hashlib.sha256(raw).hexdigest();out,m=c.derive(raw,'solo',c.LANDSCAPE_POLICY)
   expected=ImageOps.grayscale(Image.open(io.BytesIO(raw)))
   actual=Image.open(io.BytesIO(out));self.assertEqual(actual.size,size);self.assertEqual(actual.tobytes(),expected.tobytes())
   self.assertEqual(m['source_crop_bounds'],[0,0,*size]);self.assertEqual(c.expected(m),size)
   self.assertNotIn('paste_xy',m);self.assertNotIn('fit_size',m);self.assertEqual(hashlib.sha256(raw).hexdigest(),before)
 def test_invalid_or_blank_scene_still_stops_without_a_retry(self):
  for size,blank in [((624,1872),False),((100,50),False),((1872,624),True)]:
   with self.assertRaises(ValueError):c.derive(png(size,blank),'solo',c.LANDSCAPE_POLICY)
 def test_wide_request_removes_internal_strip_but_school_stays_byte_compatible(self):
  r={'date':'2026-11-01','concept':'A sculptural cloud over rooftops.','style':'ink','layout':'solo','public_safe':True}
  p=c.parameters(r,c.LANDSCAPE_POLICY);self.assertEqual(p['size'],'1872x624');self.assertNotIn('y=104',p['prompt']);self.assertIn('whole',p['prompt'])
  r['layout']='school';self.assertEqual(c.parameters(r),c.parameters(r,c.LANDSCAPE_POLICY))
  raw=png((1536,768));self.assertEqual(c.derive(raw,'school'),c.derive(raw,'school',c.LANDSCAPE_POLICY))
 def test_public_archive_pointer_verifies_native_dimensions_and_immutability(self):
  with tempfile.TemporaryDirectory() as root:
   raw=png((1536,768));display,m=c.derive(raw,'solo',c.LANDSCAPE_POLICY);p=gd.GitPublisher(root)
   def commit(*args):return 'a'*40
   def fetch(url):return (Path(root)/url.split('/'+'a'*40+'/')[1]).read_bytes()
   with patch.object(gd,'commit',commit),patch.object(p,'fetch_bytes',fetch):
    m['archived_original_url']=p.archive_original('2026-11-01',raw,m);result=p('2026-11-01',raw,display,m)
    self.assertTrue(result['image_url'].endswith('-landscape-cover-v3.png'));self.assertEqual(p.current_for('2026-11-01',{}),result)
    with self.assertRaises(g.Stopped):p('2026-11-01',raw,display,m)
 def test_daily_duplicate_uncertain_and_completed_revision_guards_remain(self):
  with tempfile.TemporaryDirectory() as root:
   store=Store(root);t=Transport();p=NativePublisher();r={'date':'2026-11-01','concept':'A large original accordion cloud above rooftops.','style':'ink','layout':'solo','public_safe':True}
   def run():return g.generate(r,store=store,transport=t,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=c.LANDSCAPE_POLICY)
   first=run();self.assertEqual((first['width'],first['height']),(1872,624));self.assertEqual(run(),first);self.assertEqual(len(t.calls),1)
   p.selected=dict(first,revision_id='approved');self.assertEqual(run(),p.selected);self.assertEqual(len(t.calls),1)
  with tempfile.TemporaryDirectory() as root:
   store=Store(root);t=Transport();t.failure=TimeoutError();p=NativePublisher()
   for _ in range(2):
    with self.assertRaises(g.Stopped):g.generate(r,store=store,transport=t,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=c.LANDSCAPE_POLICY)
   self.assertEqual(len(t.calls),1);self.assertEqual(store.get('2026-11-01')['reserved_cents'],500)
 def test_activation_config_uses_a_supported_reviewed_policy(self):
  policy=json.loads((Path(__file__).resolve().parents[1]/'.pipeline/art-policy.json').read_text())
  self.assertEqual(set(policy),{'policy_id','enabled'});self.assertIn(policy['policy_id'],c.POLICIES);self.assertIs(type(policy['enabled']),bool)
 def test_old_layouts_are_byte_compatible_and_solo_requires_enabled_policy(self):
  from public_prompt import validate_public_request
  for layout,size in [('school',(1536,768)),('non-school',(1872,624))]:
   r={'date':'2026-11-01','concept':'A sculptural cloud above rooftops.','style':'ink','layout':layout,'public_safe':True}
   self.assertEqual(c.parameters(r),c.parameters(r,c.LANDSCAPE_POLICY))
   self.assertEqual(c.derive(png(size),layout),c.derive(png(size),layout,c.LANDSCAPE_POLICY))
  r['layout']='solo';validate_public_request(r)
  for policy in [None,c.POLICY]:
   with tempfile.TemporaryDirectory() as root:
    store=Store(root);t=Transport()
    with self.assertRaisesRegex(g.Stopped,'solo_requires'):g.generate(r,store=store,transport=t,publisher=NativePublisher(),pilot=PILOT,format_policy=policy)
    self.assertEqual(t.calls,[]);self.assertFalse(store.path.exists())
  with self.assertRaises(ValueError):validate_public_request(dict(r,mode='solo'))
 def test_native_manifest_rejects_wrong_layout_size_or_hash(self):
  from active_manifest import validate_manifest
  raw=png((1600,1000));out,m=c.derive(raw,'solo',c.LANDSCAPE_POLICY)
  m.update(date='2026-11-01',image_url=BASE+'images/2026/11/2026-11-01-landscape-cover-v3.png',display_sha256=hashlib.sha256(out).hexdigest())
  self.assertEqual(validate_manifest('2026-11-01',m,out,layout='solo'),(1600,1000))
  for change in [{'layout':'non-school'},{'width':1599},{'display_sha256':'bad'}]:
   with self.assertRaises(ValueError):validate_manifest('2026-11-01',dict(m,**change),out,layout='solo')
 def test_off_ratio_provider_result_publishes_actual_size_and_cancel_cannot_retry(self):
  r={'date':'2026-11-01','concept':'A large sculptural cloud above rooftops.','style':'ink','layout':'solo','public_safe':True}
  class OffRatio(Transport):
   def call(self,path,body):
    self.calls.append(body);self.raw=png((1536,768))
    return {'data':[{'b64_json':base64.b64encode(self.raw).decode()}],'usage':{'input_tokens':300,'output_tokens':196}},None
  with tempfile.TemporaryDirectory() as root:
   t=OffRatio();p=NativePublisher();result=g.generate(r,store=Store(root),transport=t,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=c.LANDSCAPE_POLICY)
   self.assertEqual((result['width'],result['height']),(1536,768));self.assertEqual(p.sources,[t.raw]);self.assertEqual(len(t.calls),1)
  with tempfile.TemporaryDirectory() as root:
   store=Store(root);t=Transport();t.failure=KeyboardInterrupt();p=NativePublisher()
   with self.assertRaises(KeyboardInterrupt):g.generate(r,store=store,transport=t,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=c.LANDSCAPE_POLICY)
   self.assertEqual(store.get('2026-11-01')['state'],'submitted');self.assertEqual(store.get('2026-11-01')['reserved_cents'],500)
   with self.assertRaises(g.Stopped):g.generate(r,store=store,transport=t,publisher=p,pilot=PILOT,clock=lambda:date(2026,11,1),format_policy=c.LANDSCAPE_POLICY)
   self.assertEqual(len(t.calls),1)
if __name__=='__main__':unittest.main()
