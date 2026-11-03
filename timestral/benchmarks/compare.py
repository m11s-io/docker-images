"""Compare two Timestral sizes on four required backends against frozen real targets."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
import urllib.request
import uuid

import numpy as np

REVISION='6c1067e5a57161249b17289a565178dc7a3fb3ca'
BASE=f'https://raw.githubusercontent.com/Mcompetitions/M4-methods/{REVISION}/Dataset/'
METRICS=('mae','mase','smape','pinball','wql')


def score_case(history,truth,median,quantiles,levels,seasonality):
    history,truth,median,quantiles,levels=[np.asarray(a,dtype=np.float64) for a in (history,truth,median,quantiles,levels)]
    if (truth.ndim!=1 or not truth.size or median.shape!=truth.shape or quantiles.shape!=(truth.size,levels.size)
        or levels.ndim!=1 or not levels.size or not (np.diff(levels)>0).all() or not ((levels>0)&(levels<1)).all()
        or not all(np.isfinite(a).all() for a in (truth,median,quantiles,levels)) or type(seasonality) is not int or seasonality<1):
        raise ValueError('invalid scoring arrays or seasonality')
    pairs=np.abs(history[seasonality:]-history[:-seasonality]);pairs=pairs[np.isfinite(pairs)]
    scale=float(pairs.mean()) if pairs.size else 0
    error=np.abs(truth-median);denominator=np.abs(truth)+np.abs(median)
    smape=np.divide(200*error,denominator,out=np.zeros_like(error),where=denominator>0)
    delta=truth[:,None]-quantiles;pinball=np.maximum(levels*delta,(levels-1)*delta)
    total=float(np.abs(truth).sum())
    return dict(mae=float(error.mean()),mase=float(error.mean()/scale) if scale else None,
        smape=float(smape.mean()),pinball=float(pinball.mean()),wql=float(2*pinball.sum(axis=0).mean()/total) if total else None)


def case_key(series_id):return hashlib.sha256(('timestral-compare-v1/'+series_id).encode()).hexdigest()


def read_series(path,ids):
    result={}
    with path.open(newline='') as stream:
        reader=csv.reader(stream);next(reader)
        for line in reader:
            if line[0] not in ids:continue
            if line[0] in result:raise ValueError('duplicate series')
            values=line[1:]
            while values and not values[-1].strip():values.pop()
            result[line[0]]=[float(x) if x.strip() else np.nan for x in values]
    return result


def load_cases(manifest):
    root=Path(manifest['directory'])
    required={'M4-info.csv',*(f'{split}/{f}-{split.lower()}.csv' for f in manifest['case_ids'] for split in ('Train','Test'))}
    if not required<=manifest['files'].keys():raise ValueError('missing dataset checksums')
    for name,expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('invalid dataset path')
        with (root/name).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('dataset checksum mismatch')
    with (root/'M4-info.csv').open(newline='') as stream:info={r['M4id']:r for r in csv.DictReader(stream)}
    cases=[]
    for frequency,ids in manifest['case_ids'].items():
        expected=sorted([k for k,v in info.items() if v['SP']==frequency],key=case_key)[:len(ids)]
        if not ids or ids!=expected:raise ValueError('invalid frozen cohort')
        train=read_series(root/f'Train/{frequency}-train.csv',set(ids))
        test=read_series(root/f'Test/{frequency}-test.csv',set(ids))
        for series_id in ids:
            if series_id not in info or series_id not in train or series_id not in test:raise ValueError('selected series missing')
            meta=info[series_id];history=train[series_id];truth=test[series_id]
            if meta['SP']!=frequency or len(truth)!=int(meta['Horizon']) or not np.isfinite(truth).all() or not np.isfinite(history[-256:]).any():
                raise ValueError('invalid selected case')
            cases.append(dict(id=series_id,frequency=frequency,history=history,truth=truth,seasonality=int(meta['Frequency'])))
    return cases


def prepare(config,directory):
    directory.mkdir(parents=True,exist_ok=True);files={}
    names=['M4-info.csv',*[f'{split}/{f}-{split.lower()}.csv' for f in ('Hourly','Daily','Weekly') for split in ('Train','Test')]]
    for name in names:
        path=directory/name;path.parent.mkdir(exist_ok=True)
        if not path.exists():
            with urllib.request.urlopen(BASE+name,timeout=120) as response,path.open('wb') as stream:shutil.copyfileobj(response,stream)
        with path.open('rb') as stream:files[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    with (directory/'M4-info.csv').open(newline='') as stream:info=list(csv.DictReader(stream))
    ids={f:sorted([r['M4id'] for r in info if r['SP']==f],key=case_key)[:50] for f in ('Hourly','Daily','Weekly')}
    if config['dataset'].get('files') and (files!=config['dataset']['files'] or ids!=config['dataset']['case_ids']):raise ValueError('frozen dataset changed')
    manifest=dict(revision=REVISION,directory=str(directory),files=files,case_ids=ids)
    cases=load_cases(manifest)
    if len(cases)!=150:raise ValueError('expected 150 frozen cases')
    config['dataset']=manifest


def check_identity(row,parameters):
    expected={k:row[k] for k in ('backend','model_id','model_revision','forecast_profile')}
    expected.update(max_context=row['max_context'],per_shot_horizon_patches=row['per_shot_horizon_patches'])
    if row['backend']=='openvino':expected['artifact_manifest_sha256']=row['artifact']['manifest_sha256']
    if any(parameters.get(k)!=v for k,v in expected.items()):raise ValueError('loaded identity/profile mismatch')


def forecast(row,history,horizon,request_id):
    import tritonclient.http as http
    if '_client' not in row:row['_client']=http.InferenceServerClient(row['endpoint'],connection_timeout=30,network_timeout=120)
    context=np.asarray(history[-256:],dtype=np.float32).reshape(1,1,-1);mask=np.isfinite(context)
    values=dict(context=(np.where(mask,context,0).astype(np.float32),'FP32'),observation_mask=(mask,'BOOL'),
        prediction_length=(np.array([horizon],dtype=np.int64),'INT64'),
        symmetric_averaging=(np.array([True]),'BOOL'),clip_nonnegative=(np.array([True]),'BOOL'))
    inputs=[]
    for name,(a,datatype) in values.items():
        inp=http.InferInput(name,list(a.shape),datatype);inp.set_data_from_numpy(a,binary_data=False);inputs.append(inp)
    response=row['_client'].infer('timestral',inputs,request_id=request_id,headers={'content-type':'application/json'})
    body=response.get_response()
    if body['id']!=request_id or body.get('model_version')!=row['model_revision']:raise ValueError('response identity mismatch')
    check_identity(row,body.get('parameters',{}))
    median,quantiles,levels=[response.as_numpy(k) for k in ('median','quantiles','quantile_levels')]
    for a,shape in ((median,(1,1,horizon)),(quantiles,(1,1,horizon,21)),(levels,(21,))):
        if a is None or a.shape!=shape or a.dtype!=np.float32 or not np.isfinite(a).all():raise ValueError('invalid response tensors')
    return median[0,0],quantiles[0,0],levels


def evaluate(config,cases):
    row=dict(config['row']);records=[];first={}
    if (not re.fullmatch(r'm11s/timestral@sha256:[a-f0-9]{64}',row['image']) or
        row['actual_image_id'].removeprefix('docker.io/')!=row['image'] or not re.fullmatch('[a-f0-9]{40}',row['source']) or row['forecast_profile']!='upstream-default'):
        raise ValueError('pinned image, actual Pod imageID, source and known forecast profile required')
    try:
        for i in range(config['warmups']):
            case=cases[(i*len(cases)//max(1,config['warmups']))%len(cases)]
            forecast(row,case['history'],len(case['truth']),str(uuid.uuid4()))
        for repeat in range(config['repeats']):
            for case in cases:
                request_id=str(uuid.uuid4());started=time.monotonic()
                record=dict(case_id=case['id'],frequency=case['frequency'],repeat=repeat,request_id=request_id)
                try:
                    median,quantiles,levels=forecast(row,case['history'],len(case['truth']),request_id)
                    record.update(status='success',seconds=time.monotonic()-started,
                        median=median.tolist(),quantiles=quantiles.tolist(),levels=levels.tolist())
                    if repeat==0:
                        first[case['id']]=quantiles.copy()
                        record['scores']=score_case(case['history'],case['truth'],median,quantiles,levels,case['seasonality'])
                    else:record['repeat_max_absolute_drift']=float(np.max(np.abs(quantiles-first[case['id']]))) if case['id'] in first else None
                except Exception as error:
                    record.update(status='invalid' if isinstance(error,ValueError) else 'error',
                        seconds=time.monotonic()-started,error_type=type(error).__name__)
                records.append(record)
                if record['status']=='invalid':return records
    finally:
        if '_client' in row:row['_client'].close()
    return records


def summarize(records,expected_cases,repeats):
    success=[r for r in records if r['status']=='success'];frequencies={}
    complete=(len(success)==expected_cases*repeats and len(records)==len(success)
        and len({(r['case_id'],r['repeat']) for r in success})==len(success))
    for frequency in sorted({r['frequency'] for r in records}):
        sample=[r for r in success if r['frequency']==frequency];scores=[r['scores'] for r in sample if r['repeat']==0 and 'scores' in r]
        group=dict(samples=len(sample),errors=sum(r['status']!='success' for r in records if r['frequency']==frequency))
        group.update({f'p{p}_seconds':float(np.percentile([r['seconds'] for r in sample],p)) if sample else None for p in (50,95)})
        for metric in METRICS:
            values=[r[metric] for r in scores if r[metric] is not None]
            group[metric]=float(np.mean(values)) if values else None
            group['undefined_'+metric]=len(scores)-len(values)
        frequencies[frequency]=group
    macro={k:float(np.mean([g[k] for g in frequencies.values()])) if frequencies and all(g[k] is not None for g in frequencies.values()) else None for k in METRICS}
    return dict(status='complete' if complete else 'incomplete',samples=len(success),errors=len(records)-len(success),
        p50_seconds=float(np.percentile([r['seconds'] for r in success],50)) if success else None,
        p95_seconds=float(np.percentile([r['seconds'] for r in success],95)) if success else None,frequencies=frequencies,macro=macro)


def saved_result(path,key,retry):
    if not path.exists():return None
    result=json.loads(path.read_text())
    if result.get('run_key')!=key:raise ValueError('saved run uses different code/pins/cohort; choose a new output directory')
    if retry and result['summary']['status']!='complete':
        path.rename(path.with_name(path.stem+f'.failed-{time.time_ns()}.json'))
        return None
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--retry-incomplete',action='store_true');p.add_argument('--data-dir',type=Path);p.add_argument('--prepare',action='store_true');p.add_argument('--only')
    args=p.parse_args();config=json.loads(args.config.read_text())
    if args.prepare:
        prepare(config,args.data_dir or Path(config['dataset']['directory']))
        args.config.write_text(json.dumps(config,indent=2,allow_nan=False)+'\n');return
    if args.data_dir:config['dataset']['directory']=str(args.data_dir)
    if config['warmups']!=10 or config['repeats']!=3:raise ValueError('comparison requires 10 warmups and 3 passes')
    if {(r['backend'],r['model_id']) for r in config['rows']}!={(b,'mistralai/Timestral-'+m) for b in ('cpu','cuda','rocm','openvino') for m in ('5M','209M')} or len(config['rows'])!=8:raise ValueError('eight unique required backend/model rows required')
    cases=load_cases(config['dataset'])
    if len(cases)!=150:raise ValueError('comparison requires the frozen 150-case cohort')
    args.output_dir.mkdir(parents=True,exist_ok=True);table=[]
    dataset_key={k:v for k,v in config['dataset'].items() if k!='directory'}
    for row in config['rows']:
        path=args.output_dir/(row['id']+'.json')
        key=hashlib.sha256(json.dumps(dict(row={k:v for k,v in row.items() if k!='endpoint'},dataset=dataset_key,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),warmups=config['warmups'],repeats=config['repeats']),sort_keys=True).encode()).hexdigest()
        result=saved_result(path,key,args.retry_incomplete and (not args.only or args.only==row['id']))
        if (not args.only or args.only==row['id']) and not result and row.get('endpoint'):
            try:
                records=evaluate(dict(row=row,warmups=config['warmups'],repeats=config['repeats']),cases)
                result=dict(row=row,run_key=key,records=records,summary=summarize(records,len(cases),config['repeats']))
            except Exception as error:result=dict(row=row,run_key=key,records=[],summary={'status':'incomplete','error_type':type(error).__name__})
            path.write_text(json.dumps(result,allow_nan=False)+'\n')
        summary=result['summary'] if result else {'status':'pending'}
        table.append(dict(id=row['id'],backend=row['backend'],model=row['model_id'],hardware=row.get('hardware'),
            status=summary['status'],p50_seconds=summary.get('p50_seconds'),p95_seconds=summary.get('p95_seconds'),
            **{k:summary.get('macro',{}).get(k) for k in METRICS},errors=summary.get('errors')))
    (args.output_dir/'summary.json').write_text(json.dumps(table,indent=2,allow_nan=False)+'\n')
    with (args.output_dir/'summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    print(json.dumps(table,indent=2))
    if any(r['status']!='complete' for r in table if not args.only or r['id']==args.only):raise SystemExit(1)


if __name__=='__main__':main()
