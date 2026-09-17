"""ReRime-owned additions applied after upstream adaptation, on every build.

The locked upstream recipe stays immutable. This overlay and its data are bound by
the producer tool digest and included in the corresponding-source archive.
"""
import json
from pathlib import Path
from contract import canonical, file_sha

DATA = Path(__file__).with_suffix('.json')


def apply(destination):
    data = json.loads(DATA.read_text())
    if data['format_version'] != 1:
        raise ValueError('local-additions-version')
    entries = data['entries']
    root = destination / 'wanxiang.dict.yaml'
    text = root.read_text()
    table = 'dicts/rerime_regions'
    if 'import_tables:\n' not in text or text.count('...\n') != 1:
        raise ValueError('local-additions-root')
    if f'  - {table}\n' not in text:
        if (destination / (table + '.dict.yaml')).exists():
            raise ValueError('local-additions-table-collision')
        text = text.replace('...\n', f'  - {table}\n...\n', 1)
        root.write_text(text)
    dictionary = destination / (table + '.dict.yaml')
    dictionary.write_text('---\nname: rerime_regions\nversion: "1"\nsort: by_weight\nuse_preset_vocabulary: false\n...\n' +
                          ''.join(f"{e['text']}\t{e['pinyin']}\t100\n" for e in entries))
    emoji = destination / 'opencc/emoji.txt'
    lines = emoji.read_text().splitlines()
    positions = {line.split('\t', 1)[0]: i for i, line in enumerate(lines) if '\t' in line}
    for entry in entries:
        key, flag = entry['text'], entry['emoji']
        if key in positions:
            index = positions[key]
            before, values = lines[index].split('\t', 1)
            alternatives = values.split(' ')
            if flag not in alternatives:
                lines[index] = before + '\t' + values + ' ' + flag
        else:
            positions[key] = len(lines)
            lines.append(key + '\t' + key + ' ' + flag)
    emoji.write_text('\n'.join(lines) + '\n')
    # Historical recipe glyph qualification remains upstream-only; never rewrite it
    # to suggest new native qualification. Runtime consumer tests cover the overlay.
    receipt = dict(format_version=1, data_sha256=file_sha(DATA), entries=len(entries),
                   emoji_sha256=file_sha(emoji), dictionary_sha256=file_sha(dictionary))
    (destination.parent / 'local-additions-receipt.json').write_bytes(canonical(receipt))
