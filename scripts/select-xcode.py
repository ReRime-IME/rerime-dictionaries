#!/usr/bin/env python3
"""Resolve the exact lock on an ephemeral runner; never change system selection."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def select():
    lock = json.loads((ROOT/'locks/engine.json').read_text())
    expected = f"Xcode {lock['xcode']}\nBuild version {lock['xcode_build']}"
    for app in sorted(Path('/Applications').glob('Xcode*.app')):
        developer = app/'Contents/Developer'
        executable = developer/'usr/bin/xcodebuild'
        if not executable.is_file():
            continue
        result = subprocess.run([str(executable),'-version'],env=dict(os.environ,DEVELOPER_DIR=str(developer)),
                                capture_output=True,text=True,timeout=15)
        if result.returncode == 0 and result.stdout.strip() == expected:
            return developer
    raise ValueError('Pinned Xcode is unavailable; do not substitute or publish')

if __name__ == '__main__':
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Runner-only selection; local builds use the configured native toolchain')
    developer = select()
    with open(os.environ['GITHUB_ENV'],'a') as output:
        output.write('DEVELOPER_DIR='+str(developer)+'\n')
    print('PASS pinned Xcode selected for this job')
