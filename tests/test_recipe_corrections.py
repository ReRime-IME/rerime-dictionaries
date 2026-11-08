import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from adapt import build
from contract import ROOT, PROFILE, PROFILE_V2
from recipe_corrections import apply, DATA

WEIGHTS = json.loads((ROOT / 'tools/local_additions.json').read_text()).get('weights', [])
# Rows the local weight overlay raises, as an upstream table writes them (weight 1).
WEIGHT_ROWS = ''.join(f"{w['text']}\t{w['code']}\t1\n" for w in WEIGHTS)

RULES = ROOT / 'recipe/wanxiang-v1/wanxiang_full_pinyin.yaml'
T9 = ROOT / 'recipe/wanxiang-v1/wanxiang_t9.schema.yaml'


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

    def test_nine_key_corrections_apply_to_v2_builds_only(self):
        t9_before = T9.read_bytes()
        t9_ids = ['t9-rerime-script-translator', 't9-tail-completion']
        for profile, expected in [(PROFILE, ['tei-is-a-syllable']), (PROFILE_V2, ['tei-is-a-syllable', *t9_ids])]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, 'a' * 40, profile)
                receipt = json.loads((work / 'recipe-corrections-receipt.json').read_text())
                self.assertEqual([c['id'] for c in receipt['corrections']], expected)
                if profile == PROFILE_V2:
                    schema = (work / 'adapted/wanxiang_t9.schema.yaml').read_text()
                    self.assertIn('  translators: [punct_translator, rerime_dual_script_translator, '
                                  'table_translator@personal_t9]', schema)
                    self.assertNotIn(' script_translator,', schema)
                    translator = schema[schema.index('\ntranslator:\n'):schema.index('\npersonal_t9:\n')]
                    self.assertEqual(translator.count('\n  rerime_tail_completion: true\n'), 1)
                    self.assertEqual(translator.count('\n  enable_completion: true'), 1)
                    # Only the two lines change; the tail completion key is the one added line.
                    removed = set(T9.read_text().splitlines()) - set(schema.splitlines())
                    self.assertEqual(removed, {'  translators: [punct_translator, script_translator, table_translator@personal_t9]',
                                               '  enable_completion: true'})
                    self.assertEqual(len(schema.splitlines()), len(T9.read_text().splitlines()) + 1)
        self.assertEqual(T9.read_bytes(), t9_before)

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
