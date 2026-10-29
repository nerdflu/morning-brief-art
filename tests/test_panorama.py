from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import io
import unittest
from PIL import Image, ImageDraw
from panorama import derive_panorama, parameters


def fixture(size=(1872, 624), outside=False, narrow=False):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    draw.line((100, 200, 1700 if not narrow else 500, 400), fill=(170,170,170), width=1)
    if outside:
        draw.point((900, 20), fill='black')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class PanoramaTests(unittest.TestCase):
    def test_exact_dimensions_full_scene_and_fine_gray_retained(self):
        raw = fixture()
        display, manifest = derive_panorama(raw)
        image = Image.open(io.BytesIO(display))
        self.assertEqual(image.size, (1872, 380))
        self.assertEqual(image.getpixel((100, 78)), 170)
        self.assertEqual(image.getpixel((1700, 278)), 170)
        self.assertEqual(manifest['source_band'], [0,122,1872,502])
        self.assertEqual(raw, fixture())

    def test_refuses_subject_loss_and_tiny_scene(self):
        for raw in (fixture(outside=True), fixture(narrow=True), fixture((1024,1024))):
            with self.assertRaises(ValueError):
                derive_panorama(raw)

    def test_unchanged_request_and_explicit_supported_source(self):
        request = dict(date='2026-10-30', concept='A moonlit library sailing between cloud islands.',
                       style='ink', layout='school', public_safe=True)
        before = request.copy()
        settings = parameters(request)
        self.assertEqual(request, before)
        self.assertEqual(settings['size'], '1872x624')
        self.assertEqual(settings['n'], 1)
        self.assertEqual(settings['quality'], 'low')
        self.assertIn('COMPLETE scene', settings['prompt'])


if __name__ == '__main__':
    unittest.main()
