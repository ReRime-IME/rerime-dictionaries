#!/usr/bin/env python3
"""Create public, synthetic contract fixtures; private fixture key is discarded."""
import copy,json,subprocess,tempfile
from pathlib import Path
from contract import ROOT,RUNTIME,PROFILE,ENGINE_SHA,canonical,sha
signer=ROOT/'.build/bin/sign';fixtures=ROOT/'contract/fixtures'
recipe=json.loads((ROOT/'locks/recipe.json').read_text())['sha256']
files=[dict(path=p,size=100,sha256=sha(('synthetic:'+p).encode())) for p in RUNTIME]
manifest=dict(format_version=4,payload_kind='precompiled-rime-v1',profile='mobile_wanxiang_full',package_revision=2026091101,
 release_id='wanxiang-precompiled-2026091101-'+'b'*12,compatibility_id=PROFILE,engine_archive_sha256=ENGINE_SHA,recipe_sha256=recipe,
 minimum_app_version='0.6.1',minimum_app_build=21,qualified_os=['26.5'],glyph_policy_version=1,upstream_revision='b'*40,
 adapter_revision='c'*40,source_digest='a'*64,build_receipt_sha256=next(f['sha256'] for f in files if f['path']=='build-receipt.json'),
 source_archive_sha256='d'*64,english_learning_version=1,files=files)
cases=[]
with tempfile.TemporaryDirectory(prefix='rerime-fixture-key-') as task:
 task=Path(task);key=task/'key';public=task/'public'
 subprocess.run([str(signer),'generate',str(key),str(public)],check=True)
 (fixtures/'fixture-public-key.txt').write_bytes(public.read_bytes())
 def emit(name,data,accepted=False,domain='rerime.precompiled.package.v1',key_id='fixture-contract'):
  payload=task/'payload';payload.write_bytes(data);out=fixtures/(name+'.json')
  if out.exists():out.unlink()
  subprocess.run([str(signer),'sign',str(key),key_id,domain,str(payload),str(out)],check=True)
  cases.append(dict(file=name+'.json',accepted=1 if accepted else 0))
 emit('valid-package',canonical(manifest),True)
 changes={'unknown-field':('extra',1),'old-format':('format_version',3),'wrong-kind':('payload_kind','source'),
  'wrong-engine':('engine_archive_sha256','f'*64),'wrong-profile':('compatibility_id','unsupported'),
  'wrong-recipe':('recipe_sha256','f'*64),'unknown-os':('qualified_os',['99.0']),'newer-app':('minimum_app_version','0.7.0'),
  'newer-build':('minimum_app_build',999),'zero-revision':('package_revision',0),'wrong-release':('release_id','wanxiang-precompiled-1-'+'b'*12),
  'wrong-source-revision':('upstream_revision','x'*40),'receipt-mismatch':('build_receipt_sha256','e'*64),
  'unsafe-number':('package_revision',2**53),'negative-number':('package_revision',-1),'float-number':('package_revision',1.5)}
 for name,(field,value) in changes.items():
  changed=copy.deepcopy(manifest);changed[field]=value;emit(name,canonical(changed))
 for name,operation in [('missing-file',lambda f:f.pop()),('duplicate-file',lambda f:f.append(f[0])),
  ('unsorted-files',lambda f:f.reverse()),('path-traversal',lambda f:f[0].update(path='../outside')),
  ('case-collision',lambda f:f[0].update(path='build/DEFAULT.yaml')),
  ('oversize-file',lambda f:f[0].update(size=256*1024*1024+1)),('zero-file',lambda f:f[0].update(size=0)),
  ('file-unknown-field',lambda f:f[0].update(extra=1))]:
  changed=copy.deepcopy(manifest);operation(changed['files']);emit(name,canonical(changed))
 emit('wrong-domain',canonical(manifest),domain='rerime.precompiled.channel.v1')
 emit('unknown-key',canonical(manifest),key_id='unknown')
 encoded=canonical(manifest);emit('duplicate-json-key',b'{"format_version":4,'+encoded[1:])
 emit('noncanonical-json',json.dumps(manifest).encode())
 value=json.loads((fixtures/'valid-package.json').read_text());value['signature_base64']='A'*86+'=='
 (fixtures/'invalid-signature.json').write_bytes(canonical(value));cases.append(dict(file='invalid-signature.json',accepted=0))
 value=json.loads((fixtures/'valid-package.json').read_text());value['extra']=1
 (fixtures/'extra-envelope-field.json').write_bytes(canonical(value));cases.append(dict(file='extra-envelope-field.json',accepted=0))
(fixtures/'cases.json').write_bytes(canonical(dict(format_version=1,key_id='fixture-contract',public_key_file='fixture-public-key.txt',recipe_sha256=recipe,app_version='0.6.1',app_build=21,system_version='26.5',cases=cases)))
print('Created public contract cases:',len(cases))
