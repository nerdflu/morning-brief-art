import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

spec=importlib.util.spec_from_file_location('pilot',Path(__file__).resolve().parents[1]/'scripts/check_flare_access.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def response(size=(1024,1024),model=p.MODEL,usage=None):
    image=Image.new('RGB',size,'white');buf=io.BytesIO();image.save(buf,format='PNG')
    return {'model':model,'data':[{'b64_json':base64.b64encode(buf.getvalue()).decode()}],
            'usage':usage if usage is not None else {'input_tokens':32,'output_tokens':196,'input_tokens_details':{'image_tokens':0,'text_tokens':32}}}


class Fake:
    def __init__(self,result=None,error=None,metadata=None):self.calls=[];self.result=result or response();self.error=error;self.metadata=metadata or p.MODEL
    def call(self,path,body=None):
        self.calls.append((path,body))
        if body is None:return {'id':self.metadata},None
        if self.error:raise self.error
        return self.result,'req_fixture'


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.states=[]
    def tearDown(self):self.temp.cleanup()
    def persist(self,state):
        self.states.append(copy.deepcopy(state));target=self.root/p.LEDGER;target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(state))
    def run_pilot(self,fake,attempt='1',persist=None):return p.run_pilot(self.root,fake,persist or self.persist,'123',attempt)
    def test_happy_path_single_call_and_png(self):
        f=Fake();r=self.run_pilot(f)
        self.assertEqual([x['state']for x in self.states],['reserved','submitted','complete'])
        self.assertEqual(r['width'],1024);self.assertEqual(r['estimated_cost_usd'],.00604)
        self.assertEqual(f.calls[1][1],p.PARAMETERS);self.assertTrue((self.root/'test-artifacts/flare-test.png').exists())
    def test_second_dispatch_stops_before_any_network(self):
        self.run_pilot(Fake());f=Fake()
        with self.assertRaisesRegex(p.PilotError,'already_reserved'):self.run_pilot(f)
        self.assertEqual(f.calls,[])
    def test_actions_rerun_stops(self):
        f=Fake()
        with self.assertRaisesRegex(p.PilotError,'rerun_not_allowed'):self.run_pilot(f,attempt='2')
        self.assertEqual(f.calls,[])
    def test_metadata_mismatch_never_generates(self):
        f=Fake(metadata='other-model')
        with self.assertRaisesRegex(p.PilotError,'metadata_mismatch'):self.run_pilot(f)
        self.assertEqual(len(f.calls),1)
    def test_reservation_failure_never_generates(self):
        def fail(s):raise p.PilotError('persist_failed')
        f=Fake()
        with self.assertRaisesRegex(p.PilotError,'persist_failed'):self.run_pilot(f,persist=fail)
        self.assertEqual(len(f.calls),1)
    def test_submitted_persistence_failure_never_generates(self):
        def fail(s):
            if s['state']=='submitted':raise p.PilotError('persist_failed')
            self.persist(s)
        f=Fake()
        with self.assertRaisesRegex(p.PilotError,'persist_failed'):self.run_pilot(f,persist=fail)
        self.assertEqual(len(f.calls),1)
    def test_ambiguous_timeout_retains_reservation_and_never_retries(self):
        f=Fake(error=TimeoutError())
        with self.assertRaisesRegex(p.PilotError,'outcome_unknown'):self.run_pilot(f)
        self.assertEqual(len(f.calls),2);self.assertEqual(self.states[-1]['state'],'uncertain');self.assertEqual(self.states[-1]['reserved_aud'],5)
        with self.assertRaises(p.PilotError):self.run_pilot(Fake())
    def test_http_failure_never_retries(self):
        f=Fake(error=p.ApiError(429))
        with self.assertRaises(p.ApiError):self.run_pilot(f)
        self.assertEqual(len(f.calls),2)
    def test_bad_image_no_publication(self):
        f=Fake(result={'data':[{'b64_json':'not_base64'}]})
        with self.assertRaisesRegex(p.PilotError,'invalid_image'):self.run_pilot(f)
        self.assertFalse((self.root/'test-artifacts/flare-test.png').exists())
    def test_wrong_dimensions_stop(self):
        with self.assertRaisesRegex(p.PilotError,'dimensions'):self.run_pilot(Fake(result=response((32,32))))
    def test_unexpected_model_stops(self):
        with self.assertRaisesRegex(p.PilotError,'unexpected_model'):self.run_pilot(Fake(result=response(model='other-model')))
    def test_missing_usage_stops(self):
        r=response();r.pop('usage')
        with self.assertRaisesRegex(p.PilotError,'usage_missing'):self.run_pilot(Fake(result=r))
    def test_excess_usage_stops(self):
        with self.assertRaisesRegex(p.PilotError,'unexpected_usage_or_cost'):self.run_pilot(Fake(result=response(usage={'input_tokens':1,'output_tokens':9000})))
    def test_result_contains_no_bytes_or_auth(self):
        r=self.run_pilot(Fake());text=json.dumps(r)
        for forbidden in ['b64_json','Authorization','Bearer','OPENAI_API_KEY']:self.assertNotIn(forbidden,text)
    def test_only_allowed_endpoints(self):
        with self.assertRaisesRegex(p.PilotError,'unsupported_endpoint'):p.OpenAITransport('fixture').call('/other')

if __name__=='__main__':unittest.main()

