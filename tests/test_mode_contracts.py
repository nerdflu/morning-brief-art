import hashlib
import io
from pathlib import Path
import sys
import unittest
from PIL import Image,ImageDraw,ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import art_contracts as c


def png(size, box=None):
    im=Image.new('RGB',size,'white')
    if box: ImageDraw.Draw(im).rectangle(box,fill=(120,120,120))
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()


class ModeContractTests(unittest.TestCase):
    def request(self,layout='school',style='ink'):
        return {'date':'2026-11-01','concept':'A large expressive moon creature offers a star to a paper bird.',
                'style':style,'layout':layout,'public_safe':True}
    def test_source_parameters_and_bounded_reference_direction(self):
        for layout,size in [('school','1536x768'),('non-school','1872x624')]:
            p=c.parameters(self.request(layout))
            self.assertEqual((p['size'],p['quality'],p['n']),(size,'low',1))
            self.assertIn('One dominant expressive',p['prompt'])
            self.assertIn('selective medium-scale',p['prompt'].lower())
            self.assertLessEqual(len(p['prompt'].encode()),1800)
        p=c.parameters(self.request(style='paper-cut'))
        self.assertNotIn('Graphic paper-cut shapes',p['prompt'])
    def test_school_preserves_entire_native_scene_and_gray_lines(self):
        raw=png((1536,768),(20,20,1515,747));out,meta=c.derive(raw,'school')
        im=Image.open(io.BytesIO(out))
        self.assertEqual(im.size,(960,480));self.assertEqual(im.getpixel((100,100)),120)
        self.assertEqual(meta['source_crop_bounds'],[0,0,1536,768])
        self.assertEqual(meta['format_contract'],'school-2x1-v2')
    def test_solo_complete_window_and_grays_unmodified(self):
        raw=png((1872,624),(80,115,1790,495));out,meta=c.derive(raw,'non-school')
        im=Image.open(io.BytesIO(out));self.assertEqual(im.size,(1872,400))
        self.assertEqual(im.tobytes(),ImageOps.grayscale(Image.open(io.BytesIO(raw))).crop(tuple(meta['source_crop_bounds'])).tobytes())
        self.assertEqual(im.getpixel((100,100)),120)
    def test_tall_or_narrow_scene_never_destructively_cropped(self):
        for box in [(80,20,1790,610),(800,115,1000,495)]:
            with self.assertRaises(ValueError):c.derive(png((1872,624),box),'non-school')
    def test_wrong_source_and_private_input_fail(self):
        with self.assertRaises(ValueError):c.derive(png((1024,1024)),'school')
        r=self.request();r['concept']='A child taking medication'
        with self.assertRaises(ValueError):c.parameters(r)
    def test_published_recovered_fixture_is_geometry_only_not_style_approval(self):
        source=Path(__file__).resolve().parents[1]/'images/tests/editorial-panorama-v1/panorama-v1-original.png'
        raw=source.read_bytes();out,meta=c.derive(raw,'non-school')
        self.assertEqual(meta['source_crop_bounds'],[0,104,1872,504])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'52aadfd6ef77a2b034dd12b69aeee557dbb90462d0ab772e9eb618ea4145f051')
