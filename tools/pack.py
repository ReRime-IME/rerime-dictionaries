#!/usr/bin/env python3
"""Deterministic public source/runtime packaging; signing is a separate step."""
import argparse
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from contract import ROOT, RUNTIME, SCHEMAS, PROFILE, ENGINE_SHA, canonical, file_sha, fingerprints, validate_manifest

STAMP=(2026,1,1,0,0,0)

def zip_files(destination, files):
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for name,path in sorted(files.items()):
            if path.is_symlink() or not path.is_file(): raise ValueError('package-file')
            info=zipfile.ZipInfo(name,STAMP);info.create_system=3;info.external_attr=0o100644<<16
            info.compress_type=zipfile.ZIP_DEFLATED;info.file_size=path.stat().st_size
            with output.open(info,'w') as target,open(path,'rb') as source: shutil.copyfileobj(source,target,262144)

def validate_compiled(root):
    for schema in SCHEMAS:
        for suffix,magic in [('table',b'Rime::Table/4.0\0'),('prism',b'Rime::Prism/4.0\0'),('reverse',b'Rime::Reverse/3.1\0')]:
            with open(root/f'build/{schema}.{suffix}.bin','rb') as stream:
                if not stream.read(32).startswith(magic): raise ValueError('compiled-format')

def prepare(work, output, revision, adapter_revision, app_build):
    if not re.fullmatch('[0-9a-f]{40}',adapter_revision) or revision<=0 or app_build<=0: raise ValueError('identity')
    root=work/'qualified';validate_compiled(root)
    source=json.loads((work/'source-receipt.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    release=f"wanxiang-precompiled-{revision}-{source['revision'][:12]}"
    source_files={}
    for prefix,directory in [('original',work/'original'),('recipe',ROOT/'recipe/wanxiang-v1')]:
        for path in sorted(directory.rglob('*')):
            if path.is_file():source_files[f'{prefix}/{path.relative_to(directory).as_posix()}']=path
    source_files['source-receipt.json']=work/'source-receipt.json'
    for path in sorted((ROOT/'tools').glob('*')):
        if path.is_file(): source_files['build-tools/'+path.name]=path
    source_files['build-tools-LICENSE']=ROOT/'LICENSE'
    source_archive=output/(release+'-source.zip');zip_files(source_archive,source_files)
    runtime=fingerprints(root,[p for p in RUNTIME if p!='build-receipt.json'])
    receipt=dict(format_version=1,compatibility_id=PROFILE,engine_archive_sha256=ENGINE_SHA,engine_version='1.16.1',
        adapter_revision=adapter_revision,recipe_sha256=json.loads((ROOT/'locks/recipe.json').read_text())['sha256'],
        upstream_revision=source['revision'],source_digest=source['source_digest'],qualified_os=['26.5'],
        xcode_version='26.6',xcode_build='17F113',deployment_calls=1,runtime_files=runtime)
    (root/'build-receipt.json').write_bytes(canonical(receipt))
    manifest=dict(format_version=4,payload_kind='precompiled-rime-v1',profile='mobile_wanxiang_full',package_revision=revision,
        release_id=release,compatibility_id=PROFILE,engine_archive_sha256=ENGINE_SHA,recipe_sha256=receipt['recipe_sha256'],
        minimum_app_version='0.6.1',minimum_app_build=app_build,qualified_os=['26.5'],glyph_policy_version=1,
        upstream_revision=source['revision'],adapter_revision=adapter_revision,source_digest=source['source_digest'],
        build_receipt_sha256=file_sha(root/'build-receipt.json'),source_archive_sha256=file_sha(source_archive),
        english_learning_version=1,files=fingerprints(root,RUNTIME))
    validate_manifest(manifest)
    (output/'manifest-payload.json').write_bytes(canonical(manifest))
    # Build job produces public unsigned files. Only the publish job has a key.
    zip_files(output/'runtime-unsigned.zip',{'payload/'+p:root/p for p in RUNTIME})
    for path in ['qualification.json','build-receipt.json','upstream-lock.json']:shutil.copyfile(root/path,output/path)
    (output/'build-environment.json').write_bytes(canonical(dict(format_version=1,image_version=os.environ.get('ImageVersion','local'),
        xcode_version='26.6',xcode_build='17F113',qualified_os=['26.5'],adapter_revision=adapter_revision)))
    print(json.dumps(dict(stage='packed-unsigned',release_id=release,files=len(RUNTIME),source_sha256=manifest['source_archive_sha256'])),flush=True)

def sign(output,key,key_id):
    manifest=json.loads((output/'manifest-payload.json').read_text());validate_manifest(manifest)
    subprocess.run([str(ROOT/'.build/bin/sign'),'sign',key,key_id,'rerime.precompiled.package.v1',str(output/'manifest-payload.json'),str(output/'manifest.json')],check=True)
    # Materialize only the known public files from the unsigned build artifact.
    temporary=output/'signing-stage';temporary.mkdir(exist_ok=False)
    try:
        with zipfile.ZipFile(output/'runtime-unsigned.zip') as archive:
            expected={'payload/'+f['path']:f for f in manifest['files']}
            if set(archive.namelist())!=set(expected) or len(archive.namelist())!=len(expected):raise ValueError('unsigned-files')
            for info in archive.infolist():
                file=expected[info.filename]
                if info.file_size!=file['size']:raise ValueError('unsigned-size')
                target=temporary/info.filename;target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,open(target,'xb') as out:shutil.copyfileobj(source,out,262144)
                if file_sha(target)!=file['sha256']:raise ValueError('unsigned-hash')
        zip_files(output/(manifest['release_id']+'.zip'),{'manifest.json':output/'manifest.json',**{'payload/'+p:temporary/'payload'/p for p in RUNTIME}})
    finally:shutil.rmtree(temporary)

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('prepare');a.add_argument('--work',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--revision',type=int,required=True);a.add_argument('--adapter-revision',required=True);a.add_argument('--app-build',type=int,required=True)
    a=sub.add_parser('sign');a.add_argument('--output',type=Path,required=True);a.add_argument('--key',required=True);a.add_argument('--key-id',required=True)
    args=p.parse_args()
    if args.mode=='prepare':prepare(args.work.resolve(),args.output.resolve(),args.revision,args.adapter_revision,args.app_build)
    else:sign(args.output.resolve(),args.key,args.key_id)
