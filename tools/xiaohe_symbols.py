"""The 小鹤双拼 symbol table, derived from the locked recipe on every v4 build.

ReRime's 全拼 schema opens a symbol code with `v` (`vfh`, `vd`) or `/`. In 小鹤双拼 `v` is
the zh initial (`vi` 中, `vd` 债), so `wanxiang_xiaohe` opens the same codes with Shift+V
(`Vfh`, `Vd`) and keeps `/`. This step writes `rerime_xiaohe_symbols.yaml` beside the
copied recipe: every `/` entry of `rerime_symbols.yaml` unchanged, every `v` entry with
its prefix changed to `V`, and the recognizer pattern of `rerime_symbol_recognizer.yaml`
with the same change. The 全拼 `abc` pattern, which only lets non-code `v` input reach the
speller, is not needed: `v` and `V` are 小鹤 initials. Nothing is hand-copied, so the table
cannot drift from the qualified symbol catalog; a source whose shape changed stops the build.
"""
import re
from pathlib import Path

SYMBOLS = 'rerime_symbols.yaml'
RECOGNIZER = 'rerime_symbol_recognizer.yaml'
OUTPUT = 'rerime_xiaohe_symbols.yaml'
ENTRY = re.compile(r'  "([v/])((?:[^"\\]|\\.)*)": (\[.*\])\n')
PUNCT = re.compile(r'  punct: "\^\(\?:v\(\?:(.+)\)\|/\[A-Za-z0-9\?\./_-\]\*\)\$"\n')
SLASH = '|/[A-Za-z0-9?./_-]*)$"\n'


def generate(destination):
    """Write OUTPUT into the adapted recipe copy at `destination`; return entry counts."""
    lines = (destination / SYMBOLS).read_text().splitlines(True)
    if not lines or lines[0] != '# Generated from the qualified iOS symbol catalog; do not edit.\n' or lines[1] != 'symbols:\n':
        raise ValueError('xiaohe-symbols-source')
    entries, counts = [], {'v': 0, '/': 0}
    for line in lines[2:]:
        match = ENTRY.fullmatch(line)
        if not match:
            raise ValueError('xiaohe-symbols-entry')
        prefix, code, value = match.groups()
        counts[prefix] += 1
        entries.append(f'  "{"V" if prefix == "v" else "/"}{code}": {value}\n')
    if not counts['v'] or counts['v'] != counts['/']:
        raise ValueError('xiaohe-symbols-twins')
    punct = [line for line in (destination / RECOGNIZER).read_text().splitlines(True) if line.startswith('  punct: ')]
    if len(punct) != 1 or not PUNCT.fullmatch(punct[0]) or not punct[0].endswith(SLASH):
        raise ValueError('xiaohe-symbols-recognizer')
    pattern = punct[0].replace('  punct: "^(?:v(?:', '  punct: "^(?:V(?:', 1)
    (destination / OUTPUT).write_text(
        '# Generated at build time by tools/xiaohe_symbols.py from rerime_symbols.yaml and\n'
        '# rerime_symbol_recognizer.yaml: the 全拼 `v` prefix becomes `V` (zh = v in 小鹤); do not edit.\n'
        'patterns:\n' + pattern + 'symbols:\n' + ''.join(entries))
    return dict(V=counts['v'], slash=counts['/'])
