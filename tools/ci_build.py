#!/usr/bin/env python3
"""Run the locally reproducible producer and record separate, non-identity metrics."""
import json,os,shutil,subprocess,time
from pathlib import Path
from contract import ROOT,canonical

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted':raise ValueError('ci-wrapper-only')
    work=Path(os.environ['RERIME_BUILD_WORK']);output=Path(os.environ['RERIME_BUILD_OUTPUT'])
    if work.exists() or output.exists():raise ValueError('new-ci-directories-required')
    if shutil.disk_usage(ROOT).free<2*1024**3:raise ValueError('runner-disk-space')
    started=time.monotonic()
    subprocess.run(['bash','scripts/build-local.sh','--locked'],cwd=ROOT,check=True)
    subprocess.run(['bash','scripts/test-consumer.sh','--no-deploy'],cwd=ROOT,check=True)
    resources={name:json.loads((work/'qualified'/(name+'-resources.json')).read_text()) for name in ['qualifier','builder']}
    if any(not 0<value['peak_resident_bytes']<=4*1024**3 for value in resources.values()):raise ValueError('native-stage-resource-bound')
    resources.update(format_version=1,total_elapsed_ms=int((time.monotonic()-started)*1000),
        unsigned_output_bytes=sum(file.stat().st_size for file in output.iterdir() if file.is_file()))
    (output/'build-resources.json').write_bytes(canonical(resources))
    print(json.dumps(dict(stage='build-resources',**resources)),flush=True)

if __name__=='__main__':main()
