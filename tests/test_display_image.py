import io
from pathlib import Path
import sys
import unittest
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from display_image import derive_display

class Tests(unittest.TestCase):
    def source(self, box):
        image=Image.new('RGB',(1024,1024),'white')
        ImageDraw.Draw(image).rectangle(box,fill='black')
        out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
    def test_non_school_all_marks_fit_shallow_band(self):
        for box in [(0,0,1023,1023),(0,330,1023,700),(420,0,600,1023)]:
            raw=self.source(box)
            image=Image.open(io.BytesIO(derive_display(raw,'non-school')))
            bounds=image.point(lambda v:255 if v<250 else 0).getbbox()
            self.assertEqual(image.size,(960,480));self.assertEqual(image.mode,'L')
            self.assertGreaterEqual(bounds[1],154);self.assertLessEqual(bounds[3],326)
            self.assertEqual(derive_display(raw,'non-school'),derive_display(raw,'non-school'))
    def test_school_remains_full_two_to_one(self):
        image=Image.open(io.BytesIO(derive_display(self.source((0,0,1023,1023)),'school')))
        self.assertEqual(image.size,(960,480))
        self.assertEqual(image.getpixel((480,0)),0)
    def test_blank_remains_blank(self):
        image=Image.new('RGB',(1024,1024),'white');buf=io.BytesIO();image.save(buf,format='PNG')
        output=Image.open(io.BytesIO(derive_display(buf.getvalue(),'non-school')))
        self.assertEqual(output.getextrema(),(255,255))
    def test_invalid_layout_rejected(self):
        with self.assertRaises(ValueError):derive_display(self.source((1,1,2,2)),'unknown')

if __name__=='__main__':unittest.main()
