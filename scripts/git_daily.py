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

    def paths(self, day, metadata):
        folder = Path('images') / day[:4] / day[5:7]
        revision, test_id = metadata.get('revision'), metadata.get('test_id')
        suffix = ''
        if revision is not None:
            revision_id = revision.get('id', '')
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', revision_id) or len(revision_id)>40:
                raise Stopped('invalid_revision_id')
            suffix = '-revision-'+revision_id
        if test_id is not None:
            if revision is not None or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',test_id) or len(test_id)>60 or metadata.get('format_contract')!='panorama-v1':
                raise Stopped('invalid_panorama_test_publication')
            folder=Path('images/tests')/test_id
            stem='panorama-v1'
            manifest=Path('manifests/tests')/(test_id+'.json')
        else:
            fmt=metadata.get('format_contract')
            if fmt in ('school-2x1-v2','solo-panorama-v2'):
                from art_contracts import contract
                c=contract(metadata['layout'])
                if c['id']!=fmt: raise Stopped('format_layout_mismatch')
                stem=day+suffix+'-'+c['suffix']
            else:
                stem=day+suffix+'-flare'
            manifest=Path('manifests')/(day+suffix+'.json')
        return [folder/(stem+'-original.png'),folder/(stem+'.png')],manifest

    def fetch_bytes(self, url):
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read(20_000_001)

    def fetch_manifest(self,url):
        from active_manifest import path
        if not path(url).startswith('manifests/'):
            raise Stopped('manifest_url_required')
        return json.loads(self.fetch_bytes(url))

    def archive_original(self,day,raw,metadata):
        paths,_=self.paths(day,metadata)
        target=self.root/paths[0]
        if target.exists(): raise Stopped('immutable_original_already_exists')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        sha=commit(self.root,[str(paths[0])],'Archive unmodified daily source before formatting '+day)
        url='https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(paths[0])
        if self.fetch_bytes(url)!=raw: raise Stopped('public_source_verification_failed')
        return url

    def current_for(self,day,fallback):
        pointer_path=self.root/'manifests/current'/str(day+'.json')
        if not pointer_path.exists(): return fallback
        from active_manifest import resolve_pointer
        return resolve_pointer(day,json.loads(pointer_path.read_text()),self.fetch_manifest,self.fetch_bytes)

    def publish_current(self,day,manifest_url,manifest):
        from active_manifest import make_pointer
        path=Path('manifests/current')/(day+'.json')
        target=self.root/path
        if target.exists():
            # Ordinary generation never demotes an explicitly selected revision.
            self.current_for(day,{})  # fail closed if the existing pointer is invalid
            return
        pointer=make_pointer(day,manifest_url,manifest)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(pointer,indent=2,sort_keys=True)+'\n')
        sha=commit(self.root,[str(path)],'Select verified daily artwork '+day)
        url='https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(path)
        if json.loads(self.fetch_bytes(url))!=pointer: raise Stopped('active_pointer_verification_failed')

    def __call__(self,day,original,display,metadata):
        paths,path=self.paths(day,metadata)
        revision,test_id=metadata.get('revision'),metadata.get('test_id')
        if (self.root/path).exists():
            raise Stopped('immutable_revision_manifest_conflict' if revision is not None or test_id is not None else 'immutable_manifest_conflict')
        for p,raw in zip(paths,[original,display]):
            target=self.root/p;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=raw: raise Stopped('immutable_art_conflict')
            target.write_bytes(raw)
        sha=commit(self.root,[str(p) for p in paths],'Archive daily Flare artwork '+day)
        base='https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'
        manifest={'date':day,'original_url':metadata.get('archived_original_url',base+str(paths[0])),
                  'image_url':base+str(paths[1]),'original_sha256':hashlib.sha256(original).hexdigest(),
                  'display_sha256':hashlib.sha256(display).hexdigest(),'model':metadata.get('model','gpt-image-2.5-flare')}
        fmt=metadata.get('format_contract')
        if fmt in ('school-2x1-v2','solo-panorama-v2'):
            from art_contracts import contract
            c=contract(metadata['layout']);source_size,display_size=c['source'],c['display']
            for key in ('format_contract','layout','width','height','original_width','original_height','framing','source_crop_bounds'):
                manifest[key]=metadata[key]
        elif fmt=='panorama-v1':
            source_size,display_size=(1872,624),(1872,380)
            manifest.update(format_contract=fmt,width=1872,height=380,test_id=test_id)
        else:
            source_size,display_size=(1024,1024),(960,480)
        for url,expected,size in [(manifest['original_url'],original,source_size),(manifest['image_url'],display,display_size)]:
            data=self.fetch_bytes(url)
            if data!=expected or Image.open(io.BytesIO(data)).size!=size: raise Stopped('public_art_verification_failed')
        if revision is not None:
            manifest.update(revision_id=revision['id'],supersedes_manifest_url=revision['supersedes_manifest_url'],framing=metadata['framing'])
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        sha=commit(self.root,[str(path)],'Publish daily art manifest '+day)
        url='https://raw.githubusercontent.com/'+REPO+'/'+sha+'/'+str(path)
        if json.loads(self.fetch_bytes(url))!=manifest: raise Stopped('public_manifest_verification_failed')
        if fmt in ('school-2x1-v2','solo-panorama-v2') and revision is None and test_id is None:
            self.publish_current(day,url,manifest)
        return dict(manifest,manifest_url=url,verified=True)


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
    policy_path=root/'.pipeline/art-policy.json'
    policy=json.loads(policy_path.read_text()) if policy_path.exists() else {'policy_id':'mode-aware-ink-v2','enabled':False}
    if set(policy)!={'policy_id','enabled'} or policy['policy_id']!='mode-aware-ink-v2' or type(policy['enabled']) is not bool:
        raise Stopped('invalid_art_activation_policy')
    result = generate(request, format_policy=policy['policy_id'] if policy['enabled'] else None, store=GitStore(root), transport=OpenAITransport(os.environ['OPENAI_API_KEY']), publisher=GitPublisher(root), pilot=pilot)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    try: main()
    except Exception:
        print('{"state":"stopped","reason":"inspect_durable_ledger_do_not_retry"}')
        raise SystemExit(1)
