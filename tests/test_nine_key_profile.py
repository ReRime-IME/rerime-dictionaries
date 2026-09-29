import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapt import build
from contract import (ROOT, PROFILE, PROFILE_V2, PROFILES, RUNTIME, RUNTIME_V2, RECIPE_V2_ONLY, ENGINE_SHA,
                      build_profile, recipe_sha, sha, validate_manifest)
from consumer_test import T9_CASES, T9_PERSONAL_CASE
from pack import validate_compiled, work_profile
from test_recipe_corrections import fake_download

RECIPE = ROOT / 'recipe/wanxiang-v1'
T9 = (RECIPE / 'wanxiang_t9.schema.yaml').read_text()
T9_BODY = ''.join(line for line in T9.splitlines(True) if not line.lstrip().startswith('#'))


def block(text, key):
    """Lines of one top-level YAML mapping, without a YAML dependency."""
    match = re.search(rf'^{key}:\n((?:[ #].*\n|\n)*)', text, re.M)
    return match.group(1) if match else ''


def manifest(profile):
    files = [dict(path=p, size=100, sha256=sha(('synthetic:' + p).encode())) for p in profile['runtime']]
    return dict(format_version=4, payload_kind='precompiled-rime-v1', profile='mobile_wanxiang_full',
                package_revision=2026092601, release_id='wanxiang-precompiled-2026092601-' + 'b' * 12,
                compatibility_id=profile['id'], engine_archive_sha256=ENGINE_SHA, recipe_sha256=recipe_sha(profile),
                minimum_app_version='0.6.1', minimum_app_build=51, qualified_os=['27.0'], glyph_policy_version=1,
                upstream_revision='b' * 40, adapter_revision='c' * 40, source_digest='a' * 64,
                build_receipt_sha256=next(f['sha256'] for f in files if f['path'] == 'build-receipt.json'),
                source_archive_sha256='d' * 64, english_learning_version=1, files=files)


class NineKeyProfileTests(unittest.TestCase):
    def test_v2_runtime_adds_only_the_t9_schema_and_prism(self):
        self.assertEqual(sorted(set(RUNTIME_V2) - set(RUNTIME)),
                         ['build/wanxiang_t9.prism.bin', 'build/wanxiang_t9.schema.yaml'])
        self.assertTrue(set(RUNTIME) < set(RUNTIME_V2))
        contract = json.loads((ROOT / 'contract/compatibility-rime1161-v2.json').read_text())
        self.assertEqual(contract['id'], PROFILE_V2)
        self.assertEqual(contract['runtime_files'], RUNTIME_V2)
        self.assertEqual(contract['recipe_sha256'], recipe_sha(PROFILES[PROFILE_V2]))
        self.assertEqual(json.loads((ROOT / 'contract/compatibility-v1.json').read_text())['id'], PROFILE)

    def test_production_default_stays_v1(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(build_profile()['id'], PROFILE)
        with patch.dict('os.environ', {'RERIME_PROFILE': PROFILE_V2}):
            self.assertEqual(build_profile()['id'], PROFILE_V2)
        with self.assertRaises(ValueError):
            build_profile('wanxiang-ios-arm64-rime1161-v3')
        self.assertNotEqual(recipe_sha(PROFILES[PROFILE]), recipe_sha(PROFILES[PROFILE_V2]))

    def test_manifest_binds_profile_recipe_and_inventory(self):
        for profile in PROFILES.values():
            validate_manifest(manifest(profile))
        v1, v2 = manifest(PROFILES[PROFILE]), manifest(PROFILES[PROFILE_V2])
        mixed = [('v2-with-v1-recipe', dict(v2, recipe_sha256=v1['recipe_sha256'])),
                 ('v2-with-v1-files', dict(v2, files=v1['files'])),
                 ('v1-with-v2-files', dict(v1, files=v2['files'])),
                 ('v1-with-v2-recipe', dict(v1, recipe_sha256=v2['recipe_sha256'])),
                 ('unknown-profile', dict(v2, compatibility_id='wanxiang-ios-arm64-rime1161-v3'))]
        for label, value in mixed:
            with self.subTest(label=label), self.assertRaises((ValueError, KeyError)):
                validate_manifest(copy.deepcopy(value))

    def test_adapter_copies_t9_files_only_for_v2(self):
        for profile, present in [(PROFILE, False), (PROFILE_V2, True)]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, 'a' * 40, profile)
                for name in RECIPE_V2_ONLY:
                    self.assertEqual((work / 'adapted' / name).exists(), present)
                recorded = json.loads((work / 'profile.json').read_text())
                self.assertEqual(recorded['compatibility_id'], profile)
                self.assertEqual(work_profile(work)['id'], profile)

    def test_packing_requires_the_t9_prism_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'build').mkdir()
            magic = {'table': b'Rime::Table/4.0\0', 'prism': b'Rime::Prism/4.0\0', 'reverse': b'Rime::Reverse/3.1\0'}
            for name in ('wanxiang', 'wanxiang_english', 'wanxiang_mixedcode'):
                for suffix, data in magic.items():
                    (root / f'build/{name}.{suffix}.bin').write_bytes(data)
            validate_compiled(root, PROFILES[PROFILE])
            with self.assertRaises(FileNotFoundError):
                validate_compiled(root, PROFILES[PROFILE_V2])
            (root / 'build/wanxiang_t9.prism.bin').write_bytes(magic['table'])
            with self.assertRaises(ValueError):
                validate_compiled(root, PROFILES[PROFILE_V2])
            (root / 'build/wanxiang_t9.prism.bin').write_bytes(magic['prism'])
            validate_compiled(root, PROFILES[PROFILE_V2])

    def test_v2_default_deploys_the_t9_schema(self):
        patch_text = (RECIPE / 'default.custom.yaml').read_text()
        self.assertIn('schema_list/+:\n    - schema: wanxiang_t9\n', patch_text)
        self.assertNotIn('wanxiang_t9', (RECIPE / 'default.yaml').read_text())

    def test_t9_translator_shares_the_wanxiang_dictionary_and_learning(self):
        translator = block(T9, 'translator')
        for line in ['dictionary: wanxiang', 'prism: wanxiang_t9', 'enable_sentence: false',
                     'enable_correction: false', 'enable_completion: true', 'enable_user_dict: true',
                     'spelling_hints: 50', 'always_show_comments: true']:
            self.assertIn('  ' + line + '\n', translator)
        # No explicit user_dict: learning goes to the default wanxiang user dictionary.
        self.assertNotRegex(translator, r'(?m)^  user_dict:')
        personal = block(T9, 'personal_t9')
        for line in ["dictionary: ''", 'user_dict: rerime_personal_t9', 'db_class: stabledb', 'initial_quality: 100']:
            self.assertIn('  ' + line + '\n', personal)
        self.assertIn('table_translator@personal_t9', T9)
        for absent in ['lua_', 'grammar', 'wanxiang_lite', 'abbrev', 'table_translator@english',
                       'table_translator@mixed', 'dependencies']:
            self.assertNotIn(absent, T9_BODY)

    def test_t9_speller_is_the_upstream_digit_algebra(self):
        speller = block(T9, 'speller')
        alphabet = re.search(r'alphabet: (\S+)', speller).group(1)
        initials = re.search(r'initials: (\S+)', speller).group(1)
        for value in (alphabet, initials):
            self.assertEqual(set(value), set('abcdefghijklmnopqrstuvwxyz23456789'))
        self.assertIn('delimiter: " \'"', speller)
        rules = re.findall(r'^    - (\S+)$', speller, re.M)
        pad = dict(zip('abc def ghi jkl mno pqrs tuv wxyz'.split(), '23456789'))
        keypad = ''.join(digit * len(letters) for letters, digit in pad.items())
        self.assertEqual(rules[-1], f'xlit/ABCDEFGHIJKLMNOPQRSTUVWXYZ/{keypad}/')
        for rule in ['derive/^(.*)$/\\U$1/', 'derive/^ng$/eng/', 'xform/^n$/en/', 'xform/ḿ/me/',
                     'derive/^([nl])ve$/$1ue/', 'derive/ong$/on/', 'derive/iong$/ion/', 'derive/^([jqxy])u/$1v/']:
            self.assertIn(rule, rules)
        self.assertFalse(any(rule.startswith('abbrev/') for rule in rules))
        # No 26-key typo derivations (for example tie/tei or nag/ang transpositions).
        full = (RECIPE / 'wanxiang_full_pinyin.yaml').read_text()
        typo = [line.strip()[2:] for line in full.splitlines() if 'derive/' in line and '$1' in line and '(\\d)' not in line]
        self.assertTrue(typo)
        self.assertFalse(set(typo) & set(rules))

    def test_t9_menu_keeps_digits_for_the_speller(self):
        menu = block(T9, 'menu')
        keys = re.search(r'alternative_select_keys: (\S+)', menu).group(1)
        self.assertFalse(set(keys) & set('0123456789'))
        default_page = re.search(r'page_size: (\d+)', (RECIPE / 'default.yaml').read_text()).group(1)
        self.assertEqual(re.search(r'page_size: (\d+)', menu).group(1), default_page)

    def test_consumer_cases_use_the_nine_key_input_model(self):
        for label, schema, text, expected, mode, feed, comment in [*T9_CASES, T9_PERSONAL_CASE]:
            with self.subTest(case=label):
                self.assertEqual(schema, 'wanxiang_t9')
                self.assertRegex(text, r"^[2-9]+$" if feed == 'keys' else r"^[a-z2-9']+$")


if __name__ == '__main__':
    unittest.main()
