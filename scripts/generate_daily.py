"""Daily generation core; use git_daily.GitStore in the proposed Actions route.

No CLI, credential lookup, scheduler, or network transport is constructed here.
Durability and serialization are supplied by the GitHub Actions GitStore adapter.
"""
import copy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import io
import json
import re

from PIL import Image, ImageOps, ImageEnhance
from check_flare_access import MODEL, PARAMETERS, validate_result
from public_prompt import validate_public_request
from display_image import derive_display

CAP_CENTS = 500


class Stopped(Exception):
    pass


def save(db, key, value):
    db.save(key, value)


def get(db, key):
    return db.get(key)


def seed_pilot(db, pilot):
    """Idempotent import; only this known pilot identity is accepted, never released."""
    if pilot.get('test_id') != 'flare-access-2026-10-26' or pilot.get('reserved_aud') != 5:
        raise Stopped('pilot_evidence_invalid')
    if not get(db, 'pilot:2026-10-26'):
        save(db, 'pilot:2026-10-26', {'month': '2026-10', 'reserved_cents': 500,
                                    'state': 'pilot_reserved', 'run_id': pilot['run_id']})


def validate_request(request):
    try:
        return validate_public_request(request)
    except (ValueError, TypeError):
        raise Stopped('invalid_or_unreviewed_public_request') from None


def generate(request, *, store, transport, publisher, pilot, clock=lambda: datetime.now(timezone.utc).date(), revision=None, panorama_test=None, source_archiver=None):
    """publisher(date, original_bytes, display_bytes, metadata) -> verified manifest.

    Publisher must archive both byte strings immutably, then publicly GET-verify
    image bytes/dimensions and manifest. It must return date, image_url,
    original_url, manifest_url and verified=True. It must not write the Sheet.
    No retry occurs here; any exception after submission permanently blocks date.
    """
    panoramic = panorama_test is not None
    day, prompt = validate_request(request)
    billing_month = clock().isoformat()[:7]
    record_key = day
    identity = request
    if revision is not None:
        expected = {'id', 'supersedes_manifest_url', 'max_reservation_cents', 'approval_reference'}
        if (not isinstance(revision, dict) or set(revision) != expected
                or not isinstance(revision['id'], str)
                or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', revision['id'])
                or len(revision['id']) > 40
                or type(revision['max_reservation_cents']) is not int
                or not 1 <= revision['max_reservation_cents'] <= CAP_CENTS
                or not isinstance(revision['approval_reference'], str)
                or not revision['approval_reference'].strip()
                or len(revision['approval_reference']) > 200):
            raise Stopped('invalid_revision_approval')
        record_key = day + ':revision:' + revision['id']
        identity = {'request': request, 'revision': revision}
    if panorama_test is not None:
        if revision is not None or not isinstance(panorama_test, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', panorama_test) or len(panorama_test) > 60:
            raise Stopped('invalid_panorama_test_identity')
        record_key = 'test:panorama-v1:' + panorama_test
        identity = {'request': request, 'format_contract': 'panorama-v1', 'test_id': panorama_test}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    with store.locked() as db:
        seed_pilot(db, pilot)
        if revision is not None:
            parent = get(db, day)
            if (not parent or parent.get('state') != 'complete'
                    or parent.get('manifest', {}).get('manifest_url') != revision['supersedes_manifest_url']):
                raise Stopped('revision_requires_completed_original')
        previous = get(db, record_key)
        if previous:
            if previous['fingerprint'] != fingerprint:
                raise Stopped('date_conflict')
            if previous['state'] == 'complete':
                return previous['manifest']
            raise Stopped('date_already_reserved_no_retry')
        # Full allowance reserved until explicit reviewed reconciliation is approved.
        # Approved policy settles only validated success with buffered estimates.
        policy = get(db, 'budget-policy')
        reserve_cents = 50 if policy and policy.get('policy_id') == 'flare-low-v1-reviewed' else CAP_CENTS
        if revision is not None:
            if revision['max_reservation_cents'] < reserve_cents:
                raise Stopped('revision_approval_below_required_reservation')
        records = db.records.values()
        reserved = sum(record['reserved_cents'] for record in records if record.get('month') == billing_month)
        if reserved + reserve_cents > CAP_CENTS:
            raise Stopped('monthly_budget_reserved')
        state = {'month': billing_month, 'date': day, 'fingerprint': fingerprint,
                 'state': 'reserved', 'reserved_cents': reserve_cents, 'model': MODEL}
        if revision is not None:
            state['revision'] = copy.deepcopy(revision)
        save(db, record_key, state)
        state['state'] = 'submitted'
        save(db, record_key, state)
        try:
            parameters = dict(PARAMETERS, prompt=prompt)
            if panoramic:
                from panorama import parameters as panorama_parameters
                parameters = panorama_parameters(request)
            response, request_id = transport.call('/images/generations', parameters)
            raw, metadata = validate_result(response, expected_size=(1872, 624) if panoramic else (1024, 1024))
            metadata['model'] = MODEL
            if isinstance(request_id, str) and len(request_id) < 120 and request_id.replace('_', '').replace('-', '').isalnum():
                metadata['request_id'] = request_id
            usage = response.get('usage', {})
            metadata['reported_usage'] = {key: usage[key] for key in ('input_tokens', 'output_tokens', 'total_tokens')
                                          if type(usage.get(key)) is int and usage[key] >= 0}
            for key in ('input_tokens_details', 'output_tokens_details'):
                details = usage.get(key)
                if isinstance(details, dict):
                    metadata['reported_usage'][key] = {name: details[name] for name in ('text_tokens', 'image_tokens', 'cached_tokens')
                                                       if type(details.get(name)) is int and details[name] >= 0}
            if panoramic:
                metadata['test_id'] = panorama_test
                state['result'] = copy.deepcopy(metadata)
                save(db, record_key, state)  # retain actual usage even if framing fails
                if source_archiver is not None:
                    source_archiver(raw, copy.deepcopy(metadata))
            display_bytes = None if panoramic else derive_display(raw, request['layout'], framing='band-fill-v1' if revision is not None else 'contain-v1')
            if panoramic:
                from panorama import derive_panorama
                display_bytes, panorama_metadata = derive_panorama(raw)
                metadata.update(panorama_metadata)
                if panorama_test is not None:
                    metadata['test_id'] = panorama_test
            if revision is not None:
                metadata.update(revision=copy.deepcopy(revision), framing='band-fill-v1')
            manifest = publisher(day, raw, display_bytes, copy.deepcopy(metadata))
            required = {'date', 'image_url', 'original_url', 'manifest_url', 'verified'}
            if not isinstance(manifest, dict) or not required.issubset(manifest) or manifest['date'] != day or manifest['verified'] is not True:
                raise Stopped('publication_not_verified')
            if panoramic and ((panorama_test is not None and manifest.get('test_id') != panorama_test)
                    or manifest.get('format_contract') != 'panorama-v1'
                    or manifest.get('width') != 1872 or manifest.get('height') != 380
                    or manifest.get('original_sha256') != hashlib.sha256(raw).hexdigest()
                    or manifest.get('display_sha256') != hashlib.sha256(display_bytes).hexdigest()):
                raise Stopped('panorama_test_publication_not_verified')
            if revision is not None and (manifest.get('revision_id') != revision['id']
                    or manifest.get('supersedes_manifest_url') != revision['supersedes_manifest_url']
                    or manifest.get('original_sha256') != hashlib.sha256(raw).hexdigest()
                    or manifest.get('display_sha256') != hashlib.sha256(display_bytes).hexdigest()):
                raise Stopped('revision_publication_not_verified')
            for field in ('image_url', 'original_url', 'manifest_url'):
                if not isinstance(manifest[field], str) or not manifest[field].startswith('https://raw.githubusercontent.com/nerdflu/morning-brief-art/'):
                    raise Stopped('publication_url_not_allowed')
            if policy and policy.get('settle_success') is True:
                # Reviewed cost estimate, not provider invoice: FX ceiling 2,
                # fees/tax factor 1.2, round UP + one cent safety buffer.
                cents = max(2, int((Decimal(str(metadata['estimated_cost_usd'])) * Decimal('240')).to_integral_value(rounding=ROUND_CEILING)) + 1)
                if cents > reserve_cents:
                    raise Stopped('cost_exceeds_reserved_envelope')
                state.update(reserved_cents=cents, original_reserved_cents=reserve_cents,
                             settlement_basis='usage_estimate_usd_x_2_fx_x_1.2_fees_tax_rounded_up_plus_1_cent',
                             invoice_verified=False)
            state.update(state='complete', manifest=manifest, result=metadata)
            save(db, record_key, state)
            return manifest
        except Exception:
            state['state'] = 'uncertain_or_needs_review'
            state['reserved_cents'] = CAP_CENTS  # freeze further spending until human reconciliation
            save(db, record_key, state)
            raise Stopped('generation_or_publication_failed_no_retry') from None
