import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from adapt import build
from contract import ROOT, PROFILE, PROFILE_V2, PROFILE_V4
from recipe_corrections import apply, DATA

WEIGHTS = json.loads((ROOT / 'tools/local_additions.json').read_text()).get('weights', [])
# Rows the local weight overlay raises, as an upstream table writes them (weight 1).
WEIGHT_ROWS = ''.join(f"{w['text']}\t{w['code']}\t1\n" for w in WEIGHTS)

RULES = ROOT / 'recipe/wanxiang-v1/wanxiang_full_pinyin.yaml'
QUANPIN_RECIPE = ROOT / 'recipe/wanxiang-v1/wanxiang.schema.yaml'
PACK_IDS = ['personal-pack-quanpin', 'personal-pack-t9', 'personal-pack-xiaohe']
PACK_LINE = '\n  packs: [rerime_personal_pack]  #'
T9 = ROOT / 'recipe/wanxiang-v1/wanxiang_t9.schema.yaml'
XIAOHE_RECIPE = ROOT / 'recipe/wanxiang-v1/wanxiang_xiaohe.schema.yaml'


def fake_download(url, target):
    name = target.name
    if name == 'LICENSE':
        target.write_bytes((ROOT / 'recipe/wanxiang-v1/LICENSE').read_bytes())
        return
    schema = name.removesuffix('.dict.yaml')
    content = f'---\nname: {schema}\nversion: "1"\nsort: by_weight\n'
    if target.parent.name == 'original':
        content += f'import_tables:\n  - dicts/{schema}_fixture\n...\n'
    else:
        content += '...\n你好\tni hao\t10\n' + (WEIGHT_ROWS if schema == 'wanxiang_fixture' else '')
    target.write_text(content)


class RecipeCorrectionsTests(unittest.TestCase):
    def test_every_build_corrects_the_adapted_copy_only(self):
        recipe_before = RULES.read_bytes()
        for revision in ('a' * 40, 'b' * 40):
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, revision)
                adapted = (work / 'adapted/wanxiang_full_pinyin.yaml').read_text()
                for correction in json.loads(DATA.read_text())['corrections']:
                    if correction['file'] != 'wanxiang_full_pinyin.yaml':
                        continue
                    self.assertNotIn(correction['find'], adapted)
                    self.assertEqual(adapted.count(correction['replace']), 1)
                self.assertNotIn('([wtfghkz])ei', adapted)
                self.assertIn('derive/([wfghkz])ei$/$1ie/', adapted)
                receipt = json.loads((work / 'recipe-corrections-receipt.json').read_text())
                self.assertEqual([c['id'] for c in receipt['corrections']], ['tei-is-a-syllable'])
        # The locked recipe itself is never modified.
        self.assertEqual(RULES.read_bytes(), recipe_before)

    def test_nine_key_corrections_apply_to_v2_and_v4_builds_only(self):
        t9_before = T9.read_bytes()
        t9_ids = ['t9-rerime-script-translator', 't9-tail-completion']
        for profile, expected in [(PROFILE, ['tei-is-a-syllable']), (PROFILE_V2, ['tei-is-a-syllable', *t9_ids]),
                                  (PROFILE_V4, ['tei-is-a-syllable', *t9_ids, 'v4-deploys-xiaohe',
                                               'xiaohe-two-key-abbreviation', *PACK_IDS])]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, 'a' * 40, profile)
                receipt = json.loads((work / 'recipe-corrections-receipt.json').read_text())
                self.assertEqual([c['id'] for c in receipt['corrections']], expected)
                default = (work / 'adapted/default.custom.yaml')
                if profile == PROFILE:
                    self.assertFalse(default.exists())
                else:
                    self.assertEqual('wanxiang_xiaohe' in default.read_text(), profile == PROFILE_V4)
                if profile == PROFILE_V4:
                    # IME-561: the 小鹤 translator gains the two-key 简拼 key and (IME-710) the
                    # personal pack; nothing else changes.
                    xiaohe = (work / 'adapted/wanxiang_xiaohe.schema.yaml').read_text()
                    recipe = XIAOHE_RECIPE.read_text()
                    translator = xiaohe[xiaohe.index('\ntranslator:\n'):xiaohe.index('\npersonal_xiaohe:\n')]
                    self.assertEqual(translator.count('\n  rerime_two_key_abbreviation: true'), 1)
                    self.assertEqual(xiaohe.count('rerime_two_key_abbreviation'), 1)
                    self.assertEqual(translator.count(PACK_LINE), 1)
                    self.assertEqual(set(recipe.splitlines()) - set(xiaohe.splitlines()), set())
                    self.assertEqual(len(xiaohe.splitlines()), len(recipe.splitlines()) + 2)
                if profile != PROFILE:
                    schema = (work / 'adapted/wanxiang_t9.schema.yaml').read_text()
                    self.assertIn('  translators: [punct_translator, rerime_dual_script_translator, '
                                  'table_translator@personal_t9]', schema)
                    self.assertNotIn(' script_translator,', schema)
                    translator = schema[schema.index('\ntranslator:\n'):schema.index('\npersonal_t9:\n')]
                    self.assertEqual(translator.count('\n  rerime_tail_completion: true\n'), 1)
                    self.assertEqual(translator.count('\n  enable_completion: true'), 1)
                    # Only the two lines change; the tail completion key is the one added line,
                    # and v4 (IME-710) adds the personal pack line too.
                    removed = set(T9.read_text().splitlines()) - set(schema.splitlines())
                    self.assertEqual(removed, {'  translators: [punct_translator, script_translator, table_translator@personal_t9]',
                                               '  enable_completion: true'})
                    self.assertEqual(translator.count(PACK_LINE), int(profile == PROFILE_V4))
                    self.assertEqual(len(schema.splitlines()),
                                     len(T9.read_text().splitlines()) + 1 + int(profile == PROFILE_V4))
        self.assertEqual(T9.read_bytes(), t9_before)

    def test_v4_mounts_the_personal_pack_on_each_main_translator(self):
        # IME-710: one line per schema, directly under `dictionary: wanxiang` of the main
        # translator; the 我的词条 table translators stay; v1 and v2 builds get no pack.
        for profile in (PROFILE, PROFILE_V2, PROFILE_V4):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, 'a' * 40, profile)
                names = ['wanxiang.schema.yaml'] + ([] if profile == PROFILE else ['wanxiang_t9.schema.yaml']) \
                    + (['wanxiang_xiaohe.schema.yaml'] if profile == PROFILE_V4 else [])
                for name in names:
                    schema = (work / 'adapted' / name).read_text()
                    recipe = (ROOT / 'recipe/wanxiang-v1' / name).read_text()
                    self.assertEqual(schema.count('rerime_personal_pack'), int(profile == PROFILE_V4), name)
                    self.assertEqual(recipe.count('rerime_personal_pack'), 0, name)
                    if profile != PROFILE_V4:
                        continue
                    # Directly under the main translator's dictionary, inside its block.
                    at = schema.index('\n  dictionary: wanxiang' + PACK_LINE)
                    block = schema[schema.index('\ntranslator:\n'):at]
                    self.assertFalse(any(l and l[0] not in ' #' for l in block.splitlines()[2:]), name)
                    self.assertIn('table_translator@personal', schema, name)
                    self.assertEqual(set(recipe.splitlines()) - set(schema.splitlines()) -
                                     {'  translators: [punct_translator, script_translator, table_translator@personal_t9]',
                                      '  enable_completion: true'}, set(), name)
        # Repeat application of the pack corrections leaves a v4 copy as it was.
        data = json.loads(DATA.read_text())
        only = dict(data, corrections=[c for c in data['corrections'] if c['id'] in PACK_IDS])
        with tempfile.TemporaryDirectory() as tmp, patch('recipe_corrections.json.loads', return_value=only):
            output = Path(tmp) / 'adapted'
            output.mkdir()
            for name in ('wanxiang.schema.yaml', 'wanxiang_t9.schema.yaml', 'wanxiang_xiaohe.schema.yaml'):
                (output / name).write_bytes((ROOT / 'recipe/wanxiang-v1' / name).read_bytes())
            apply(output, PROFILE_V4)
            once = {n.name: n.read_bytes() for n in output.iterdir()}
            apply(output, PROFILE_V4)
            self.assertEqual({n.name: n.read_bytes() for n in output.iterdir()}, once)
        self.assertNotIn('rerime_personal_pack', QUANPIN_RECIPE.read_text())

    def test_profile_scoped_corrections_must_apply_in_their_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'adapted'
            output.mkdir()
            (output / 'wanxiang_full_pinyin.yaml').write_bytes(RULES.read_bytes())
            apply(output, PROFILE)  # The v1 build has no nine-key schema and needs none.
            with self.assertRaisesRegex(ValueError, 'recipe-correction-missing:t9-rerime-script-translator'):
                apply(output, PROFILE_V2)
            (output / 'wanxiang_t9.schema.yaml').write_bytes(T9.read_bytes())
            apply(output, PROFILE_V2)
            once = (output / 'wanxiang_t9.schema.yaml').read_bytes()
            apply(output, PROFILE_V2)
            self.assertEqual((output / 'wanxiang_t9.schema.yaml').read_bytes(), once)
        data = json.loads(DATA.read_text())
        for scope in ([], ['wanxiang-ios-arm64-rime1161-v3']):
            bad = dict(data, corrections=[dict(data['corrections'][0], profiles=scope)])
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as tmp, \
                    patch('recipe_corrections.json.loads', return_value=bad):
                output = Path(tmp) / 'adapted'
                output.mkdir()
                (output / 'wanxiang_full_pinyin.yaml').write_bytes(RULES.read_bytes())
                with self.assertRaisesRegex(ValueError, 'recipe-correction-profiles:tei-is-a-syllable'):
                    apply(output, PROFILE)

    def test_repeat_application_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'adapted'
            output.mkdir()
            (output / 'wanxiang_full_pinyin.yaml').write_bytes(RULES.read_bytes())
            apply(output)
            once = (output / 'wanxiang_full_pinyin.yaml').read_bytes()
            apply(output)
            self.assertEqual((output / 'wanxiang_full_pinyin.yaml').read_bytes(), once)

    def test_a_changed_or_missing_rule_stops_the_build(self):
        for text in ('speller:\n  algebra:\n    - derive/([wtfghkz])ei$/$1ie/  # upstream reworded\n',
                     'speller:\n  algebra:\n    - erase/^xx$/\n'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'adapted'
                output.mkdir()
                (output / 'wanxiang_full_pinyin.yaml').write_text(text)
                with self.assertRaisesRegex(ValueError, 'recipe-correction-missing:tei-is-a-syllable'):
                    apply(output)

    def test_corrected_rules_keep_every_other_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'adapted'
            output.mkdir()
            original = RULES.read_text()
            (output / 'wanxiang_full_pinyin.yaml').write_text(original)
            apply(output)
            corrected = (output / 'wanxiang_full_pinyin.yaml').read_text()
            removed = set(original.splitlines()) - set(corrected.splitlines())
            added = set(corrected.splitlines()) - set(original.splitlines())
            self.assertEqual(removed, {'  - derive/([wtfghkz])ei$/$1ie/'})
            self.assertEqual(len(added), 1)
            self.assertEqual(len(original.splitlines()), len(corrected.splitlines()))


if __name__ == '__main__':
    unittest.main()
