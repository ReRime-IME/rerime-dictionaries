"""Resolve official upstream Releases; never silently substitute branch HEAD."""
import re
from urllib.parse import quote
from release_http import api

UPSTREAM = 'repos/amzxyz/rime-wanxiang'


def resolve_release(release_id=None):
    if release_id is not None and not re.fullmatch(r'[1-9][0-9]{0,18}', str(release_id)):
        raise ValueError('release-id')
    release = api(f'{UPSTREAM}/releases/{release_id or "latest"}')
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('release-not-official')
    if not release.get('published_at') or type(release.get('id')) is not int:
        raise ValueError('release-unpublished')
    tag = release.get('tag_name', '')
    if not isinstance(tag, str) or not 1 <= len(tag) <= 128:
        raise ValueError('release-tag')
    obj = api(f'{UPSTREAM}/git/ref/tags/{quote(tag, safe="")}')['object']
    for _ in range(5):
        if not re.fullmatch('[0-9a-f]{40}', obj.get('sha', '')):
            raise ValueError('release-object')
        if obj.get('type') == 'commit':
            return dict(id=release['id'], tag=tag, revision=obj['sha'])
        if obj.get('type') != 'tag':
            break
        obj = api(f'{UPSTREAM}/git/tags/{obj["sha"]}')['object']
    raise ValueError('release-tag-depth')


def release_relation(base, revision):
    if not all(re.fullmatch('[0-9a-f]{40}', value) for value in (base, revision)):
        raise ValueError('release-revision')
    if base == revision:
        return 'identical'
    result = api(f'{UPSTREAM}/compare/{base}...{revision}')
    status = result.get('status')
    if status not in ('ahead', 'behind', 'identical', 'diverged'):
        raise ValueError('release-ancestry')
    return status
