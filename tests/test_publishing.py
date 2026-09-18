import copy,json,re,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from contract import ROOT,SCHEMAS,canonical,sha
from check_release import source_snapshot,decide
from promote import publish_assets,write_channel

class PublishingTests(unittest.TestCase):
    def snapshot(self):
        roots={name+'.dict.yaml':f'---\nname: {name}\nversion: x\nsort: by_weight\nimport_tables:\n - dicts/{name}\n...\n'.encode() for name in SCHEMAS}
        paths=['LICENSE',*roots,*['dicts/'+name+'.dict.yaml' for name in SCHEMAS]]
        return roots,dict(truncated=False,tree=[dict(path=path,type='blob',mode='100644',sha='a'*40,size=100) for path in paths])
    def test_related_identity_only(self):
        roots,tree=self.snapshot();original=source_snapshot('b'*40,tree,roots)
        tree['tree'].append(dict(path='README.md',type='blob',mode='100644',sha='c'*40,size=100))
        self.assertEqual(original,source_snapshot('d'*40,tree,roots))
        tree['tree'][0]['sha']='e'*40
        self.assertNotEqual(sha(canonical(original)),sha(canonical(source_snapshot('d'*40,tree,roots))))
    def test_source_missing_truncated_or_symlink_rejected(self):
        for mode in ['missing','truncated','symlink']:
            roots,tree=self.snapshot()
            if mode=='missing':tree['tree'].pop()
            if mode=='truncated':tree['truncated']=True
            if mode=='symlink':tree['tree'][0]['mode']='120000'
            with self.subTest(mode=mode),self.assertRaises(ValueError):source_snapshot('b'*40,tree,roots)
    def test_build_refresh_and_noop(self):
        previous=dict(receipt=dict(input_identity='same'),channel=dict(upstream_checked_at=1000))
        self.assertEqual(decide('same',previous,1001),'noop')
        self.assertEqual(decide('same',previous,87400),'refresh')
        self.assertEqual(decide('changed',previous,1001),'build')
        self.assertEqual(decide('same',None,1001),'build')
    def release(self,draft=False):
        return dict(id=1,target_commitish='a'*40,draft=draft,immutable=not draft,
            assets=[dict(name='asset.zip',size=100,digest='sha256:'+'b'*64)])
    def test_published_assets_are_idempotent(self):
        release=self.release();records=[dict(name='asset.zip',size=100,sha256='b'*64)]
        with patch('promote.get_release',return_value=release),patch('promote.api',return_value=release),patch('promote.subprocess.run') as run:
            result=publish_assets('tag','a'*40,Path('/unused'),records)
            self.assertTrue(result['immutable']);run.assert_not_called()
    def test_published_asset_conflict_or_missing_never_overwrites(self):
        for mode in ['conflict','missing']:
            release=self.release()
            if mode=='conflict':release['assets'][0]['digest']='sha256:'+'c'*64
            else:release['assets']=[]
            with self.subTest(mode=mode),patch('promote.get_release',return_value=release),patch('promote.api') as api,patch('promote.subprocess.run') as run:
                with self.assertRaises(ValueError):publish_assets('tag','a'*40,Path('/unused'),[dict(name='asset.zip',size=100,sha256='b'*64)])
                api.assert_not_called();run.assert_not_called()
    def test_channel_conflict_has_no_ref_write(self):
        with patch('promote.api',return_value={'object':{'sha':'a'*40}}) as api,patch('promote.current_channel',return_value=b'new') as current:
            with self.assertRaises(ValueError):write_channel(b'candidate',sha(b'old'))
            current.assert_called_once_with('a'*40)
            self.assertEqual(api.call_count,1)
    def test_channel_ref_is_fast_forward_only(self):
        calls=[]
        def api(path,method='GET',body=None,missing=False):
            calls.append((path,method,body))
            if '/git/ref/' in path:return {'object':{'sha':'a'*40}}
            if method=='GET':return {'tree':{'sha':'c'*40}}
            if method=='PATCH':
                self.assertIs(body['force'],False)
                raise RuntimeError('concurrent writer')
            return {'sha':'d'*40}
        with patch('promote.api',side_effect=api),patch('promote.current_channel',return_value=b'old'):
            with self.assertRaises(RuntimeError):write_channel(b'candidate',sha(b'old'))
        self.assertEqual(calls[-1][1],'PATCH')
        commit=next(body for path,method,body in calls if '/git/commits' in path and method=='POST')
        self.assertEqual(commit['parents'],['a'*40])
    def test_workflow_secret_and_cost_scope(self):
        value=(ROOT/'.github/workflows/dictionary.yml').read_text()
        self.assertEqual(set(re.findall(r'runs-on: (\S+)',value)),{'xcode-27'})
        self.assertNotIn('pull_request_target',value)
        self.assertEqual(value.count('secrets.RERIME_SIGNING_KEY'),1)
        self.assertNotIn('secrets.',value.split('  promote:')[0])
        self.assertEqual(value.count('contents: write'),1)
        self.assertTrue(all(len(ref)==40 for ref in re.findall(r'uses: [^@]+@(\S+)',value)))
        self.assertIn("  workflow_dispatch:",value)
        self.assertNotIn("  schedule:",value)
        self.assertNotIn("  push:",value)

if __name__=='__main__':unittest.main()
