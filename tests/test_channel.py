import json,subprocess,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from contract import ROOT,envelope_payload,strict_json
from channel import validate_channel

class ChannelTests(unittest.TestCase):
    def test_shared_channel_fixtures(self):
        folder=ROOT/'contract/channel-fixtures'
        index=json.loads((folder/'cases.json').read_text())
        for case in index['cases']:
            with self.subTest(case=case['file']):
                passed=False
                try:
                    envelope,payload=envelope_payload((folder/case['file']).read_bytes())
                    if len(payload)>65536:raise ValueError('size')
                    validate_channel(strict_json(payload,limit=65536,require_canonical=True),index['now'])
                    result=subprocess.run([str(ROOT/'.build/bin/sign'),'verify',str(folder/'public-key.txt'),index['key_id'],
                        'rerime.precompiled.channel.v1',str(folder/case['file'])],capture_output=True)
                    passed=result.returncode==0
                except (ValueError,KeyError,TypeError):pass
                self.assertEqual(passed,bool(case['accepted']))

if __name__=='__main__':unittest.main()
