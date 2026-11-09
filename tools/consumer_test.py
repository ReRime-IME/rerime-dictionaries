#!/usr/bin/env python3
"""Use a fresh source-free consumer tree and a separately compiled no-deploy CLI."""
import argparse,json,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from contract import ROOT,PROFILE_V2,PROFILE_V4,canonical,file_sha
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
# IME-545: the nine-key schema names ReRime's copy of librime's script translator and turns
# its tail completion on. This stock CLI does not have that component, so it types the nine-key
# cases through librime's own script translator in its scratch copy (which ignores the key);
# ReRime's benchmark measures tail completion itself.
T9_TRANSLATOR=('    - rerime_dual_script_translator\n','    - script_translator\n')
T9_TAIL_KEY='  rerime_tail_completion: true\n'
# Profile v4 小鹤双拼 cases (ReRime IME-554): full codes, a short last code, lone initials
# (简拼) alone and mid-input, two keys as one character, zh = v, the V and / symbol prefixes,
# and the full-Pinyin comment. Two lone initials are always also a full code (ud 晒), and
# librime then keeps only the full reading, so 简拼 cases use three or more keys.
XIAOHE_CASES=[('xh-nihao','wanxiang_xiaohe','nihc','你好','simplified','keys','ni hao'),
  ('xh-shide','wanxiang_xiaohe','uide','是的','simplified','keys','shi de'),
  ('xh-short-last','wanxiang_xiaohe','uid','是的','simplified','keys','-'),
  ('xh-initials-three','wanxiang_xiaohe','dyg','第一个','simplified','keys','-'),
  ('xh-two-keys-one-char','wanxiang_xiaohe','vg','正','simplified','keys','zheng'),
  ('xh-initials-four','wanxiang_xiaohe','vgrm','中国人民','simplified','keys','-'),
  ('xh-initial-mid-input','wanxiang_xiaohe','jbttmqi','今天天气','simplified','keys','-'),
  ('xh-zh-is-v','wanxiang_xiaohe','vi','知','simplified','keys','zhi'),
  ('xh-symbol-shift-v','wanxiang_xiaohe','Vjt','→','simplified','keys','-'),
  ('xh-symbol-slash','wanxiang_xiaohe','/jt','→','simplified','keys','-'),
  ('xh-traditional','wanxiang_xiaohe','vsgo','中國','traditional','keys','zhong guo')]
# Imported personal words reach 小鹤 only through their companion table, keyed by joined
# 小鹤 codes (瑞 rv 莱 ld 姆 mu 工 gs 坊 fh), as the App will write it.
XIAOHE_PERSONAL_CASE=('xh-personal','wanxiang_xiaohe','rvldmugsfh','瑞莱姆工坊','simplified','keys','-')
# The 小鹤 schema names ReRime's dual translator, exactly as the App's grammar opt-in writes it,
# and carries a grammar block. The stock CLI types through librime's translator in its scratch
# copy; ReRime's shuangpin.benchmark measures the dual translator and the grammar sentence.
XIAOHE_TRANSLATOR=('    - "rerime_dual_script_translator@translator"\n','    - script_translator\n')
# librime writes the block's keys sorted and its values quoted.
XIAOHE_GRAMMAR=re.compile(r'^grammar:\n(?:  [a-z_]+: .*\n)*  language: "?rerime-grammar"?\n',re.M)
NINE_KEY_PROFILES=(PROFILE_V2,PROFILE_V4)
CONSUMER_CASES=[case[0] for case in [*CASES, PERSONAL_EDIT_CASE]]
T9_CONSUMER_CASES=[case[0] for case in [*T9_CASES, T9_PERSONAL_CASE]]
XIAOHE_CONSUMER_CASES=[case[0] for case in [*XIAOHE_CASES, XIAOHE_PERSONAL_CASE]]

def consumer_cases(profile):
    """Exact case order a profile's consumer receipt must record."""
    return (CONSUMER_CASES+(T9_CONSUMER_CASES if profile in NINE_KEY_PROFILES else [])+
            (XIAOHE_CONSUMER_CASES if profile==PROFILE_V4 else []))

def t9_stand_in(schema):
    """The compiled nine-key schema names ReRime's translator once and turns tail completion on;
    the consumer's scratch copy names librime's stock one in its place (see T9_TRANSLATOR)."""
    text=schema.read_text()
    translator=text[text.index('\ntranslator:\n'):]
    if text.count(T9_TRANSLATOR[0])!=1 or T9_TRANSLATOR[1] in text or translator.count(T9_TAIL_KEY)!=1:
        raise ValueError('consumer-t9-translator')
    schema.write_text(text.replace(*T9_TRANSLATOR))
    return dict(t9_rerime_translator=1,t9_tail_completion=1)

def xiaohe_stand_in(schema):
    """The compiled 小鹤 schema names ReRime's dual translator once, in the App's opt-in form, and
    carries the grammar block; the scratch copy names librime's stock translator in its place."""
    text=schema.read_text()
    if text.count(XIAOHE_TRANSLATOR[0])!=1 or XIAOHE_TRANSLATOR[1] in text or len(XIAOHE_GRAMMAR.findall(text))!=1:
        raise ValueError('consumer-xiaohe-translator')
    schema.write_text(text.replace(*XIAOHE_TRANSLATOR))
    return dict(xiaohe_rerime_translator=1,xiaohe_grammar_block=1)

def test(directory,simulator):
    manifest=json.loads((directory/'manifest-payload.json').read_text());zip_shape(directory/'runtime-unsigned.zip',manifest,False)
    scratch=Path(tempfile.mkdtemp(prefix='consumer-',dir=ROOT/'.build'))
    try:
        with zipfile.ZipFile(directory/'runtime-unsigned.zip') as archive:
            for info in archive.infolist():
                target=scratch/info.filename.removeprefix('payload/');target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(info) as source,open(target,'xb') as out:shutil.copyfileobj(source,out,262144)
        if list(scratch.rglob('*.dict.yaml')):raise ValueError('consumer-has-source')
        stand_in={}
        if manifest['compatibility_id'] in NINE_KEY_PROFILES:stand_in=t9_stand_in(scratch/'build/wanxiang_t9.schema.yaml')
        if manifest['compatibility_id']==PROFILE_V4:stand_in.update(xiaohe_stand_in(scratch/'build/wanxiang_xiaohe.schema.yaml'))
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
        if manifest['compatibility_id'] in NINE_KEY_PROFILES:
            # Before the App writes the digit-coded companion table, T9 still types.
            for case in T9_CASES:run(case)
            (scratch/'rerime_personal_t9.txt').write_text('瑞莱姆工坊\t7845246846643264\t100000\n')
            run(T9_PERSONAL_CASE)
        if manifest['compatibility_id']==PROFILE_V4:
            # Before the App writes the 小鹤 companion table, 小鹤 still types.
            for case in XIAOHE_CASES:run(case)
            (scratch/'rerime_personal_xiaohe.txt').write_text('瑞莱姆工坊\trvldmugsfh\t100000\n')
            run(XIAOHE_PERSONAL_CASE)
        if before!={p:file_sha(scratch/p) for p in public}:raise ValueError('public-files-mutated')
        extra={}
        def reject_missing_prism(schema,text,expected,key):
            prism=scratch/f'build/{schema}.prism.bin';prism.rename(prism.with_suffix('.absent'))
            failure=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),schema,text,expected,'simplified'],capture_output=True,timeout=90)
            if failure.returncode==0 or prism.exists():raise ValueError(key.replace('_rejected','-regenerated').replace('_','-'))
            extra[key]=1
        if manifest['compatibility_id'] in NINE_KEY_PROFILES:reject_missing_prism('wanxiang_t9','64426','你好','missing_t9_prism_rejected')
        if manifest['compatibility_id']==PROFILE_V4:reject_missing_prism('wanxiang_xiaohe','nihc','你好','missing_xiaohe_prism_rejected')
        missing=scratch/'build/wanxiang.table.bin';missing.rename(missing.with_suffix('.absent'))
        failure=subprocess.run(['xcrun','simctl','spawn',simulator,str(ROOT/'.build/bin/RimeConsumer'),str(scratch),'wanxiang','nihao','你好','simplified'],capture_output=True,timeout=90)
        if failure.returncode==0 or missing.exists():raise ValueError('missing-table-regenerated')
        receipt=dict(format_version=1,compatibility_id=manifest['compatibility_id'],cases=result,public_hashes_unchanged=1,dictionary_sources_absent=1,deployment_calls=0,missing_table_rejected=1,**extra,**stand_in)
        (directory/'consumer-receipt.json').write_bytes(canonical(receipt));print(json.dumps(receipt),flush=True)
    finally:shutil.rmtree(scratch)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--simulator',required=True);args=p.parse_args();test(args.directory.resolve(),args.simulator)
