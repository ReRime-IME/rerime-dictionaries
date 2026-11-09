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
from check_release import minimum_app_build, policy
from consumer_test import (CONSUMER_CASES, T9_CONSUMER_CASES, XIAOHE_CASES, XIAOHE_CONSUMER_CASES,
                           XIAOHE_PERSONAL_CASE, XIAOHE_TRANSLATOR, consumer_cases, xiaohe_stand_in)
from contract import (ROOT, PROFILE, PROFILE_V2, PROFILE_V4, PROFILES, RUNTIME_V2, RUNTIME_V4, RECIPE_V4_ONLY,
                      build_profile, recipe_sha, validate_manifest)
from pack import validate_compiled, work_profile
from test_nine_key_profile import block, manifest
from test_recipe_corrections import fake_download
import xiaohe_symbols

RECIPE = ROOT / 'recipe/wanxiang-v1'
XIAOHE = (RECIPE / 'wanxiang_xiaohe.schema.yaml').read_text()
BODY = ''.join(line for line in XIAOHE.splitlines(True) if not line.lstrip().startswith('#'))
# ReRime's App opt-in (re_rime GrammarSecondCandidateStaging.grammarBlock), byte for byte.
APP_GRAMMAR = ('grammar:\n  language: rerime-grammar\n  collocation_max_length: 6\n  collocation_min_length: 2\n'
               '  collocation_penalty: -14\n  non_collocation_penalty: -6\n  weak_collocation_penalty: -100\n'
               '  rear_penalty: -18\n')


def xiaohe_code(syllable):
    """小鹤 code of one toneless syllable, the standard layout (an independent reference)."""
    zero = {'a': 'aa', 'ai': 'ai', 'an': 'an', 'ang': 'ah', 'ao': 'ao', 'e': 'ee', 'ei': 'ei', 'en': 'en',
            'eng': 'eg', 'er': 'er', 'o': 'oo', 'ou': 'ou'}
    if syllable in zero:
        return zero[syllable]
    finals = {'iu': 'q', 'ei': 'w', 'uan': 'r', 'ue': 't', 've': 't', 'un': 'y', 'uo': 'o', 'ie': 'p', 'ong': 's',
              'iong': 's', 'ing': 'k', 'uai': 'k', 'ai': 'd', 'en': 'f', 'eng': 'g', 'iang': 'l', 'uang': 'l',
              'ang': 'h', 'ian': 'm', 'an': 'j', 'ou': 'z', 'ia': 'x', 'ua': 'x', 'iao': 'n', 'ao': 'c', 'ui': 'v',
              'in': 'b'}
    initial = next((p for p in ('zh', 'ch', 'sh') if syllable.startswith(p)), syllable[0])
    final = syllable[len(initial):]
    key = {'zh': 'v', 'ch': 'i', 'sh': 'u'}.get(initial, initial)
    return key + (finals.get(final) or final)


class XiaoheProfileTests(unittest.TestCase):
    def test_v4_runtime_is_v2_plus_the_xiaohe_schema_and_prism(self):
        self.assertEqual(sorted(set(RUNTIME_V4) - set(RUNTIME_V2)),
                         ['build/wanxiang_xiaohe.prism.bin', 'build/wanxiang_xiaohe.schema.yaml'])
        self.assertTrue(set(RUNTIME_V2) < set(RUNTIME_V4))
        contract = json.loads((ROOT / 'contract/compatibility-rime1161-v4.json').read_text())
        self.assertEqual(contract['id'], PROFILE_V4)
        self.assertEqual(contract['runtime_files'], RUNTIME_V4)
        self.assertEqual(contract['recipe_sha256'], recipe_sha(PROFILES[PROFILE_V4]))
        v2 = json.loads((ROOT / 'contract/compatibility-rime1161-v2.json').read_text())
        self.assertEqual({k: v for k, v in contract.items() if k not in ('id', 'runtime_files', 'recipe_sha256')},
                         {k: v for k, v in v2.items() if k not in ('id', 'runtime_files', 'recipe_sha256')})
        # v3 was ReRime's retired grammar profile; its ID is never reused.
        self.assertNotIn('wanxiang-ios-arm64-rime1161-v3', PROFILES)

    def test_v4_is_selected_explicitly_and_binds_its_recipe(self):
        with patch.dict('os.environ', {'RERIME_PROFILE': PROFILE_V4}):
            self.assertEqual(build_profile()['id'], PROFILE_V4)
        self.assertEqual(len({recipe_sha(p) for p in PROFILES.values()}), 3)
        validate_manifest(manifest(PROFILES[PROFILE_V4]))
        v2, v4 = manifest(PROFILES[PROFILE_V2]), manifest(PROFILES[PROFILE_V4])
        for label, value in [('v4-with-v2-files', dict(v4, files=v2['files'])),
                             ('v4-with-v2-recipe', dict(v4, recipe_sha256=v2['recipe_sha256'])),
                             ('v2-with-v4-files', dict(v2, files=v4['files']))]:
            with self.subTest(label=label), self.assertRaises((ValueError, KeyError)):
                validate_manifest(value)

    def test_v4_app_floor_is_the_dual_translator_build(self):
        self.assertEqual(minimum_app_build(policy(), PROFILE_V4), 63)

    def test_adapter_copies_xiaohe_files_only_for_v4(self):
        for profile, present in [(PROFILE, False), (PROFILE_V2, False), (PROFILE_V4, True)]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                with patch('adapt.download', fake_download):
                    build(work, 'a' * 40, profile)
                adapted = work / 'adapted'
                for name in [*RECIPE_V4_ONLY, xiaohe_symbols.OUTPUT]:
                    self.assertEqual((adapted / name).exists(), present, name)
                self.assertEqual(work_profile(work)['id'], profile)
                if present:
                    self.assertIn('    - schema: wanxiang_xiaohe', (adapted / 'default.custom.yaml').read_text())

    def test_packing_requires_the_xiaohe_prism_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'build').mkdir()
            magic = {'table': b'Rime::Table/4.0\0', 'prism': b'Rime::Prism/4.0\0', 'reverse': b'Rime::Reverse/3.1\0'}
            for name in ('wanxiang', 'wanxiang_english', 'wanxiang_mixedcode'):
                for suffix, data in magic.items():
                    (root / f'build/{name}.{suffix}.bin').write_bytes(data)
            (root / 'build/wanxiang_t9.prism.bin').write_bytes(magic['prism'])
            validate_compiled(root, PROFILES[PROFILE_V2])
            with self.assertRaises(FileNotFoundError):
                validate_compiled(root, PROFILES[PROFILE_V4])
            (root / 'build/wanxiang_xiaohe.prism.bin').write_bytes(magic['table'])
            with self.assertRaises(ValueError):
                validate_compiled(root, PROFILES[PROFILE_V4])
            (root / 'build/wanxiang_xiaohe.prism.bin').write_bytes(magic['prism'])
            validate_compiled(root, PROFILES[PROFILE_V4])


class XiaoheSchemaTests(unittest.TestCase):
    def test_speller_is_upstream_xiaohe_with_v_as_an_initial_and_jianpin(self):
        speller = block(XIAOHE, 'speller')
        for key in ('alphabet', 'initials'):
            value = re.search(rf'{key}: (\S+)', speller).group(1)
            self.assertEqual(value, 'abcdefghijklmnopqrstuvwxyz' + 'abcdefghijklmnopqrstuvwxyz'.upper())
        rules = re.findall(r'^    - (\S+)(?:  # .*)?$', speller, re.M)
        self.assertEqual(rules[0], 'xform/Ⅲ//')
        # Upstream's last three rules: derive/^(..)(\d)$/$1/, derive/^(.).+(\d)$/$1$2/ and the
        # commented-out 简拼 rule. ReRime keeps only typeable spellings and turns 简拼 on.
        self.assertEqual(rules[-3:], ['xform/^(aj|ac|ad|ew|ef|oz)(\\d?)$//', 'xform/^(..)(\\d)$/$1/',
                                      'abbrev/^([a-z]).+$/$1/'])
        self.assertNotIn('derive/^(.).+(\\d)$/$1$2/', rules)
        self.assertFalse(set('0123456789') & set(re.search(r'alphabet: (\S+)', speller).group(1)))
        self.assertEqual(sum(rule.startswith('abbrev/') for rule in rules), 1)
        for rule in ['xform/^sh/Ⓤ/', 'xform/^ch/Ⓘ/', 'xform/^zh/Ⓥ/',
                     'xlit/ⓆⓌⓇⓉⓎⓊⒾⓄⓅⓈⒹⒻⒼⒽⒿⓀⓁⓏⓍⒸⓋⒷⓃⓂ/qwrtyuiopsdfghjklzxcvbnm/']:
            self.assertIn(rule, rules)
        # Not ReRime's 全拼 rules: no full-Pinyin typo derivations or abbreviations.
        full = (RECIPE / 'wanxiang_full_pinyin.yaml').read_text()
        self.assertNotIn('__include', speller)
        self.assertFalse({line.strip()[2:] for line in full.splitlines() if 'derive/([' in line} & set(rules))

    def test_translator_shares_the_wanxiang_dictionary_and_comments_carry_pinyin(self):
        translator = block(XIAOHE, 'translator')
        for line in ['dictionary: wanxiang', 'prism: wanxiang_xiaohe', 'enable_user_dict: true',
                     'enable_completion: true', 'enable_sentence: true', 'enable_correction: false',
                     'spelling_hints: 50', 'always_show_comments: true']:
            self.assertIn('  ' + line + '\n', translator)
        self.assertNotRegex(translator, r'(?m)^  user_dict:')  # learning stays in wanxiang's user dictionary
        self.assertEqual(block(XIAOHE, 'translator').split('comment_format:\n')[1],
                         block((RECIPE / 'wanxiang_t9.schema.yaml').read_text(), 'translator').split('comment_format:\n')[1])
        self.assertNotIn('preedit_format', translator)  # raw 小鹤 codes; ReRime decodes them (IME-547 C)

    def test_translators_are_the_app_grammar_opt_in_and_personal_xiaohe(self):
        engine = block(XIAOHE, 'engine')
        translators = re.search(r'translators: \[(.*)\]', engine).group(1).split(', ')
        self.assertEqual(translators, ['punct_translator', 'rerime_dual_script_translator@translator',
                                       'table_translator@personal_xiaohe', 'table_translator@learned_english',
                                       'table_translator@english', 'table_translator@mixed'])
        self.assertTrue(XIAOHE.endswith('\n' + APP_GRAMMAR))
        personal = block(XIAOHE, 'personal_xiaohe')
        for line in ["dictionary: ''", 'user_dict: rerime_personal_xiaohe', 'db_class: stabledb', 'initial_quality: 100']:
            self.assertIn('  ' + line + '\n', personal)
        self.assertNotIn('table_translator@personal,', XIAOHE)
        for absent in ['lua_', 'wanxiang_lite', 'rerime_symbols:', 'rerime_symbol_recognizer:']:
            self.assertNotIn(absent, BODY)

    def test_everything_else_matches_the_quanpin_schema(self):
        quanpin = (RECIPE / 'wanxiang.schema.yaml').read_text()
        for key in ['switches', 'learned_english', 'english', 'mixed', 'emoji', 'traditionalize', 'key_binder']:
            self.assertEqual(block(XIAOHE, key), block(quanpin, key), key)
        for key in ['processors', 'segmentors', 'filters']:
            self.assertEqual(re.search(rf'  {key}: .*\n', XIAOHE).group(0), re.search(rf'  {key}: .*\n', quanpin).group(0))
        self.assertEqual(block(XIAOHE, 'punctuator').replace('rerime_xiaohe_symbols:', 'rerime_symbols:'),
                         block(quanpin, 'punctuator'))
        self.assertEqual(block(XIAOHE, 'recognizer').replace('rerime_xiaohe_symbols:/patterns', 'rerime_symbol_recognizer:/patterns'),
                         block(quanpin, 'recognizer'))


class XiaoheSymbolTests(unittest.TestCase):
    def generated(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in (xiaohe_symbols.SYMBOLS, xiaohe_symbols.RECOGNIZER):
            (root / name).write_bytes((RECIPE / name).read_bytes())
        return root, xiaohe_symbols.generate(root), (root / xiaohe_symbols.OUTPUT).read_text()

    def test_every_v_code_moves_to_shift_v_and_slash_stays(self):
        _, counts, text = self.generated()
        source = (RECIPE / xiaohe_symbols.SYMBOLS).read_text().splitlines()[2:]
        output = text.split('symbols:\n', 1)[1].splitlines()
        self.assertEqual(counts['V'], counts['slash'])
        self.assertEqual(len(output), len(source))
        for before, after in zip(source, output):
            self.assertEqual(after, before.replace('  "v', '  "V', 1) if before.startswith('  "v') else before)
        self.assertFalse(any(line.startswith('  "v') for line in output))
        self.assertIn('  "Vjt": ["→"', text)
        self.assertIn('  "/jt": ["→"', text)

    def test_the_recognizer_takes_shift_v_codes_and_leaves_lowercase_v_to_the_speller(self):
        _, _, text = self.generated()
        patterns = text.split('symbols:\n', 1)[0]
        self.assertEqual(patterns.count('\n  '), 1)
        pattern = json.loads(re.search(r'  punct: (".*")\n', patterns).group(1))
        for code in ['Vjt', 'Vfh', 'V1', 'Vd', 'Vxl', '/jt', '/anything']:
            self.assertTrue(re.fullmatch(pattern, code), code)
        # zh = v: 小鹤 codes and English stay out of the symbol path.
        for code in ['vjt', 'vfh', 'vd', 'vi', 'vsgo', 'uide', 'V', 'Vjtx', 'hello']:
            self.assertFalse(re.fullmatch(pattern, code), code)
        quanpin = json.loads(re.search(r'  punct: (".*")\n', (RECIPE / xiaohe_symbols.RECOGNIZER).read_text()).group(1))
        self.assertEqual(pattern, quanpin.replace('^(?:v(?:', '^(?:V(?:', 1))

    def test_a_changed_source_stops_the_build(self):
        root, _, _ = self.generated()
        symbols = (root / xiaohe_symbols.SYMBOLS).read_text()
        recognizer = (root / xiaohe_symbols.RECOGNIZER).read_text()
        for name, text, error in [
                (xiaohe_symbols.SYMBOLS, symbols.replace('  "/---": ["—"]\n', ''), 'xiaohe-symbols-twins'),
                (xiaohe_symbols.SYMBOLS, symbols + '  vxyz: ["x"]\n', 'xiaohe-symbols-entry'),
                (xiaohe_symbols.SYMBOLS, symbols.replace('# Generated', '# Edited', 1), 'xiaohe-symbols-source'),
                (xiaohe_symbols.RECOGNIZER, recognizer.replace('|/[A-Za-z0-9?./_-]*)$"', ')$"'), 'xiaohe-symbols-recognizer')]:
            with self.subTest(error=error):
                (root / name).write_text(text)
                with self.assertRaisesRegex(ValueError, error):
                    xiaohe_symbols.generate(root)
                (root / xiaohe_symbols.SYMBOLS).write_text(symbols)
                (root / xiaohe_symbols.RECOGNIZER).write_text(recognizer)


class XiaoheConsumerTests(unittest.TestCase):
    def test_v4_consumer_runs_every_profile_case(self):
        self.assertEqual(consumer_cases(PROFILE_V2), CONSUMER_CASES + T9_CONSUMER_CASES)
        self.assertEqual(consumer_cases(PROFILE_V4), CONSUMER_CASES + T9_CONSUMER_CASES + XIAOHE_CONSUMER_CASES)

    def test_cases_are_real_xiaohe_codes(self):
        words = {'你好': 'ni hao', '是的': 'shi de', '中国': 'zhong guo', '中國': 'zhong guo', '知': 'zhi',
                 '第一个': 'di yi ge', '正': 'zheng',
                 '中国人民': 'zhong guo ren min', '今天天气': 'jin tian tian qi', '瑞莱姆工坊': 'rui lai mu gong fang'}
        for label, schema, text, expected, mode, feed, comment in [*XIAOHE_CASES, XIAOHE_PERSONAL_CASE]:
            with self.subTest(case=label):
                self.assertEqual((schema, feed), ('wanxiang_xiaohe', 'keys'))
                if text[0] in 'V/':
                    continue
                codes = [xiaohe_code(s) for s in words[expected].split()]
                self.assertTrue(text == ''.join(codes) or text == ''.join(codes)[:-1] or
                                any(text == ''.join(c if i != k else c[0] for i, c in enumerate(codes))
                                    for k in range(len(codes))) or text == ''.join(c[0] for c in codes), text)
                if comment != '-':
                    self.assertEqual(comment, words[expected])

    def test_stand_in_requires_the_app_opt_in_form(self):
        # As librime writes it: keys sorted, values quoted.
        compiled = ('engine:\n  translators:\n    - punct_translator\n' + XIAOHE_TRANSLATOR[0] +
                    '    - table_translator@personal_xiaohe\ngrammar:\n  collocation_max_length: 6\n'
                    '  language: "rerime-grammar"\n  rear_penalty: "-18"\nkey_binder:\n  import_preset: default\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wanxiang_xiaohe.schema.yaml'
            path.write_text(compiled)
            self.assertEqual(xiaohe_stand_in(path), dict(xiaohe_rerime_translator=1, xiaohe_grammar_block=1))
            self.assertIn(XIAOHE_TRANSLATOR[1], path.read_text())
            for broken in [compiled.replace(XIAOHE_TRANSLATOR[0], XIAOHE_TRANSLATOR[1]),
                           compiled.replace('\ngrammar:\n', '\nother:\n'),
                           compiled.replace('rerime-grammar', 'other-grammar')]:
                path.write_text(broken)
                with self.assertRaisesRegex(ValueError, 'consumer-xiaohe-translator'):
                    xiaohe_stand_in(path)


if __name__ == '__main__':
    unittest.main()
