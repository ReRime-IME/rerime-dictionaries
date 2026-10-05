"""Minimal S3 SigV4 client for one bucket (Cloudflare R2): put, get, list, delete.
Standard library only; the payload is sent over HTTPS and left unsigned."""
import datetime,hashlib,hmac,http.client,urllib.parse
import xml.etree.ElementTree as ET

def _quote(value,safe='-_.~'):
    return urllib.parse.quote(value,safe=safe)

class Bucket:
    def __init__(self,host,bucket,key_id,secret,region='auto'):
        if not all([host,bucket,key_id,secret]):raise ValueError('s3-configuration')
        self.host,self.bucket,self.key_id,self.secret,self.region=host,bucket,key_id,secret,region

    def signed_headers(self,method,path,query,now=None):
        """Authorization for one request; `query` is a dict of decoded values."""
        now=now or datetime.datetime.now(datetime.timezone.utc)
        stamp,day=now.strftime('%Y%m%dT%H%M%SZ'),now.strftime('%Y%m%d')
        headers={'host':self.host,'x-amz-content-sha256':'UNSIGNED-PAYLOAD','x-amz-date':stamp}
        canonical_query='&'.join(f'{_quote(k)}={_quote(v)}' for k,v in sorted(query.items()))
        canonical='\n'.join([method,path,canonical_query,''.join(f'{k}:{v}\n' for k,v in sorted(headers.items())),
            ';'.join(sorted(headers)),'UNSIGNED-PAYLOAD'])
        scope=f'{day}/{self.region}/s3/aws4_request'
        to_sign='\n'.join(['AWS4-HMAC-SHA256',stamp,scope,hashlib.sha256(canonical.encode()).hexdigest()])
        key=('AWS4'+self.secret).encode()
        for part in (day,self.region,'s3','aws4_request'):key=hmac.new(key,part.encode(),hashlib.sha256).digest()
        signature=hmac.new(key,to_sign.encode(),hashlib.sha256).hexdigest()
        headers['authorization']=(f'AWS4-HMAC-SHA256 Credential={self.key_id}/{scope}, '
            f'SignedHeaders={";".join(sorted(headers))}, Signature={signature}')
        return headers,canonical_query

    def request(self,method,key='',query=None,body=None,length=None,extra=None):
        path='/'+self.bucket+('/'+_quote(key,safe='/-_.~') if key else '')
        headers,canonical_query=self.signed_headers(method,path,query or {})
        headers.update(extra or {})
        if length is not None:headers['content-length']=str(length)
        connection=http.client.HTTPSConnection(self.host,timeout=120)
        try:
            connection.request(method,path+('?'+canonical_query if canonical_query else ''),body=body,headers=headers)
            response=connection.getresponse();data=response.read()
        finally:connection.close()
        return response.status,data

    def put_file(self,key,path,cache_control,content_type='application/octet-stream'):
        with open(path,'rb') as stream:
            status,data=self.request('PUT',key,body=stream,length=path.stat().st_size,
                extra={'cache-control':cache_control,'content-type':content_type})
        if status!=200:raise RuntimeError(f's3-put {status}: {data[:300]!r}')

    def list(self,prefix):
        """[(key,size)] under `prefix`, following continuation tokens."""
        result,token=[],None
        for _ in range(100):
            query={'list-type':'2','prefix':prefix}
            if token:query['continuation-token']=token
            status,data=self.request('GET',query=query)
            if status!=200:raise RuntimeError(f's3-list {status}: {data[:300]!r}')
            root=ET.fromstring(data);space=root.tag.partition('}')[0]+'}' if root.tag.startswith('{') else ''
            for item in root.findall(space+'Contents'):
                result.append((item.findtext(space+'Key'),int(item.findtext(space+'Size'))))
            if root.findtext(space+'IsTruncated')!='true':return result
            token=root.findtext(space+'NextContinuationToken')
        raise RuntimeError('s3-list-unbounded')

    def delete(self,key):
        status,data=self.request('DELETE',key)
        if status not in (200,204):raise RuntimeError(f's3-delete {status}: {data[:300]!r}')
