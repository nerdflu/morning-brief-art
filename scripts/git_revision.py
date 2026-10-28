"""Manual-only versioned replacement. No retries, Sheet access, or scheduling."""
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from generate_daily import generate, Stopped
from git_daily import GitStore, GitPublisher
from check_flare_access import OpenAITransport


def resolve_revision(raw, today):
    if not isinstance(raw, str) or len(raw.encode()) > 3000:
        raise Stopped('invalid_revision_envelope')
    envelope = json.loads(raw)
    if not isinstance(envelope, dict) or set(envelope) != {'request', 'revision'}:
        raise Stopped('invalid_revision_envelope')
    if not isinstance(envelope['revision'], dict):
        raise Stopped('named_revision_required')
    if not isinstance(envelope['request'], dict) or envelope['request'].get('date') != today:
        raise Stopped('only_current_brisbane_date_allowed')
    return envelope


def main():
    if (os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'
            or os.environ.get('GITHUB_REPOSITORY') != 'nerdflu/morning-brief-art'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'):
        raise Stopped('manual_main_first_attempt_required')
    envelope = resolve_revision(os.environ.get('ART_REVISION_JSON', ''), datetime.now(ZoneInfo('Australia/Brisbane')).date().isoformat())
    root = Path.cwd()
    pilot = json.loads((root/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
    result = generate(**envelope, store=GitStore(root), transport=OpenAITransport(os.environ['OPENAI_API_KEY']),
                      publisher=GitPublisher(root), pilot=pilot)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"state":"stopped","reason":"inspect_durable_ledger_do_not_retry"}')
        raise SystemExit(1)
