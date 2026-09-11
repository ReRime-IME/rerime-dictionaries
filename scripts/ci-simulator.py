#!/usr/bin/env python3
"""Select an existing qualified Simulator only on an ephemeral GitHub runner."""
import json,os,platform,subprocess

def select(devices):
    runtime='com.apple.CoreSimulator.SimRuntime.iOS-26-5'
    choices=[item for item in devices.get('devices',{}).get(runtime,[]) if item.get('isAvailable') and item.get('deviceTypeIdentifier')=='com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro']
    if not choices:raise ValueError('qualified-simulator-missing')
    return sorted(choices,key=lambda item:item['udid'])[0]

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted' or platform.machine()!='arm64':
        raise ValueError('github-hosted-arm64-only; local builds must select their existing device explicitly')
    if subprocess.check_output(['xcodebuild','-version'],text=True).strip()!='Xcode 26.6\nBuild version 17F113':raise ValueError('xcode-identity')
    device=select(json.loads(subprocess.check_output(['xcrun','simctl','list','devices','available','--json'])))
    if device['state']=='Shutdown':subprocess.run(['xcrun','simctl','boot',device['udid']],check=True)
    subprocess.run(['xcrun','simctl','bootstatus',device['udid'],'-b'],check=True)
    with open(os.environ['GITHUB_ENV'],'a') as stream:stream.write('RERIME_SIMULATOR_UDID='+device['udid']+'\n')
    print(json.dumps(dict(stage='qualified-simulator',model='iPhone 17 Pro',runtime='26.5',udid=device['udid'])))

if __name__=='__main__':main()
