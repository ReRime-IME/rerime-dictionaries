"""Small versioned data contract shared by producer validation and public fixtures."""
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'wanxiang-ios-arm64-rime1161-v1'
ENGINE_SHA = 'd123d38b004d60548eef21c2688c17a9b988c8565dd8aee334a8fe215f273bd5'
SCHEMAS = ('wanxiang', 'wanxiang_english', 'wanxiang_mixedcode')
RUNTIME = sorted(['default.yaml', 'build/default.yaml', 'opencc/s2t.json', 'opencc/STCharacters.ocd2',
    'opencc/STPhrases.ocd2', 'opencc/LICENSE', 'opencc/emoji.json', 'opencc/emoji.txt', 'opencc/others.txt',
    'LICENSE', 'NOTICE.md', 'LICENSE-rime-ice.txt', 'upstream-lock.json', 'qualification.json', 'build-receipt.json'] +
    [f'build/{name}.{suffix}' for name in SCHEMAS for suffix in ('schema.yaml','table.bin','prism.bin','reverse.bin')])
MAX_ZIP = 512 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for data in iter(lambda: stream.read(256 * 1024), b''): digest.update(data)
    return digest.hexdigest()

def fingerprints(root, paths):
    return [dict(path=p, size=(root/p).stat().st_size, sha256=file_sha(root/p)) for p in sorted(paths)]

def strict_json(data, limit=256*1024, require_canonical=False):
    if len(data) > limit: raise ValueError('json-size')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate-key')
            result[key] = value
        return result
    def number(text):
        value = int(text)
        if not 0 <= value <= 2**53-1: raise ValueError('number')
        return value
    def invalid(_): raise ValueError('number')
    result = json.loads(data, object_pairs_hook=pairs, parse_int=number, parse_float=invalid, parse_constant=invalid)
    count = 0
    def walk(value, depth):
        nonlocal count
        count += 1
        if count > 12000 or depth > 12: raise ValueError('json-complexity')
        if type(value) is dict:
            if len(value) > 1024: raise ValueError('json-items')
            for key, child in value.items():
                if not isinstance(key, str): raise ValueError('key')
                walk(child, depth+1)
        elif type(value) is list:
            if len(value) > 1024: raise ValueError('json-items')
            for child in value: walk(child, depth+1)
        elif type(value) not in (str, int): raise ValueError('type')
    walk(result, 0)
    if require_canonical and canonical(result) != data: raise ValueError('canonical')
    return result

def validate(value, schema):
    """Only the JSON Schema vocabulary used in this repository's frozen contract."""
    types = {'object':dict, 'array':list, 'string':str, 'integer':int}
    if 'type' in schema and type(value) is not types[schema['type']]: raise ValueError('schema-type')
    if 'const' in schema and value != schema['const']: raise ValueError('schema-const')
    if 'enum' in schema and value not in schema['enum']: raise ValueError('schema-enum')
    if type(value) is dict:
        if set(schema.get('required',[])) - value.keys(): raise ValueError('schema-required')
        props = schema.get('properties',{})
        if schema.get('additionalProperties') is False and value.keys() - props.keys(): raise ValueError('schema-extra')
        for key, child in value.items():
            if key in props: validate(child, props[key])
    elif type(value) is list:
        if not schema.get('minItems',0) <= len(value) <= schema.get('maxItems',2**53-1): raise ValueError('schema-items')
        if schema.get('uniqueItems') and len({canonical(v) for v in value}) != len(value): raise ValueError('schema-unique')
        for child in value: validate(child,schema['items'])
    elif type(value) is str:
        if not schema.get('minLength',0) <= len(value) <= schema.get('maxLength',2**53-1): raise ValueError('schema-length')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value): raise ValueError('schema-pattern')
    elif type(value) is int:
        if not schema.get('minimum',0) <= value <= schema.get('maximum',2**53-1): raise ValueError('schema-number')

def validate_manifest(value):
    validate(value,json.loads((ROOT/'contract/package-v4.schema.json').read_text()))
    if [f['path'] for f in value['files']] != RUNTIME: raise ValueError('runtime-file-set')
    if sum(f['size'] for f in value['files']) > MAX_EXPANDED: raise ValueError('expanded-size')
    if value['release_id'] != f"wanxiang-precompiled-{value['package_revision']}-{value['upstream_revision'][:12]}": raise ValueError('release-id')
    if value['recipe_sha256'] != json.loads((ROOT/'locks/recipe.json').read_text())['sha256']: raise ValueError('recipe')
    receipt = next(f for f in value['files'] if f['path']=='build-receipt.json')
    if receipt['sha256'] != value['build_receipt_sha256']: raise ValueError('receipt-hash')

def validate_compatibility(value, app_version='0.6.1', app_build=21, system_version='26.5'):
    if system_version not in value['qualified_os'] or system_version != '26.5': raise ValueError('qualified-os')
    current=tuple(map(int,app_version.split('.'))); minimum=tuple(map(int,value['minimum_app_version'].split('.')))
    if current<minimum or app_build<value['minimum_app_build']: raise ValueError('minimum-app')

def envelope_payload(data, maximum=256*1024):
    value = strict_json(data, maximum*2)
    if set(value) != {'key_id','payload_base64','signature_base64'}: raise ValueError('envelope')
    for field in ('payload_base64','signature_base64'):
        decoded = base64.b64decode(value[field],validate=True)
        if base64.b64encode(decoded).decode() != value[field]: raise ValueError('base64')
    payload = base64.b64decode(value['payload_base64'],validate=True)
    if len(payload) > maximum or len(base64.b64decode(value['signature_base64'])) != 64: raise ValueError('envelope-size')
    return value, payload
