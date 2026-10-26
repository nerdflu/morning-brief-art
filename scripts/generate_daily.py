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


def generate(request, *, store, transport, publisher, pilot, clock=lambda: datetime.now(timezone.utc).date()):
    """publisher(date, original_bytes, display_bytes, metadata) -> verified manifest.

    Publisher must archive both byte strings immutably, then publicly GET-verify
    image bytes/dimensions and manifest. It must return date, image_url,
    original_url, manifest_url and verified=True. It must not write the Sheet.
    No retry occurs here; any exception after submission permanently blocks date.
    """
    day, prompt = validate_request(request)
    billing_month = clock().isoformat()[:7]
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    with store.locked() as db:
        seed_pilot(db, pilot)
        previous = get(db, day)
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
        records = db.records.values()
        reserved = sum(record['reserved_cents'] for record in records if record.get('month') == billing_month)
        if reserved + reserve_cents > CAP_CENTS:
            raise Stopped('monthly_budget_reserved')
        state = {'month': billing_month, 'date': day, 'fingerprint': fingerprint,
                 'state': 'reserved', 'reserved_cents': reserve_cents, 'model': MODEL}
        save(db, day, state)
        state['state'] = 'submitted'
        save(db, day, state)
        try:
            parameters = dict(PARAMETERS, prompt=prompt)
            response, request_id = transport.call('/images/generations', parameters)
            raw, metadata = validate_result(response)
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
            display_bytes = derive_display(raw, request['layout'])
            manifest = publisher(day, raw, display_bytes, copy.deepcopy(metadata))
            required = {'date', 'image_url', 'original_url', 'manifest_url', 'verified'}
            if not isinstance(manifest, dict) or not required.issubset(manifest) or manifest['date'] != day or manifest['verified'] is not True:
                raise Stopped('publication_not_verified')
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
            save(db, day, state)
            return manifest
        except Exception:
            state['state'] = 'uncertain_or_needs_review'
            state['reserved_cents'] = CAP_CENTS  # freeze further spending until human reconciliation
            save(db, day, state)
            raise Stopped('generation_or_publication_failed_no_retry') from None
