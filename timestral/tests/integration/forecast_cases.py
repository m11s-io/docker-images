"""Synthetic requests shared by the independent reference and transport checks."""
import numpy as np

CASES = ('short','nonaligned','long','missing','grouped','blocks','multi-block',
         'covariates','symmetry-off','clip-off','options')


def make_case(case, max_context):
    b,v,t,h = {'short':(1,1,7,3),'nonaligned':(1,1,65,35),'long':(1,1,1103,33),
               'missing':(1,1,65,35),'grouped':(2,2,65,35),'blocks':(1,1,65,1024),'multi-block':(1,1,65,200),
               'covariates':(1,1,65,35),'symmetry-off':(1,1,65,35),'clip-off':(1,1,65,35),'options':(1,1,65,35)}[case]
    if case == 'long': t = min(32768, max_context + 65)
    context = np.sin(np.arange(b*v*t,dtype=np.float32).reshape(b,v,t)/7)
    mask = np.ones(context.shape,dtype=bool)
    if case == 'missing': mask[...,1::3] = False
    values = {'context':context,'observation_mask':mask,
              'prediction_length':np.array([h],dtype=np.int64)}
    kwargs = {'observation_mask':mask}
    if case in ('symmetry-off','clip-off','options'):
        if case == 'clip-off': context[:] = np.abs(context)
        symmetric, clip = case == 'clip-off', case == 'symmetry-off'
        values.update(symmetric_averaging=np.array([symmetric]),clip_nonnegative=np.array([clip]))
        kwargs.update(symmetric_averaging=symmetric,clip_nonnegative=clip)
    if case == 'covariates':
        for name in ('past_covariates','known_covariates','categorical_past_covariates','categorical_known_covariates'):
            length = t+h if 'known' in name else t
            a = (np.arange(length).reshape(1,1,length)%3).astype(np.float64 if name.startswith('categorical') else np.float32)
            if name.startswith('categorical'): a += 2**24
            observed = np.ones(a.shape,dtype=bool); observed[...,2::5] = False
            values[name],values[name+'_mask'] = a,observed
            internal = a.copy(); internal[~observed] = np.nan
            kwargs[name] = internal
    return b, v, t, h, context, values, kwargs
