#!/usr/bin/env python3
"""Public synthetic channel corpus; the temporary signing key is discarded."""
import json,subprocess,tempfile
from pathlib import Path
from contract import ROOT,PROFILE,canonical

folder=ROOT/'contract/channel-fixtures';folder.mkdir(exist_ok=True)
signer=ROOT/'.build/bin/sign';now=1789110000
release='wanxiang-precompiled-2026091101-'+'b'*12
value=dict(format_version=1,repository='Nongfsq/rerime-dictionaries',compatibility_id=PROFILE,
 sequence=1,issued_at=now,expires_at=now+30*86400,upstream_checked_at=now,
 package_revision=2026091101,release_id=release,
 package_url=f'https://github.com/Nongfsq/rerime-dictionaries/releases/download/{release}/ReRime-{release}.zip',
 package_size=40000000,package_sha256='a'*64,manifest_sha256='b'*64)
cases=[]
with tempfile.TemporaryDirectory(prefix='rerime-channel-fixture-') as task:
    task=Path(task);key=task/'key';public=task/'public'
    subprocess.run([str(signer),'generate',str(key),str(public)],check=True)
    (folder/'public-key.txt').write_bytes(public.read_bytes())
    def emit(name,payload,accepted=0,domain='rerime.precompiled.channel.v1',key_id='fixture-channel'):
        source=task/'payload';source.write_bytes(payload);output=folder/(name+'.json')
        if output.exists():output.unlink()
        subprocess.run([str(signer),'sign',str(key),key_id,domain,str(source),str(output)],check=True)
        cases.append(dict(file=output.name,accepted=accepted))
    emit('valid-channel',canonical(value),1)
    for name,field,new in [
        ('unknown-field','extra',1),('old-version','format_version',2),('wrong-repository','repository','other/repo'),
        ('wrong-profile','compatibility_id','other'),('zero-sequence','sequence',0),('zero-revision','package_revision',0),
        ('expired','expires_at',now),('long-expiry','expires_at',now+30*86400+1),('future','issued_at',now+301),
        ('future-check','upstream_checked_at',now+1),('wrong-release','package_revision',2),
        ('wrong-hash','package_sha256','A'*64),('oversize','package_size',512*1024*1024+1),
        ('http','package_url',value['package_url'].replace('https:','http:')),
        ('wrong-asset','package_url',value['package_url']+'?token=x'),('number-bool','sequence',True),
        ('number-float','sequence',1.0),('number-overflow','sequence',2**53)]:
        changed=dict(value);changed[field]=new;emit(name,canonical(changed))
    emit('wrong-domain',canonical(value),domain='rerime.precompiled.package.v1')
    emit('unknown-key',canonical(value),key_id='unknown')
    emit('duplicate-key',b'{"sequence":1,'+canonical(value)[1:])
    emit('noncanonical',json.dumps(value).encode())
(folder/'cases.json').write_bytes(canonical(dict(format_version=1,key_id='fixture-channel',now=now,cases=cases)))
print('Public channel fixtures:',len(cases))
