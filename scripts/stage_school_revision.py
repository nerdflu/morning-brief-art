"""One owner-approved school revision, staged for human visual review.

No default workflow, production request, Sheet, prompt or template is modified.
The original is archived before review; display publication is a separate action.
"""
import base64
import copy
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo
from check_flare_access import MODEL, OpenAITransport, validate_result
from generate_daily import Stopped, CAP_CENTS
from git_daily import GitStore, REPO, commit
from public_prompt import validate_public_request

DAY = '2026-10-30'
REVISION_ID = 'school-reference-redo-v1'
KEY = DAY+':revision:'+REVISION_ID
HOLD_CENTS = 50
REQUEST = {'date': DAY, 'concept':
    'A large expressive raven on a seaside windowsill shelters a small pumpkin traveller under one wing; the traveller offers a star-shaped biscuit. A simple distant headland and broad white sky frame this warm, wry act of kindness.',
    'style': 'ink', 'layout': 'school', 'public_safe': True}
PROMPT = (REQUEST['concept'] +
    ' Original hand-drawn black-and-white editorial illustration. Large expressive'
    ' foreground characters, lively gestures, confident varied black contours.'
    ' Purposeful black masses balanced by clean white faces, feather cuts and sky.'
    ' Selective medium-scale hatching, only a few memorable details. One dominant'
    ' raven, one supporting pumpkin; distant scenery simple and light. Witty and'
    ' sophisticated, not preschool-cute. No miniature buildings, repetitive tiny'
    ' textures, pale grey wash, dense etching, vector clipart or flat cutout style.'
    ' Compose the COMPLETE 2:1 scene across almost the full 1024px width inside'
    ' y=256..767 of the 1024x1024 canvas; unused top and bottom pure white.'
    ' Main figures occupy most scene height and remain clear at 280px-wide preview.'
    ' Calm light upper-left for a separate date. No lettering, dates, headlines,'
    ' people, cats, dogs, reference identities or private details.')
PARAMETERS = {'model': MODEL, 'n': 1, 'quality': 'low', 'size': '1024x1024',
              'output_format': 'png', 'prompt': PROMPT}


def stage(*, store, transport, archive, today, run_id):
    validate_public_request(REQUEST)
    if today != DAY:
        raise Stopped('only_approved_current_date')
    fingerprint = hashlib.sha256(json.dumps({'request': REQUEST,
        'parameters': PARAMETERS, 'revision_id': REVISION_ID}, sort_keys=True).encode()).hexdigest()
    with store.locked() as db:
        parent = db.get(DAY)
        if not parent or parent.get('state') != 'complete' or not parent.get('manifest', {}).get('manifest_url'):
            raise Stopped('completed_original_required')
        previous = db.get(KEY)
        if previous:
            if previous.get('fingerprint') != fingerprint:
                raise Stopped('revision_fingerprint_conflict')
            raise Stopped('revision_already_reserved_no_retry')
        policy = db.get('budget-policy')
        if not policy or policy.get('policy_id') != 'flare-low-v1-reviewed':
            raise Stopped('existing_reviewed_budget_policy_required')
        month = DAY[:7]
        total = sum(r.get('reserved_cents', 0) for r in db.records.values() if r.get('month') == month)
        if total+HOLD_CENTS > CAP_CENTS:
            raise Stopped('monthly_budget_reserved')
        state = {'date': DAY, 'month': month, 'revision_id': REVISION_ID,
            'fingerprint': fingerprint, 'state': 'reserved', 'reserved_cents': HOLD_CENTS,
            'original_reserved_cents': HOLD_CENTS, 'run_id': str(run_id),
            'model': MODEL, 'quality': 'low', 'size': '1024x1024', 'n': 1,
            'supersedes_manifest_url': parent['manifest']['manifest_url'],
            'approval_reference': 'Owner approved one today-only reference-style replacement 2026-10-30',
            'invoice_verified': False}
        db.save(KEY, state)
        state['state'] = 'submitted'
        db.save(KEY, state)  # durable before the sole paid call
        known_usage = False
        try:
            response, request_id = transport.call('/images/generations', copy.deepcopy(PARAMETERS))
            raw, metadata = validate_result(response)
            known_usage = True
            metadata.update(model=MODEL, reported_usage=response['usage'])
            if isinstance(request_id, str) and len(request_id) < 120 and request_id.replace('_','').replace('-','').isalnum():
                metadata['request_id'] = request_id
            state['result'] = metadata
            db.save(KEY, state)
            source = archive(raw, metadata)
            if (source.get('sha256') != hashlib.sha256(raw).hexdigest()
                    or not source.get('url', '').startswith('https://raw.githubusercontent.com/'+REPO+'/')):
                raise Stopped('source_archive_not_verified')
            state.update(state='awaiting_visual_review', original_url=source['url'],
                         original_sha256=source['sha256'], paid_calls=1)
            db.save(KEY, state)
            return copy.deepcopy(state)
        except Exception:
            state.update(state='uncertain_or_needs_review', reserved_cents=HOLD_CENTS if known_usage else CAP_CENTS)
            db.save(KEY, state)
            raise Stopped('staged_revision_failed_no_retry') from None


class CapturingTransport:
    def __init__(self, root, transport):
        self.root, self.transport = root, transport
    def call(self, path, body):
        response, request_id = self.transport.call(path, body)
        folder = self.root/'.revision-recovery'
        folder.mkdir(exist_ok=True)
        for i, item in enumerate(response.get('data', [])):
            target = folder/('original-'+str(i)+'.png')
            if target.exists():
                raise Stopped('recovery_source_exists_no_retry')
            target.write_bytes(base64.b64decode(item['b64_json'], validate=True))
        (folder/'usage.json').write_text(json.dumps(response.get('usage', {}), sort_keys=True))
        return response, request_id


def archive_source(root, raw, metadata):
    path = Path('images/2026/10')/(DAY+'-revision-'+REVISION_ID+'-flare-original.png')
    target = root/path
    if target.exists():
        raise Stopped('immutable_revision_source_exists')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    sha = commit(root, [str(path)], 'Archive original for one school revision visual review')
    url = 'https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(path)
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.read(20_000_001) != raw:
            raise Stopped('public_source_bytes_mismatch')
    return {'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    if (os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'
            or os.environ.get('GITHUB_REPOSITORY') != REPO
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('SCHOOL_REVISION_APPROVED') != REVISION_ID):
        raise Stopped('one_approved_manual_revision_only')
    root = Path.cwd()
    result = stage(store=GitStore(root),
        transport=CapturingTransport(root, OpenAITransport(os.environ['OPENAI_API_KEY'])),
        archive=lambda raw, metadata: archive_source(root, raw, metadata),
        today=datetime.now(ZoneInfo('Australia/Brisbane')).date().isoformat(),
        run_id=os.environ.get('GITHUB_RUN_ID', ''))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"state":"stopped","reason":"inspect_revision_ledger_do_not_retry"}')
        raise SystemExit(1)
