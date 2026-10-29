"""GitHub Actions adapter. Disabled until workflow and budget policy approved."""
import copy
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import hashlib
import io
import json
import os
import re
from pathlib import Path
import subprocess
import urllib.request
from PIL import Image
from generate_daily import generate, Stopped
from check_flare_access import OpenAITransport

LEDGER = '.pipeline/daily-ledger.json'
REPO = 'nerdflu/morning-brief-art'


def command(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise Stopped('git_operation_failed_no_retry')
    return result.stdout.strip()


def commit(root, paths, message):
    command(root, 'add', '--', *paths)
    command(root, '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m', message)
    command(root, 'push', 'origin', 'HEAD:main')  # normal push: no force, no automatic replay
    sha = command(root, 'rev-parse', 'HEAD')
    remote = command(root, 'ls-remote', 'origin', 'refs/heads/main').split()[0]
    if remote != sha:
        raise Stopped('remote_commit_not_confirmed_no_retry')
    return sha


class GitStore:
    def __init__(self, root): self.root = Path(root)
    @contextmanager
    def locked(self):
        # Actual cross-run lock is REQUIRED workflow concurrency, shared with pilot.
        # Environment marker is set only by the reviewed workflow, not request JSON.
        if os.environ.get('ART_GLOBAL_LOCK') != 'morning-brief-art-writer':
            raise Stopped('global_workflow_lock_required')
        if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != REPO
                or os.environ.get('GITHUB_REF') != 'refs/heads/main'):
            raise Stopped('reviewed_main_actions_workflow_required')
        command(self.root, 'fetch', 'origin', 'main')
        command(self.root, 'merge', '--ff-only', 'origin/main')
        if command(self.root, 'rev-parse', 'HEAD') != command(self.root, 'rev-parse', 'origin/main'):
            raise Stopped('checkout_not_fresh_main')
        path = self.root / LEDGER
        self.records = json.loads(path.read_text()) if path.exists() else {}
        yield self
    def get(self, key): return copy.deepcopy(self.records.get(key))
    def save(self, key, value):
        self.save_many({key: value})
    def save_many(self, updates):
        self.records.update(copy.deepcopy(updates))
        path = self.root / LEDGER; path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.records, indent=2, sort_keys=True)+'\n')
        commit(self.root, [LEDGER], 'Record daily art ledger transition')


class GitPublisher:
    def __init__(self, root): self.root = Path(root)
    def __call__(self, day, original, display, metadata):
        folder = Path('images') / day[:4] / day[5:7]
        revision = metadata.get('revision')
        test_id = metadata.get('test_id')
        panoramic = metadata.get('format_contract') == 'panorama-v1'
        if test_id is not None:
            if revision is not None or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', test_id) or len(test_id) > 60 or metadata.get('format_contract') != 'panorama-v1':
                raise Stopped('invalid_panorama_test_publication')
            folder = Path('images/tests') / test_id
        suffix = ''
        if revision is not None:
            revision_id = revision.get('id', '')
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', revision_id) or len(revision_id) > 40:
                raise Stopped('invalid_revision_id')
            suffix = '-revision-' + revision_id
        stem = 'panorama-v1' if test_id is not None else day+suffix+'-flare'
        paths = [folder / (stem+'-original.png'), folder / (stem+'.png')]
        for path, raw in zip(paths, [original, display]):
            target = self.root / path; target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != raw:
                raise Stopped('immutable_art_conflict')
            target.write_bytes(raw)
        sha = commit(self.root, [str(p) for p in paths], 'Archive daily Flare artwork '+day)
        base = 'https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'
        manifest = {'date': day, 'original_url': base+str(paths[0]), 'image_url': base+str(paths[1]),
                    'original_sha256': hashlib.sha256(original).hexdigest(), 'display_sha256': hashlib.sha256(display).hexdigest(), 'model': metadata.get('model', 'gpt-image-2.5-flare')}
        original_size, display_size = ((1872,624),(1872,380)) if panoramic else ((1024,1024),(960,480))
        if panoramic:
            manifest.update(format_contract='panorama-v1', width=1872, height=380)
        if test_id is not None:
            manifest['test_id'] = test_id
        for url, expected, size in [(manifest['original_url'], original, original_size), (manifest['image_url'], display, display_size)]:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(20_000_001)
            if data != expected or Image.open(io.BytesIO(data)).size != size:
                raise Stopped('public_art_verification_failed')
        if revision is not None:
            manifest.update(revision_id=revision['id'], supersedes_manifest_url=revision['supersedes_manifest_url'],
                            framing=metadata['framing'])
        path = Path('manifests') / (day+suffix+'.json');
        if test_id is not None:
            path = Path('manifests/tests') / (test_id+'.json')
        if (revision is not None or test_id is not None) and (self.root/path).exists():
            raise Stopped('immutable_revision_manifest_conflict')
        target = self.root/path; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
        sha = commit(self.root, [str(path)], 'Publish daily art manifest '+day)
        url = 'https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(path)
        with urllib.request.urlopen(url, timeout=30) as response:
            if json.loads(response.read(100_001)) != manifest:
                raise Stopped('public_manifest_verification_failed')
        return dict(manifest, manifest_url=url, verified=True)


def resolve_request(root, event_name, event, manual_json=''):
    """Only this push's one added/modified request, never historical inputs."""
    if event_name == 'workflow_dispatch':
        if len(manual_json.encode()) > 2000:
            raise Stopped('request_too_large')
        return json.loads(manual_json)
    if event_name != 'push' or event.get('ref') != 'refs/heads/main' or event.get('repository', {}).get('full_name') != REPO or event.get('forced'):
        raise Stopped('unsupported_request_event')
    before, after = event.get('before', ''), event.get('after', '')
    if any(not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha) or sha == '0'*40 for sha in (before, after)):
        raise Stopped('invalid_event_commit')
    # Exact trusted commit strings passed as argv; no shell interpolation.
    command(root, 'merge-base', '--is-ancestor', before, after)
    command(root, 'merge-base', '--is-ancestor', after, 'HEAD')
    changed = command(root, 'diff', '--name-only', '-z', '--diff-filter=AM', before, after, '--', 'requests/').split('\0')
    paths = [path for path in changed if path]
    if len(paths) != 1 or not re.fullmatch(r'requests/\d{4}-\d{2}-\d{2}\.json', paths[0]):
        raise Stopped('exactly_one_dated_request_required')
    raw = command(root, 'show', after + ':' + paths[0])
    if len(raw.encode()) > 2000:
        raise Stopped('request_too_large')
    request = json.loads(raw)
    if not isinstance(request, dict) or request.get('date') != Path(paths[0]).stem:
        raise Stopped('request_date_filename_mismatch')
    return request


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise Stopped('wrong_repository_or_branch')
    if os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise Stopped('rerun_not_allowed')
    root = Path.cwd()
    event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    request = resolve_request(root, event_name, event, os.environ.get('ART_REQUEST_JSON', ''))
    if request.get('date') != datetime.now(ZoneInfo('Australia/Brisbane')).date().isoformat():
        raise Stopped('only_current_brisbane_date_allowed')
    pilot = json.loads((root/'.pipeline-tests/flare-access-2026-10-26.json').read_text())
    result = generate(request, store=GitStore(root), transport=OpenAITransport(os.environ['OPENAI_API_KEY']), publisher=GitPublisher(root), pilot=pilot)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    try: main()
    except Exception:
        print('{"state":"stopped","reason":"inspect_durable_ledger_do_not_retry"}')
        raise SystemExit(1)
