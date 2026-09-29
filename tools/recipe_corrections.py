"""ReRime corrections to upstream Wanxiang spelling rules, applied on every build.

The locked recipe stays byte-identical to what was reviewed from upstream; its
hash and the App trust list do not change. Each correction replaces one exact rule
line in the adapted copy before compilation. A correction whose rule line is
neither present nor already corrected stops the build, so a refreshed recipe can
never quietly bring a removed rule back or drop a fix. This overlay and its data
are bound by the producer tool digest and included in the corresponding-source
archive.
"""
import json
from pathlib import Path
from contract import canonical, file_sha

DATA = Path(__file__).with_suffix('.json')


def apply(destination):
    data = json.loads(DATA.read_text())
    if data['format_version'] != 1:
        raise ValueError('recipe-corrections-version')
    applied = []
    for correction in data['corrections']:
        find, replace = correction['find'], correction['replace']
        if not find.endswith('\n') or not replace.endswith('\n') or find == replace:
            raise ValueError('recipe-correction-shape:' + correction['id'])
        path = destination / correction['file']
        text = path.read_text()
        if text.count(find) == 1 and replace not in text:
            path.write_text(text.replace(find, replace, 1))
        elif not (text.count(replace) == 1 and find not in text):
            raise ValueError('recipe-correction-missing:' + correction['id'])
        applied.append(dict(id=correction['id'], file=correction['file'], sha256=file_sha(path)))
    receipt = dict(format_version=1, data_sha256=file_sha(DATA), corrections=applied)
    (destination.parent / 'recipe-corrections-receipt.json').write_bytes(canonical(receipt))
