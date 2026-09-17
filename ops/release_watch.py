#!/usr/bin/env python3
"""Private outbound-only watcher. Never prints config, tokens or HTTP bodies."""
import argparse
import base64
import fcntl
import json
import os
import re
import time
import subprocess
from datetime import datetime
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = 'ReRime-IME/rerime-dictionaries'
UPSTREAM = 'amzxyz/rime-wanxiang'
WORKFLOW = f'repos/{REPO}/actions/workflows/dictionary.yml'
CHANNEL = f'repos/{REPO}/contents/channels/wanxiang-ios-arm64-rime1161-v1.json?ref=channel'
DAY = 86400


class RequestError(Exception):
    def __init__(self, status=0):
        self.status = status
        super().__init__('github-request-failed')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RequestError(302)


class GitHub:
    def __init__(self, token=None, token_endpoint=None):
        self.token = token
        self.token_endpoint = token_endpoint

    def request(self, path, method='GET', body=None, etag=None):
        if not (path == self.token_endpoint or path.startswith((f'repos/{REPO}/', f'repos/{UPSTREAM}/'))):
            raise ValueError('api-scope')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'rerime-release-watch/1',
                   'X-GitHub-Api-Version': '2026-03-10'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + (self.token() if callable(self.token) else self.token)
        if etag:
            headers['If-None-Match'] = etag
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request('https://api.github.com/' + path, method=method,
                                     headers=headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError('response-size')
                return json.loads(raw) if raw else None, response.headers.get('ETag')
        except urllib.error.HTTPError as error:
            if error.code == 304:
                return None, etag
            raise RequestError(error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RequestError() from None



class AppCredential:
    """One short-lived token per busy process; no persistent token cache."""
    def __init__(self, config, key_path, clock=time.time):
        if set(config) != {'client_id', 'installation_id'}:
            raise ValueError('app-config')
        if not isinstance(config['client_id'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', config['client_id']):
            raise ValueError('app-client-id')
        if type(config['installation_id']) is not int or config['installation_id'] <= 0:
            raise ValueError('app-installation-id')
        if not key_path.is_file():
            raise ValueError('app-key-missing')
        self.config, self.key_path, self.clock = config, key_path, clock
        self.cached, self.expires = None, 0

    @staticmethod
    def encode(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')

    def jwt(self, now):
        header = self.encode(b'{"alg":"RS256","typ":"JWT"}')
        payload = self.encode(json.dumps(dict(iat=now-60, exp=now+540,
                                             iss=self.config['client_id'])).encode())
        message = (header + '.' + payload).encode('ascii')
        try:
            result = subprocess.run(['/usr/bin/openssl', 'dgst', '-sha256', '-sign',
                                     str(self.key_path)], input=message,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=10, check=True)
        except (OSError, subprocess.SubprocessError):
            raise ValueError('app-signing-failed') from None
        return message.decode() + '.' + self.encode(result.stdout)

    def __call__(self):
        now = int(self.clock())
        if self.cached and self.expires > now + 60:
            return self.cached
        endpoint = f'app/installations/{self.config["installation_id"]}/access_tokens'
        response, _ = GitHub(self.jwt(now), token_endpoint=endpoint).request(
            endpoint, method='POST', body={
                'repositories': [REPO.split('/')[1]],
                'permissions': {'actions': 'write', 'metadata': 'read'}})
        # Reject a broader or malformed response instead of silently accepting it.
        if not isinstance(response, dict) or response.get('permissions') != {'actions': 'write', 'metadata': 'read'}:
            raise ValueError('app-token-scope')
        repositories = response.get('repositories', [])
        if len(repositories) != 1 or repositories[0].get('full_name') != REPO:
            raise ValueError('app-token-repositories')
        token = response.get('token')
        if not isinstance(token, str) or not re.fullmatch(r'ghs_[A-Za-z0-9_]+', token):
            raise ValueError('app-token-format')
        try:
            expiry = datetime.fromisoformat(response['expires_at'].replace('Z', '+00:00'))
            if expiry.tzinfo is None:
                raise ValueError('app-token-timezone')
            expires = int(expiry.timestamp())
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ValueError('app-token-expiry') from None
        if not now + 60 < expires <= now + 3700:
            raise ValueError('app-token-lifetime')
        self.cached, self.expires = token, expires
        return token


def load_credential(directory):
    config = directory / 'github-app.json'
    key = directory / 'github-app.pem'
    if config.exists() or key.exists():
        return AppCredential(json.loads(config.read_text()), key)
    credential = directory / 'github-token'
    token = credential.read_text().strip() if credential.is_file() else None
    if token and not re.fullmatch(r'github_pat_[A-Za-z0-9_]+', token):
        raise ValueError('fine-grained-credential-required')
    return token


def release_identity(value):
    if value.get('draft') is not False or value.get('prerelease') is not False or not value.get('published_at'):
        raise ValueError('release-not-official')
    if type(value.get('id')) is not int or value['id'] <= 0:
        raise ValueError('release-id')
    return str(value['id'])


def channel_expiry(value):
    # Advisory scheduling only. Cloud producer verifies signature before any write.
    envelope = json.loads(base64.b64decode(value['content']))
    channel = json.loads(base64.b64decode(envelope['payload_base64'], validate=True))
    if channel.get('repository') != REPO or type(channel.get('expires_at')) is not int:
        raise ValueError('channel-shape')
    return channel['expires_at']


def save(path, state):
    temporary = path.with_suffix('.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(state, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def reconcile(api, state, now):
    pending = state['pending']
    if pending.get('run_id'):
        run, _ = api.request(f'repos/{REPO}/actions/runs/{pending["run_id"]}')
    else:
        response, _ = api.request(WORKFLOW + '/runs?event=workflow_dispatch&branch=main&per_page=100')
        matches = [run for run in response['workflow_runs']
                   if run.get('display_title') == 'Dictionary ' + pending['request_id']]
        if not matches:
            if now - pending['created_at'] > DAY:
                state['blocked'] = 'dispatch-not-found'
            return 'awaiting-run'
        if len(matches) != 1:
            state['blocked'] = 'duplicate-correlation'
            return 'blocked'
        run = matches[0]
        pending['run_id'] = run['id']
    if run['status'] != 'completed':
        return 'running'
    state['last_run_id'] = run['id']
    state['last_conclusion'] = run['conclusion']
    state.pop('pending')
    if run['conclusion'] == 'success':
        if pending['operation'] == 'release':
            state['completed_release'] = pending['release_id']
        state['attempts'] = 0
        state['next_channel_check'] = 0
        return 'completed'
    state['retry_after'] = now + 6 * 3600
    if state.get('attempts', 0) >= 3:
        state['blocked'] = 'workflow-failed'
    return 'failed'


def tick(api, state, now, persist):
    if state.get('blocked'):
        return 'blocked'
    if state.get('pending'):
        result = reconcile(api, state, now)
        persist()
        return result
    if now < state.get('retry_after', 0):
        return 'backoff'
    if now >= state.get('next_release_check', 0):
        value, etag = api.request(f'repos/{UPSTREAM}/releases/latest', etag=state.get('release_etag'))
        if value is not None:
            identity = release_identity(value)
            if identity != state.get('observed_release'):
                state['attempts'] = 0
            state['observed_release'] = identity
            state['release_etag'] = etag
        state['next_release_check'] = now + DAY
        persist()
    if now >= state.get('next_channel_check', 0):
        channel, _ = api.request(CHANNEL)
        state['expires_at'] = channel_expiry(channel)
        state['next_channel_check'] = now + DAY
        persist()
    operation = None
    if state.get('observed_release') and state['observed_release'] != state.get('completed_release'):
        operation = 'release'
    elif state['expires_at'] - now <= 10 * DAY:
        operation = 'renew'
    if operation is None:
        return 'unchanged'
    if not api.token:
        return 'credential-required'
    pending = dict(operation=operation, release_id=state['observed_release'] if operation == 'release' else '',
                   request_id=uuid.uuid4().hex, created_at=now)
    state['pending'] = pending
    state['attempts'] = state.get('attempts', 0) + 1
    persist()  # A crash or ambiguous POST must reconcile; never blindly resend.
    try:
        api.request(WORKFLOW + '/dispatches', method='POST', body=dict(ref='main', inputs={
            key: pending[key] for key in ('operation', 'release_id', 'request_id')}))
    except RequestError as error:
        if error.status in (400, 401, 403, 404, 422):
            state.pop('pending')
            state['blocked'] = 'dispatch-access-or-input'
            persist()
        raise
    return 'dispatched'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.probe:
        api = GitHub()
        value, _ = api.request(f'repos/{UPSTREAM}/releases/latest')
        channel, _ = api.request(CHANNEL)
        print(json.dumps(dict(event='probe-ok', release_id=release_identity(value),
                              channel_days_remaining=(channel_expiry(channel)-int(time.time()))//DAY)))
        return
    args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(args.state.with_suffix('.lock'), 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('{"event":"already-running"}')
            return
        state = json.loads(args.state.read_text()) if args.state.exists() else {'format_version': 1}
        if state.get('format_version') != 1:
            raise ValueError('state-version')
        token = load_credential(Path(os.environ.get('CREDENTIALS_DIRECTORY', '/nonexistent')))
        result = tick(GitHub(token), state, int(time.time()), lambda: save(args.state, state))
        print(json.dumps(dict(event=result, run_id=state.get('last_run_id'))))
        if result in ('blocked','failed','credential-required'):
            raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except RequestError as error:
        print(json.dumps(dict(event='github-error', status=error.status)))
        raise SystemExit(1) from None
    except (ValueError, KeyError, OSError):
        print('{"event":"invalid-state-or-configuration"}')
        raise SystemExit(1) from None
