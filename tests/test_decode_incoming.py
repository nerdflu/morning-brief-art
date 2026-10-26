import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

spec = importlib.util.spec_from_file_location('decoder', Path(__file__).resolve().parents[1] / 'scripts/decode_incoming.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'incoming').mkdir()
        buf = io.BytesIO()
        Image.new('RGB', (1200, 600), 'white').save(buf, format='PNG')
        self.valid = base64.b64encode(buf.getvalue())
    def tearDown(self):
        self.tmp.cleanup()
    def source(self, name, data):
        path = self.root / 'incoming' / (name + '.b64')
        path.write_bytes(data)
        return path
    def test_bad_first_input_does_not_block_valid_later_input(self):
        bad = self.source('2026-10-22-bad', b'invalid!')
        good = self.source('2026-10-27-good', self.valid)
        self.assertEqual(d.run(self.root), 1)
        output = self.root / 'images/2026/10/2026-10-27-good.png'
        with Image.open(output) as image:
            self.assertEqual(image.size, (960, 480))
        self.assertEqual(bad.read_bytes(), b'invalid!')
        self.assertEqual(good.read_bytes(), self.valid)
        report = json.loads((self.root / '.pipeline-status/decode.json').read_text())
        self.assertEqual(report['failed'], 1)
        self.assertEqual(report['sources'][bad.name]['state'], 'failed')
    def test_invalid_image_never_overwrites_existing(self):
        self.source('2026-10-27-good', self.valid)
        self.assertEqual(d.run(self.root), 0)
        output = self.root / 'images/2026/10/2026-10-27-good.png'
        before = output.read_bytes()
        self.source('2026-10-27-good', base64.b64encode(b'not an image'))
        self.assertEqual(d.run(self.root), 1)
        self.assertEqual(before, output.read_bytes())
    def test_invalid_dates_and_names_fail_without_output(self):
        self.source('2026-02-31-impossible', self.valid)
        self.source('unsafe', self.valid)
        self.assertEqual(d.run(self.root), 1)
        self.assertFalse((self.root / 'images').exists())
    def test_encoded_limit_before_decode(self):
        source = self.source('2026-10-27-big', b'x' * 100)
        with patch.object(d, 'MAX_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'encoded_source_too_large'):
                d.decode_one(source, self.root)
    def test_pixel_limit_before_load(self):
        source = self.source('2026-10-27-big', self.valid)
        with patch.object(d, 'MAX_PIXELS', 10):
            with self.assertRaisesRegex(ValueError, 'dimensions_too_large'):
                d.decode_one(source, self.root)
    def test_rerun_is_deterministic(self):
        self.source('2026-10-27-good', self.valid)
        self.assertEqual(d.run(self.root), 0)
        files = {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(d.run(self.root), 0)
        self.assertEqual(files, {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_no_input_has_explicit_empty_report(self):
        self.assertEqual(d.run(self.root), 0)
        self.assertEqual(json.loads((self.root / '.pipeline-status/decode.json').read_text()), {'sources':{}, 'failed':0})

if __name__ == '__main__':
    unittest.main()
