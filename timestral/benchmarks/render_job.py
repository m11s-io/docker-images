"""Render bounded benchmark Jobs from the shared hardware resource builder."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def resources(variant,image,source,node,model,*,client_requirements,profiles,artifact=None,device_groups=()):
    if not profiles or len(set(profiles))!=len(profiles) or not set(profiles)<={'upstream-default','bounded-v1'}:
        raise ValueError('explicit unique comparison profiles required')
    if variant=='openvino' and profiles!=['bounded-v1']:
        raise ValueError('OpenVINO requires only bounded-v1')
    path=Path(__file__).parents[1]/'tests/hardware/render_job.py'
    spec=importlib.util.spec_from_file_location('hardware_job',path)
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    r=base.resources(variant,image,source,node,model,device_groups,artifact)
    plan=dict(profiles=profiles,window_seconds=120,fixture=dict(name='sine-v1',batch=1,variates=1,
        context_steps=256,horizon=160,mask_stride=3,symmetric_averaging=True,clip_nonnegative=True))
    data={name:Path(__file__).with_name(name).read_text() for name in ('v2.py','run_isolated.py','server_process.py')}
    data.update({'client-requirements.txt':client_requirements,'plan.json':json.dumps(plan,sort_keys=True)})
    fingerprint=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    deployment=dict(code_sha256=fingerprint,variant=variant,image=image,source=source,node=node,
        model=model,artifact=artifact,device_groups=list(device_groups))
    run_fingerprint=hashlib.sha256(json.dumps(deployment,sort_keys=True).encode()).hexdigest()
    name=f'timestral-bench-{variant}-{model.lower()}-{run_fingerprint[:12]}'
    labels={'m11s.io/timestral-acceptance':name}
    for item in r:item['metadata'].update(name=name,labels=labels)
    r[0]['data']=data;r[1]['spec']['endpointSelector']['matchLabels']=labels
    job=r[-1];job['spec']['activeDeadlineSeconds']=7200
    job['spec']['template']['metadata'].update(labels=labels,annotations={'m11s.io/benchmark-code-sha256':fingerprint})
    pod=job['spec']['template']['spec'];pod['volumes'][0]['configMap']['name']=name
    next(v for v in pod['volumes'] if v['name']=='results')['emptyDir']['sizeLimit']='1Gi'
    container=pod['containers'][0]
    container['resources']['limits']['ephemeral-storage']='20Gi'
    container['env'].append(dict(name='BENCHMARK_SHA256',value=fingerprint))
    container['command']=['/bin/sh','-c','/usr/local/bin/python -m pip install --disable-pip-version-check --no-deps --require-hashes --target /tmp/clients -r /acceptance/client-requirements.txt && PYTHONPATH=/tmp/clients:/app:/acceptance python /acceptance/run_isolated.py']
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant',choices=['cpu','cuda','rocm','openvino'],required=True)
    for key in ('image','source','node','model'):p.add_argument('--'+key,required=True)
    p.add_argument('--client-requirements',type=Path,required=True)
    p.add_argument('--profile',action='append',required=True)
    p.add_argument('--artifact-receipt',type=Path)
    p.add_argument('--device-group',type=int,action='append',default=[])
    a=p.parse_args()
    r=resources(a.variant,a.image,a.source,a.node,a.model,client_requirements=a.client_requirements.read_text(),
        profiles=a.profile,artifact=json.loads(a.artifact_receipt.read_text()) if a.artifact_receipt else None,device_groups=a.device_group)
    print(json.dumps(dict(apiVersion='v1',kind='List',items=r),indent=2))


if __name__=='__main__':main()
