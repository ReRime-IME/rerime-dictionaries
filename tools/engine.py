#!/usr/bin/env python3
"""Download the pinned public engine, validate it, and build public iOS CLIs."""
import argparse
import json
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath
from contract import ROOT, file_sha

def run(args): subprocess.run([str(a) for a in args],check=True)
def prepare(archive=None):
    lock=json.loads((ROOT/'locks/engine.json').read_text())
    if platform.machine()!='arm64': raise ValueError('host-architecture')
    xcode=subprocess.check_output(['xcodebuild','-version'],text=True)
    if xcode.strip()!=f"Xcode {lock['xcode']}\nBuild version {lock['xcode_build']}": raise ValueError('xcode-identity')
    cache=ROOT/'.build/engine';cache.mkdir(parents=True,exist_ok=True)
    saved=cache/'Frameworks.tgz'
    if not saved.exists():
        if archive: shutil.copyfile(archive,saved)
        else:
            with urllib.request.urlopen(lock['url'],timeout=60) as source,open(saved,'xb') as target:
                size=0
                while data:=source.read(262144):
                    size+=len(data)
                    if size>256*1024*1024: raise ValueError('engine-size')
                    target.write(data)
    if file_sha(saved)!=lock['sha256']: raise ValueError('engine-archive-hash')
    extracted=cache/'frameworks'
    if not extracted.exists():
        extracted.mkdir()
        with tarfile.open(saved,'r:gz') as bundle:
            total=0
            for item in bundle:
                path=PurePosixPath(item.name)
                if path.is_absolute() or '..' in path.parts or not (item.isfile() or item.isdir()): raise ValueError('engine-path')
                total+=item.size
                if total>1024*1024*1024: raise ValueError('engine-expanded')
                if any(p.startswith('._') for p in path.parts): continue
                destination=extracted/item.name
                if item.isdir(): destination.mkdir(parents=True,exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with bundle.extractfile(item) as source,open(destination,'xb') as output: shutil.copyfileobj(source,output)
    simulator='ios-arm64_x86_64-simulator'
    for slice_name,expected in [(simulator,lock['simulator_sha256']),('ios-arm64',lock['device_sha256'])]:
        if file_sha(extracted/'librime.xcframework'/slice_name/'librime.a')!=expected: raise ValueError('engine-slice')
    libraries=[]
    for framework in ['librime','boost_filesystem','boost_regex','boost_system','boost_thread','libglog','libleveldb','libmarisa','libopencc','libyaml-cpp']:
        name=framework if framework.startswith('lib') else 'lib'+framework
        libraries.append(extracted/(framework+'.xcframework')/simulator/(name+'.a'))
    include=extracted/'librime.xcframework'/simulator/'Headers'
    opencc=extracted/'libopencc.xcframework'/simulator/'Headers'
    sdk=subprocess.check_output(['xcrun','--sdk','iphonesimulator','--show-sdk-path'],text=True).strip()
    output=ROOT/'.build/bin';output.mkdir(exist_ok=True)
    for tool in ['RimeBuilder','RimeConsumer']:
        run(['xcrun','--sdk','iphonesimulator','clang++','-target','arm64-apple-ios17.0-simulator','-isysroot',sdk,
             '-std=c++17','-O2','-I',include,ROOT/'tools'/(tool+'.cc'),*libraries,'-lc++','-liconv','-lz','-o',output/tool])
    run(['xcrun','--sdk','iphonesimulator','swiftc','-target','arm64-apple-ios17.0-simulator','-sdk',sdk,'-O','-parse-as-library',
         '-import-objc-header',opencc/'opencc/opencc.h',ROOT/'tools/GlyphQualifier.swift',ROOT/'tools/GlyphQualificationCache.swift',libraries[-2],libraries[-3],'-lc++','-o',output/'GlyphQualifier'])
    print('PASS pinned engine and native build tools')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path);args=p.parse_args();prepare(args.archive)
