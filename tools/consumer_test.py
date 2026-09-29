#!/usr/bin/env python3
"""Use a fresh source-free consumer tree and a separately compiled no-deploy CLI."""
import argparse,json,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from contract import ROOT,PROFILE_V2,canonical,file_sha
from verify import zip_shape

CASES=[('chinese','wanxiang','nihao','你好','simplified'),('china','wanxiang','zhongguo','中国','simplified'),
    ('english','wanxiang_english','hello','hello','simplified'),('mixed','wanxiang_mixedcode','agu','A股','simplified'),
    ('traditional','wanxiang','zhongguo','中國','traditional'),('personal','wanxiang','xinghegongzuoshi','星河工作室','simplified')]
CASES += [('taiwan-flag','wanxiang','taiwan','🇹🇼','simplified'),
  ('hongkong-flag','wanxiang','xianggang','🇭🇰','simplified'),
  ('taiwan-flag-traditional','wanxiang','taiwanqizhi','🇹🇼','traditional'),
  ('hongkong-flag-traditional','wanxiang','xianggangquqi','🇭🇰','traditional')]
CASES += [('emoji-happy','wanxiang','haha','😄','simplified'),
          ('emoji-cry','wanxiang','daku','😭','simplified'),
          ('emoji-laugh-cry','wanxiang','xiaoku','😂','simplified')]
PERSONAL_EDIT_CASE=('personal-edit','wanxiang','xinghexingongzuoshi','星河新工作室','simplified')
# Profile v2 nine-key cases: digits reach the speller, a spelled prefix
# is accepted through set_input, and each comment carries the toneless spelling.
# Optional fields: feed (keys|set_input) and the exact expected comment ('-' skips).
T9_CASES=[('t9-nihao','wanxiang_t9','64426','你好','simplified','keys','ni hao'),
  ('t9-726-any','wanxiang_t9','726','*','simplified','keys','-'),
  ('t9-set-input-pan','wanxiang_t9','pan','盘','simplified','set_input','pan'),
  ('t9-spelled-prefix','wanxiang_t9','ni426','你好','simplified','set_input','ni hao'),
  ('t9-traditional','wanxiang_t9','94664486','中國','traditional','keys','zhong guo')]
# A phrase absent from the dictionary and from 26-key learning, so only the
# companion table can produce it. Its codes are joined digits, as the App writes.
T9_PERSONAL_CASE=('t9-personal','wanxiang_t9','7845246846643264','瑞莱姆工坊','simplified','keys','-')
CONSUMER_CASES=[case[0] for case in [*CASES, PERSONAL_EDIT_CASE]]
T9_CONSUMER_CASES=[case[0] for case in [*T9_CASES, T9_PERSONAL_CASE]]

def consumer_cases(profile):
    """Exact case order a profile's consumer receipt must record."""
    return CONSUMER_CASES+(T9_CONSUMER_CASES if profile==PROFILE_V2 else [])

def test(directory,simulator):
    manifest=json.loads((directory/'manifest-payload.json').read_text());zip_shape(directory/'runtime-unsigned.zip',manifest,False)
    scratch=Path(tempfile.mkdtemp(prefix='consumer-',dir=ROOT/'.build'))
    try:
        with zipfile.ZipFile(directory/'runtime-unsigned.zip') as archive:
            for info in archive.infolist():
                target=scratch/info.filename.removeprefix('payload/');target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,open(target,'xb') as out:shutil.copyfileobj(source,out,262144)
        if list(scratch.rglob('*.dict.yaml')):raise ValueError('consumer-has-source')
        public=[f['path'] for f in manifest['files']]
        before={p:file_sha(scratch/p) for p in public}
        (scratch/'rerime_personal.txt').write_text('星河工作室\txing he gong zuo shi\t100000\n')
        cases=CASES
        result=[]
        def run(case):
            label,schema,text,expected,mode,*extra=case
            process=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),schema,text,expected,mode,*extra],capture_output=True,text=True,timeout=90)
            (directory/('consumer-'+label+'.log')).write_text(process.stdout+process.stderr)
            if process.returncode:raise ValueError('consumer-'+label)
            result.append(dict(case=label,exit=0))
        for case in cases:run(case)
        (scratch/'rerime_personal.txt').write_text('星河新工作室\txing he xin gong zuo shi\t100000\n')
        run(PERSONAL_EDIT_CASE)
        if manifest['compatibility_id']==PROFILE_V2:
            # Before the App writes the digit-coded companion table, T9 still types.
            for case in T9_CASES:run(case)
            (scratch/'rerime_personal_t9.txt').write_text('瑞莱姆工坊\t7845246846643264\t100000\n')
            run(T9_PERSONAL_CASE)
        if before!={p:file_sha(scratch/p) for p in public}:raise ValueError('public-files-mutated')
        extra={}
        if manifest['compatibility_id']==PROFILE_V2:
            prism=scratch/'build/wanxiang_t9.prism.bin';prism.rename(prism.with_suffix('.absent'))
            failure=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),'wanxiang_t9','64426','你好','simplified'],capture_output=True,timeout=90)
            if failure.returncode==0 or prism.exists():raise ValueError('missing-t9-prism-regenerated')
            extra=dict(missing_t9_prism_rejected=1)
        missing=scratch/'build/wanxiang.table.bin';missing.rename(missing.with_suffix('.absent'))
        failure=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),'wanxiang','nihao','你好','simplified'],capture_output=True,timeout=90)
        if failure.returncode==0 or missing.exists():raise ValueError('missing-table-regenerated')
        receipt=dict(format_version=1,compatibility_id=manifest['compatibility_id'],cases=result,public_hashes_unchanged=1,dictionary_sources_absent=1,deployment_calls=0,missing_table_rejected=1,**extra)
        (directory/'consumer-receipt.json').write_bytes(canonical(receipt));print(json.dumps(receipt),flush=True)
    finally:shutil.rmtree(scratch)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--simulator',required=True);args=p.parse_args();test(args.directory.resolve(),args.simulator)
