import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from contract import ROOT, RUNTIME, LEGACY_RUNTIME, RECIPE_V2_ONLY, canonical, fingerprints, sha
from wanxiang_auxiliary import read_locked, convert_emoji

class SourceUnificationTests(unittest.TestCase):
    def test_active_recipe_uses_verified_wanxiang_and_opencc_rows(self):
        recipe = ROOT / 'recipe/wanxiang-v1'
        upstream = recipe / 'upstream-auxiliary'
        read_locked(upstream)
        expected = convert_emoji((upstream/'lua/data/emoji.txt').read_bytes())
        self.assertEqual(expected, (recipe/'opencc/emoji.txt').read_bytes())
        self.assertTrue(all('\t' in row for row in expected.decode().splitlines()))
        for retired in ['opencc/others.txt','LICENSE-rime-ice.txt']:
            self.assertFalse((recipe/retired).exists())
            self.assertNotIn(retired, RUNTIME)
            self.assertIn(retired, LEGACY_RUNTIME)

    def test_exact_recipe_and_source_lock(self):
        # The v2 lock covers every recipe file; v1 is the same set without the
        # nine-key additions, so the production recipe hash stays unchanged.
        recipe = ROOT / 'recipe/wanxiang-v1'
        every = sorted(p.relative_to(recipe).as_posix() for p in recipe.rglob('*') if p.is_file())
        for lock_path, paths in [('locks/recipe.json', [p for p in every if p not in RECIPE_V2_ONLY]),
                                 ('locks/recipe-v2.json', every)]:
            with self.subTest(lock=lock_path):
                lock = json.loads((ROOT/lock_path).read_text())
                actual = fingerprints(recipe, paths)
                self.assertEqual(actual,lock['files'])
                self.assertEqual(sha(canonical(actual)),lock['sha256'])
        self.assertEqual(json.loads((ROOT/'locks/recipe.json').read_text())['sha256'],
                         '9630235fe1c5a48a08063ecea08c7c5eb3d6e03ae825025251cdfe2afb8d0ca2')

    def test_promotion_requires_current_os_evidence(self):
        from promote import validate_qualification
        validate_qualification({'qualified_os':['27.0'],'glyph_policy_version':1,'rows':1})
        for value in (['26.5'], ['26.5','27.0'], [], ['27.0']):
            with self.assertRaises(ValueError):
                validate_qualification({'qualified_os':value,'glyph_policy_version':1,
                                        'rows':0 if value == ['27.0'] else 1})
