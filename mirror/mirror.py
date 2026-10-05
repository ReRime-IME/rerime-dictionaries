#!/usr/bin/env python3
"""Copy the published, signed files of each profile to the mirrors, then prune
old releases everywhere.

Mirrors are untrusted transport: the App verifies the channel signature, the
manifest signature and every hash. This tool never signs and never holds the
signing key. It reads GitHub (the origin) and writes:

  R2   https://dict.rerime.com/channels/<profile>.json
       https://dict.rerime.com/releases/<release>/<asset>
  CNB  https://cnb.cool/<repo>/-/git/raw/channel/channels/<profile>.json
       https://cnb.cool/<repo>/-/releases/download/<release>/<asset>

Assets are uploaded and read back anonymously before a mirror's channel file is
replaced, so a mirror never announces a release it cannot serve."""
import argparse,hashlib,json,os,re,sys,tempfile,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'mirror'))
from contract import PROFILES,MAX_ZIP,envelope_payload,file_sha,sha,strict_json
from check_release import channel_path,current_channel,release_profile
from release_http import REPO,api,download,read
from s3 import Bucket
from cnb import CNB,WEB

TAG=re.compile(r'wanxiang-precompiled-([1-9][0-9]*)-[0-9a-f]{12}')
R2_HOST='dict.rerime.com'
CNB_REPO='ReRime-IME/rerime-dictionaries'
# What the App downloads; receipts and source archives stay on GitHub only.
CLIENT_ASSETS=('manifest.json','delta.json','delta.bin')
MAX_DELETIONS=12
README=f'''# ReRime dictionaries (mirror)

Signed public dictionary packages for the ReRime keyboard, copied unchanged from
https://github.com/{REPO}. Sources, build receipts and licenses are published there.

ReRime 输入法公共词库的签名发布包镜像，文件与 GitHub 源仓库完全一致；源码、构建记录和许可证见源仓库。
'''

def fetch(url,hosts,limit,destination=None):
    """Anonymous bounded GET; redirects may only reach `hosts`."""
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            target=urllib.parse.urlsplit(newurl)
            if target.scheme!='https' or target.hostname not in hosts or getattr(req,'hops',0)>=3:raise ValueError('mirror-redirect')
            result=urllib.request.Request(newurl,headers={'User-Agent':'ReRime-Dictionary'});result.hops=getattr(req,'hops',0)+1
            return result
    if urllib.parse.urlsplit(url).hostname not in hosts:raise ValueError('mirror-host')
    request=urllib.request.Request(url,headers={'User-Agent':'ReRime-Dictionary','Accept':'application/octet-stream'})
    digest,count=hashlib.sha256(),0
    with urllib.request.build_opener(Redirect()).open(request,timeout=120) as source:
        output=open(destination,'wb') if destination else None
        try:
            while chunk:=source.read(262144):
                count+=len(chunk)
                if count>limit:raise ValueError('mirror-size')
                digest.update(chunk)
                if output:output.write(chunk)
        finally:
            if output:output.close()
    return count,digest.hexdigest()

def read_back(url,hosts,size,digest,attempts=6,wait=10):
    """The exact bytes must be anonymously readable before a channel points at them."""
    for attempt in range(attempts):
        try:
            if fetch(url,hosts,max(size,1))==(size,digest):return
        except (urllib.error.URLError,ValueError,TimeoutError,ConnectionError):pass
        if attempt<attempts-1:time.sleep(wait)
    raise RuntimeError('mirror-readback '+urllib.parse.urlsplit(url).hostname+urllib.parse.urlsplit(url).path)

def origin_release(profile,scratch):
    """The channel bytes and client files GitHub currently serves for `profile`."""
    envelope=current_channel(profile=profile)
    if envelope is None:return None
    channel=strict_json(envelope_payload(envelope)[1],limit=65536,require_canonical=True)
    release=channel['release_id']
    if channel['compatibility_id']!=profile or not TAG.fullmatch(release):raise ValueError('origin-channel')
    base=f'https://github.com/{REPO}/releases/download/{release}/'
    listing=strict_json(read(base+'release-files.json',524288),limit=524288,require_canonical=True)
    if listing.get('release_id')!=release:raise ValueError('origin-listing')
    records={item['name']:item for item in listing['files']}
    package='ReRime-'+release+'.zip'
    names=[package,*(name for name in CLIENT_ASSETS if name in records)]
    directory=scratch/release;directory.mkdir()
    files=[]
    for name in names:
        record=records[name];path=directory/name
        download(base+name,path,min(MAX_ZIP,record['size']))
        if path.stat().st_size!=record['size'] or file_sha(path)!=record['sha256']:raise ValueError('origin-asset-integrity')
        files.append(dict(name=name,path=path,size=record['size'],sha256=record['sha256']))
    by_name={item['name']:item for item in files}
    if (by_name[package]['size'],by_name[package]['sha256'])!=(channel['package_size'],channel['package_sha256']) or \
            by_name['manifest.json']['sha256']!=channel['manifest_sha256']:
        raise ValueError('origin-channel-binding')
    return dict(profile=profile,release=release,envelope=envelope,files=files)

# -- mirrors -------------------------------------------------------------
class R2Mirror:
    name='r2'
    def __init__(self,environment):
        self.bucket=Bucket(environment['R2_ACCOUNT_ID']+'.r2.cloudflarestorage.com',environment.get('R2_BUCKET','rerime-dictionaries'),
            environment['R2_ACCESS_KEY_ID'],environment['R2_SECRET_ACCESS_KEY'])
    def publish(self,origin):
        prefix=f'releases/{origin["release"]}/';present=dict(self.bucket.list(prefix))
        for item in origin['files']:
            if present.get(prefix+item['name'])!=item['size']:
                self.bucket.put_file(prefix+item['name'],item['path'],'public, max-age=31536000, immutable')
            read_back(f'https://{R2_HOST}/{prefix}{item["name"]}',{R2_HOST},item['size'],item['sha256'])
        path=channel_path(origin['profile']);temporary=origin['files'][0]['path'].parent/'channel.json'
        temporary.write_bytes(origin['envelope'])
        self.bucket.put_file(path,temporary,'no-cache','application/json')
        read_back(f'https://{R2_HOST}/{path}',{R2_HOST},len(origin['envelope']),sha(origin['envelope']))
    def stored_releases(self):
        return sorted({key.split('/')[1] for key,_ in self.bucket.list('releases/') if key.count('/')>=2})
    def delete_release(self,release):
        if not TAG.fullmatch(release):raise ValueError('retention-tag')
        for key,_ in self.bucket.list(f'releases/{release}/'):self.bucket.delete(key)

class CNBMirror:
    name='cnb'
    hosts={'cnb.cool','asset.cnb.cool'}
    def __init__(self,environment):
        self.client=CNB(environment.get('CNB_REPO',CNB_REPO),environment['CNB_TOKEN'])
    def publish(self,origin):
        client=self.client;client.ensure_main(README)
        release=client.ensure_release(origin['release'],f'Mirror of https://github.com/{REPO}/releases/tag/{origin["release"]} for {origin["profile"]}.')
        present={asset.get('name'):asset.get('size') for asset in release.get('assets') or []}
        for item in origin['files']:
            if present.get(item['name'])!=item['size']:client.upload_asset(release['id'],item['name'],item['path'])
            url=f'{WEB}/{client.repo}/-/releases/download/{origin["release"]}/{item["name"]}'
            read_back(url,self.hosts,item['size'],item['sha256'])
        path=channel_path(origin['profile']);client.write_channel(path,origin['envelope'])
        read_back(f'{WEB}/{client.repo}/-/git/raw/channel/{path}',self.hosts,len(origin['envelope']),sha(origin['envelope']))
    def stored_releases(self):
        self._releases={item['tag_name']:item for item in self.client.releases()}
        return sorted(self._releases)
    def delete_release(self,release):
        if not TAG.fullmatch(release):raise ValueError('retention-tag')
        self.client.delete_release(self._releases[release])

MIRRORS={'r2':R2Mirror,'cnb':CNBMirror}

# -- retention -----------------------------------------------------------
def retention_policy():
    value=json.loads((ROOT/'ops/retention.json').read_text())
    if value.get('format_version')!=1 or type(value.get('keep_per_profile')) is not int or value['keep_per_profile']<2 or \
            any(not TAG.fullmatch(tag) for tag in value.get('pinned_releases',[])):
        raise ValueError('retention-policy')
    return value

def plan_retention(releases,channel_releases,policy):
    """(keep,delete) release tags. Kept: the newest `keep_per_profile` published
    releases of each profile, every release a channel points at, and pinned ones
    (the dictionary bundled in the shipping App). Drafts and foreign tags are never touched."""
    published=[r for r in releases if not r.get('draft') and TAG.fullmatch(r.get('tag_name',''))]
    tags={r['tag_name'] for r in published}
    if not channel_releases or not set(channel_releases)<=tags:raise ValueError('retention-channel-missing')
    keep=set(channel_releases)|(set(policy.get('pinned_releases',[]))&tags)
    for profile in PROFILES:
        mine=sorted((r for r in published if release_profile(r)==profile),key=lambda r:int(TAG.fullmatch(r['tag_name']).group(1)),reverse=True)
        keep.update(r['tag_name'] for r in mine[:policy['keep_per_profile']])
    delete=sorted(tags-keep,key=lambda tag:int(TAG.fullmatch(tag).group(1)))
    if len(delete)>MAX_DELETIONS:raise ValueError('retention-too-many')
    return keep,delete

def origin_releases():
    result=[]
    for page in range(1,11):
        batch=api(f'repos/{REPO}/releases?per_page=100&page={page}');result.extend(batch)
        if len(batch)<100:return result
    raise ValueError('too-many-releases')

def prune(mirrors,channel_releases,apply):
    releases=origin_releases();keep,delete=plan_retention(releases,channel_releases,retention_policy())
    report=dict(stage='retention',apply=apply,keep=sorted(keep),github=delete,mirrors={})
    for mirror in mirrors:
        # A mirror holds only what this tool copied; anything GitHub no longer keeps goes.
        stale=[tag for tag in mirror.stored_releases() if TAG.fullmatch(tag) and tag not in keep]
        if len(stale)>MAX_DELETIONS:raise ValueError('retention-too-many')
        report['mirrors'][mirror.name]=stale
        if apply:
            for tag in stale:mirror.delete_release(tag)
    if apply:
        by_tag={r['tag_name']:r for r in releases}
        for tag in delete:
            api(f'repos/{REPO}/releases/{by_tag[tag]["id"]}','DELETE')
            api(f'repos/{REPO}/git/refs/tags/{tag}','DELETE',missing=True)
    print(json.dumps(report),flush=True)
    return report

def main(arguments=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',action='append',choices=sorted(PROFILES),help='default: every profile with a channel')
    parser.add_argument('--mirror',action='append',choices=sorted(MIRRORS),help='default: all')
    parser.add_argument('--retention',choices=['apply','dry-run','skip'],default='dry-run')
    args=parser.parse_args(arguments)
    failures=[];mirrors=[]
    for name in args.mirror or sorted(MIRRORS):
        try:mirrors.append(MIRRORS[name](os.environ))
        except KeyError as error:failures.append(f'{name}: missing {error.args[0]}')
    channel_releases=[];complete=True
    with tempfile.TemporaryDirectory(prefix='rerime-mirror-') as temporary:
        for profile in args.profile or sorted(PROFILES):
            origin=origin_release(profile,Path(temporary))
            if origin is None:continue
            channel_releases.append(origin['release'])
            for mirror in mirrors:
                try:
                    mirror.publish(origin)
                    print(json.dumps(dict(stage='mirrored',mirror=mirror.name,profile=profile,release=origin['release'],
                        files=[item['name'] for item in origin['files']])),flush=True)
                except Exception as error:
                    complete=False;failures.append(f'{mirror.name} {profile}: {type(error).__name__}: {error}')
    # Prune only after a complete copy of every profile, with every channel known.
    if args.retention!='skip' and not args.profile:
        if complete and not failures:prune(mirrors,channel_releases,args.retention=='apply')
        else:print('{"stage":"retention","skipped":"mirror-incomplete"}',flush=True)
    for failure in failures:print('FAIL '+failure,file=sys.stderr,flush=True)
    return 1 if failures else 0

if __name__=='__main__':sys.exit(main())
