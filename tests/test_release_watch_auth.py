import base64
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
from release_watch import AppCredential, GitHub, REPO, load_credential, tick, RequestError


class AppAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root / 'github-app.pem'
        self.key.write_text('test fixture, mocked except signature test')
        self.now = 1700000000
        self.config = {'client_id': 'Iv1.test', 'installation_id': 42}
        self.auth = AppCredential(self.config, self.key, lambda: self.now)

    def response(self):
        return {'token': 'ghs_test_fixture',
                'permissions': {'actions': 'write', 'metadata': 'read'},
                'repositories': [{'full_name': REPO}],
                'expires_at': datetime.fromtimestamp(self.now+3600, timezone.utc).isoformat()}

    def test_real_signature_and_bounded_claims(self):
        subprocess.run(['/usr/bin/openssl', 'genrsa', '-out', str(self.key), '2048'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public = self.root / 'public.pem'
        subprocess.run(['/usr/bin/openssl', 'rsa', '-in', str(self.key), '-pubout', '-out', str(public)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        jwt = self.auth.jwt(self.now)
        header, claims, signature = jwt.split('.')
        decode = lambda x: base64.urlsafe_b64decode(x+'='*(-len(x)%4))
        self.assertEqual(json.loads(decode(header))['alg'], 'RS256')
        self.assertEqual(json.loads(decode(claims)), {'iat': self.now-60, 'exp': self.now+540, 'iss':'Iv1.test'})
        sig = self.root / 'sig'; sig.write_bytes(decode(signature))
        checked = subprocess.run(['/usr/bin/openssl', 'dgst', '-sha256', '-verify', str(public),
                                  '-signature', str(sig)], input=(header+'.'+claims).encode(),
                                 capture_output=True)
        self.assertEqual(checked.returncode, 0)

    def test_narrow_exchange_cache_and_automatic_refresh(self):
        with patch.object(AppCredential, 'jwt', return_value='test.jwt'), patch.object(
                GitHub, 'request', side_effect=lambda *a, **kw: (self.response(), None)) as request:
            self.assertEqual(self.auth(), 'ghs_test_fixture')
            self.auth()
            self.assertEqual(request.call_count, 1)
            args, kwargs = request.call_args
            self.assertEqual(args[0], 'app/installations/42/access_tokens')
            self.assertEqual(kwargs['body'], {'repositories':['rerime-dictionaries'],
                                             'permissions':{'actions':'write','metadata':'read'}})
            self.now += 3550
            self.auth()
            self.assertEqual(request.call_count, 2)

    def test_idle_tick_neither_signs_nor_requests_token(self):
        state = {'completed_release':'42', 'observed_release':'42',
                 'next_release_check':self.now+100, 'next_channel_check':self.now+100,
                 'expires_at':self.now+30*86400}
        with patch.object(AppCredential, 'jwt', side_effect=AssertionError('idle auth')), patch.object(
                GitHub, 'request', side_effect=AssertionError('idle request')):
            self.assertEqual(tick(GitHub(self.auth), state, self.now, lambda:None), 'unchanged')

    def test_invalid_exchange_scope_expiry_and_failure_are_closed(self):
        for field, value in [('permissions', {'contents':'write'}), ('repositories', []),
                             ('token','unexpected'), ('expires_at','2000-01-01T00:00:00Z')]:
            response = self.response(); response[field] = value
            with self.subTest(field=field), patch.object(AppCredential,'jwt',return_value='test.jwt'), patch.object(
                    GitHub,'request',return_value=(response,None)):
                with self.assertRaises(ValueError): self.auth()
                self.assertIsNone(self.auth.cached)
        with patch.object(AppCredential,'jwt',return_value='test.jwt'), patch.object(
                GitHub,'request',side_effect=RequestError(401)):
            with self.assertRaises(RequestError): self.auth()

    def test_partial_app_config_never_falls_back_to_pat(self):
        (self.root/'github-token').write_text('github_pat_test')
        with self.assertRaises(OSError): load_credential(self.root)
        (self.root/'github-app.json').write_text(json.dumps(self.config))
        self.assertIsInstance(load_credential(self.root), AppCredential)
        self.key.unlink()
        with self.assertRaises(ValueError): load_credential(self.root)
        (self.root/'github-app.json').unlink()
        self.assertEqual(load_credential(self.root), 'github_pat_test')

    def test_untrusted_endpoint_rejected_before_network(self):
        with self.assertRaises(ValueError):
            GitHub('test').request('app/installations/42/access_tokens')
        with self.assertRaises(ValueError):
            GitHub('test', token_endpoint='app/installations/42/access_tokens').request(
                'app/installations/43/access_tokens')

    def test_invalid_key_error_does_not_expose_openssl_output(self):
        with self.assertRaisesRegex(ValueError, '^app-signing-failed$'):
            self.auth.jwt(self.now)
