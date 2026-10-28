"""Verify revision bytes, then CAS the explicitly selected row through an adapter.

No credentials or default Sheet transport. The adapter MUST provide atomic
compare_and_swap(row_id, expected_row, replacement_row), then read(row_id).
Never substitute append or an unchecked write for this contract.
"""
import copy
import hashlib
import io
import json
import re
import urllib.request
from PIL import Image
from generate_daily import Stopped


def archive_url(value):
    return isinstance(value, str) and re.fullmatch(
        r'https://raw\.githubusercontent\.com/nerdflu/morning-brief-art/[0-9a-f]{40}/(?:images/\d{4}/\d{2}/[a-z0-9-]+\.png|manifests/[a-z0-9-]+\.json)', value)


def verify_manifest(result, fetch=None):
    if result.get('verified') is not True:
        raise Stopped('unverified_revision')
    def public_get(url):
        if not archive_url(url):
            raise Stopped('non_immutable_archive_url')
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.geturl() != url:
                raise Stopped('archive_redirect_rejected')
            return response.read(20_000_001)
    get = fetch or public_get
    url = result.get('manifest_url')
    if not archive_url(url):
        raise Stopped('non_immutable_archive_url')
    manifest = json.loads(get(url))
    expected = {k: v for k, v in result.items() if k not in ('manifest_url', 'verified')}
    if manifest != expected or not manifest.get('revision_id'):
        raise Stopped('revision_manifest_mismatch')
    for field, hash_field, size in [('original_url', 'original_sha256', (1024, 1024)), ('image_url', 'display_sha256', (960, 480))]:
        if not archive_url(manifest.get(field)):
            raise Stopped('non_immutable_archive_url')
        raw = get(manifest[field])
        if hashlib.sha256(raw).hexdigest() != manifest.get(hash_field):
            raise Stopped('revision_hash_mismatch')
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.size != size:
                raise Stopped('revision_dimensions_mismatch')
    return manifest


def switch_same_row(adapter, row_id, expected_row, original_manifest, result, *, fetch=None):
    manifest = verify_manifest(result, fetch)
    if (manifest.get('supersedes_manifest_url') != original_manifest.get('manifest_url')
            or manifest.get('date') != original_manifest.get('date')):
        raise Stopped('revision_original_mismatch')
    replacement = copy.deepcopy(expected_row)
    if replacement.get('image_url') != original_manifest.get('image_url'):
        raise Stopped('row_original_image_mismatch')
    payload = json.loads(replacement['payload_json'])
    # hero_image takes precedence in Liquid; update it only when it references
    # the superseded image. Never silently replace another selected hero.
    for field in ('hero_image', 'image_url'):
        if payload.get(field) and payload[field] != original_manifest['image_url']:
            raise Stopped('row_has_different_image')
        if payload.get(field):
            payload[field] = manifest['image_url']
    replacement['image_url'] = manifest['image_url']
    replacement['payload_json'] = json.dumps(payload, separators=(',', ':'))
    if not adapter.compare_and_swap(row_id, expected_row, replacement):
        raise Stopped('row_changed_no_switch')
    if adapter.read(row_id) != replacement:
        raise Stopped('row_switch_outcome_uncertain_inspect_no_retry')
    return replacement
