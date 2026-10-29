"""Manual-only single named experiment; never writes requests/ or Sheets.

No production activation. Uses the existing global lock, secret and monthly
ledger; submitted/uncertain outcomes cannot be replayed.
"""
import json
import os
import base64
import hashlib
import urllib.request
from pathlib import Path
from check_flare_access import OpenAITransport
from generate_daily import generate, Stopped
from git_daily import GitStore, GitPublisher, REPO, commit

TEST_ID = 'editorial-panorama-v1'
REQUEST = {'date': '2026-10-30', 'concept':
    'An expansive coastal town floats above curling waves; crooked observatories and rooftop gardens connect by impossible bridges. From a gull-eye viewpoint, a teacup moon tows a tiny lighthouse, and cloud islands hide playful architectural surprises.',
    'style': 'ink', 'layout': 'school', 'public_safe': True}


class CapturingTransport:
    """Keep unmodified provider pixels even when validation refuses publication."""
    def __init__(self, root, transport):
        self.root, self.transport = root, transport
    def call(self, path, body):
        response, request_id = self.transport.call(path, body)
        recovery = self.root/'.panorama-recovery'
        recovery.mkdir(exist_ok=True)
        if isinstance(response, dict) and isinstance(response.get('data'), list):
            for i, item in enumerate(response['data']):
                raw = base64.b64decode(item['b64_json'], validate=True)
                target = recovery/('original-'+str(i)+'.png')
                if target.exists():
                    raise Stopped('recovery_original_already_exists_no_retry')
                target.write_bytes(raw)
            (recovery/'usage.json').write_text(json.dumps(response.get('usage', {}), sort_keys=True))
        return response, request_id


def archive_source(root, raw, metadata):
    path = Path('images/tests')/TEST_ID/'panorama-v1-original.png'
    target = root/path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise Stopped('test_source_already_archived_no_retry')
    target.write_bytes(raw)
    sha = commit(root, [str(path)], 'Archive unmodified nonproduction panorama source')
    url = 'https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(path)
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.read(20_000_001) != raw:
            raise Stopped('test_source_public_verification_failed')
    print(json.dumps({'test_source_url': url, 'sha256': hashlib.sha256(raw).hexdigest()}))


def main():
    if (os.environ.get('GITHUB_REPOSITORY') != REPO
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'
            or os.environ.get('PANORAMA_TEST_APPROVED') != TEST_ID):
        raise Stopped('one_reviewed_manual_test_only')
    root = Path.cwd()
    pilot = json.loads((root/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
    result = generate(REQUEST, store=GitStore(root),
        transport=CapturingTransport(root, OpenAITransport(os.environ['OPENAI_API_KEY'])),
        publisher=GitPublisher(root), pilot=pilot, panorama_test=TEST_ID,
        source_archiver=lambda raw, metadata: archive_source(root, raw, metadata))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"state":"stopped","reason":"inspect_durable_ledger_do_not_retry"}')
        raise SystemExit(1)
