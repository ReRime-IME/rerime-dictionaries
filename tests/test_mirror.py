"""Mirror copy and retention: mirrors are untrusted transport, and pruning never
removes a release a channel points at, a pinned release, a draft or a foreign tag."""
import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'mirror'))
import mirror
from contract import PROFILE, PROFILE_V2
from s3 import Bucket


def release(revision, profile=PROFILE, draft=False, tag=None):
    return dict(id=revision, tag_name=tag or f'wanxiang-precompiled-{revision}-{revision:012x}', draft=draft,
                body=f'Public precompiled Wanxiang resources for {profile}.')


def tags(*revisions):
    return {f'wanxiang-precompiled-{r}-{r:012x}' for r in revisions}


POLICY = dict(format_version=1, keep_per_profile=5, pinned_releases=[])


class RetentionTests(unittest.TestCase):
    def test_keeps_five_newest_per_profile(self):
        releases = [release(r, PROFILE if r % 2 else PROFILE_V2) for r in range(1, 21)]
        keep, delete = mirror.plan_retention(releases, sorted(tags(19, 20)), POLICY)
        self.assertEqual(keep, tags(11, 13, 15, 17, 19, 12, 14, 16, 18, 20))
        self.assertEqual(set(delete), tags(*range(1, 11)))
        self.assertEqual(delete, sorted(delete, key=lambda t: int(t.split('-')[2])))

    def test_one_profile_never_evicts_the_other(self):
        releases = [release(1, PROFILE_V2)] + [release(r) for r in range(2, 12)]
        keep, delete = mirror.plan_retention(releases, sorted(tags(1, 11)), POLICY)
        self.assertIn(*tags(1), keep)
        self.assertEqual(set(delete), tags(2, 3, 4, 5, 6))

    def test_channel_and_pinned_releases_survive_beyond_the_window(self):
        releases = [release(r) for r in range(1, 11)]
        policy = dict(POLICY, pinned_releases=sorted(tags(2)))
        keep, delete = mirror.plan_retention(releases, sorted(tags(1)), policy)
        self.assertTrue(tags(1, 2) <= keep)
        self.assertEqual(set(delete), tags(3, 4, 5))

    def test_drafts_and_foreign_tags_are_untouched(self):
        releases = [release(r) for r in range(1, 8)] + [release(8, draft=True), release(9, tag='v1.0')]
        keep, delete = mirror.plan_retention(releases, sorted(tags(7)), POLICY)
        self.assertEqual(set(delete), tags(1, 2))
        self.assertFalse(tags(8) & (keep | set(delete)))
        self.assertNotIn('v1.0', keep | set(delete))

    def test_refuses_without_a_channel_or_with_an_unknown_channel_release(self):
        releases = [release(r) for r in range(1, 8)]
        with self.assertRaisesRegex(ValueError, 'retention-channel-missing'):
            mirror.plan_retention(releases, [], POLICY)
        with self.assertRaisesRegex(ValueError, 'retention-channel-missing'):
            mirror.plan_retention(releases, sorted(tags(99)), POLICY)

    def test_refuses_an_implausibly_large_deletion(self):
        releases = [release(r) for r in range(1, 40)]
        with self.assertRaisesRegex(ValueError, 'retention-too-many'):
            mirror.plan_retention(releases, sorted(tags(39)), POLICY)

    def test_committed_policy_is_valid(self):
        self.assertEqual(mirror.retention_policy()['keep_per_profile'], 5)

    def test_dry_run_deletes_nothing_and_apply_follows_the_plan(self):
        class Fake:
            name = 'fake'
            def __init__(self): self.deleted = []
            def stored_releases(self): return sorted(tags(1, 6, 7)) + ['unrelated']
            def delete_release(self, tag): self.deleted.append(tag)
        releases = [release(r) for r in range(1, 8)]
        calls = []
        def api(path, method='GET', body=None, missing=False):
            calls.append((method, path))
            return releases if method == 'GET' and 'page=1' in path else []
        with patch.object(mirror, 'api', api):
            fake = Fake()
            report = mirror.prune([fake], sorted(tags(7)), apply=False)
            self.assertEqual((fake.deleted, [c for c in calls if c[0] == 'DELETE']), ([], []))
            self.assertEqual(report['mirrors']['fake'], sorted(tags(1)))
            mirror.prune([fake], sorted(tags(7)), apply=True)
        self.assertEqual(fake.deleted, sorted(tags(1)))
        deleted = [path for method, path in calls if method == 'DELETE']
        self.assertEqual(len(deleted), 4)
        self.assertTrue(all('/releases/' in p or '/git/refs/tags/wanxiang-precompiled-' in p for p in deleted))


class S3Tests(unittest.TestCase):
    def test_signature_matches_the_published_sigv4_derivation(self):
        # AWS's documented signing-key example (secret, 20120215, us-east-1, iam).
        import hashlib, hmac
        key = ('AWS4' + 'wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY').encode()
        for part in ('20120215', 'us-east-1', 'iam', 'aws4_request'):
            key = hmac.new(key, part.encode(), hashlib.sha256).digest()
        self.assertEqual(key.hex(), 'f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d')

    def test_headers_are_deterministic_and_bound_to_the_request(self):
        bucket = Bucket('account.r2.cloudflarestorage.com', 'b', 'KEY', 'SECRET')
        now = datetime.datetime(2026, 10, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)
        first, query = bucket.signed_headers('GET', '/b', {'list-type': '2', 'prefix': 'releases/a b/'}, now)
        again, _ = bucket.signed_headers('GET', '/b', {'prefix': 'releases/a b/', 'list-type': '2'}, now)
        other, _ = bucket.signed_headers('PUT', '/b', {'list-type': '2', 'prefix': 'releases/a b/'}, now)
        self.assertEqual(query, 'list-type=2&prefix=releases%2Fa%20b%2F')
        self.assertEqual(first, again)
        self.assertNotEqual(first['authorization'], other['authorization'])
        self.assertIn('Credential=KEY/20261004/auto/s3/aws4_request', first['authorization'])
        self.assertNotIn('SECRET', first['authorization'])

    def test_list_follows_continuation(self):
        pages = [b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Contents><Key>releases/x/a</Key><Size>3</Size></Contents>'
                 b'<IsTruncated>true</IsTruncated><NextContinuationToken>t</NextContinuationToken></ListBucketResult>',
                 b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Contents><Key>releases/x/b</Key><Size>4</Size></Contents>'
                 b'<IsTruncated>false</IsTruncated></ListBucketResult>']
        seen = []
        bucket = Bucket('h', 'b', 'k', 's')
        def request(method, key='', query=None, **_):
            seen.append(dict(query)); return 200, pages[len(seen) - 1]
        with patch.object(bucket, 'request', request):
            self.assertEqual(bucket.list('releases/'), [('releases/x/a', 3), ('releases/x/b', 4)])
        self.assertEqual(seen[1].get('continuation-token'), 't')


class LayoutTests(unittest.TestCase):
    def test_only_client_files_leave_github(self):
        self.assertEqual(mirror.CLIENT_ASSETS, ('manifest.json', 'delta.json', 'delta.bin'))

    def test_mirror_code_is_outside_the_producer_input_identity(self):
        # tools/, recipe/, locks/, contract/, scripts/ and keys/ feed the build identity;
        # mirror code and the retention policy must not force a dictionary rebuild.
        from check_release import relevant_tools
        paths = {item['path'] for item in relevant_tools()}
        self.assertFalse(any(p.startswith(('mirror/', 'ops/')) for p in paths))


if __name__ == '__main__':
    unittest.main()
