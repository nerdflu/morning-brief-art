import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from public_prompt import validate_public_request

class Tests(unittest.TestCase):
    def request(self, **updates):
        return dict({'date':'2026-10-27','concept':'A surreal orchestra of dancing olive branches beneath festival bunting.', 'style':'linocut','layout':'non-school','public_safe':True}, **updates)
    def test_arbitrary_public_concepts_and_crop_contract(self):
        day,prompt=validate_public_request(self.request())
        self.assertEqual(day,'2026-10-27');self.assertIn('5.1:1',prompt)
        self.assertIn('2:1',validate_public_request(self.request(layout='school'))[1])
        self.assertIn('No text, people, cats or dogs',prompt)
    def test_private_or_unreviewed_or_contact_input_rejected(self):
        for updates in [{'public_safe':False},{'concept':'A child taking medication'}, {'concept':'Call me at +61412345678'}, {'concept':'A cat running through flowers'}, {'concept':'Email hello@example.com'}, {'concept':'A dog and a kite'}]:
            with self.assertRaises(ValueError):validate_public_request(self.request(**updates))
    def test_bounded_fields(self):
        for updates in [{'concept':'x'*281},{'concept':'hello\nworld'}, {'style':'custom'}, {'date':'2026-02-31'}, {'layout':'other'}, {'concept':'A scene '+chr(233)}]:
            with self.assertRaises(ValueError):validate_public_request(self.request(**updates))
        request=self.request();request['brief']='never forward the brief'
        with self.assertRaises(ValueError):validate_public_request(request)

if __name__=='__main__':unittest.main()
