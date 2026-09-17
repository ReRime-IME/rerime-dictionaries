#!/usr/bin/env python3
"""Fetch a fixed public commit and parse dictionary data without executing YAML."""
import argparse
import json
import re
import shutil
import urllib.request
from pathlib import Path
from contract import ROOT, SCHEMAS, canonical, fingerprints, sha
from local_additions import apply as apply_local_additions

MAX_FILE = 80 * 1024 * 1024
TABLE = re.compile(r'dicts/[a-z_]{1,40}')

def download(url, destination):
    request = urllib.request.Request(url,headers={'User-Agent':'rerime-public-dictionaries/1'})
    total = 0
    with urllib.request.urlopen(request,timeout=60) as response, open(destination,'xb') as output:
        if response.geturl().split('/')[2] != 'raw.githubusercontent.com': raise ValueError('source-redirect')
        while data := response.read(256*1024):
            total += len(data)
            if total > MAX_FILE: raise ValueError('source-size')
            output.write(data)
    if total == 0: raise ValueError('empty-source')

def header(stream, expected=None):
    found = {}; imports=[]; start=False; importing=False; size=0
    for raw in stream:
        size += len(raw)
        if size > 16*1024: raise ValueError('header-size')
        line = raw.decode('utf-8').split('#',1)[0].strip()
        if not line: continue
        if line=='---':
            if start: raise ValueError('header-start')
            start=True;continue
        if not start: raise ValueError('header-start')
        if line=='...': break
        if line.startswith('- '):
            item=line[2:]
            if not importing or not TABLE.fullmatch(item) or item in imports or len(imports)>=64: raise ValueError('import')
            imports.append(item);continue
        if ':' not in line: raise ValueError('header-field')
        key,value=line.split(':',1);value=value.strip();importing=False
        if key in found: raise ValueError('duplicate-header')
        if key=='name':
            if not re.fullmatch('[a-z_]{1,64}',value): raise ValueError('name')
        elif key=='version':
            if not 1<=len(value)<=80: raise ValueError('version')
        elif key=='sort':
            if value not in ('by_weight','original'): raise ValueError('sort')
        elif key=='use_preset_vocabulary':
            if value!='false': raise ValueError('preset')
        elif key=='import_tables':
            if expected is None or value: raise ValueError('import-scope')
            importing=True
        else: raise ValueError('unknown-header')
        found[key]=value
    else: raise ValueError('header-end')
    if not {'name','version','sort'} <= found.keys(): raise ValueError('required-header')
    if expected and (found['name'] != expected or not imports): raise ValueError('root-name')
    return found,imports

def adapt(source,destination,expected=None,english=False):
    rows=0
    with open(source,'rb') as stream,open(destination,'xb') as output:
        fields,imports=header(stream,expected)
        text=f"# Public dictionary adaptation; attribution retained in corresponding-source.\n---\nname: {fields['name']}\nversion: \"LTS\"\nsort: {fields['sort']}\nuse_preset_vocabulary: false\n"
        if imports:text+='import_tables:\n'+''.join(f'  - {item}\n' for item in imports)
        output.write((text+'...\n').encode())
        for raw in stream:
            if len(raw)>16*1024: raise ValueError('row-size')
            line=raw.decode('utf-8').rstrip('\n').removesuffix('\r')
            if not line or line.startswith('#'): continue
            if expected: raise ValueError('root-inline-data')
            columns=line.split('\t')
            if not 2<=len(columns)<=4 or not columns[0] or not columns[1]: raise ValueError('row-columns')
            if len(columns[0].encode('utf-16-le'))>1024 or len(columns[1].encode('utf-16-le'))>2048: raise ValueError('row-length')
            if any(ord(c)<32 and c!='\t' for c in line): raise ValueError('row-control')
            if len(columns)>=3 and (len(columns[2])>32 or any(not 32<=ord(c)<=126 for c in columns[2])): raise ValueError('weight')
            if len(columns)==4 and len(columns[3].encode('utf-16-le'))>1024: raise ValueError('annotation')
            if english: columns[1]=columns[1].translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
            rows+=1
            if rows>4_000_000: raise ValueError('row-count')
            output.write(('\t'.join(columns)+'\n').encode())
    if expected is None and rows==0: raise ValueError('empty-table')
    return imports,rows

def build(work,revision):
    if not re.fullmatch('[0-9a-f]{40}',revision): raise ValueError('revision')
    source=work/'original';destination=work/'adapted'
    source.mkdir(parents=True,exist_ok=False);destination.mkdir(exist_ok=False)
    (source/'dicts').mkdir();(destination/'dicts').mkdir()
    recipe=ROOT/'recipe/wanxiang-v1'
    lock=json.loads((ROOT/'locks/recipe.json').read_text())
    actual=fingerprints(recipe,[f['path'] for f in lock['files']])
    if actual!=lock['files'] or sha(canonical(actual))!=lock['sha256']: raise ValueError('recipe-integrity')
    for entry in actual:
        target=destination/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(recipe/entry['path'],target)
    paths=[];tables={};rows={}
    def fetch(path):
        download(f'https://raw.githubusercontent.com/amzxyz/rime-wanxiang/{revision}/{path}',source/path)
        paths.append(path)
        if sum((source/p).stat().st_size for p in paths)>256*1024*1024: raise ValueError('total-source-size')
    for schema in SCHEMAS:
        path=schema+'.dict.yaml';fetch(path)
        imports,_=adapt(source/path,destination/path,expected=schema)
        for table in imports:
            english=schema=='wanxiang_english'
            if table in tables and tables[table]!=english: raise ValueError('shared-table-semantics')
            tables[table]=english
    for table,english in sorted(tables.items()):
        path=table+'.dict.yaml';fetch(path)
        _,rows[path]=adapt(source/path,destination/path,english=english)
    apply_local_additions(destination)
    fetch('LICENSE')
    # License drift requires review rather than automatically replacing notices.
    if (source/'LICENSE').read_bytes()!=(recipe/'LICENSE').read_bytes(): raise ValueError('license-changed')
    entries=fingerprints(source,paths)
    receipt=dict(format_version=1,repository='amzxyz/rime-wanxiang',revision=revision,source_digest=sha(canonical(entries)),files=entries)
    (destination/'upstream-lock.json').write_bytes(canonical(receipt))
    (work/'source-receipt.json').write_bytes(canonical(receipt))
    (work/'adapt-receipt.json').write_bytes(canonical(dict(format_version=1,rows=rows,english_ascii_lowercase=1)))
    print(json.dumps(dict(stage='adapted',files=len(paths),rows=sum(rows.values()),source_digest=receipt['source_digest'])),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--revision')
    args=parser.parse_args(); revision=args.revision or json.loads((ROOT/'locks/source.json').read_text())['revision']
    build(args.work.resolve(),revision)
