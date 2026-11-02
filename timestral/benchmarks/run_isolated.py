"""Measure one image/model in an isolated Job, retaining files for collection.

The external collector must provide the actual Pod imageID in receipt.json,
then copy the checksum-listed result files before signalling `collected`.
There is no Kubernetes token, custom HTTP route, model fallback or publication.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from v2 import BenchmarkFailure,run_benchmark

ROOT=Path('/results')


def wait_receipt():
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        path=ROOT/'receipt.json'
        if path.exists():
            receipt=json.loads(path.read_text())
            if receipt['image_id'].removeprefix('docker.io/')!=os.environ['ACCEPTANCE_IMAGE']:
                raise ValueError('collector image identity mismatch')
            return receipt
        time.sleep(1)
    raise TimeoutError('actual Pod imageID receipt was not provided')


def ready(server):
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        if server.poll() is not None:raise RuntimeError('server exited before Ready')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/v2/models/timestral/ready',timeout=2) as response:
                if response.status==200:return
        except OSError:pass
        time.sleep(1)
    raise TimeoutError('server readiness timed out')


def main():
    ROOT.mkdir(exist_ok=True)
    summary=dict(status='failed',runs=[],startup=[],image=os.environ['ACCEPTANCE_IMAGE'],
        source=os.environ['ACCEPTANCE_SOURCE'],benchmark_sha256=os.environ['BENCHMARK_SHA256'],
        telemetry_scope='one server process; client shares its container CPU/cgroup; other node workloads remain running')
    try:
        receipt=wait_receipt()
        plan=json.loads(Path('/acceptance/plan.json').read_text())
        identity=dict(model_id=os.environ['MODEL_ID'],model_revision=os.environ['MODEL_REVISION'],
            backend=os.environ['TIMESTRAL_BACKEND'],image=os.environ['ACCEPTANCE_IMAGE'],source=os.environ['ACCEPTANCE_SOURCE'])
        if identity['backend']=='openvino':identity['artifact']=json.loads(os.environ['ACCEPTANCE_ARTIFACT'])
        for profile in plan['profiles']:
            env=dict(os.environ,TIMESTRAL_FORECAST_PROFILE=profile,
                BENCHMARK_GPU_SAMPLES=str(ROOT/f'{profile}-gpu.jsonl'))
            log=(ROOT/f'{profile}-server.log').open('w')
            start=time.monotonic()
            server=subprocess.Popen([sys.executable,'/acceptance/server_process.py','--workers','1',
                '--http_port','8080','--grpc_port','8081','--grpc_max_receive_message_length','8388608',
                '--enable_latency_logging','false'],env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                ready(server)
                summary['startup'].append(dict(profile=profile,readiness_seconds=time.monotonic()-start,
                    cache_state='fresh_job_cache' if len(summary['startup'])==0 else 'same_job_warm_model_cache',
                    note='artifact initialization is recorded separately by collector in receipt.json'))
                # The expected resolved settings are fixed for these two pinned checkpoints.
                settings=dict(max_context=256,per_shot_horizon_patches=5) if profile=='bounded-v1' else dict(max_context=32768,per_shot_horizon_patches=32)
                for transport in ('http-json','http-binary','grpc'):
                    for concurrency,windows in ((1,3),(2,1)):
                        config=dict(endpoint='127.0.0.1:'+('8081' if transport=='grpc' else '8080'),
                            transport=transport,identity=identity,deployment_receipt=receipt,
                            forecast_profile=profile,forecast_settings=settings,fixture=plan['fixture'],
                            warmup_count=10,window_seconds=plan['window_seconds'],windows=windows,
                            concurrency=concurrency,server_pid=server.pid,server_latency_logging=False)
                        name=f'{profile}-{transport}-c{concurrency}.json'
                        try:report=run_benchmark(config)
                        except BenchmarkFailure as error:
                            (ROOT/name).write_text(json.dumps(error.report,separators=(',',':'))+'\n')
                            raise
                        (ROOT/name).write_text(json.dumps(report,separators=(',',':'))+'\n')
                        summary['runs'].append(dict(file=name,profile=profile,transport=transport,
                            concurrency=concurrency,status=report['status'],windows=report['windows'],
                            fixture_sha256=report['fixture_sha256']))
                        print('BENCHMARK_PROGRESS '+json.dumps(summary['runs'][-1]),flush=True)
                if identity['backend'] in ('cuda','rocm'):
                    gpu=ROOT/f'{profile}-gpu.jsonl'
                    if not gpu.exists() or not gpu.stat().st_size:raise RuntimeError('GPU telemetry missing')
                    summary.setdefault('gpu_telemetry',[]).append(dict(profile=profile,file=gpu.name,scope='server framework cumulative peaks and whole-device free/total'))
                if any(r['status']!='measured' for r in summary['runs']):
                    raise RuntimeError('benchmark completed with inference errors')
            finally:
                server.terminate()
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:server.kill();server.wait()
                log.close()
        summary['status']='measured'
    except Exception as error:
        summary['error_type']=type(error).__name__
        # No upstream exception text: URLs, tokens or request data may be present.
    finally:
        (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name not in ('done.json','collected')}
        (ROOT/'done.json').write_text(json.dumps(dict(status=summary['status'],files=files),indent=2)+'\n')
        print('BENCHMARK_COMPLETE '+json.dumps(dict(status=summary['status'],files=len(files))),flush=True)
        deadline=time.monotonic()+600
        while not (ROOT/'collected').exists() and time.monotonic()<deadline:time.sleep(1)
    if summary['status']!='measured':raise SystemExit(1)


if __name__=='__main__':main()
