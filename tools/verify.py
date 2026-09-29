#!/usr/bin/env python3
"""Validate the bounded wire format before signing or distributing public data."""
import argparse
import hashlib
import json
import stat
import struct
import subprocess
import zipfile
from pathlib import Path
from contract import ROOT, RUNTIME, MAX_ZIP, MAX_EXPANDED, canonical, strict_json, file_sha, envelope_payload, validate_manifest

def zip_shape(path,manifest,signed=True):
    size=path.stat().st_size
    if not 22<=size<=MAX_ZIP:raise ValueError('zip-size')
    with open(path,'rb') as stream:
        stream.seek(-22,2);end=stream.read(22)
        magic,disk,central_disk,disk_count,count,directory_size,start,comment=struct.unpack('<4s4H2IH',end)
        if magic!=b'PK\x05\x06' or disk or central_disk or comment or disk_count!=count or not 1<=count<=1025:raise ValueError('zip-end')
        if directory_size>512*1024 or start+directory_size!=size-22:raise ValueError('zip-directory')
        expected={'payload/'+f['path']:f for f in manifest['files']}
        if signed:expected['manifest.json']=None
        next_offset=0;seen=set();total=0
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist()
            if len(entries)!=count or len(entries)!=len(expected):raise ValueError('zip-count')
            for info in entries:
                if info.filename not in expected or info.filename.lower() in seen:raise ValueError('zip-path')
                seen.add(info.filename.lower());total+=info.file_size
                if info.header_offset!=next_offset or info.extra or info.comment or info.flag_bits not in (0,2048) or info.compress_type not in (0,8):raise ValueError('zip-shape')
                if not stat.S_ISREG(info.external_attr>>16) or not 1<=info.file_size<=256*1024*1024 or info.compress_size<=0:raise ValueError('zip-file')
                stream.seek(info.header_offset);header=stream.read(30)
                local=struct.unpack('<4s5H3I2H',header);name=stream.read(local[-2])
                if local[0]!=b'PK\x03\x04' or local[2]!=info.flag_bits or local[3]!=info.compress_type or local[6]!=info.CRC or local[7]!=info.compress_size or local[8]!=info.file_size or local[-1] or name.decode()!=info.filename:raise ValueError('zip-local-header')
                next_offset=info.header_offset+30+len(name)+info.compress_size
                if next_offset>start:raise ValueError('zip-offset')
                record=expected[info.filename]
                if record and info.file_size!=record['size']:raise ValueError('zip-file-size')
                if not record and info.file_size>512*1024:raise ValueError('manifest-size')
                digest=hashlib.sha256();actual=0
                with archive.open(info) as expanded:
                    for chunk in iter(lambda:expanded.read(65536),b''):
                        actual+=len(chunk)
                        if actual>info.file_size:raise ValueError('zip-expanded-size')
                        digest.update(chunk)
                if actual!=info.file_size or record and digest.hexdigest()!=record['sha256']:raise ValueError('zip-hash')
            if next_offset!=start or total>MAX_EXPANDED:raise ValueError('zip-layout')

def verify(directory,public_key=None,key_id=None):
    payload=(directory/'manifest-payload.json').read_bytes()
    manifest=strict_json(payload,require_canonical=True);validate_manifest(manifest)
    source=directory/(manifest['release_id']+'-source.zip')
    if file_sha(source)!=manifest['source_archive_sha256']:raise ValueError('source-hash')
    if file_sha(directory/'build-receipt.json')!=manifest['build_receipt_sha256']:raise ValueError('build-receipt-hash')
    zip_shape(directory/'runtime-unsigned.zip',manifest,signed=False)
    if public_key:
        envelope=(directory/'manifest.json').read_bytes();_,signed_payload=envelope_payload(envelope)
        if signed_payload!=payload:raise ValueError('manifest-payload')
        subprocess.run([str(ROOT/'.build/bin/sign'),'verify',str(public_key),key_id,'rerime.precompiled.package.v1',str(directory/'manifest.json')],check=True)
        package=directory/(manifest['release_id']+'.zip');zip_shape(package,manifest)
        with zipfile.ZipFile(package) as archive:
            if archive.read('manifest.json')!=envelope:raise ValueError('archive-manifest')
    print(json.dumps(dict(stage='verified',release_id=manifest['release_id'],signed=bool(public_key))),flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--public-key',type=Path);p.add_argument('--key-id')
    args=p.parse_args();verify(args.directory.resolve(),args.public_key,args.key_id)
