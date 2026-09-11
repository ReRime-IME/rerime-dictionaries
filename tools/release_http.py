"""Bounded public reads; GitHub API authentication never reaches download hosts."""
import json,subprocess,urllib.request,urllib.error,urllib.parse
from pathlib import Path

REPO='ReRime-IME/rerime-dictionaries'
ASSET_HOSTS={'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        target=urllib.parse.urlsplit(newurl)
        if target.scheme!='https' or target.hostname not in ASSET_HOSTS or target.username or target.password or target.port:
            raise ValueError('download-redirect')
        count=getattr(req,'redirect_count',0)+1
        if count>3:raise ValueError('download-redirect-limit')
        result=urllib.request.Request(newurl,headers={'User-Agent':'rerime-public-dictionaries/1'})
        result.redirect_count=count
        return result

def response(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ASSET_HOSTS|{'raw.githubusercontent.com'} or parsed.username or parsed.password or parsed.port:
        raise ValueError('public-url')
    request=urllib.request.Request(url,headers={'User-Agent':'rerime-public-dictionaries/1'})
    value=urllib.request.build_opener(PublicRedirect()).open(request,timeout=60)
    if value.status!=200:raise ValueError('public-status')
    return value

def read(url,limit,missing=False):
    try:
        with response(url) as source:
            data=source.read(limit+1)
            if len(data)>limit:raise ValueError('public-size')
            return data
    except urllib.error.HTTPError as error:
        if missing and error.code==404:return None
        raise

def download(url,destination,limit):
    count=0
    try:
        with response(url) as source,open(destination,'xb') as output:
            while chunk:=source.read(256*1024):
                count+=len(chunk)
                if count>limit:raise ValueError('download-size')
                output.write(chunk)
        if not count:raise ValueError('download-empty')
    except Exception:
        Path(destination).unlink(missing_ok=True)
        raise

def api(path,method='GET',body=None,missing=False):
    if not path.startswith(('repos/'+REPO+'/', 'repos/amzxyz/rime-wanxiang/')):
        raise ValueError('api-scope')
    args=['gh','api',path,'--method',method,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2026-03-10']
    if body is not None:args+=['--input','-']
    result=subprocess.run(args,input=json.dumps(body) if body is not None else None,text=True,capture_output=True)
    if result.returncode:
        if missing and 'HTTP 404' in result.stderr:return None
        # API responses contain public object errors; never include environment values.
        raise RuntimeError('GitHub API failed for '+path+': '+result.stderr[:1000])
    return json.loads(result.stdout) if result.stdout.strip() else None
