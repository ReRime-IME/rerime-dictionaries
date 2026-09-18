"""Build-time Wanxiang-to-OpenCC adapter; no legacy alias or per-key runtime work."""
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_locked(root):
    lock = json.loads((root / 'source-lock.json').read_text())
    if lock['repository'] != 'https://github.com/amzxyz/rime-wanxiang':
        raise ValueError('Unexpected auxiliary upstream')
    for name, expected in lock['files'].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe auxiliary source path')
        if digest(path.read_bytes()) != expected:
            raise ValueError('Auxiliary source hash mismatch: ' + name)
    return lock


def convert_emoji(data):
    """Keep the original word available, then preserve Wanxiang alternative order."""
    seen = set()
    # OpenCC TextDict does not support comment lines; attribution stays in NOTICE/lock.
    lines = []
    for raw in data.decode('utf-8').splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        parts = raw.split()
        if len(parts) < 2 or parts[0] in seen:
            raise ValueError('Invalid or duplicate Wanxiang Emoji row')
        key, *values = parts
        seen.add(key)
        alternatives = list(dict.fromkeys([key, *values]))
        lines.append(key + '\t' + ' '.join(alternatives))
    if not seen:
        raise ValueError('Empty Wanxiang Emoji input')
    return ('\n'.join(lines) + '\n').encode()


def generate(overlay):
    source = overlay / 'upstream-auxiliary'
    upstream = read_locked(source)
    configuration = {
        'name': 'Wanxiang word-triggered Emoji',
        'segmentation': {'type': 'mmseg', 'dict': {'type': 'text', 'file': 'emoji.txt'}},
        'conversion_chain': [{'dict': {'type': 'text', 'file': 'emoji.txt'}}],
    }
    payload = {
        'opencc/emoji.txt': convert_emoji((source / 'lua/data/emoji.txt').read_bytes()),
        'opencc/emoji.json': (json.dumps(configuration, indent=2) + '\n').encode(),
    }
    for name, data in payload.items():
        (overlay / name).write_bytes(data)
    lock = {key: upstream[key] for key in ('repository', 'revision', 'licenseSPDX')}
    lock['adaptation'] = 'Original-word passthrough plus ordered Wanxiang alternatives; no Ice aliases.'
    lock['upstreamFiles'] = upstream['files']
    lock['files'] = {name: digest(data) for name, data in payload.items()}
    (overlay / 'emoji-source-lock.json').write_text(json.dumps(lock, indent=2) + '\n')


if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1] / 'recipe/wanxiang-v1')
