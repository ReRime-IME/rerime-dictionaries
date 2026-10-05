"""CNB (cnb.cool) mirror: release attachments through the OpenAPI, the channel
file through Git on the `channel` branch. The token never appears in arguments,
URLs or error text."""
import base64,json,os,subprocess,tempfile,urllib.error,urllib.parse,urllib.request
from pathlib import Path

API='https://api.cnb.cool'
WEB='https://cnb.cool'
AGENT='rerime-public-dictionaries/1'

class CNB:
    def __init__(self,repo,token):
        if not repo or not token:raise ValueError('cnb-configuration')
        self.repo,self.token=repo,token

    # -- OpenAPI ---------------------------------------------------------
    def call(self,method,path,body=None,missing=False):
        url=path if path.startswith('https://') else f'{API}/{self.repo}{path}'
        if urllib.parse.urlsplit(url).hostname!='api.cnb.cool':raise ValueError('cnb-api-host')
        data=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+self.token,
            'Accept':'application/vnd.cnb.api+json','Content-Type':'application/json','User-Agent':AGENT})
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                text=response.read(4*1024*1024)
        except urllib.error.HTTPError as error:
            if missing and error.code==404:return None
            raise RuntimeError(f'cnb-api {method} {urllib.parse.urlsplit(url).path} -> {error.code}: {error.read(300)!r}') from None
        return json.loads(text) if text.strip() else None

    def release(self,tag):
        return self.call('GET','/-/releases/tags/'+urllib.parse.quote(tag,safe=''),missing=True)

    def releases(self):
        result=[]
        for page in range(1,21):
            batch=self.call('GET',f'/-/releases?page={page}&page_size=100') or []
            result.extend(batch)
            if len(batch)<100:return result
        raise RuntimeError('cnb-releases-unbounded')

    def ensure_release(self,tag,body):
        return self.release(tag) or self.call('POST','/-/releases',dict(tag_name=tag,target_commitish='main',
            name=tag,body=body,draft=False,prerelease=False,make_latest='false'))

    def upload_asset(self,release_id,name,path):
        ticket=self.call('POST',f'/-/releases/{release_id}/asset-upload-url',
            dict(asset_name=name,size=path.stat().st_size,overwrite=True))
        upload=urllib.parse.urlsplit(ticket['upload_url'])
        if upload.scheme!='https':raise ValueError('cnb-upload-url')
        with open(path,'rb') as stream:
            request=urllib.request.Request(ticket['upload_url'],data=stream,method='PUT',
                headers={'Content-Length':str(path.stat().st_size),'Content-Type':'application/octet-stream','User-Agent':AGENT})
            try:
                with urllib.request.urlopen(request,timeout=600) as response:response.read(65536)
            except urllib.error.HTTPError as error:
                raise RuntimeError(f'cnb-upload {name} -> {error.code}: {error.read(300)!r}') from None
        verify=ticket['verify_url']
        self.call('POST',verify if verify.startswith('https://') else API+'/'+verify.lstrip('/'))

    def delete_release(self,release):
        self.call('DELETE',f'/-/releases/{release["id"]}')
        self.call('DELETE','/-/git/tags/'+urllib.parse.quote(release['tag_name'],safe=''),missing=True)

    # -- Git (initial commit and the channel branch) ----------------------
    def git(self,*args,cwd=None,check=True):
        basic=base64.b64encode(('cnb:'+self.token).encode()).decode()
        environment=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_CONFIG_COUNT='1',
            GIT_CONFIG_KEY_0='http.extraHeader',GIT_CONFIG_VALUE_0='Authorization: Basic '+basic)
        result=subprocess.run(['git','-c','user.name=ReRime dictionaries','-c','user.email=noreply@rerime.com',*args],
            cwd=cwd,env=environment,capture_output=True,text=True)
        if check and result.returncode:
            raise RuntimeError('cnb-git '+args[0]+' failed: '+result.stderr[-400:].replace(self.token,'***').replace(basic,'***'))
        return result

    @property
    def remote(self):
        return f'{WEB}/{self.repo}.git'

    def has_branch(self,branch):
        return bool(self.git('ls-remote','--heads',self.remote,branch).stdout.strip())

    def ensure_main(self,readme):
        """Releases need a commit to tag; an empty repository gets one README commit."""
        if self.has_branch('main'):return False
        with tempfile.TemporaryDirectory(prefix='rerime-cnb-') as temporary:
            self.git('init','-q','-b','main',temporary)
            (Path(temporary)/'README.md').write_text(readme)
            self.git('add','README.md',cwd=temporary);self.git('commit','-q','-m','Describe this mirror',cwd=temporary)
            self.git('push','-q',self.remote,'main',cwd=temporary)
        return True

    def write_channel(self,path,data):
        """Replace one file on the `channel` branch; other profiles' files stay."""
        with tempfile.TemporaryDirectory(prefix='rerime-cnb-') as temporary:
            if self.has_branch('channel'):
                self.git('clone','-q','--depth','1','--branch','channel',self.remote,temporary)
            else:
                self.git('init','-q','-b','channel',temporary)
            target=Path(temporary)/path
            if target.is_file() and target.read_bytes()==data:return False
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            self.git('add',path,cwd=temporary)
            self.git('commit','-q','-m','Refresh authenticated dictionary channel '+Path(path).stem,cwd=temporary)
            self.git('push','-q',self.remote,'HEAD:channel',cwd=temporary)
        return True
