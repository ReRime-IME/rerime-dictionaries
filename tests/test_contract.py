import io,json,sys,subprocess,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from contract import ROOT,canonical,strict_json,envelope_payload,validate_manifest,validate_compatibility
from adapt import header,adapt
from pack import zip_files
from verify import zip_shape

class ContractTests(unittest.TestCase):
 def test_shared_fixtures(self):
  folder=ROOT/'contract/fixtures';index=json.loads((folder/'cases.json').read_text())
  for case in index['cases']:
   with self.subTest(case=case['file']):
    passed=False
    try:
     envelope,payload=envelope_payload((folder/case['file']).read_bytes())
     value=strict_json(payload,require_canonical=True);validate_manifest(value)
     validate_compatibility(value,index['app_version'],index['app_build'],index['system_version'])
     p=subprocess.run([str(ROOT/'.build/bin/sign'),'verify',str(folder/index['public_key_file']),index['key_id'],'rerime.precompiled.package.v1',str(folder/case['file'])],capture_output=True)
     passed=p.returncode==0
    except (ValueError,KeyError,TypeError):pass
    self.assertEqual(passed,bool(case['accepted']))
 def test_header_rejects_execution_and_nested_imports(self):
  for field in ['lua: evil','name: !!python/object:evil','import_tables:\n  - ../evil','use_preset_vocabulary: true','unknown: value']:
   with self.subTest(field=field),self.assertRaises(ValueError):
    header(io.BytesIO(('---\nname: wanxiang\nversion: x\nsort: by_weight\n'+field+'\n...\n').encode()),'wanxiang')
 def test_english_normalization_and_weights(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'in';output=root/'out'
   source.write_text('---\nname: en\nversion: x\nsort: by_weight\n...\nPython\tPyThOn\t10s\n')
   _,rows=adapt(source,output,english=True)
   self.assertEqual(rows,1);self.assertIn('Python\tpython\t10s\n',output.read_text())
 def test_zip_layout_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=root/'file';f.write_bytes(b'public synthetic bytes')
   from contract import file_sha
   manifest={'files':[dict(path='test',size=f.stat().st_size,sha256=file_sha(f))]}
   archive=root/'valid.zip';zip_files(archive,{'payload/test':f});zip_shape(archive,manifest,False)
   # Additional unknown entry is rejected before extraction.
   with zipfile.ZipFile(archive,'a') as z:z.writestr('../escape',b'bad')
   with self.assertRaises(ValueError):zip_shape(archive,manifest,False)
 def test_strict_json(self):
  for value in [b'{"a":1,"a":2}',b'{"a":true}',b'{"a":null}',b'{"a":-1}',b'{"a":1e1}']:
   with self.subTest(value=value),self.assertRaises(ValueError):strict_json(value)

if __name__=='__main__':unittest.main()
