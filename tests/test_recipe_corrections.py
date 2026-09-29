import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from adapt import build
from contract import ROOT
from recipe_corrections import apply, DATA

RULES = ROOT / 'recipe/wanxiang-v1/wanxiang_full_pinyin.yaml'


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
        content += '...\n你好\tni hao\t10\n'
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
                    self.assertNotIn(correction['find'], adapted)
                    self.assertEqual(adapted.count(correction['replace']), 1)
                self.assertNotIn('([wtfghkz])ei', adapted)
                self.assertIn('derive/([wfghkz])ei$/$1ie/', adapted)
                receipt = json.loads((work / 'recipe-corrections-receipt.json').read_text())
                self.assertEqual([c['id'] for c in receipt['corrections']], ['tei-is-a-syllable'])
        # The locked recipe itself is never modified.
        self.assertEqual(RULES.read_bytes(), recipe_before)

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
