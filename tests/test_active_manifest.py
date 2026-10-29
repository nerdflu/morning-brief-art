import copy
import hashlib
import io
from pathlib import Path
import sys
import unittest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import active_manifest as a

DAY='2026-10-30'
BASE=a.BASE+'a'*40+'/'


class ActiveManifestTests(unittest.TestCase):
    def setUp(self):
        out=io.BytesIO();Image.new('L',(960,480),255).save(out,format='PNG');self.raw=out.getvalue()
        self.manifest={'date':DAY,'image_url':BASE+'images/2026/10/'+DAY+'-revision-approved-flare.png',
            'original_url':BASE+'images/2026/10/'+DAY+'-revision-approved-flare-original.png',
            'display_sha256':hashlib.sha256(self.raw).hexdigest(),'revision_id':'approved',
            'supersedes_manifest_url':BASE+'manifests/'+DAY+'.json'}
        self.url=BASE+'manifests/'+DAY+'-revision-approved.json'
    def pointer(self):
        return a.make_pointer(DAY,self.url,self.manifest,approved_revision=True,approval_reference='owner-approved')
    def test_approved_revision_resolves_without_touching_old_canonical(self):
        original=copy.deepcopy(self.manifest)
        p=self.pointer();value=a.resolve_pointer(DAY,p,lambda url:self.manifest,lambda url:self.raw)
        self.assertEqual(value['image_url'],self.manifest['image_url']);self.assertTrue(value['verified'])
        self.assertEqual(self.manifest,original)
    def test_revision_needs_explicit_approval(self):
        with self.assertRaises(ValueError):a.make_pointer(DAY,self.url,self.manifest)
    def test_test_staged_or_wrong_date_cannot_be_selected(self):
        for change in [{'test_id':'test'},{'date':'2026-10-29'}]:
            with self.assertRaises(ValueError):a.make_pointer(DAY,self.url,dict(self.manifest,**change),approved_revision=True,approval_reference='owner')
        with self.assertRaises(ValueError):a.make_pointer(DAY,BASE+'manifests/tests/approved.json',self.manifest,approved_revision=True,approval_reference='owner')
    def test_hash_mismatch_is_not_old_canonical_fallback(self):
        p=self.pointer()
        with self.assertRaisesRegex(ValueError,'hash'):a.resolve_pointer(DAY,p,lambda url:self.manifest,lambda url:self.raw+b'changed')
    def test_unpinned_url_or_original_rejected(self):
        for image in [self.manifest['image_url'].replace('a'*40,'main'),self.manifest['original_url']]:
            with self.assertRaises(ValueError):a.validate_manifest(DAY,dict(self.manifest,image_url=image),self.raw)
    def test_legacy_dimensions_still_accepted(self):
        self.assertEqual(a.validate_manifest(DAY,self.manifest,self.raw),(960,480))
        with self.assertRaises(ValueError):a.validate_manifest(DAY,dict(self.manifest,width=1872,height=400),self.raw)
    def test_pointer_tampering_or_unknown_contract_fails_closed(self):
        p=self.pointer();p['display_sha256']='wrong'
        with self.assertRaises(ValueError):a.resolve_pointer(DAY,p,lambda url:self.manifest,lambda url:self.raw)
        with self.assertRaises(ValueError):a.validate_manifest(DAY,dict(self.manifest,format_contract='unknown'),self.raw)
