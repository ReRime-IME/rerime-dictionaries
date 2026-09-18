#!/usr/bin/env python3
"""Native cold/warm cache parity using synthetic public strings, no installed data."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    udid=os.environ['RERIME_SIMULATOR_UDID']
    with tempfile.TemporaryDirectory(prefix='rerime-glyph-cache-test-') as temporary:
        root=Path(temporary);source=root/'source';source.mkdir();cache=root/'cache'
        shutil.copytree(ROOT/'recipe/wanxiang-v1/opencc',source/'opencc')
        for name in ('one','two'):
            (source/(name+'.dict.yaml')).write_text('---\nname: '+name+'\nversion: "1"\n...\n中国\tzhong guo\t100\nhello\thello\t10\n\U0010ffff\tinvalid\t1\n')
        def run(label,context='fixture-v1'):
            output=root/label
            env=dict(os.environ,SIMCTL_CHILD_RERIME_QUALIFICATION_CACHE=str(cache),SIMCTL_CHILD_RERIME_QUALIFICATION_CONTEXT=context)
            subprocess.run(['xcrun','simctl','spawn',udid,str(ROOT/'.build/bin/GlyphQualifier'),str(source),str(output)],env=env,check=True,stdout=subprocess.DEVNULL)
            return json.loads((output/'qualification.json').read_text()),json.loads((output/'qualifier-resources.json').read_text())
        cold,c=run('cold');warm,w=run('warm')
        assert cold==warm and c['cache_hits']==0 and w['cache_hits']==2
        with (source/'one.dict.yaml').open('a') as f:f.write('世界\tshi jie\t99\n')
        changed,ch=run('changed');assert ch['cache_hits']==1 and ch['cache_misses']==1
        fresh,fr=run('new-context','fixture-v2');assert fresh==changed and fr['cache_hits']==0
        for p in cache.glob('*.data'):p.write_bytes(b'corrupt')
        repaired,r=run('corrupt','fixture-v2');assert repaired==fresh and r['cache_hits']==0
        print(json.dumps(dict(result='PASS',cold=c,warm=w,changed=ch,new_context=fr,corrupt=r)))

if __name__=='__main__':main()
