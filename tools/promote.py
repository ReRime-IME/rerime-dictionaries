#!/usr/bin/env python3
"""Publish complete immutable assets, verify anonymous bytes, then advance one channel."""
import argparse,base64,json,os,re,shutil,subprocess,tempfile,time,zipfile
from pathlib import Path
from contract import ROOT,PROFILE,MAX_ZIP,canonical,sha,file_sha,strict_json,validate_manifest
from channel import validate_channel
from check_release import policy,previous,current_channel,CHANNEL_PATH,relevant_tools
from release_http import REPO,api,download,read
from pack import sign
from verify import verify,zip_shape

from consumer_test import CONSUMER_CASES

def require_plan(plan,now):
    if plan.get('format_version')!=1 or plan.get('mode') not in ('build','refresh','noop'):raise ValueError('check-plan')
    for field in ['tool_commit','upstream_revision']:
        if not re.fullmatch('[0-9a-f]{40}',plan.get(field,'')):raise ValueError('check-identity')
    for field in ['input_identity','tool_digest','source_git_digest']:
        if not re.fullmatch('[0-9a-f]{64}',plan.get(field,'')):raise ValueError('check-identity')
    if type(plan.get('checked_at')) is not int or not now-4*3600<=plan['checked_at']<=now+300:raise ValueError('stale-check')
    for field in ['package_revision','minimum_app_build']:
        if type(plan.get(field)) is not int or not 0<plan[field]<2**53:raise ValueError('check-number')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if plan['tool_commit']!=actual or os.environ.get('GITHUB_SHA',actual)!=actual:raise ValueError('trusted-tool-commit')
    if sha(canonical(relevant_tools()))!=plan['tool_digest']:raise ValueError('trusted-tool-digest')

def validate_qualification(qualification):
    expected_os = json.loads((ROOT/'locks/engine.json').read_text())['ios']
    if (qualification.get('qualified_os') != [expected_os] or
            qualification.get('glyph_policy_version') != 1 or qualification.get('rows', 0) <= 0):
        raise ValueError('candidate-qualification')


def verify_candidate(output,plan,public_policy):
    files=list(output.iterdir())
    if len(files)>32:raise ValueError('artifact-count')
    for file in files:
        limit=MAX_ZIP if file.suffix=='.zip' else 8*1024*1024 if file.suffix=='.log' else 524288
        if file.is_symlink() or not file.is_file() or not 0<file.stat().st_size<=limit:raise ValueError('artifact-file-bound')
    manifest=verify(output)
    if manifest['package_revision']!=plan['package_revision'] or manifest['upstream_revision']!=plan['upstream_revision'] or manifest['adapter_revision']!=plan['tool_commit']:
        raise ValueError('candidate-identity')
    if manifest['minimum_app_build']!=public_policy['minimum_app_build'] or manifest['minimum_app_build']!=plan['minimum_app_build']:
        raise ValueError('candidate-app')
    receipt=strict_json((output/'build-receipt.json').read_bytes(),limit=524288,require_canonical=True)
    for field in ['input_identity','tool_digest','source_git_digest']:
        if receipt.get(field)!=plan[field]:raise ValueError('candidate-'+field)
    expected_files={file['path']:file for file in manifest['files']}
    for name in ['qualification.json','build-receipt.json','upstream-lock.json']:
        if file_sha(output/name)!=expected_files[name]['sha256']:raise ValueError('candidate-receipt')
    qualification=json.loads((output/'qualification.json').read_text())
    validate_qualification(qualification)
    consumer=json.loads((output/'consumer-receipt.json').read_text())
    if consumer.get('cases')!=[dict(case=name,exit=0) for name in CONSUMER_CASES]:raise ValueError('consumer-cases')
    if any(consumer.get(key)!=value for key,value in dict(deployment_calls=0,dictionary_sources_absent=1,missing_table_rejected=1,public_hashes_unchanged=1).items()):
        raise ValueError('consumer-gate')
    allowed={'manifest-payload.json','runtime-unsigned.zip',manifest['release_id']+'-source.zip',
        'qualification.json','build-receipt.json','upstream-lock.json','build-environment.json',
        'consumer-receipt.json','build-resources.json',*(f'consumer-{name}.log' for name in CONSUMER_CASES)}
    if {file.name for file in output.iterdir()}!=allowed:raise ValueError('unsigned-artifact-allowlist')
    return manifest

def files_for_release(output,manifest,staging,delta_directory=None):
    release=manifest['release_id'];staging.mkdir(exist_ok=False)
    mapping={'ReRime-'+release+'.zip':output/(release+'.zip'),release+'-source.zip':output/(release+'-source.zip')}
    for name in ['manifest.json','qualification.json','build-receipt.json','upstream-lock.json',
                 'build-environment.json','consumer-receipt.json','build-resources.json']:
        mapping[name]=output/name
    if delta_directory and (delta_directory/'delta.json').is_file():
        mapping.update({name:delta_directory/name for name in ('delta.json','delta.bin')})
    for name,source in mapping.items():
        if not source.is_file() or source.is_symlink():raise ValueError('release-file')
        shutil.copyfile(source,staging/name)
    records=[dict(name=name,size=(staging/name).stat().st_size,sha256=file_sha(staging/name)) for name in sorted(mapping)]
    (staging/'release-files.json').write_bytes(canonical(dict(format_version=1,release_id=release,files=records)))
    records.append(dict(name='release-files.json',size=(staging/'release-files.json').stat().st_size,sha256=file_sha(staging/'release-files.json')))
    return records

def get_release(tag):
    release=api(f'repos/{REPO}/releases/tags/{tag}',missing=True)
    if release is None:
        release=next((item for item in api(f'repos/{REPO}/releases?per_page=100') if item['tag_name']==tag),None)
    return release

def publish_assets(tag,commit,staging,records):
    release=get_release(tag)
    if release is None:
        body=(f'Public precompiled Wanxiang resources for {PROFILE}.\n\n'
              'Runtime and editable source archives, qualification, no-deploy consumer checks and build receipts are attached. '
              'The authenticated channel is promoted only after anonymous asset verification. '
              'Compatibility remains limited to the profile documented in this repository.')
        release=api(f'repos/{REPO}/releases','POST',dict(tag_name=tag,target_commitish=commit,name=tag,body=body,draft=True,prerelease=False))
    if release.get('target_commitish')!=commit:raise ValueError('release-commit-conflict')
    expected={item['name']:item for item in records}
    assets={item['name']:item for item in release['assets']}
    if set(assets)-set(expected):raise ValueError('release-extra-asset')
    for name,item in expected.items():
        if name in assets:
            existing=assets[name]
            if existing['size']!=item['size'] or existing.get('digest')!='sha256:'+item['sha256']:
                raise ValueError('release-asset-conflict')
        else:
            if not release['draft']:raise ValueError('published-release-missing-asset')
            subprocess.run(['gh','release','upload',tag,str(staging/name),'--repo',REPO],check=True)
    current=api(f'repos/{REPO}/releases/{release["id"]}')
    if {item['name'] for item in current['assets']}!=set(expected):raise ValueError('release-incomplete')
    for asset in current['assets']:
        if asset['size']!=expected[asset['name']]['size'] or asset.get('digest')!='sha256:'+expected[asset['name']]['sha256']:
            raise ValueError('uploaded-asset-integrity')
    if current['draft']:
        current=api(f'repos/{REPO}/releases/{release["id"]}','PATCH',dict(draft=False,make_latest='true'))
    if current.get('immutable') is not True:raise ValueError('release-not-immutable')
    return current

def anonymous_assets(tag,records,scratch):
    for item in records:
        destination=scratch/item['name']
        url=f'https://github.com/{REPO}/releases/download/{tag}/{item["name"]}'
        for attempt in range(6):
            try:download(url,destination,min(MAX_ZIP,item['size']));break
            except Exception:
                if attempt==5:raise
                time.sleep(10)
        if destination.stat().st_size!=item['size'] or file_sha(destination)!=item['sha256']:
            raise ValueError('anonymous-asset-integrity')
    print(json.dumps(dict(stage='anonymous-assets-verified',release_id=tag,assets=len(records))),flush=True)

def write_channel(envelope,expected_hash):
    ref=api(f'repos/{REPO}/git/ref/heads/channel',missing=True)
    current=current_channel(ref['object']['sha']) if ref else None
    if (sha(current) if current else None)!=expected_hash:raise ValueError('channel-concurrent-change')
    blob=api(f'repos/{REPO}/git/blobs','POST',dict(content=base64.b64encode(envelope).decode(),encoding='base64'))
    tree_body=dict(tree=[dict(path=CHANNEL_PATH,mode='100644',type='blob',sha=blob['sha'])])
    parents=[]
    if ref:
        parents=[ref['object']['sha']]
        prior=api(f'repos/{REPO}/git/commits/{parents[0]}');tree_body['base_tree']=prior['tree']['sha']
    tree=api(f'repos/{REPO}/git/trees','POST',tree_body)
    commit=api(f'repos/{REPO}/git/commits','POST',dict(message='Refresh authenticated dictionary channel',tree=tree['sha'],parents=parents))
    if ref:api(f'repos/{REPO}/git/refs/heads/channel','PATCH',dict(sha=commit['sha'],force=False))
    else:api(f'repos/{REPO}/git/refs','POST',dict(ref='refs/heads/channel',sha=commit['sha']))
    return commit['sha']

def prepare_delta(live,target,scratch):
    """Optimization is optional; a verified full package always remains publishable."""
    if not live:return None
    directory=scratch/'delta'
    try:
        from delta import generate
        base=scratch/'delta-base.zip';channel=live['channel']
        download(channel['package_url'],base,min(MAX_ZIP,channel['package_size']))
        if base.stat().st_size!=channel['package_size'] or file_sha(base)!=channel['package_sha256']:
            raise ValueError('delta-base-integrity')
        zip_shape(base,live['manifest'])
        result=generate(base,target,directory)
        if result:
            print(json.dumps(dict(stage='delta-ready',base_sha256=result['base_sha256'],
                target_size=result['target_size'],patch_size=result['patch_size'])),flush=True)
            return directory
        print('{"stage":"delta-skipped","reason":"no-material-saving"}',flush=True)
    except Exception:
        print('{"stage":"delta-skipped","reason":"optional-base-or-patch-unavailable"}',flush=True)
    return None


def promote(plan_path,output):
    now=int(time.time());plan=json.loads(plan_path.read_text());require_plan(plan,now)
    if plan['mode']=='noop':print('No promotion required');return
    public_policy=policy()
    with tempfile.TemporaryDirectory(prefix='rerime-promote-') as temporary:
        scratch=Path(temporary)
        live=previous(scratch,public_policy,now)
        expected=plan['previous']['channel_sha256'] if plan['previous'] else None
        if (live['channel_sha256'] if live else None)!=expected:raise ValueError('stale-channel-plan')
        # Verify the dedicated secret matches the committed public trust root.
        key_output=scratch/'publisher-public.txt'
        subprocess.run([str(ROOT/'.build/bin/sign'),'public','environment',str(key_output)],check=True)
        if key_output.read_bytes()!=(ROOT/public_policy['public_key_file']).read_bytes():raise ValueError('publisher-key-mismatch')
        if plan['mode']=='build':
            if output is None:raise ValueError('missing-build-artifact')
            manifest=verify_candidate(output,plan,public_policy)
            sign(output,'environment',public_policy['key_id'])
            verify(output,ROOT/public_policy['public_key_file'],public_policy['key_id'])
            delta_directory=prepare_delta(live,output/(manifest['release_id']+'.zip'),scratch)
            staging=scratch/'assets';records=files_for_release(output,manifest,staging,delta_directory)
            release=publish_assets(manifest['release_id'],plan['tool_commit'],staging,records)
            readback=scratch/'readback';readback.mkdir()
            anonymous_assets(manifest['release_id'],records,readback)
            package=readback/('ReRime-'+manifest['release_id']+'.zip')
            zip_shape(package,manifest)
            channel=dict(format_version=1,repository=REPO,compatibility_id=PROFILE,
                package_revision=manifest['package_revision'],release_id=manifest['release_id'],
                package_url=f'https://github.com/{REPO}/releases/download/{manifest["release_id"]}/{package.name}',
                package_size=package.stat().st_size,package_sha256=file_sha(package),manifest_sha256=file_sha(readback/'manifest.json'))
        else:
            if not live or live['receipt'].get('input_identity')!=plan['input_identity']:raise ValueError('refresh-input-changed')
            channel=dict(live['channel'])
        issued=int(time.time())
        channel.update(sequence=live['channel']['sequence']+1 if live else 1,issued_at=issued,
            expires_at=issued+30*86400,upstream_checked_at=plan.get('upstream_checked_at',plan['checked_at']))
        validate_channel(channel,issued)
        payload=scratch/'channel-payload.json';payload.write_bytes(canonical(channel));envelope=scratch/'channel.json'
        subprocess.run([str(ROOT/'.build/bin/sign'),'sign','environment',public_policy['key_id'],
            'rerime.precompiled.channel.v1',str(payload),str(envelope)],check=True)
        commit=write_channel(envelope.read_bytes(),expected)
        url=f'https://raw.githubusercontent.com/{REPO}/channel/{CHANNEL_PATH}'
        for attempt in range(16):
            data=read(url,131072,missing=True)
            if data==envelope.read_bytes():break
            if attempt==15:raise ValueError('anonymous-channel-not-current; Git commit is published, retry verification after CDN expiry')
            time.sleep(20)
        print(json.dumps(dict(stage='promoted',release_id=channel['release_id'],package_revision=channel['package_revision'],
            sequence=channel['sequence'],channel_commit=commit,package_sha256=channel['package_sha256'],mode=plan['mode'])),flush=True)
        if summary:=os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(summary,'a') as stream:stream.write(f'Published `{channel["release_id"]}`; authenticated channel sequence {channel["sequence"]}. Anonymous assets and channel bytes verified.\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args();promote(args.plan.resolve(),args.output.resolve() if args.output else None)
