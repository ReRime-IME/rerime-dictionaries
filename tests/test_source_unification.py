import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from contract import ROOT, RUNTIME, LEGACY_RUNTIME, canonical, fingerprints, sha
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
        recipe = ROOT / 'recipe/wanxiang-v1'
        lock = json.loads((ROOT/'locks/recipe.json').read_text())
        actual = fingerprints(recipe,[p.relative_to(recipe).as_posix() for p in recipe.rglob('*') if p.is_file()])
        self.assertEqual(actual,lock['files'])
        self.assertEqual(sha(canonical(actual)),lock['sha256'])
