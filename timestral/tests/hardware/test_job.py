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
