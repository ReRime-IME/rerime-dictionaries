"""Profile-scoped publication: v2 gets its own channel file and releases
without changing anything the v1 channel, its releases or the watcher depend on."""
import base64
import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from contract import ROOT, SCHEMAS, PROFILE, PROFILE_V2, PROFILES, canonical, recipe_sha, sha
from channel import validate_channel
from check_release import (channel_path, check, continuation, minimum_app_build, policy, release_profile, verify_source,
                           CHANNEL_PATH)
from consumer_test import CONSUMER_CASES, T9_CONSUMER_CASES, consumer_cases
from promote import publish_assets, require_plan, write_channel
from release_http import REPO

V1_PATH = f'channels/{PROFILE}.json'
V2_PATH = f'channels/{PROFILE_V2}.json'


class FakeGit:
    """A minimal content-addressed GitHub Git Data API for the channel branch."""

    def __init__(self, files):
        self.blobs, self.trees, self.commits, self.ref = {}, {}, {}, None
        self.tree_bodies = []
        if files:
            tree = self._tree({path: self._blob(data) for path, data in files.items()})
            self.ref = self._commit(tree, [])

    def _key(self, kind, value):
        return hashlib.sha1(kind.encode() + canonical(value) if not isinstance(value, bytes) else kind.encode() + value).hexdigest()

    def _blob(self, data):
        key = self._key('blob', data)
        self.blobs[key] = data
        return key

    def _tree(self, entries):
        key = self._key('tree', entries)
        self.trees[key] = dict(entries)
        return key

    def _commit(self, tree, parents):
        key = self._key('commit', dict(tree=tree, parents=parents, n=len(self.commits)))
        self.commits[key] = dict(tree=tree, parents=parents)
        return key

    def files(self):
        return {path: self.blobs[blob] for path, blob in self.trees[self.commits[self.ref]['tree']].items()}

    def api(self, path, method='GET', body=None, missing=False):
        prefix = f'repos/{REPO}/'
        assert path.startswith(prefix), path
        path = path[len(prefix):]
        if path == 'git/ref/heads/channel' and method == 'GET':
            return {'object': {'sha': self.ref}} if self.ref else None
        if path.startswith('contents/') and method == 'GET':
            name, ref = re.fullmatch(r'contents/(.+)\?ref=([0-9a-f]{40})', path).groups()
            blob = self.trees[self.commits[ref]['tree']].get(name)
            if blob is None:
                return None
            data = self.blobs[blob]
            return dict(encoding='base64', size=len(data), content=base64.b64encode(data).decode())
        if path == 'git/blobs' and method == 'POST':
            return {'sha': self._blob(base64.b64decode(body['content']))}
        if path.startswith('git/commits/') and method == 'GET':
            return {'tree': {'sha': self.commits[path.split('/')[-1]]['tree']}}
        if path == 'git/trees' and method == 'POST':
            self.tree_bodies.append(copy.deepcopy(body))
            entries = dict(self.trees[body['base_tree']]) if 'base_tree' in body else {}
            for item in body['tree']:
                entries[item['path']] = item['sha']
            return {'sha': self._tree(entries)}
        if path == 'git/commits' and method == 'POST':
            return {'sha': self._commit(body['tree'], body['parents'])}
        if path == 'git/refs/heads/channel' and method == 'PATCH':
            if body['force'] is not False or self.ref not in self.commits[body['sha']]['parents']:
                raise RuntimeError('not a fast forward')
            self.ref = body['sha']
            return {}
        if path == 'git/refs' and method == 'POST':
            self.ref = body['sha']
            return {}
        raise AssertionError((path, method))


class ChannelBranchTests(unittest.TestCase):
    def publish(self, git, envelope, expected, profile):
        with patch('promote.api', side_effect=git.api), patch('check_release.api', side_effect=git.api):
            return write_channel(envelope, expected, profile)

    def test_v2_promotion_leaves_the_v1_channel_byte_identical(self):
        v1 = b'{"key_id":"k","payload_base64":"djE=","signature_base64":"c2ln"}'
        other = b'unrelated branch content\n'
        git = FakeGit({V1_PATH: v1, 'README.md': other})
        before = git.ref
        self.publish(git, b'v2-envelope', None, PROFILE_V2)
        files = git.files()
        self.assertEqual(files[V1_PATH], v1)
        self.assertEqual(files['README.md'], other)
        self.assertEqual(files[V2_PATH], b'v2-envelope')
        self.assertEqual(set(files), {V1_PATH, V2_PATH, 'README.md'})
        # The new tree names only the v2 file and is based on the current tree.
        body = git.tree_bodies[-1]
        self.assertEqual([item['path'] for item in body['tree']], [V2_PATH])
        self.assertEqual(body['base_tree'], git.commits[before]['tree'])
        self.assertEqual(git.commits[git.ref]['parents'], [before])

    def test_v1_promotion_leaves_the_v2_channel_byte_identical(self):
        git = FakeGit({V1_PATH: b'v1-old', V2_PATH: b'v2-current'})
        self.publish(git, b'v1-new', sha(b'v1-old'), PROFILE)
        self.assertEqual(git.files(), {V1_PATH: b'v1-new', V2_PATH: b'v2-current'})

    def test_concurrent_change_protection_is_per_channel_file(self):
        git = FakeGit({V1_PATH: b'v1-changed-by-another-run', V2_PATH: b'v2-old'})
        # A v1 change does not block v2: the plan only bound the v2 file.
        self.publish(git, b'v2-new', sha(b'v2-old'), PROFILE_V2)
        self.assertEqual(git.files()[V1_PATH], b'v1-changed-by-another-run')
        # A stale v2 expectation is refused before any write.
        ref = git.ref
        with self.assertRaisesRegex(ValueError, 'channel-concurrent-change'):
            self.publish(git, b'v2-newer', sha(b'v2-old'), PROFILE_V2)
        self.assertEqual(git.ref, ref)
        # A first v2 channel requires that no v2 file exists yet.
        with self.assertRaisesRegex(ValueError, 'channel-concurrent-change'):
            self.publish(git, b'v2-newer', None, PROFILE_V2)

    def test_channel_paths_are_per_profile(self):
        self.assertEqual(CHANNEL_PATH, V1_PATH)
        self.assertEqual(channel_path(), V1_PATH)
        self.assertEqual(channel_path(PROFILE_V2), V2_PATH)
        with self.assertRaises(ValueError):
            channel_path('../wanxiang-ios-arm64-rime1161-v1')


def channel_value(profile):
    release = 'wanxiang-precompiled-20-' + 'b' * 12
    return dict(format_version=1, repository=REPO, compatibility_id=profile, sequence=1, issued_at=1000,
                expires_at=1000 + 86400, upstream_checked_at=1000, package_revision=20, release_id=release,
                package_url=f'https://github.com/{REPO}/releases/download/{release}/ReRime-{release}.zip',
                package_size=100, package_sha256='a' * 64, manifest_sha256='b' * 64)


class ProfilePolicyTests(unittest.TestCase):
    def test_channel_is_bound_to_its_profile(self):
        validate_channel(channel_value(PROFILE), 1000, PROFILE)
        validate_channel(channel_value(PROFILE_V2), 1000, PROFILE_V2)
        validate_channel(channel_value(PROFILE), 1000)
        for value, profile in [(channel_value(PROFILE), PROFILE_V2), (channel_value(PROFILE_V2), PROFILE)]:
            with self.assertRaisesRegex(ValueError, 'channel-profile'):
                validate_channel(value, 1000, profile)
        with self.assertRaises(ValueError):
            validate_channel(channel_value('wanxiang-ios-arm64-rime1161-v3'), 1000)

    def test_v2_app_build_floor_is_higher_and_v1_is_unchanged(self):
        public = policy()
        self.assertEqual(minimum_app_build(public, PROFILE), public['minimum_app_build'])
        self.assertEqual(public['minimum_app_build'], 51)
        self.assertEqual(minimum_app_build(public, PROFILE_V2), 62)
        for override in (50, '62', None):
            with self.subTest(override=override), self.assertRaises(ValueError):
                minimum_app_build(dict(minimum_app_build=51, profile_minimum_app_build={PROFILE_V2: override}), PROFILE_V2)

    def test_release_profile_comes_from_the_publisher_body(self):
        self.assertEqual(release_profile(dict(body=f'Public precompiled Wanxiang resources for {PROFILE_V2}.\n\nx')), PROFILE_V2)
        self.assertEqual(release_profile(dict(body=f'Public precompiled Wanxiang resources for {PROFILE}.\n\nx')), PROFILE)
        # Every release before v2 is v1.
        self.assertEqual(release_profile(dict(body=None)), PROFILE)
        self.assertEqual(release_profile(dict()), PROFILE)

    def test_consumer_receipt_requires_nine_key_cases_only_for_v2(self):
        self.assertEqual(consumer_cases(PROFILE), CONSUMER_CASES)
        self.assertEqual(consumer_cases(PROFILE_V2), CONSUMER_CASES + T9_CONSUMER_CASES)

    def test_promotion_refuses_a_plan_for_another_profile(self):
        for planned, selected in [(PROFILE, PROFILE_V2), (PROFILE_V2, PROFILE), (None, PROFILE)]:
            plan = dict(format_version=1, mode='build')
            if planned:
                plan['profile'] = planned
            with self.subTest(planned=planned), self.assertRaisesRegex(ValueError, 'check-profile'):
                require_plan(plan, 0, selected)

    def test_checked_source_must_be_adapted_for_the_checked_profile(self):
        with tempfile.TemporaryDirectory() as tmp, patch('check_release.relevant_tools', return_value=[]):
            work, plan = Path(tmp), Path(tmp) / 'check.json'
            plan.write_text(json.dumps(dict(upstream_revision='a' * 40, source_files=[], profile=PROFILE_V2,
                                            tool_digest=sha(canonical([])))))
            (work / 'source-receipt.json').write_text(json.dumps(dict(revision='a' * 40, files=[])))
            (work / 'profile.json').write_text(json.dumps(dict(compatibility_id=PROFILE)))
            with self.assertRaisesRegex(ValueError, 'checked-profile'):
                verify_source(plan, work)
            (work / 'profile.json').write_text(json.dumps(dict(compatibility_id=PROFILE_V2)))
            verify_source(plan, work)


def published(revision, profile, draft=False):
    return dict(tag_name=f'wanxiang-precompiled-{revision}-' + 'c' * 12, draft=draft,
                body=f'Public precompiled Wanxiang resources for {profile}.\n\nRuntime...')


class ProfileCheckTests(unittest.TestCase):
    def run_check(self, profile, releases, old=None, floors=(0, 0)):
        roots = {name + '.dict.yaml': f'---\nname: {name}\nversion: x\nsort: by_weight\nimport_tables:\n - dicts/{name}\n...\n'.encode()
                 for name in SCHEMAS}
        paths = ['LICENSE', *roots, *['dicts/' + name + '.dict.yaml' for name in SCHEMAS]]
        tree = dict(truncated=False, tree=[dict(path=p, type='blob', mode='100644', sha='a' * 40, size=100) for p in paths])

        def api(path, method='GET', body=None, missing=False):
            if '/git/trees/' in path:
                return tree
            if '/releases?' in path:
                return releases if 'page=1' in path else []
            raise AssertionError(path)

        def read(url, limit, missing=False):
            return roots[url.rsplit('/', 1)[1]]

        with tempfile.TemporaryDirectory() as tmp, \
                patch('check_release.previous', return_value=old) as previous, \
                patch('check_release.continuation', return_value=floors), \
                patch('check_release.resolve_release', return_value={'revision': 'b' * 40}), \
                patch('check_release.relevant_tools', return_value=[]), \
                patch('check_release.subprocess.check_output', return_value='d' * 40), \
                patch('check_release.api', side_effect=api), patch('check_release.read', side_effect=read):
            check(Path(tmp) / 'out', profile=profile)
            self.assertEqual(previous.call_args.args[3], profile)
            return json.loads((Path(tmp) / 'out/check.json').read_text())

    def test_first_channel_continues_above_the_previous_repository(self):
        # The floors in locks/release.json, with no release or channel in this repository yet.
        self.assertEqual(continuation(policy(), PROFILE), (26, 22))
        self.assertEqual(continuation(policy(), PROFILE_V2), (26, 3))
        self.assertEqual(self.run_check(PROFILE, [], floors=(26, 22))['package_revision'], 27)
        # Existing releases above the floor still win.
        self.assertEqual(self.run_check(PROFILE, [published(30, PROFILE_V2)], floors=(26, 22))['package_revision'], 31)
        value = json.loads((ROOT / 'locks/release.json').read_text())
        for floors in [{'package_revision': -1}, {'channel_sequence': {'unknown-profile': 1}}, {'other': 1}]:
            with self.subTest(floors=floors), patch('check_release.json.loads', return_value=dict(value, continuation=floors)):
                with self.assertRaisesRegex(ValueError, 'release-policy-continuation'):
                    policy()

    def test_first_v2_check_coexists_with_published_v1_releases(self):
        releases = [published(19, PROFILE), published(18, PROFILE)]
        plan = self.run_check(PROFILE_V2, releases)
        self.assertEqual(plan['profile'], PROFILE_V2)
        self.assertEqual(plan['mode'], 'build')
        # Shared counter: the v2 tag cannot collide with any existing release.
        self.assertEqual(plan['package_revision'], 20)
        self.assertEqual(plan['minimum_app_build'], 62)
        v1 = self.run_check(PROFILE, [], None)
        self.assertEqual(v1['minimum_app_build'], 51)
        self.assertNotEqual(plan['input_identity'], v1['input_identity'])
        expected = sha(canonical(dict(source_git_digest=plan['source_git_digest'], tool_digest=plan['tool_digest'],
                                      recipe_sha256=recipe_sha(PROFILES[PROFILE_V2]),
                                      engine_archive_sha256='d123d38b004d60548eef21c2688c17a9b988c8565dd8aee334a8fe215f273bd5')))
        self.assertEqual(plan['input_identity'], expected)

    def test_missing_channel_still_refuses_to_conceal_its_own_published_release(self):
        with self.assertRaisesRegex(ValueError, 'published-release-without-channel'):
            self.run_check(PROFILE_V2, [published(20, PROFILE_V2), published(19, PROFILE)])
        # v1 behavior is unchanged: a published v1 release without a v1 channel stops.
        with self.assertRaisesRegex(ValueError, 'published-release-without-channel'):
            self.run_check(PROFILE, [published(19, PROFILE)])
        # A v2 draft (failed promotion) is not concealment, and its revision is skipped.
        plan = self.run_check(PROFILE_V2, [published(20, PROFILE_V2, draft=True), published(19, PROFILE)])
        self.assertEqual(plan['package_revision'], 21)


class ProfileReleaseTests(unittest.TestCase):
    records = [dict(name='asset.zip', size=100, sha256='b' * 64)]

    def test_a_release_of_another_profile_is_never_adopted(self):
        for existing, profile in [(PROFILE, PROFILE_V2), (PROFILE_V2, PROFILE)]:
            release = dict(id=1, target_commitish='a' * 40, draft=True, immutable=False, assets=[],
                           body=f'Public precompiled Wanxiang resources for {existing}.\n')
            with self.subTest(existing=existing), patch('promote.get_release', return_value=release), \
                    patch('promote.api') as api, patch('promote.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'release-profile-conflict'):
                    publish_assets('tag', 'a' * 40, Path('/unused'), self.records, profile)
                api.assert_not_called()
                run.assert_not_called()

    def test_new_v2_release_names_its_profile_and_is_not_marked_latest(self):
        for profile, latest in [(PROFILE_V2, 'false'), (PROFILE, 'true')]:
            calls = []
            asset = dict(name='asset.zip', size=100, digest='sha256:' + 'b' * 64)

            def api(path, method='GET', body=None, missing=False):
                calls.append((method, body))
                if method == 'POST':
                    return dict(id=1, target_commitish='a' * 40, draft=True, assets=[])
                if method == 'PATCH':
                    return dict(id=1, draft=False, immutable=True, assets=[asset])
                return dict(id=1, draft=True, assets=[asset])

            with self.subTest(profile=profile), patch('promote.get_release', return_value=None), \
                    patch('promote.api', side_effect=api), patch('promote.subprocess.run'):
                publish_assets('tag', 'a' * 40, Path('/unused'), self.records, profile)
                created = next(body for method, body in calls if method == 'POST')
                self.assertTrue(created['body'].startswith(f'Public precompiled Wanxiang resources for {profile}.'))
                self.assertEqual(release_profile(created), profile)
                self.assertEqual(next(body for method, body in calls if method == 'PATCH')['make_latest'], latest)


class WorkflowProfileTests(unittest.TestCase):
    value = (ROOT / '.github/workflows/dictionary.yml').read_text()

    def test_profile_input_defaults_to_v1_for_the_watcher(self):
        block = re.search(r'      profile:\n((?:        .*\n)+)', self.value).group(1)
        self.assertIn(f'options: [{PROFILE}, {PROFILE_V2}]', block)
        self.assertIn(f'default: {PROFILE}', block)
        self.assertEqual(sorted(PROFILES), [PROFILE, PROFILE_V2])
        # The watcher's exact title and the v1 concurrency group are unchanged.
        self.assertIn("run-name: Dictionary ${{ inputs.request_id || github.run_id }}${{ inputs.profile == "
                      f"'{PROFILE_V2}' && ' v2' || '' }}}}\n", self.value)
        self.assertIn(f"  group: dictionary-channel-${{{{ inputs.profile == '{PROFILE_V2}' && 'v2' || 'v1' }}}}\n", self.value)

    def test_each_stage_receives_the_selected_profile(self):
        check = self.value.split('\n  check:\n')[1].split('\n  build:\n')[0]
        build = self.value.split('\n  build:\n')[1].split('\n  promote:\n')[0]
        promote = self.value.split('\n  promote:\n')[1]
        self.assertIn(f"RERIME_PROFILE: ${{{{ inputs.profile || '{PROFILE}' }}}}", check)
        self.assertIn('--profile "$RERIME_PROFILE"', check)
        self.assertIn('profile: ${{ steps.check.outputs.profile }}', check)
        self.assertIn('RERIME_PROFILE: ${{ needs.check.outputs.profile }}', build)
        self.assertIn(f"RERIME_PROFILE: ${{{{ inputs.profile || '{PROFILE}' }}}}", promote)
        self.assertIn('--profile "$RERIME_PROFILE"', promote)
        self.assertIn('group: dictionary-release-publish', promote)
        # Inputs reach shell only through environment variables.
        self.assertNotRegex(self.value, r'run: .*\$\{\{ inputs\.')


if __name__ == '__main__':
    unittest.main()
