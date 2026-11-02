"""Service benchmark accounting and identity checks, without model downloads."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('v2_benchmark', Path(__file__).parents[1]/'benchmarks/v2.py')
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def sample(status, seconds, request_id):
    return dict(status=status,elapsed_seconds=seconds,request_id=request_id)


def test_percentiles_are_seconds_and_only_success_counts_as_throughput():
    report = v2.summarize([sample('success',.1,'a'),sample('success',.3,'b'),
                           sample('busy',.001,'c'),sample('error',2,'d')],2)
    assert report['latency_seconds']['p50'] == pytest.approx(.2)
    assert report['latency_seconds']['p95'] == pytest.approx(.29)
    assert report['successful_requests_per_second'] == 1
    assert report['counts'] == dict(success=2,busy=1,error=1)


def test_no_success_cannot_be_presented_as_a_latency_measurement():
    with pytest.raises(ValueError, match='successful'):
        v2.summarize([sample('busy',.1,'a')],1)


def test_duplicate_request_ids_cannot_merge_unrelated_timings():
    with pytest.raises(ValueError, match='request ID'):
        v2.summarize([sample('success',.1,'same'),sample('success',.2,'same')],1)


def config():
    return dict(endpoint='127.0.0.1:8080',transport='http-json',
        identity=dict(model_id='mistralai/Timestral-5M',model_revision='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f',backend='cpu',image='m11s/timestral@sha256:'+'a'*64,source='b'*40),
        deployment_receipt=dict(image_id='docker.io/m11s/timestral@sha256:'+'a'*64),
        forecast_profile='bounded-v1',forecast_settings=dict(max_context=256,per_shot_horizon_patches=5),
        fixture=dict(name='sine-v1',context_steps=65,horizon=160,batch=1,variates=1,mask_stride=3,symmetric_averaging=True,clip_nonnegative=True),
        warmup_count=10,window_seconds=.02,windows=1,concurrency=1)


@pytest.mark.parametrize('change',[
    dict(identity={**config()['identity'],'image':'m11s/timestral:latest-cpu'}),
    dict(deployment_receipt={'image_id':'m11s/timestral@sha256:'+'c'*64}),
    dict(forecast_profile='auto'),dict(concurrency=0),dict(window_seconds=0),
    dict(forecast_settings={'max_context':32768,'per_shot_horizon_patches':32}),
])
def test_bad_identity_or_configuration_fails_before_requests(change):
    with pytest.raises(ValueError): v2.validate_config(config()|change)


def test_response_id_and_loaded_operation_must_match():
    c=config(); metadata=dict(model_id=c['identity']['model_id'],model_revision=c['identity']['model_revision'],backend='cpu',forecast_profile='bounded-v1',max_context=256,per_shot_horizon_patches=5)
    v2.validate_response(c,'request-id','request-id',metadata)
    for bad in (metadata|{'model_id':'mistralai/Timestral-209M'},metadata|{'per_shot_horizon_patches':32}):
        with pytest.raises(ValueError):v2.validate_response(c,'request-id','request-id',bad)
    with pytest.raises(ValueError):v2.validate_response(c,'request-id','different-id',metadata)


def test_same_fixture_fingerprint_covers_masks_horizon_and_options():
    c=config(); a=v2.fixture_values(c['fixture'])
    digest=v2.fixture_sha256(a)
    for change in (dict(horizon=159),dict(mask_stride=0),dict(clip_nonnegative=False)):
        assert v2.fixture_sha256(v2.fixture_values(c['fixture']|change))!=digest


def test_measurement_runs_network_client_and_records_raw_timings(monkeypatch):
    class Client:
        def __init__(self):self.calls=[]
        def infer(self,values,request_id):
            self.calls.append(request_id)
            c=config()
            return request_id, dict(model_id=c['identity']['model_id'],model_revision=c['identity']['model_revision'],backend='cpu',forecast_profile='bounded-v1',max_context=256,per_shot_horizon_patches=5)
        def close(self):pass
    client=Client()
    monkeypatch.setattr(v2,'create_client',lambda _:client)
    report=v2.run_benchmark(config())
    assert report['windows'][0]['counts']['success']>0
    assert len(client.calls)==10+len(report['samples'])
    assert len({s['request_id'] for s in report['samples']})==len(report['samples'])
    assert all(s['elapsed_seconds']>=0 for s in report['samples'])
    assert report['comparison_group']=='bounded-v1'


def test_loaded_identity_change_invalidates_the_entire_window(monkeypatch):
    class Client:
        calls=0
        def infer(self,values,request_id):
            self.calls+=1;c=config()
            return request_id, dict(model_id=c['identity']['model_id'],model_revision=c['identity']['model_revision'],backend='cpu' if self.calls<=10 or self.calls%2==0 else 'rocm',forecast_profile='bounded-v1',max_context=256,per_shot_horizon_patches=5)
        def close(self):pass
    client=Client();monkeypatch.setattr(v2,'create_client',lambda _:client)
    with pytest.raises(v2.BenchmarkFailure) as failure:v2.run_benchmark(config())
    assert failure.value.report['status']=='failed'
    assert failure.value.report['samples']


def test_linux_resource_units_and_process_cpu_are_explicit(tmp_path):
    import os
    proc=tmp_path/'proc';process=proc/'123';process.mkdir(parents=True)
    (process/'status').write_text('VmRSS:\t20 kB\nVmHWM:\t30 kB\nThreads:\t2\n')
    (process/'stat').write_text('123 (model server) '+'S '+'0 '*10+'200 100 '+'0 '*10)
    cgroup=tmp_path/'cgroup';cgroup.mkdir()
    (cgroup/'cpu.stat').write_text('nr_throttled 4\nthrottled_usec 1500000\n')
    (cgroup/'cpu.max').write_text('200000 100000\n')
    (cgroup/'memory.current').write_text('999\n')
    resources=v2.sample_resources(123,proc,cgroup)
    assert resources['server_rss_bytes']==20480
    assert resources['server_peak_rss_bytes']==30720
    assert resources['server_cpu_seconds']==pytest.approx(300/os.sysconf('SC_CLK_TCK'))
    assert resources['container_throttled_seconds']==1.5
    assert resources['container_memory_current_bytes']==999


def test_comparison_keys_keep_model_and_operation_separate():
    c=config();key=v2.comparison_key(c)
    other=c|{'identity':c['identity']|{'model_id':'mistralai/Timestral-209M','model_revision':'9874d252ab0aae16f7f7c999f98f98d6ad7d8365'}}
    assert v2.comparison_key(other)!=key
    assert v2.comparison_key(c|{'fixture':c['fixture']|{'horizon':159}})!=key
    assert v2.comparison_key(c|{'identity':c['identity']|{'backend':'rocm'}})==key


def test_sample_budget_cannot_be_reported_as_a_full_window(monkeypatch):
    class Client:
        def infer(self,values,request_id):
            c=config()
            return request_id, dict(model_id=c['identity']['model_id'],model_revision=c['identity']['model_revision'],backend='cpu',forecast_profile='bounded-v1',max_context=256,per_shot_horizon_patches=5)
        def close(self):pass
    monkeypatch.setattr(v2,'create_client',lambda _:Client())
    with pytest.raises(v2.BenchmarkFailure,match='sample budget') as failure:
        v2.run_benchmark(config()|{'max_samples_per_window':2})
    assert len(failure.value.report['samples'])==2
