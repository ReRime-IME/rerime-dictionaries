import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from adapt import build
from contract import ROOT
from local_additions import apply, DATA


class LocalAdditionsTests(unittest.TestCase):
    def test_two_upstream_syncs_preserve_words_and_flags(self):
        # Two fresh builds emulate an upstream change removing both region words.
        for revision in ('a' * 40, 'b' * 40):
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as tmp:
                def download(url, target):
                    name = target.name
                    if name == 'LICENSE':
                        target.write_bytes((ROOT / 'recipe/wanxiang-v1/LICENSE').read_bytes())
                        return
                    root = target.parent.name == 'original'
                    schema = name.removesuffix('.dict.yaml')
                    content = f'---\nname: {schema}\nversion: "1"\nsort: by_weight\n'
                    if root:
                        content += f'import_tables:\n  - dicts/{schema}_fixture\n...\n'
                    else:
                        content += '...\n你好\tni hao\t10\n'
                    target.write_text(content)
                work = Path(tmp)
                with patch('adapt.download', download):
                    build(work, revision)
                output = work / 'adapted'
                dictionary = (output / 'dicts/rerime_regions.dict.yaml').read_text()
                emoji = (output / 'opencc/emoji.txt').read_text()
                for entry in json.loads(DATA.read_text())['entries']:
                    self.assertIn(entry['text'] + '\t' + entry['pinyin'] + '\t100\n', dictionary)
                    mapping = dict(line.split('\t', 1) for line in emoji.splitlines() if '\t' in line)
                    self.assertIn(entry['emoji'], mapping[entry['text']].split())
                self.assertIn('  - dicts/rerime_regions\n', (output / 'wanxiang.dict.yaml').read_text())
                before = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
                apply(output)
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertNotIn('rerime_regions', (work / 'original/wanxiang.dict.yaml').read_text())

    def test_preserves_existing_alternatives(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'adapted'
            (output / 'dicts').mkdir(parents=True)
            (output / 'opencc').mkdir()
            (output / 'wanxiang.dict.yaml').write_text('---\nimport_tables:\n  - dicts/base\n...\n')
            (output / 'opencc/emoji.txt').write_text('台湾\t台湾 🏝️\n香港\t香港 🇭🇰\n')
            apply(output)
            self.assertIn('台湾\t台湾 🏝️ 🇹🇼\n', (output / 'opencc/emoji.txt').read_text())
            self.assertIn('香港\t香港 🇭🇰\n', (output / 'opencc/emoji.txt').read_text())
            self.assertNotIn('🇭🇰 🇭🇰', (output / 'opencc/emoji.txt').read_text())
