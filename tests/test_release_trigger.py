import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from upstream_release import resolve_release, release_relation
from check_release import maintenance


class ReleaseTriggerTests(unittest.TestCase):
    def test_tag_resolves_to_commit_not_target_branch(self):
        release = dict(id=12, draft=False, prerelease=False, published_at='2026-09-16', tag_name='v1', target_commitish='wanxiang')
        with patch('upstream_release.api', side_effect=[release, {'object': {'sha': 'a'*40, 'type': 'tag'}},
                                                        {'object': {'sha': 'b'*40, 'type': 'commit'}}]) as api:
            self.assertEqual(resolve_release('12')['revision'], 'b'*40)
            self.assertIn('/git/ref/tags/v1', api.call_args_list[1].args[0])

    def test_rejects_nightly_draft_invalid_ids(self):
        for field in ('draft', 'prerelease'):
            with patch('upstream_release.api', return_value={'draft': False, 'prerelease': False, field: True}):
                with self.assertRaises(ValueError): resolve_release()
        with patch('upstream_release.api') as api:
            for value in ('../latest', '0', '12;echo', ''):
                with self.assertRaises(ValueError): resolve_release(value)
            api.assert_not_called()

    def test_ancestry_is_explicit(self):
        for status in ('behind', 'ahead', 'diverged'):
            with patch('upstream_release.api', return_value={'status': status}):
                self.assertEqual(release_relation('a'*40, 'b'*40), status)
        with patch('upstream_release.api') as api:
            self.assertEqual(release_relation('a'*40, 'a'*40), 'identical')
            api.assert_not_called()

    def test_renew_preserves_data_and_check_time(self):
        old = {'manifest': {'upstream_revision': 'a'*40},
               'receipt': {'source_git_digest': 'b'*64, 'input_identity': 'c'*64},
               'channel': {'expires_at': 2000, 'upstream_checked_at': 100, 'package_revision': 11}}
        with tempfile.TemporaryDirectory() as tmp, patch('check_release.relevant_tools', return_value=[]), \
             patch('check_release.subprocess.check_output', return_value='d'*40):
            maintenance(Path(tmp), old, 1000, {'minimum_app_build': 21}, 'renew', None)
            plan = json.loads((Path(tmp)/'check.json').read_text())
            self.assertEqual(plan['mode'], 'refresh')
            self.assertEqual(plan['upstream_checked_at'], 100)
            self.assertEqual(plan['input_identity'], 'c'*64)
            self.assertEqual(plan['upstream_revision'], 'a'*40)
            self.assertEqual(plan['package_revision'], 11)

    def test_old_release_never_fetches_or_compiles_old_source(self):
        from check_release import check
        from contract import sha, canonical
        old = {'manifest': {'upstream_revision': 'a'*40}, 'receipt': {'tool_digest':sha(canonical([]))}}
        for relation in ('behind', 'diverged'):
            with tempfile.TemporaryDirectory() as tmp, patch('check_release.policy', return_value={}), patch('check_release.relevant_tools', return_value=[]), \
                 patch('check_release.previous', return_value=old), \
                 patch('check_release.resolve_release', return_value={'revision':'b'*40}), \
                 patch('check_release.release_relation', return_value=relation), \
                 patch('check_release.maintenance') as maintain, patch('check_release.api') as api:
                check(Path(tmp)/'out')
                api.assert_not_called()
                self.assertEqual(maintain.call_args.args[4], 'release-'+relation)


class ProducerRebuildTests(unittest.TestCase):
    def test_changed_recipe_rebuilds_current_source_not_older_release(self):
        from check_release import check
        old={'manifest':{'upstream_revision':'a'*40},'receipt':{'tool_digest':'old'}}
        for relation in ('behind','diverged'):
            with tempfile.TemporaryDirectory() as tmp, patch('check_release.policy',return_value={}), \
                 patch('check_release.previous',return_value=old), \
                 patch('check_release.relevant_tools',return_value=[]), \
                 patch('check_release.resolve_release',return_value={'revision':'b'*40}), \
                 patch('check_release.release_relation',return_value=relation), \
                 patch('check_release.maintenance') as maintenance, \
                 patch('check_release.api',side_effect=RuntimeError('reached-tree')) as api:
                with self.assertRaisesRegex(RuntimeError,'reached-tree'):check(Path(tmp)/'out')
                self.assertIn('/trees/'+ 'a'*40,api.call_args.args[0])
                maintenance.assert_not_called()
