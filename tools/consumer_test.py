#!/usr/bin/env python3
"""Use a fresh source-free consumer tree and a separately compiled no-deploy CLI."""
import argparse,json,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from contract import ROOT,RUNTIME,canonical,file_sha
from verify import zip_shape

def test(directory,simulator):
    manifest=json.loads((directory/'manifest-payload.json').read_text());zip_shape(directory/'runtime-unsigned.zip',manifest,False)
    scratch=Path(tempfile.mkdtemp(prefix='consumer-',dir=ROOT/'.build'))
    try:
        with zipfile.ZipFile(directory/'runtime-unsigned.zip') as archive:
            for info in archive.infolist():
                target=scratch/info.filename.removeprefix('payload/');target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,open(target,'xb') as out:shutil.copyfileobj(source,out,262144)
        if list(scratch.rglob('*.dict.yaml')):raise ValueError('consumer-has-source')
        before={p:file_sha(scratch/p) for p in RUNTIME}
        (scratch/'rerime_personal.txt').write_text('星河工作室\txing he gong zuo shi\t100000\n')
        cases=[('chinese','wanxiang','nihao','你好','simplified'),('china','wanxiang','zhongguo','中国','simplified'),
            ('english','wanxiang_english','hello','hello','simplified'),('mixed','wanxiang_mixedcode','agu','A股','simplified'),
            ('traditional','wanxiang','zhongguo','中國','traditional'),('personal','wanxiang','xinghegongzuoshi','星河工作室','simplified')]
        result=[]
        def run(case):
            label,schema,text,expected,mode=case
            process=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),schema,text,expected,mode],capture_output=True,text=True,timeout=90)
            (directory/('consumer-'+label+'.log')).write_text(process.stdout+process.stderr)
            if process.returncode:raise ValueError('consumer-'+label)
            result.append(dict(case=label,exit=0))
        for case in cases:run(case)
        (scratch/'rerime_personal.txt').write_text('星河新工作室\txing he xin gong zuo shi\t100000\n')
        run(('personal-edit','wanxiang','xinghexingongzuoshi','星河新工作室','simplified'))
        if before!={p:file_sha(scratch/p) for p in RUNTIME}:raise ValueError('public-files-mutated')
        missing=scratch/'build/wanxiang.table.bin';missing.rename(missing.with_suffix('.absent'))
        failure=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),'wanxiang','nihao','你好','simplified'],capture_output=True,timeout=90)
        if failure.returncode==0 or missing.exists():raise ValueError('missing-table-regenerated')
        receipt=dict(format_version=1,cases=result,public_hashes_unchanged=1,dictionary_sources_absent=1,deployment_calls=0,missing_table_rejected=1)
        (directory/'consumer-receipt.json').write_bytes(canonical(receipt));print(json.dumps(receipt),flush=True)
    finally:shutil.rmtree(scratch)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--simulator',required=True);args=p.parse_args();test(args.directory.resolve(),args.simulator)
