import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('hardware_job', Path(__file__).with_name('render_job.py'))
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


def test_job_requires_immutable_image_and_stays_bounded_nonroot():
    for image in ('m11s/timestral:latest-cuda', 'm11s/timestral:acceptance-test'):
        with pytest.raises(ValueError):
            job.resources('cuda', image, 'a'*40, 'gpu-test', '5M')
    resources = job.resources('rocm', 'm11s/timestral@sha256:'+'a'*64, 'b'*40, 'gpu-test', '5M')
    workload = resources[-1]
    pod = workload['spec']['template']['spec']
    assert pod['automountServiceAccountToken'] is False
    assert pod['securityContext']['runAsUser'] == 10001
    assert pod['nodeSelector']['kubernetes.io/hostname'] == 'gpu-test'
    assert pod['restartPolicy'] == 'Never'
    container = pod['containers'][0]
    assert container['resources']['limits']['amd.com/gpu'] == 1
    assert container['securityContext']['readOnlyRootFilesystem'] is True
    assert not any('hostPath' in v for v in pod['volumes'])
    assert workload['spec']['backoffLimit'] == 0
    assert workload['spec']['activeDeadlineSeconds'] == 2400


def test_cpu_job_does_not_request_an_accelerator():
    pod = job.resources('cpu', 'm11s/timestral@sha256:'+'a'*64,
                        'b'*40, 'cpu-test', '209M')[-1]['spec']['template']['spec']
    env = {e['name']: e['value'] for e in pod['containers'][0]['env']}
    assert env['MODEL_DEVICE'] == 'cpu'
    assert env['MODEL_ID'] == 'mistralai/Timestral-209M'
    assert 'runtimeClassName' not in pod
    assert not any('/gpu' in k for k in pod['containers'][0]['resources']['limits'])


def receipt(model='5M'):
    receipts = __import__('json').loads((Path(__file__).parents[2]/'docs/verification/2026-11-01-published-candidates.json').read_text())
    return receipts['openvino_profiles'][model]


def test_openvino_job_pins_private_initialization_and_readonly_profiles():
    artifact = receipt()
    pod = job.resources('openvino', 'm11s/timestral@sha256:'+'a'*64,
                        'b'*40, 'cpu-test', '5M', artifact=artifact)[-1]['spec']['template']['spec']
    init = pod['initContainers'][0]
    token = next(e for e in init['env'] if e['name'] == 'HF_TOKEN')
    assert token['valueFrom']['secretKeyRef'] == {'name': 'timestral-openvino-hf-token', 'key': 'HF_TOKEN'}
    env = {e['name']: e['value'] for e in pod['containers'][0]['env']}
    assert env['TIMESTRAL_ARTIFACT_MANIFEST_SHA256'] == artifact['manifest_sha256']
    assert 'HF_TOKEN' not in env
    assert next(m for m in pod['containers'][0]['volumeMounts'] if m['name'] == 'profiles')['readOnly']


@pytest.mark.parametrize('variant,model,artifact', [
    ('cpu','5M',receipt()), ('openvino','5M',None),
    ('openvino','209M',receipt()),
    ('openvino','5M',{**receipt(), 'manifest_sha256':''}),
    ('openvino','5M',{**receipt(), 'revision':'main'}),
])
def test_rejects_untrusted_or_mismatched_artifact(variant, model, artifact):
    with pytest.raises(ValueError):
        job.resources(variant, 'm11s/timestral@sha256:'+'a'*64,
                      'b'*40, 'cpu-test', model, artifact=artifact)


def test_openvino_initialization_is_executable_python():
    pod = job.resources('openvino', 'm11s/timestral@sha256:'+'a'*64,
                        'b'*40, 'cpu-test', '5M', artifact=receipt())[-1]['spec']['template']['spec']
    compile(pod['initContainers'][0]['command'][2], '<init>', 'exec')


def test_large_profile_initialization_has_bounded_download_space():
    pod = job.resources('openvino', 'm11s/timestral@sha256:'+'a'*64,
                        'b'*40, 'cpu-test', '209M', artifact=receipt('209M'))[-1]['spec']['template']['spec']
    assert next(v for v in pod['volumes'] if v['name']=='tmp')['emptyDir']['sizeLimit'] == '6Gi'
    assert pod['initContainers'][0]['resources']['limits']['ephemeral-storage'] == '16Gi'


def test_profile_copy_uses_owned_child_directory_not_volume_root():
    pod = job.resources('openvino', 'm11s/timestral@sha256:'+'a'*64,
                        'b'*40, 'cpu-test', '5M', artifact=receipt())[-1]['spec']['template']['spec']
    env = {e['name']:e.get('value') for e in pod['initContainers'][0]['env']}
    mount = next(m['mountPath'] for m in pod['initContainers'][0]['volumeMounts'] if m['name']=='profiles')
    assert env['TIMESTRAL_FORECAST_ARTIFACTS'].startswith(mount+'/')
