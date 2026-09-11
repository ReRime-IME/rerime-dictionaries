"""Authenticated-channel shape and time policy. Signature verification is separate."""
import json
from contract import ROOT,validate

REPOSITORY = 'Nongfsq/rerime-dictionaries'

def validate_channel(value, now):
    validate(value, json.loads((ROOT/'contract/channel-v1.schema.json').read_text()))
    release = value['release_id']
    if not release.startswith(f"wanxiang-precompiled-{value['package_revision']}-"):
        raise ValueError('release-identity')
    expected = f'https://github.com/{REPOSITORY}/releases/download/{release}/ReRime-{release}.zip'
    if value['package_url'] != expected:
        raise ValueError('release-url')
    issued,expires,checked = (value[k] for k in ('issued_at','expires_at','upstream_checked_at'))
    if issued > now+300 or expires <= now or not issued < expires <= issued+30*86400 or checked > issued:
        raise ValueError('channel-time')
    return value
