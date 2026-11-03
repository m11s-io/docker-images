"""Export and validate CPU-equivalent v2 neural graphs in isolated processes.

This creates local candidate artifacts only. It never publishes or edits upstream.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def convert_block(model, *, covariates=False):
    """Convert a neural branch; horizon comes from a dynamic future dimension."""
    import torch
    import openvino as ov
    ps=model.config.patch_size

    from timestral.model import TimestralModel
    class NormalizedBlock(TimestralModel):
        def __init__(self):
            torch.nn.Module.__init__(self)
            self.config=model.config
            self.representation=model.representation
            self.transformer=model.transformer
            self.head=model.head
        def scale(self,inputs,observed):return self.normalization
        def _known_cov_scaling(self,inputs,observed,scaled,loc,scale,known_rows):
            return scaled,loc,scale
        def forward(self,context,observed,group_ids,known_future,loc,scale,role_ids=None):
            self.normalization=(context,loc,scale)
            h=known_future.shape[1]//ps
            if covariates:return self._predict_window(context,observed,group_ids,h,role_ids)
            return self._predict_context_only(context,observed,group_ids,h)

    length=ps*(6 if covariates else 4)
    examples=[torch.zeros(4,length),torch.ones(4,length,dtype=torch.bool),
              torch.tensor([0,0,1,1]),torch.zeros(4,ps*2),torch.zeros(4,length),torch.ones(4,length)]
    inputs=[('context',[-1,-1],ov.Type.f32),('observed',[-1,-1],ov.Type.boolean),
            ('group_ids',[-1],ov.Type.i64),('known_future',[-1,-1],ov.Type.f32),
            ('loc',[-1,-1],ov.Type.f32),('scale',[-1,-1],ov.Type.f32)]
    if covariates:
        examples += [torch.tensor([0,2,0,2])]
        inputs += [('role_ids',[-1],ov.Type.i64)]
    with torch.inference_mode():
        graph=ov.convert_model(NormalizedBlock().eval(),
                              example_input=tuple(examples),input=inputs)
    for port,(name,_,_) in zip(graph.inputs,inputs):port.get_tensor().set_names({name})
    graph.output(0).get_tensor().set_names({'quantiles'})
    return graph


def cases():
    import numpy as np
    rng=np.random.default_rng(20261030)
    shapes=[('short',1,1,17,1),('fixed',1,1,128,32),('nonaligned',1,1,129,65),
        ('long-context',1,1,1103,96),('five-patches',1,1,128,160),
        ('four-patches',1,1,128,128),('maximum-horizon',1,1,65,1024),
        ('missing',1,1,129,65),('multi-block',1,1,128,321),('nonnegative',1,1,128,65),
        ('grouped',2,2,257,33),('maximum-batch',8,1,32,3),('maximum-rows',4,8,32,3),
        ('maximum-context',1,1,32768,1),('context-edge',1,1,32767,1),
        ('horizon-31',1,1,65,31),('horizon-33',1,1,65,33),('horizon-161',1,1,65,161),
        ('horizon-320',1,1,65,320),('covariates',2,2,289,33),('covariate-rows',1,4,32,33)]
    result={}
    for name,b,v,t,h in shapes:
        x=rng.normal(size=(b,v,t)).astype(np.float32);mask=np.ones(x.shape,bool);kwargs={}
        if name=='missing':mask[...,:32]=False;mask[...,::7]=False;x[~mask]=0
        if name=='nonnegative':x=np.abs(x)
        if name in ('covariates','covariate-rows'):
            for key in ('past_covariates','known_covariates','categorical_past_covariates','categorical_known_covariates'):
                count=7 if name=='covariate-rows' else 1
                a=rng.normal(size=(b,count,t+h if 'known' in key else t)).astype(np.float32)
                if key.startswith('categorical'):a=np.floor(a).astype(np.float64)+2**24
                a[...,::7]=np.nan;kwargs[key]=a
        result[name]=(x,mask,h,kwargs)
    return result


def case_options(name):
    # Full-length contexts are expensive; cover all four option combinations
    # on the other shapes instead of repeating the same boundary four times.
    return [(False,False)] if name in ('maximum-context','context-edge') else [(s,c) for s in (False,True) for c in (False,True)]


def validate_outputs(reference,actual,horizon):
    import numpy as np
    for value in (reference,actual):
        if value.ndim!=4 or value.shape[-2:]!=(horizon,21) or value.shape!=reference.shape or value.dtype!=np.float32 or not np.isfinite(value).all():
            raise ValueError('final forecast must be finite FP32[B,V,H,21]')
    np.testing.assert_allclose(actual,reference,rtol=1e-4,atol=1e-4)
    return {'max_absolute_error':float(np.max(np.abs(actual-reference))),'rtol':1e-4,'atol':1e-4}


def worker(args):
    # Separate processes prevent conversion-only imports contaminating reference
    # or direct-runtime forecasting. No third_party checkout is ever modified.
    sys.path.insert(0,str(Path(args.source)/'src'))
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    from timestral.forecaster import TimestralForecaster
    root=Path(args.output)
    profiles=root/'profiles'; evidence=root/'evidence'
    if args.worker=='convert':
        import openvino as ov
        from timestral.loading import load_model
        model=load_model(args.checkpoint,dtype=torch.float32)
        for branch in ('context','covariates'):
            ir=convert_block(model,covariates=branch=='covariates')
            ov.save_model(ir,profiles/f'{branch}.xml',compress_to_fp16=False)
        return
    if args.worker=='reference':
        from timestral.loading import load_model
        forecaster=TimestralForecaster(load_model(args.checkpoint,dtype=torch.float32))
    else:
        # This worker allocates no reference neural model/weights. The plain
        # neural object owns compiled OpenVINO profiles and delegates scale to
        # the upstream function. All forecast loops remain upstream.
        backend_path=Path(__file__).resolve().parents[1]/'backend.py'
        spec=importlib.util.spec_from_file_location('timestral_openvino_backend',backend_path)
        backend=importlib.util.module_from_spec(spec); spec.loader.exec_module(backend)
        forecaster=backend.create_forecaster(profiles)
        if isinstance(forecaster.model,torch.nn.Module): raise ValueError('unexpected PyTorch neural model')
    arrays={}; results={}
    reference=np.load(evidence/'reference.npz',allow_pickle=False) if args.worker=='runtime' else None
    for name,(context,mask,h,kwargs) in cases().items():
        for symmetric,clip in case_options(name):
            key=f'{name}-s{int(symmetric)}-c{int(clip)}'
            forecast=forecaster.forecast(context,h,observation_mask=mask,
                symmetric_averaging=symmetric,clip_nonnegative=clip,**kwargs)
            q=forecast.quantiles.numpy()
            levels=np.asarray(forecast.quantile_levels,dtype=np.float32)
            if reference is None:
                validate_outputs(q,q,h)
                arrays[key]=q
                arrays['levels']=levels
            else:
                from serving.divergence import assess
                arrays[key]=q
                results[key]=assess(q,reference[key],model_id='mistralai/Timestral-'+args.model_size,case=name)
                np.testing.assert_array_equal(levels,reference['levels'])
                # assess includes the median's reference parity limits. Verify
                # the separate median output still matches its quantile exactly.
                np.testing.assert_array_equal(forecast.median.numpy(),q[...,10])
                print(key,json.dumps(results[key]),flush=True)
    if reference is None:
        np.savez(evidence/'reference.npz',**arrays)
    else:
        np.savez(evidence/'runtime.npz',**arrays)
        report={'passed':all(r['accepted'] for r in results.values()),'cases':results,'neural_backend':'openvino',
                'reference_weights_loaded_in_runtime_worker':False,
                'packages':{p:importlib.metadata.version(p) for p in ('torch','openvino','numpy')},
                'forecast_evidence_sha256':{name:hashlib.sha256((evidence/name).read_bytes()).hexdigest() for name in ('reference.npz','runtime.npz')},
                'architecture':platform.machine(),'github_run':os.environ.get('GITHUB_RUN_ID')}
        (evidence/'parity.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        if not report['passed']:raise AssertionError('forecast divergence exceeds accepted evidence')


def export(output,model_size='5M'):
    from serving.artifacts import SOURCE_REVISION,MODEL_REVISIONS,PROFILE_FILES,verify_profiles
    model_id='mistralai/Timestral-'+model_size
    model_revision=MODEL_REVISIONS[model_id]
    from fetch_source import fetch
    from rewrites import patch_source
    from huggingface_hub import hf_hub_download
    if platform.machine() not in ('x86_64','AMD64'): raise ValueError('profile export requires native amd64 hardware')
    if output.exists(): raise ValueError('use a fresh export output directory')
    (output/'profiles').mkdir(parents=True)
    (output/'evidence').mkdir()
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'source'; fetch(source)
        patched=Path(tmp)/'conversion-only'; patch_source(source,patched)
        checkpoint=Path(hf_hub_download(model_id,'config.json',revision=model_revision,token=False)).parent
        hf_hub_download(model_id,'model.safetensors',revision=model_revision,token=False)
        shutil.copyfile(checkpoint/'config.json',output/'profiles/config.json')
        shutil.copyfile(source/'LICENSE',output/'profiles/LICENSE')
        card=Path(__file__).with_name('model-card.md').read_text()
        (output/'profiles/README.md').write_text(card+'\n\nModel: '+model_id+'\nRevision: '+model_revision+'\n')
        for mode,src in [('reference',source),('convert',patched),('runtime',source)]:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',mode,'--model-size',model_size,
                            '--source',str(src),'--checkpoint',str(checkpoint),'--output',str(output.resolve())],check=True)
    # Only a fully passing run reaches a versioned manifest. Publication remains
    # independent; CI evidence is retained alongside, outside the runtime bundle.
    report=output/'evidence/parity.json'
    manifest={'format':'timestral-openvino-profiles-v2','model_id':model_id,
              'model_revision':model_revision,'source_revision':SOURCE_REVISION,'precision':'FP32',
              'parity_report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
              'files':{name:hashlib.sha256((output/'profiles'/name).read_bytes()).hexdigest() for name in sorted(PROFILE_FILES)}}
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    (output/'profiles/manifest.json').write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    verify_profiles(output/'profiles',digest,model_id,model_revision)
    (output/'evidence/manifest-sha256.txt').write_text(digest+'\n')
    print('Validated candidate manifest SHA256: '+digest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model-size',choices=['5M','28M','123M','209M'],default='5M')
    parser.add_argument('--worker',choices=['reference','convert','runtime'])
    parser.add_argument('--source'); parser.add_argument('--checkpoint')
    args=parser.parse_args()
    if args.worker: worker(args)
    else: export(args.output,args.model_size)
