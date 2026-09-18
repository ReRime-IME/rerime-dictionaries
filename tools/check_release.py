#!/usr/bin/env python3
"""Check only relevant public inputs; unchanged input skips all native compilation."""
import argparse,base64,hashlib,io,json,os,re,subprocess,time
from pathlib import Path
from contract import ROOT,SCHEMAS,PROFILE,ENGINE_SHA,canonical,sha,file_sha,strict_json,envelope_payload,validate_manifest
from adapt import header,MAX_FILE
from channel import validate_channel
from release_http import REPO,api,read
from upstream_release import resolve_release,release_relation

CHANNEL_PATH=f'channels/{PROFILE}.json'

def policy():
    value=json.loads((ROOT/'locks/release.json').read_text())
    if value['format_version']!=1 or value['repository']!=REPO or not re.fullmatch('[a-z0-9-]{1,64}',value['key_id']):
        raise ValueError('release-policy')
    if value['public_key_file']!=f"keys/{value['key_id']}.pub":raise ValueError('release-key-path')
    return value

def verify_envelope(data,domain,public_policy,scratch):
    envelope,payload=envelope_payload(data)
    limit=65536 if domain.endswith('channel.v1') else 262144
    value=strict_json(payload,limit=limit,require_canonical=True)
    temporary=scratch/'verify-envelope.json';temporary.write_bytes(data)
    result=subprocess.run([str(ROOT/'.build/bin/sign'),'verify',str(ROOT/public_policy['public_key_file']),
        public_policy['key_id'],domain,str(temporary)],capture_output=True,text=True)
    temporary.unlink()
    if result.returncode:raise ValueError('release-signature')
    return value

def current_channel(ref="channel"):
    result=api(f'repos/{REPO}/contents/{CHANNEL_PATH}?ref={ref}',missing=True)
    if result is None:return None
    if result.get('encoding')!='base64' or result.get('size',2**30)>131072:raise ValueError('channel-size')
    data=base64.b64decode(result['content'],validate=False)
    if len(data)>131072:raise ValueError('channel-size')
    return data

def previous(scratch,public_policy,now):
    data=current_channel()
    if data is None:return None
    channel=verify_envelope(data,'rerime.precompiled.channel.v1',public_policy,scratch)
    # An expired authentic channel can be maintained, but cannot be used by clients.
    validate_channel(channel,channel['issued_at'])
    if channel['issued_at']>now+300:raise ValueError('channel-clock')
    base=f"https://github.com/{REPO}/releases/download/{channel['release_id']}/"
    envelope=read(base+'manifest.json',524288)
    if sha(envelope)!=channel['manifest_sha256']:raise ValueError('manifest-binding')
    manifest=verify_envelope(envelope,'rerime.precompiled.package.v1',public_policy,scratch)
    validate_manifest(manifest)
    if manifest['release_id']!=channel['release_id'] or manifest['package_revision']!=channel['package_revision']:
        raise ValueError('release-binding')
    receipt_data=read(base+'build-receipt.json',524288)
    if sha(receipt_data)!=manifest['build_receipt_sha256']:raise ValueError('receipt-binding')
    receipt=strict_json(receipt_data,limit=524288,require_canonical=True)
    return dict(channel=channel,channel_sha256=sha(data),manifest=manifest,receipt=receipt)

def source_snapshot(revision,tree,root_data):
    if not re.fullmatch('[0-9a-f]{40}',revision) or tree.get('truncated') is not False:raise ValueError('source-tree')
    entries={item['path']:item for item in tree['tree']}
    wanted={'LICENSE'}
    for schema in SCHEMAS:
        path=schema+'.dict.yaml';wanted.add(path)
        _,imports=header(io.BytesIO(root_data[path]),schema)
        wanted.update(table+'.dict.yaml' for table in imports)
    result=[]
    for path in sorted(wanted):
        item=entries.get(path)
        if not item or item.get('type')!='blob' or item.get('mode')!='100644' or not re.fullmatch('[0-9a-f]{40}',item.get('sha','')):
            raise ValueError('source-entry')
        if type(item.get('size')) is not int or not 0<item['size']<=MAX_FILE:raise ValueError('source-size')
        result.append(dict(path=path,size=item['size'],git_blob_sha=item['sha']))
    if sum(item['size'] for item in result)>256*1024*1024:raise ValueError('source-total')
    return result

def relevant_tools():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    # Documentation-only and scheduling-only commits do not rebuild data.
    paths=sorted(p for p in paths if p and p.startswith(('tools/','recipe/','locks/','contract/','scripts/','keys/')))
    if not paths:raise ValueError('tool-inputs')
    return [dict(path=p,size=(ROOT/p).stat().st_size,sha256=file_sha(ROOT/p)) for p in paths]

def decide(input_identity,previous_value,now):
    if previous_value is None or previous_value['receipt'].get('input_identity')!=input_identity:return 'build'
    return 'refresh' if now-previous_value['channel']['upstream_checked_at']>=86400 else 'noop'

def check(output,operation="release",release_id=None):
    output.mkdir(parents=True,exist_ok=False)
    now=int(time.time());public_policy=policy()
    old=previous(output,public_policy,now)
    if operation not in ('release','renew'):raise ValueError('operation')
    if operation=='renew':
        if release_id:raise ValueError('renew-release-id')
        if old is None:raise ValueError('renew-without-channel')
        return maintenance(output,old,now,public_policy,'renew',None)
    release=resolve_release(release_id)
    revision=release['revision']
    tools_digest=sha(canonical(relevant_tools()))
    if old:
        relation=release_relation(old['manifest']['upstream_revision'],revision)
        if relation in ('behind','diverged'):
            # Never roll dictionaries back. A producer migration may rebuild the
            # already authenticated current source even when the official tag lags.
            if old['receipt'].get('tool_digest') == tools_digest:
                return maintenance(output,old,now,public_policy,'release-'+relation,release)
            revision=old['manifest']['upstream_revision']
    tree=api(f'repos/amzxyz/rime-wanxiang/git/trees/{revision}?recursive=1')
    root_data={schema+'.dict.yaml':read(f'https://raw.githubusercontent.com/amzxyz/rime-wanxiang/{revision}/{schema}.dict.yaml',16384) for schema in SCHEMAS}
    sources=source_snapshot(revision,tree,root_data)
    source_digest=sha(canonical(sources))
    recipe=json.loads((ROOT/'locks/recipe.json').read_text())['sha256']
    identity=sha(canonical(dict(source_git_digest=source_digest,tool_digest=tools_digest,recipe_sha256=recipe,engine_archive_sha256=ENGINE_SHA)))
    releases=[]
    for page in range(1,11):
        batch=api(f'repos/{REPO}/releases?per_page=100&page={page}');releases.extend(batch)
        if len(batch)<100 or old and any(r['tag_name']==old['channel']['release_id'] for r in batch):break
    else:raise ValueError('too-many-orphan-releases')
    if old is None and any(not release['draft'] for release in releases):
        raise ValueError('published-release-without-channel: rerun the failed promotion or restore the channel history')
    revisions=[int(match.group(1)) for release in releases if (match:=re.fullmatch(r'wanxiang-precompiled-([1-9][0-9]*)-[0-9a-f]{12}',release['tag_name']))]
    next_revision=max([0,*revisions,old['channel']['package_revision'] if old else 0])+1
    mode=decide(identity,old,now)
    plan=dict(format_version=1,mode=mode,checked_at=now,upstream_checked_at=now,upstream_release=release,
        operation="release",upstream_revision=revision,source_files=sources,
        source_git_digest=source_digest,tool_digest=tools_digest,input_identity=identity,
        tool_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        package_revision=next_revision if mode=='build' else old['channel']['package_revision'],
        previous=old,minimum_app_build=public_policy['minimum_app_build'])
    emit_plan(output,plan)

def maintenance(output,old,now,public_policy,reason,release):
    tools_digest=sha(canonical(relevant_tools()))
    due=old['channel']['expires_at']-now <= 10*86400
    checked=now if release else old['channel']['upstream_checked_at']
    plan=dict(format_version=1,mode='refresh' if due else 'noop',checked_at=now,
        upstream_checked_at=checked,operation=reason,upstream_release=release,
        upstream_revision=old['manifest']['upstream_revision'],source_files=[],
        source_git_digest=old['receipt']['source_git_digest'],tool_digest=tools_digest,
        input_identity=old['receipt']['input_identity'],
        tool_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        package_revision=old['channel']['package_revision'],previous=old,
        minimum_app_build=public_policy['minimum_app_build'])
    emit_plan(output,plan)

def emit_plan(output,plan):
    (output/'check.json').write_text(json.dumps(plan,sort_keys=True,separators=(',',':'))+'\n')
    if github_output:=os.environ.get('GITHUB_OUTPUT'):
        with open(github_output,'a') as stream:
            for key in ('mode','upstream_revision','package_revision','minimum_app_build'):
                stream.write(f'{key}={plan[key]}\n')
    print(json.dumps(dict(stage='checked',mode=plan['mode'],operation=plan['operation'],
        upstream_revision=plan['upstream_revision'],input_identity=plan['input_identity'],
        files=len(plan['source_files']))),flush=True)

def verify_source(plan_path,work):
    plan=json.loads(plan_path.read_text());receipt=json.loads((work/'source-receipt.json').read_text())
    if receipt['revision']!=plan['upstream_revision'] or {f['path'] for f in receipt['files']}!={f['path'] for f in plan['source_files']}:
        raise ValueError('checked-source-identity')
    if sha(canonical(relevant_tools()))!=plan['tool_digest']:raise ValueError('checked-tool-identity')
    for item in plan['source_files']:
        file=work/'original'/item['path']
        digest=hashlib.sha1(f'blob {item["size"]}\0'.encode())
        if file.stat().st_size!=item['size']:raise ValueError('checked-source-size')
        with open(file,'rb') as stream:
            for chunk in iter(lambda:stream.read(262144),b''):digest.update(chunk)
        if digest.hexdigest()!=item['git_blob_sha']:raise ValueError('checked-source-content')
    print('PASS adapted bytes match the checked Git input identity',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('check');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--operation',choices=['release','renew'],default='release');p.add_argument('--release-id')
    p=sub.add_parser('verify-source');p.add_argument('--plan',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='check':check(args.output.resolve(),args.operation,args.release_id)
    else:verify_source(args.plan.resolve(),args.work.resolve())
