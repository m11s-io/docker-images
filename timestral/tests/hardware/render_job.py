"""Render isolated acceptance resources; stdout is suitable for server dry-run.

No Deployment, Service, existing cache, secret or stable tag is changed. Delete
only the emitted resources after collecting the report. Jobs are run sequentially.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def resources(variant, image, source, node, model, device_groups=()):
    if variant not in ('cuda', 'rocm') or model not in ('5M', '209M'):
        raise ValueError('unsupported hardware acceptance variant/model')
    if not re.fullmatch(r'm11s/timestral@sha256:[a-f0-9]{64}', image):
        raise ValueError('an immutable candidate digest is required')
    if not re.fullmatch(r'[a-f0-9]{40}', source):
        raise ValueError('an immutable source revision is required')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', node):
        raise ValueError('an explicit node is required')
    code = Path(__file__).with_name('probe.py').read_text()
    fingerprint = hashlib.sha256(code.encode()).hexdigest()
    name = f'timestral-accept-{variant}-{model.lower()}-{fingerprint[:6]}'
    labels = {'m11s.io/timestral-acceptance': name}
    def metadata():
        return dict(name=name, namespace='timestral', labels=labels)
    resource = 'nvidia.com/gpu' if variant == 'cuda' else 'amd.com/gpu'
    revision = ('bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f' if model == '5M'
                else '9874d252ab0aae16f7f7c999f98f98d6ad7d8365')
    env = dict(MODEL_ID='mistralai/Timestral-'+model, MODEL_REVISION=revision,
               TIMESTRAL_BACKEND=variant, MODEL_DEVICE='cuda:0',
               HF_HOME='/models/huggingface', HOME='/tmp', TORCH_NUM_THREADS='2',
               OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONPATH='/app',
               ACCEPTANCE_IMAGE=image, ACCEPTANCE_SOURCE=source,
               ACCEPTANCE_PROBE_SHA256=fingerprint)
    security = dict(runAsNonRoot=True, runAsUser=10001, runAsGroup=10001,
                    fsGroup=10001, seccompProfile={'type': 'RuntimeDefault'})
    if device_groups:
        security['supplementalGroups'] = list(device_groups)
    pod = dict(restartPolicy='Never', automountServiceAccountToken=False,
        securityContext=security,
        nodeSelector={'kubernetes.io/hostname': node, 'kubernetes.io/arch': 'amd64'},
        tolerations=[dict(key='tier.m11s.io', operator='Equal', value='gpu', effect='NoSchedule')],
        containers=[dict(name='acceptance', image=image,
            command=['python', '/acceptance/probe.py'],
            env=[dict(name=k, value=v) for k, v in env.items()],
            securityContext=dict(allowPrivilegeEscalation=False, readOnlyRootFilesystem=True,
                                 capabilities={'drop': ['ALL']}),
            resources=dict(requests={'cpu': '2', 'memory': '4Gi', resource: 1,
                                     'ephemeral-storage': '4Gi'},
                           limits={'cpu': '3', 'memory': '8Gi', resource: 1,
                                   'ephemeral-storage': '8Gi'}),
            volumeMounts=[dict(name='code', mountPath='/acceptance', readOnly=True),
                          dict(name='models', mountPath='/models'),
                          dict(name='tmp', mountPath='/tmp'),
                          dict(name='results', mountPath='/results')])],
        volumes=[dict(name='code', configMap={'name': name}),
                 dict(name='models', emptyDir={'sizeLimit': '3Gi'}),
                 dict(name='tmp', emptyDir={'sizeLimit': '512Mi'}),
                 dict(name='results', emptyDir={'sizeLimit': '16Mi'})])
    if variant == 'cuda':
        pod['runtimeClassName'] = 'nvidia'
    return [
        dict(apiVersion='v1', kind='ConfigMap', metadata=metadata(), data={'probe.py': code}),
        dict(apiVersion='cilium.io/v2', kind='CiliumNetworkPolicy', metadata=metadata(),
             spec=dict(endpointSelector={'matchLabels': labels},
                       enableDefaultDeny={'ingress': True, 'egress': True}, egress=[
                 dict(toEntities=['host'], toPorts=[dict(ports=[dict(port='53', protocol='UDP'), dict(port='53', protocol='TCP')])]),
                 dict(toEndpoints=[{'matchLabels': {'k8s:io.kubernetes.pod.namespace': 'kube-system', 'k8s-app': 'kube-dns'}}],
                      toPorts=[dict(ports=[dict(port='53', protocol='UDP'), dict(port='53', protocol='TCP')])]),
                 dict(toEntities=['world'], toPorts=[dict(ports=[dict(port='443', protocol='TCP')])])])),
        dict(apiVersion='batch/v1', kind='Job', metadata=metadata(), spec=dict(
             backoffLimit=0, activeDeadlineSeconds=2400, ttlSecondsAfterFinished=86400,
             template=dict(metadata=dict(labels=labels, annotations={'m11s.io/acceptance-code-sha256': fingerprint}), spec=pod)))
    ]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', choices=['cuda', 'rocm'], required=True)
    p.add_argument('--image', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--node', required=True)
    p.add_argument('--model', choices=['5M', '209M'], default='5M')
    p.add_argument('--device-group', type=int, action='append', default=[])
    a = p.parse_args()
    print(json.dumps(dict(apiVersion='v1', kind='List', items=resources(
        a.variant, a.image, a.source, a.node, a.model, a.device_group)), indent=2))


if __name__ == '__main__':
    main()
