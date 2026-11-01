"""Independent fixtures to evaluate, not automatically adopt, a device budget."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np


def cases():
    # Seed and input families are independent of the diagnostic sine fixture.
    rng=np.random.default_rng(20261102)
    t=513;x=np.arange(t,dtype=np.float32)
    families={
        'trend': (x/256-.5)[None,None,:],
        'seasonal': (np.cos(x/11)+.3*np.sin(x/29))[None,None,:],
        'noise': rng.normal(0,.7,(1,1,t)).astype(np.float32),
        'steps': np.where(x<170,-.4,np.where(x<340,1.2,.2))[None,None,:].astype(np.float32),
        'constant': np.full((1,1,t),.75,dtype=np.float32),
        'zero': np.zeros((1,1,t),dtype=np.float32),
        'missing': (np.cos(x/17)+x/700)[None,None,:],
        'grouped': rng.normal(0,.5,(2,2,129)).astype(np.float32),
        'options-off': (np.sin(x/19)-.3)[None,None,:],
    }
    for name,base in families.items():
        for scale in (1e-3,1.,1e3):
            context=(base*scale).astype(np.float32)
            observed=np.ones(context.shape,dtype=bool)
            if name=='missing':
                observed[...,:53]=False;observed[...,::5]=False;context[~observed]=0
            options=dict(observation_mask=observed)
            if name=='options-off':options.update(symmetric_averaging=False,clip_nonnegative=False)
            for horizon in (160,1024):
                yield f'{name}-scale{scale}-h{horizon}',context,observed,horizon,options,scale


def budget_metrics(actual,expected,input_scale):
    assert actual.dtype==expected.dtype==np.float32 and actual.shape==expected.shape
    assert np.isfinite(actual).all() and np.isfinite(expected).all()
    error=np.abs(actual.astype(np.float64)-expected.astype(np.float64))
    original=error>1e-5+1e-5*np.abs(expected)
    unit_scaled=error/np.maximum(np.abs(expected),1.)
    input_scaled=error/np.maximum(np.abs(expected),input_scale)
    return dict(original_violations=int(original.sum()),max_absolute_error=float(error.max()),
        unit_floor_scaled_error=float(unit_scaled.max()),input_scale_floor_error=float(input_scaled.max()),
        provisional_unit_budget_pass=bool((unit_scaled<=5e-4).all()),
        provisional_input_scale_budget_pass=bool((input_scaled<=5e-4).all()))


def run(report):
    import torch
    from timestral import TimestralForecaster
    from serving.upstream import Settings,_check_device
    s=Settings.from_env();device=_check_device(s,torch);torch.set_num_threads(2)
    if s.backend=='cuda':
        torch.backends.fp32_precision='ieee';torch.backends.cuda.matmul.fp32_precision='ieee'
        torch.backends.cudnn.conv.fp32_precision='ieee';torch.backends.cudnn.rnn.fp32_precision='ieee'
    else:torch.set_float32_matmul_precision('highest')
    report.update(backend=s.backend,model=s.model_id,revision=s.model_revision,
        image=os.environ['ACCEPTANCE_IMAGE'],source=os.environ['ACCEPTANCE_SOURCE'],
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        device=torch.cuda.get_device_name(device),torch=torch.__version__,cases=[])
    cpu=TimestralForecaster.from_pretrained(s.model_id,revision=s.model_revision,device='cpu',cache_dir=s.hf_home)
    gpu=TimestralForecaster.from_pretrained(s.model_id,revision=s.model_revision,device=device,cache_dir=s.hf_home)
    assert all(p.dtype==torch.float32 and p.device==device for p in gpu.model.parameters())
    for name,context,observed,horizon,kwargs,scale in cases():
        reference=cpu.forecast(context,horizon,**kwargs)
        actual=gpu.forecast(context,horizon,**kwargs)
        outputs={}
        for key in ('quantiles','median','quantile_levels'):
            a=getattr(actual,key);e=getattr(reference,key)
            if isinstance(a,torch.Tensor):a=a.detach().cpu().numpy()
            if isinstance(e,torch.Tensor):e=e.detach().cpu().numpy()
            outputs[key]=budget_metrics(np.asarray(a,dtype=np.float32),np.asarray(e,dtype=np.float32),scale)
        item=dict(name=name,context_shape=list(context.shape),horizon=horizon,input_scale=scale,outputs=outputs)
        report['cases'].append(item);print('CROSS_CASE '+json.dumps(item),flush=True)
    report['diagnostic_complete']=True
    report['provisional_unit_budget_pass']=all(o['provisional_unit_budget_pass'] for c in report['cases'] for o in c['outputs'].values())
    report['provisional_input_scale_budget_pass']=all(o['provisional_input_scale_budget_pass'] for c in report['cases'] for o in c['outputs'].values())


def main():
    report=dict(diagnostic_complete=False,promotion='not-authorized',policy_adopted=False)
    try:run(report)
    finally:
        Path('/results/cross-device.json').write_text(json.dumps(report,indent=2)+'\n')
        print('CROSS_REPORT '+json.dumps(report),flush=True)


if __name__=='__main__':main()
