"""Optional ZIP-member delta. Final signed target ZIP hash is the trust boundary."""
import json, shutil, zipfile
from pathlib import Path
from contract import canonical, file_sha, MAX_ZIP

MAX_OPERATIONS=1025

def segments(path):
    with zipfile.ZipFile(path) as archive:
        offsets=[info.header_offset for info in archive.infolist()]+[archive.start_dir,path.stat().st_size]
    return [(offsets[i],offsets[i+1]-offsets[i]) for i in range(len(offsets)-1)]

def read_at(stream,offset,count):
    stream.seek(offset);data=stream.read(count)
    if len(data)!=count:raise ValueError('delta-truncated')
    return data

def reconstruct(base,patch,metadata,target):
    if file_sha(base)!=metadata['base_sha256'] or base.stat().st_size!=metadata['base_size']:raise ValueError('delta-base')
    if file_sha(patch)!=metadata['patch_sha256'] or patch.stat().st_size!=metadata['patch_size']:raise ValueError('delta-patch')
    if not 0<metadata['target_size']<=MAX_ZIP or not 0<len(metadata['operations'])<=MAX_OPERATIONS:raise ValueError('delta-bounds')
    total=0
    with open(base,'rb') as old,open(patch,'rb') as new,open(target,'xb') as out:
        for operation in metadata['operations']:
            kind,offset,count=operation['source'],operation['offset'],operation['count']
            if kind not in ('base','patch') or type(offset)is not int or type(count)is not int:raise ValueError('delta-operation')
            size=metadata['base_size'] if kind=='base' else metadata['patch_size']
            if not 0<=offset<=size or not 0<count<=size-offset or count>metadata['target_size']-total:raise ValueError('delta-range')
            source=old if kind=='base' else new;source.seek(offset)
            remaining=count
            while remaining:
                data=source.read(min(262144,remaining))
                if not data:raise ValueError('delta-truncated')
                out.write(data);remaining-=len(data)
            total+=count
    if total!=metadata['target_size'] or file_sha(target)!=metadata['target_sha256']:raise ValueError('delta-target')

def generate(base,target,output):
    import hashlib
    output.mkdir(exist_ok=True)
    patch=output/'delta.bin';description=output/'delta.json'
    index={}
    with open(base,'rb') as old:
        for offset,count in segments(base):
            digest=hashlib.sha256(read_at(old,offset,count)).hexdigest()
            index[(digest,count)]=offset
    operations=[];patch_size=0
    with open(target,'rb') as new,open(patch,'xb') as out:
        for offset,count in segments(target):
            data=read_at(new,offset,count);digest=hashlib.sha256(data).hexdigest()
            match=index.get((digest,count))
            if match is not None:operations.append(dict(source='base',offset=match,count=count))
            else:
                operations.append(dict(source='patch',offset=patch_size,count=count))
                out.write(data);patch_size+=count
    metadata=dict(format_version=1,base_sha256=file_sha(base),base_size=base.stat().st_size,
        target_sha256=file_sha(target),target_size=target.stat().st_size,
        patch_sha256=file_sha(patch),patch_size=patch_size,operations=operations)
    encoded=canonical(metadata)
    if not 0<patch_size or len(operations)>MAX_OPERATIONS or len(encoded)>262144 or patch_size+len(encoded)>=target.stat().st_size*0.95:
        patch.unlink();return None
    rebuilt=output/'delta-self-check.zip'
    try:reconstruct(base,patch,metadata,rebuilt)
    finally:rebuilt.unlink(missing_ok=True)
    description.write_bytes(encoded)
    return metadata
