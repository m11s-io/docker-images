"""Collect checksum-verified results before removing isolated plt benchmark Jobs."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
import tarfile
import time


def verify_bundle(path):
    with tarfile.open(path,'r:gz') as tar:
        files={}
        total=0
        for member in tar.getmembers():
            name=PurePosixPath(member.name)
            if member.isdir() and str(name)=='.':continue
            if not member.isfile() or name.is_absolute() or len(name.parts)!=1 or not re.fullmatch(r'[A-Za-z0-9_.-]+',str(name)) or str(name) in ('.','..'):
                raise ValueError('unexpected archive path/type')
            if str(name) in files:raise ValueError('duplicate archive path')
            total+=member.size
            if total>1_200_000_000:raise ValueError('result bundle exceeds storage budget')
            files[str(name)]=member
        if 'done.json' not in files or files['done.json'].size>65536:raise ValueError('missing bounded checksum manifest')
        manifest=json.load(tar.extractfile(files['done.json']))
        if set(files)!={'done.json',*manifest['files']} or manifest['status'] not in ('measured','failed'):
            raise ValueError('missing or unexpected result files/status')
        for name,expected in manifest['files'].items():
            if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('invalid checksum')
            if hashlib.file_digest(tar.extractfile(files[name]),'sha256').hexdigest()!=expected:
                raise ValueError('result checksum mismatch')
        if 'summary.json' not in files or json.load(tar.extractfile(files['summary.json']))['status']!=manifest['status']:
            raise ValueError('summary/checksum status mismatch')
        return manifest


def collect(manifest_path,output_dir):
    data=json.loads(manifest_path.read_text());items=data['items'];job=items[-1]
    name=job['metadata']['name'];namespace=job['metadata']['namespace']
    if namespace!='timestral' or not name.startswith('timestral-bench-'):
        raise ValueError('only emitted Timestral benchmark Jobs may be collected')
    node=job['spec']['template']['spec']['nodeSelector']['kubernetes.io/hostname']
    if not node.startswith('plt-'):raise ValueError('benchmark target must be explicit plt hardware')
    if job['spec']['activeDeadlineSeconds']>7200:raise ValueError('benchmark Job must be bounded')
    def k(*args,check=True,input=None):
        return subprocess.run(['kubectl','--context','admin@plt','-n',namespace,*args],
            capture_output=True,text=True,input=input,check=check,timeout=60)
    k('get','node',node)
    k('apply','--dry-run=server','-f',str(manifest_path))
    k('apply','-f',str(manifest_path))
    print('BENCHMARK_STARTED '+name,flush=True)
    directory=output_dir/name;directory.mkdir(parents=True,exist_ok=False)
    deadline=time.monotonic()+job['spec']['activeDeadlineSeconds']+120
    receipt_sent=False;pod_name=None;safe_to_cleanup=False
    try:
        while time.monotonic()<deadline:
            pods=json.loads(k('get','pods','-l','m11s.io/timestral-acceptance='+name,'-o','json').stdout)['items']
            if not pods:time.sleep(5);continue
            if len(pods)!=1:raise ValueError('expected one non-retrying benchmark Pod')
            pod=pods[0];pod_name=pod['metadata']['name']
            statuses=pod['status'].get('containerStatuses',[])
            container=next((c for c in statuses if c['name']=='acceptance'),None)
            if pod['status']['phase'] in ('Failed','Succeeded'):
                safe_to_cleanup=True
                raise RuntimeError('benchmark Pod exited before result collection')
            if container and container.get('imageID') and not receipt_sent:
                receipt=dict(image_id=container['imageID'],pod_uid=pod['metadata']['uid'],
                    initialization=[dict(name=c['name'],image_id=c.get('imageID'),
                        exit_code=c.get('state',{}).get('terminated',{}).get('exitCode'),
                        started=c.get('state',{}).get('terminated',{}).get('startedAt'),
                        finished=c.get('state',{}).get('terminated',{}).get('finishedAt')) for c in pod['status'].get('initContainerStatuses',[])])
                result=k('exec','-i',pod_name,'--','python','-c',
                    'import sys; from pathlib import Path; p=Path("/results/receipt.tmp"); p.write_text(sys.stdin.read()); p.replace("/results/receipt.json")',
                    check=False,input=json.dumps(receipt))
                receipt_sent=result.returncode==0
            if receipt_sent:
                result=k('exec',pod_name,'--','cat','/results/done.json',check=False)
                if result.returncode==0:
                    try:json.loads(result.stdout)
                    except json.JSONDecodeError:time.sleep(1);continue
                    archive=directory/'results.tar.gz'
                    with archive.open('wb') as stream:
                        subprocess.run(['kubectl','--context','admin@plt','-n',namespace,'exec',pod_name,'--',
                            'tar','-czf','-','-C','/results','.'],stdout=stream,check=True,timeout=300)
                    verified=verify_bundle(archive)
                    (directory/'verified.json').write_text(json.dumps(verified,indent=2)+'\n')
                    k('exec',pod_name,'--','touch','/results/collected')
                    safe_to_cleanup=True
                    print('BENCHMARK_COLLECTED '+name+' '+verified['status'],flush=True)
                    return verified['status']=='measured'
            time.sleep(10)
        raise TimeoutError('bounded benchmark/collection deadline exceeded')
    finally:
        if pod_name:
            (directory/'pod.json').write_text(k('get','pod',pod_name,'-o','json',check=False).stdout)
            (directory/'job.log').write_text(k('logs',pod_name,check=False).stdout)
            for init in job['spec']['template']['spec'].get('initContainers',[]):
                (directory/(init['name']+'.log')).write_text(k('logs',pod_name,'-c',init['name'],check=False).stdout)
        if safe_to_cleanup:k('delete','-f',str(manifest_path),'--wait=false')
        else:print('Collection incomplete; emitted resources retained within their bounded lifetime: '+name,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,action='append',required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    nodes={json.loads(path.read_text())['items'][-1]['spec']['template']['spec']['nodeSelector']['kubernetes.io/hostname'] for path in a.manifest}
    if len(nodes)!=1:raise ValueError('one serial target per collector; use separate collectors for independent nodes')
    for manifest in a.manifest:
        if not collect(manifest,a.output_dir):raise SystemExit('benchmark failed; results preserved and temporary resources removed')


if __name__=='__main__':main()
