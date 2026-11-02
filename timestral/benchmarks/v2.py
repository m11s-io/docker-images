"""Pinned standard-protocol Timestral service measurements."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

import numpy as np


class BenchmarkFailure(ValueError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def summarize(samples, elapsed_seconds):
    if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0:
        raise ValueError('positive elapsed seconds required')
    ids = [s['request_id'] for s in samples]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique request IDs required')
    counts = dict(success=0, busy=0, error=0)
    latencies = []
    for sample in samples:
        status, seconds = sample['status'], sample['elapsed_seconds']
        if status not in counts or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('invalid request measurement')
        counts[status] += 1
        if status == 'success': latencies.append(seconds)
    if not latencies:
        raise ValueError('no successful samples; latency/throughput acceptance unavailable')
    return dict(counts=counts, elapsed_seconds=elapsed_seconds,
                latency_seconds={f'p{p}':float(np.percentile(latencies,p)) for p in (50,90,95,99)},
                successful_requests_per_second=len(latencies)/elapsed_seconds)


def validate_config(config):
    identity = config['identity']
    revisions = {'mistralai/Timestral-5M':'bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f',
                 'mistralai/Timestral-209M':'9874d252ab0aae16f7f7c999f98f98d6ad7d8365'}
    if identity['model_id'] not in revisions or identity['model_revision'] != revisions[identity['model_id']]:
        raise ValueError('unsupported pinned model identity')
    if not re.fullmatch(r'm11s/timestral@sha256:[0-9a-f]{64}',identity['image']):
        raise ValueError('immutable image required')
    if not re.fullmatch(r'[0-9a-f]{40}',identity['source']):
        raise ValueError('immutable source required')
    actual = config['deployment_receipt']['image_id'].removeprefix('docker.io/')
    if actual != identity['image']:
        raise ValueError('Pod image ID does not match the configured image')
    if identity['backend'] not in ('cpu','cuda','rocm','openvino'):
        raise ValueError('explicit backend required')
    if config['transport'] not in ('http-json','http-binary','grpc') or not config['endpoint']:
        raise ValueError('standard transport and endpoint required')
    if config['forecast_profile'] not in ('upstream-default','bounded-v1'):
        raise ValueError('explicit forecasting profile required')
    settings = config['forecast_settings']
    if (set(settings) != {'max_context','per_shot_horizon_patches'} or
        any(type(v) is not int or v < 1 for v in settings.values())):
        raise ValueError('resolved upstream forecast settings required')
    if config['forecast_profile']=='bounded-v1' and settings != dict(max_context=256,per_shot_horizon_patches=5):
        raise ValueError('bounded profile settings mismatch')
    if identity['backend']=='openvino':
        if config['forecast_profile']!='bounded-v1': raise ValueError('OpenVINO requires bounded-v1')
        artifact = identity['artifact']
        if not re.fullmatch('[0-9a-f]{40}',artifact['revision']) or not re.fullmatch('[0-9a-f]{64}',artifact['manifest_sha256']):
            raise ValueError('pinned OpenVINO artifact required')
        if artifact['path'] != 'standard-v1/'+artifact['manifest_sha256']:
            raise ValueError('artifact prefix must match trusted manifest')
    for key in ('warmup_count','windows','concurrency'):
        if type(config[key]) is not int or config[key]<1: raise ValueError('positive benchmark counts required')
    if config['concurrency']>2 or config['windows']>10 or config['warmup_count']>1000:
        raise ValueError('benchmark count budget exceeded')
    if not math.isfinite(config['window_seconds']) or not 0<config['window_seconds']<=600:
        raise ValueError('bounded measurement window required')
    budget=config.get('max_samples_per_window',250000)
    if type(budget) is not int or not 1<=budget<=1_000_000:raise ValueError('bounded raw sample budget required')
    fixture_values(config['fixture'])
    if identity['backend']=='openvino':
        f=config['fixture']
        if f['batch']!=1 or f['variates']!=1 or f['context_steps']>256 or f['horizon']>320:
            raise ValueError('fixture exceeds OpenVINO scope')


def fixture_values(fixture):
    if fixture['name']!='sine-v1': raise ValueError('unknown reproducible fixture')
    b,v,t,h = (fixture[k] for k in ('batch','variates','context_steps','horizon'))
    if any(type(n) is not int or n<1 for n in (b,v,t,h)) or b>8 or b*v>32 or t>32768 or h>1024 or b*v*h*21>1_000_000:
        raise ValueError('fixture exceeds contract budgets')
    stride=fixture.get('mask_stride',0)
    if type(stride) is not int or stride<0: raise ValueError('invalid mask stride')
    if any(type(fixture.get(k,True)) is not bool for k in ('symmetric_averaging','clip_nonnegative')):
        raise ValueError('explicit boolean options required')
    context=np.sin(np.arange(b*v*t,dtype=np.float32).reshape(b,v,t)/7)
    mask=np.ones(context.shape,dtype=bool)
    if stride: mask[...,1::stride]=False
    if not mask.any(axis=-1).all():raise ValueError('fixture has no observations')
    return dict(context=context,observation_mask=mask,prediction_length=np.array([h],dtype=np.int64),
        symmetric_averaging=np.array([fixture.get('symmetric_averaging',True)],dtype=bool),
        clip_nonnegative=np.array([fixture.get('clip_nonnegative',True)],dtype=bool))


def fixture_sha256(values):
    digest=hashlib.sha256()
    for name,a in sorted(values.items()):
        digest.update(json.dumps([name,str(a.dtype),list(a.shape)],separators=(',',':')).encode())
        digest.update(a.tobytes())
    return digest.hexdigest()


def comparison_key(config):
    return dict(model_id=config['identity']['model_id'],model_revision=config['identity']['model_revision'],
        source=config['identity']['source'],forecast_profile=config['forecast_profile'],
        forecast_settings=config['forecast_settings'],transport=config['transport'],
        fixture_sha256=fixture_sha256(fixture_values(config['fixture'])))


def parameter_value(value):
    if hasattr(value,'WhichOneof'):
        field=value.WhichOneof('parameter_choice')
        if field is None:raise ValueError('empty identity parameter')
        return getattr(value,field)
    return value


def validate_response(config, expected_id, actual_id, parameters):
    if expected_id != actual_id: raise ValueError('response request ID mismatch')
    identity=config['identity']
    expected={key:identity[key] for key in ('model_id','model_revision','backend')}
    expected.update(forecast_profile=config['forecast_profile'],**config['forecast_settings'])
    if identity['backend']=='openvino':expected['artifact_manifest_sha256']=identity['artifact']['manifest_sha256']
    for key,value in expected.items():
        if key not in parameters or parameter_value(parameters[key])!=value:
            raise ValueError('loaded identity/config mismatch: '+key)


class StandardClient:
    def __init__(self, config):
        self.config=config
        if config['transport']=='grpc': import tritonclient.grpc as protocol
        else: import tritonclient.http as protocol
        self.protocol=protocol
        self.client=protocol.InferenceServerClient(config['endpoint'],**(dict(connection_timeout=60,network_timeout=600) if config['transport']!='grpc' else {}))

    def infer(self, values, request_id):
        inputs=[]
        dtypes={'float32':'FP32','int64':'INT64','bool':'BOOL'}
        for name,a in values.items():
            inp=self.protocol.InferInput(name,list(a.shape),dtypes[str(a.dtype)])
            if self.config['transport']=='grpc':inp.set_data_from_numpy(a)
            else:inp.set_data_from_numpy(a,binary_data=self.config['transport']=='http-binary')
            inputs.append(inp)
        # KServe's versioned URL returns 501 at this pinned SDK. Pin loaded
        # revision via response identity checks on the standard unversioned route.
        kwargs=dict(request_id=request_id)
        if self.config['transport']=='http-json':kwargs['headers']={'content-type':'application/json'}
        if self.config['transport']=='grpc':kwargs['client_timeout']=600
        result=self.client.infer('timestral',inputs,**kwargs)
        response=result.get_response()
        actual_id=response['id'] if isinstance(response,dict) else response.id
        parameters=response.get('parameters',{}) if isinstance(response,dict) else response.parameters
        expected_shape=(*values['context'].shape[:2],int(values['prediction_length'][0]))
        for name,shape in [('quantiles',(*expected_shape,21)),('median',expected_shape),('quantile_levels',(21,))]:
            a=result.as_numpy(name)
            if a is None or a.dtype!=np.float32 or a.shape!=shape or not np.isfinite(a).all():
                raise ValueError('invalid output tensor')
        return actual_id,parameters

    def close(self): self.client.close()


def create_client(config): return StandardClient(config)


def _busy(error):
    # Only occupied-capacity responses count as busy. Other 503s remain errors.
    status=error.status() if callable(getattr(error,'status',None)) else None
    return str(status) in ('503','StatusCode.UNAVAILABLE') and 'inference capacity is occupied' in str(error)


def sample_resources(pid, proc_root=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup')):
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (proc_root/str(pid)/'status').read_text().splitlines() if ':' in line}
    fields=(proc_root/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    result=dict(monotonic_seconds=time.monotonic(),server_rss_bytes=int(status['VmRSS'].split()[0])*1024,
        server_peak_rss_bytes=int(status['VmHWM'].split()[0])*1024,server_threads=int(status['Threads']),
        server_cpu_seconds=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'))
    path=cgroup_root/'cpu.stat'
    if path.exists():
        cpu=dict(line.split() for line in path.read_text().splitlines())
        result.update(container_throttled_seconds=int(cpu.get('throttled_usec',0))/1e6,
            container_throttled_periods=int(cpu.get('nr_throttled',0)))
    for file in ('memory.current','memory.peak'):
        path=cgroup_root/file
        if path.exists():result['container_'+file.replace('.','_')+'_bytes']=int(path.read_text())
    for file in ('cpu.max','memory.max'):
        path=cgroup_root/file
        if path.exists():result['container_'+file.replace('.','_')]=path.read_text().strip()
    path=proc_root/'loadavg'
    if path.exists():result['node_loadavg']=path.read_text().split()[:3]
    return result


def run_benchmark(config: dict) -> dict:
    validate_config(config)
    values=fixture_values(config['fixture'])
    report=dict(status='failed',config=config,comparison_group=config['forecast_profile'],comparison_key=comparison_key(config),
        fixture_sha256=fixture_sha256(values),samples=[],windows=[],warmup=[],resource_samples=[])
    client=create_client(config)
    try:
        for _ in range(config['warmup_count']):
            request_id=str(uuid.uuid4());started=time.monotonic()
            response_id,parameters=client.infer(values,request_id)
            validate_response(config,request_id,response_id,parameters)
            report['warmup'].append(dict(request_id=request_id,elapsed_seconds=time.monotonic()-started))
    except Exception as error:
        raise BenchmarkFailure('warmup identity/inference validation failed',report) from error
    finally:client.close()
    for window in range(config['windows']):
        started=time.monotonic();deadline=started+config['window_seconds']
        lock=threading.Lock();samples=[];stop_sampling=threading.Event();invalid_identity=threading.Event();budget_exhausted=threading.Event();issued=[0]
        def sample_loop():
            while not stop_sampling.is_set():
                try:report['resource_samples'].append(dict(window=window,**sample_resources(config['server_pid'])))
                except (OSError,KeyError,ValueError):
                    report.setdefault('resource_errors',[]).append(dict(window=window,error='server/container telemetry unavailable'))
                    return
                stop_sampling.wait(1)
        sampler=threading.Thread(target=sample_loop,daemon=True) if config.get('server_pid') else None
        if sampler:sampler.start()
        def worker():
            connection=create_client(config)
            try:
                while time.monotonic()<deadline and not invalid_identity.is_set():
                    with lock:
                        if issued[0]>=config.get('max_samples_per_window',250000):
                            budget_exhausted.set();break
                        issued[0]+=1
                    request_id=str(uuid.uuid4());begin=time.monotonic();status='success';error_type=None
                    try:
                        response_id,parameters=connection.infer(values,request_id)
                        validate_response(config,request_id,response_id,parameters)
                    except Exception as error:
                        status='busy' if _busy(error) else 'error'
                        error_type=type(error).__name__
                        if isinstance(error,ValueError):invalid_identity.set()
                    sample=dict(window=window,request_id=request_id,start_offset_seconds=begin-started,
                        elapsed_seconds=time.monotonic()-begin,status=status,error_type=error_type)
                    with lock:samples.append(sample)
            finally:connection.close()
        try:
            with ThreadPoolExecutor(max_workers=config['concurrency']) as executor:
                futures=[executor.submit(worker) for _ in range(config['concurrency'])]
                for future in futures:future.result()
        finally:
            stop_sampling.set()
            if sampler:sampler.join(timeout=5)
        elapsed=time.monotonic()-started
        report['samples'].extend(sorted(samples,key=lambda s:s['start_offset_seconds']))
        if budget_exhausted.is_set():raise BenchmarkFailure('raw sample budget exhausted before full window',report)
        if any(s['error_type']=='ValueError' for s in samples):
            raise BenchmarkFailure('identity/output validation failed during measurement',report)
        try:summary=summarize(samples,elapsed)
        except ValueError as error:raise BenchmarkFailure(str(error),report) from error
        summary.update(window=window,requested_window_seconds=config['window_seconds'],drain_seconds=max(0,elapsed-config['window_seconds']))
        report['windows'].append(summary)
    report['status']='measured' if not any(w['counts']['error'] for w in report['windows']) else 'measured-with-errors'
    report['measured_resources']=dict(status='collected' if report['resource_samples'] else 'not-collected',
        scope='server process and shared server/client container cgroup; node load includes other workloads',
        gpu_vram='requires external device telemetry',cold_start='requires launcher initialization/readiness evidence')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:report=run_benchmark(json.loads(args.config.read_text()))
    except BenchmarkFailure as error:
        args.output.write_text(json.dumps(error.report,indent=2)+'\n')
        raise SystemExit(str(error)) from None
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
