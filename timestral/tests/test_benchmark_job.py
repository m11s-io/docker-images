import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('benchmark_job',Path(__file__).parents[1]/'benchmarks/render_job.py')
job=importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


def test_benchmark_reuses_isolated_security_and_pins_profiles_and_deadline():
    r=job.resources('cpu','m11s/timestral@sha256:'+'a'*64,'b'*40,'cpu-test','5M',
        client_requirements='pytest==9.1.1 --hash=sha256:'+'c'*64,profiles=['upstream-default','bounded-v1'])
    pod=r[-1]['spec']['template']['spec']
    assert pod['securityContext']['runAsUser']==10001
    assert pod['automountServiceAccountToken'] is False
    assert not any('hostPath' in v for v in pod['volumes'])
    assert next(v for v in pod['volumes'] if v['name']=='results')['emptyDir']['sizeLimit']=='1Gi'
    assert r[-1]['spec']['activeDeadlineSeconds']==7200
    assert pod['containers'][0]['command']==['/bin/sh','-c','/usr/local/bin/python -m pip install --disable-pip-version-check --no-deps --require-hashes --target /tmp/clients -r /acceptance/client-requirements.txt && PYTHONPATH=/tmp/clients:/app:/acceptance python /acceptance/run_isolated.py']
    assert r[0]['data']['client-requirements.txt'].startswith('pytest==')
    assert 'v2.py' in r[0]['data'] and 'server_process.py' in r[0]['data']


@pytest.mark.parametrize('profiles',[[],['auto'],['bounded-v1','bounded-v1']])
def test_benchmark_rejects_ambiguous_profiles(profiles):
    with pytest.raises(ValueError):job.resources('cpu','m11s/timestral@sha256:'+'a'*64,'b'*40,'cpu-test','5M',client_requirements='locked',profiles=profiles)


def test_independent_targets_and_images_do_not_share_cleanup_resources():
    def render(node='cpu-one',image='a'*64,source='b'*40):
        return job.resources('cpu','m11s/timestral@sha256:'+image,source,node,'5M',
            client_requirements='locked',profiles=['bounded-v1'])
    baseline=render();others=[render(node='cpu-two'),render(image='d'*64),render(source='e'*40)]
    for other in others:
        assert baseline[-1]['metadata']['name']!=other[-1]['metadata']['name']
        assert baseline[-1]['spec']['template']['metadata']['annotations']==other[-1]['spec']['template']['metadata']['annotations']
