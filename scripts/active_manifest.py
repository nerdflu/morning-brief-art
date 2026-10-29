"""Active selection never overwrites immutable daily/revision manifests."""
import hashlib
import io
import re
from PIL import Image
from art_contracts import expected

BASE='https://raw.githubusercontent.com/nerdflu/morning-brief-art/'
PINNED=re.compile(r'^'+re.escape(BASE)+r'[0-9a-f]{40}/(.+)$')


def path(url):
    m=PINNED.fullmatch(url or '')
    if not m or '..' in m[1].split('/') or '?' in m[1] or '#' in m[1]:
        raise ValueError('immutable_allowed_url_required')
    return m[1]


def validate_manifest(day, manifest, image_bytes, layout=None):
    if manifest.get('date')!=day or manifest.get('test_id'):
        raise ValueError('date_or_test_manifest_rejected')
    p=path(manifest.get('image_url'))
    if not p.startswith('images/'+day[:4]+'/'+day[5:7]+'/'+day) or '/tests/' in p:
        raise ValueError('date_scoped_display_required')
    if p.endswith('-original.png'):
        raise ValueError('original_is_not_display')
    size=expected(manifest)
    if ('width' in manifest or 'height' in manifest) and (manifest.get('width'),manifest.get('height'))!=size:
        raise ValueError('declared_dimensions_mismatch')
    if layout and manifest.get('layout') and layout!=manifest['layout']:
        raise ValueError('layout_mismatch')
    fmt=manifest.get('format_contract','legacy-v1')
    if (fmt=='school-2x1-v2' and not p.endswith('-school-v2.png')) or (fmt=='solo-panorama-v2' and not p.endswith('-solo-panorama-v2.png')):
        raise ValueError('versioned_path_mismatch')
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.format!='PNG' or im.size!=size:
            raise ValueError('public_png_contract_mismatch')
    if hashlib.sha256(image_bytes).hexdigest()!=manifest.get('display_sha256'):
        raise ValueError('public_png_hash_mismatch')
    return size


def make_pointer(day, manifest_url, manifest, *, approval_reference='', approved_revision=False):
    mp=path(manifest_url)
    revision=manifest.get('revision_id')
    if revision is not None and (not isinstance(revision,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',revision) or len(revision)>40):
        raise ValueError('invalid_revision_id')
    wanted='manifests/'+day+('-revision-'+revision if revision else '')+'.json'
    if mp!=wanted or manifest.get('date')!=day or manifest.get('test_id'):
        raise ValueError('date_manifest_required')
    if revision and (not approved_revision or not approval_reference.strip()):
        raise ValueError('reviewed_revision_approval_required')
    if revision and path(manifest.get('supersedes_manifest_url'))!='manifests/'+day+'.json':
        raise ValueError('completed_original_link_required')
    return {'date':day,'source':'approved-revision' if revision else 'daily',
            'manifest_url':manifest_url,'revision_id':revision,
            'display_sha256':manifest['display_sha256'],
            'format_contract':manifest.get('format_contract','legacy-v1'),
            'width':expected(manifest)[0],'height':expected(manifest)[1],
            **({'approval_reference':approval_reference} if revision else {})}


def resolve_pointer(day,pointer,fetch_manifest,fetch_image):
    if pointer.get('date')!=day or pointer.get('source') not in ('daily','approved-revision'):
        raise ValueError('active_pointer_identity_invalid')
    manifest=fetch_manifest(pointer.get('manifest_url'))
    rebuilt=make_pointer(day,pointer['manifest_url'],manifest,
        approved_revision=pointer.get('source')=='approved-revision',
        approval_reference=pointer.get('approval_reference',''))
    if rebuilt!=pointer:
        raise ValueError('active_pointer_does_not_match_manifest')
    validate_manifest(day,manifest,fetch_image(manifest['image_url']))
    return dict(manifest,manifest_url=pointer['manifest_url'],verified=True)
