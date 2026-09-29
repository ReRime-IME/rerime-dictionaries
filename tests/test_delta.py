import json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from delta import generate,reconstruct

class DeltaTests(unittest.TestCase):
    def archives(self,root):
        shared=os.urandom(200_000)
        for name,value in [('base',b'old'),('target',b'new')]:
            with zipfile.ZipFile(root/(name+'.zip'),'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr(zipfile.ZipInfo('stable.bin',(2026,1,1,0,0,0)),shared,compress_type=zipfile.ZIP_DEFLATED)
                z.writestr(zipfile.ZipInfo('changed.txt',(2026,1,1,0,0,0)),value,compress_type=zipfile.ZIP_DEFLATED)
        return root/'base.zip',root/'target.zip'
    def test_exact_round_trip_and_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);base,target=self.archives(r);m=generate(base,target,r/'delta')
            self.assertLess(m['patch_size'],target.stat().st_size/10)
            reconstruct(base,r/'delta/delta.bin',m,r/'rebuilt.zip')
            self.assertEqual(target.read_bytes(),(r/'rebuilt.zip').read_bytes())
    def test_bad_base_corruption_and_out_of_range_rejected(self):
        for bad in ('base','patch','range','target'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp);base,target=self.archives(r);m=generate(base,target,r/'delta');patch=r/'delta/delta.bin'
                if bad=='base':base.write_bytes(b'bad')
                elif bad=='patch':patch.write_bytes(b'bad')
                elif bad=='range':m['operations'][0]['offset']=2**63-1
                else:m['target_sha256']='0'*64
                with self.assertRaises(ValueError):reconstruct(base,patch,m,r/'bad.zip')
    def test_no_benefit_omits_optional_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp)
            for name in ('base','target'):
                with zipfile.ZipFile(r/(name+'.zip'),'w') as z:z.writestr('data',os.urandom(10000))
            self.assertIsNone(generate(r/'base.zip',r/'target.zip',r/'delta'))
            self.assertFalse((r/'delta/delta.bin').exists())
