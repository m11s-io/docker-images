"""Export and validate the bounded v1 profile bundle in isolated processes.

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


def cases():
    import numpy as np
    rng=np.random.default_rng(20261030)
    result={}
    for name,t,h in [('short',17,1),('fixed',128,32),('nonaligned',129,65),
                     ('long-context',256,96),('five-patches',128,160),
                     ('four-patches',128,128),('maximum-horizon',128,320),
                     ('missing',129,65),('multi-block',128,200),('nonnegative',128,65)]:
        x=rng.normal(size=(1,1,t)).astype(np.float32)
        mask=np.ones(x.shape,dtype=bool)
        if name=='missing': mask[...,:32]=False; mask[...,::7]=False; x[~mask]=0
        if name=='nonnegative': x=np.abs(x)
        result[name]=(x,mask,h)
    return result


def validate_outputs(reference,actual,horizon):
    import numpy as np
    for value in (reference,actual):
        if value.shape!=(1,1,horizon,21) or value.dtype!=np.float32 or not np.isfinite(value).all():
            raise ValueError('final forecast must be finite FP32[1,1,H,21]')
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
        class Block(torch.nn.Module):
            def __init__(self,h): super().__init__(); self.model=model; self.h=h
            def forward(self,context,observed):
                return self.model.predict_block(context,observed,torch.zeros(1,dtype=torch.long),self.h)
        for h in range(1,6):
            with torch.inference_mode():
                ir=ov.convert_model(Block(h).eval(),example_input=(torch.zeros(1,128),torch.ones(1,128,dtype=torch.bool)),
                    input=[('context',[1,ov.Dimension(32,256)],ov.Type.f32),
                           ('observed',[1,ov.Dimension(32,256)],ov.Type.boolean)])
            ir.input(0).get_tensor().set_names({'context'})
            ir.input(1).get_tensor().set_names({'observed'})
            ir.output(0).get_tensor().set_names({'quantiles'})
            ov.save_model(ir,profiles/f'block-{h}.xml',compress_to_fp16=False)
        return
    if args.worker=='reference':
        from timestral.loading import load_model
        forecaster=TimestralForecaster(load_model(args.checkpoint,dtype=torch.float32),
                                       max_context=256,per_shot_horizon_patches=5)
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
    for name,(context,mask,h) in cases().items():
        for symmetric in (False,True):
            for clip in (False,True):
                key=f'{name}-s{int(symmetric)}-c{int(clip)}'
                forecast=forecaster.forecast(context,h,observation_mask=mask,
                    symmetric_averaging=symmetric,clip_nonnegative=clip)
                q=forecast.quantiles.numpy()
                levels=np.asarray(forecast.quantile_levels,dtype=np.float32)
                if reference is None:
                    validate_outputs(q,q,h)
                    arrays[key]=q
                    arrays['levels']=levels
                else:
                    results[key]=validate_outputs(reference[key],q,h)
                    np.testing.assert_array_equal(levels,reference['levels'])
                    np.testing.assert_allclose(forecast.median.numpy(),reference[key][...,10],rtol=1e-4,atol=1e-4)
    if reference is None:
        np.savez(evidence/'reference.npz',**arrays)
    else:
        report={'passed':True,'cases':results,'neural_backend':'openvino',
                'reference_weights_loaded_in_runtime_worker':False,
                'packages':{p:importlib.metadata.version(p) for p in ('torch','openvino','numpy')},
                'architecture':platform.machine(),'github_run':os.environ.get('GITHUB_RUN_ID')}
        (evidence/'parity.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


def export(output,model_size='5M'):
    from serving.artifacts import SOURCE_REVISION,MODEL_REVISIONS,PROFILE_FILES,verify_profiles
    model_id='mistralai/Timestral-'+model_size
    model_revision=MODEL_REVISIONS[model_id]
    from fetch_source import fetch
    from rewrites import patch_source
    from huggingface_hub import snapshot_download
    if platform.machine() not in ('x86_64','AMD64'): raise ValueError('profile export requires native amd64 hardware')
    if output.exists(): raise ValueError('use a fresh export output directory')
    (output/'profiles').mkdir(parents=True)
    (output/'evidence').mkdir()
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'source'; fetch(source)
        patched=Path(tmp)/'conversion-only'; patch_source(source,patched)
        checkpoint=Path(snapshot_download(model_id,revision=model_revision,
                                         allow_patterns=['config.json','model.safetensors'],token=False))
        shutil.copyfile(checkpoint/'config.json',output/'profiles/config.json')
        shutil.copyfile(source/'LICENSE',output/'profiles/LICENSE')
        card=Path(__file__).with_name('model-card.md').read_text()
        (output/'profiles/README.md').write_text(card+'\n\nModel: '+model_id+'\nRevision: '+model_revision+'\n')
        for mode,src in [('reference',source),('convert',patched),('runtime',source)]:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',mode,
                            '--source',str(src),'--checkpoint',str(checkpoint),'--output',str(output.resolve())],check=True)
    # Only a fully passing run reaches a versioned manifest. Publication remains
    # independent; CI evidence is retained alongside, outside the runtime bundle.
    report=output/'evidence/parity.json'
    manifest={'format':'timestral-openvino-profiles-v1','model_id':model_id,
              'model_revision':model_revision,'source_revision':SOURCE_REVISION,'precision':'FP32',
              'max_context':256,'per_shot_horizon_patches':5,
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
    parser.add_argument('--model-size',choices=['5M','209M'],default='5M')
    parser.add_argument('--worker',choices=['reference','convert','runtime'])
    parser.add_argument('--source'); parser.add_argument('--checkpoint')
    args=parser.parse_args()
    if args.worker: worker(args)
    else: export(args.output,args.model_size)
