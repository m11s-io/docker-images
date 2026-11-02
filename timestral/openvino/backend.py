"""Direct OpenVINO neural blocks with unchanged upstream forecasting."""
from pathlib import Path
import numpy as np
import torch
from timestral.config import TimestralConfig
from timestral.forecaster import TimestralForecaster
from timestral.model import TimestralModel


class OpenVINOBlocks:
    def __init__(self,artifact_directory):
        import openvino as ov
        root=Path(artifact_directory)
        self.config=TimestralConfig.load(root/'config.json')
        core=ov.Core();self.compiled={}
        for branch in ('context','covariates'):
            model=core.read_model(root/f'{branch}.xml')
            types={'context':ov.Type.f32,'observed':ov.Type.boolean,
                   'group_ids':ov.Type.i64,'known_future':ov.Type.f32,'loc':ov.Type.f32,'scale':ov.Type.f32}
            if branch=='covariates':types.update(role_ids=ov.Type.i64)
            if {p.get_any_name() for p in model.inputs}!=set(types):
                raise ValueError('IR input names do not match contract')
            for name,dtype in types.items():
                port=model.input(name);shape=port.get_partial_shape()
                rank=1 if name in ('group_ids','role_ids') else 2
                if (port.get_element_type()!=dtype or shape.rank!=rank or
                    any(d.get_min_length()!=0 or d.get_max_length()!=-1 for d in shape)):
                    raise ValueError('IR inputs must preserve dynamic CPU shapes')
            if len(model.outputs)!=1:
                raise ValueError('IR must return one quantile tensor')
            port=model.output(0);shape=port.get_partial_shape()
            if (port.get_any_name()!='quantiles' or port.get_element_type()!=ov.Type.f32 or
                shape.rank!=3 or shape[0].is_static or shape[1].is_static or
                not shape[2].compatible(ov.Dimension(self.config.num_quantiles))):
                raise ValueError('invalid IR output contract')
            compiled=core.compile_model(model,'CPU',{'INFERENCE_PRECISION_HINT':'f32',
                'INFERENCE_NUM_THREADS':2,'NUM_STREAMS':1,'ENABLE_CPU_PINNING':False})
            self.compiled[branch]=compiled
            for r,t,h in [(1,self.config.patch_size*3,self.config.patch_size),
                          (4,self.config.patch_size*5,self.config.patch_size*min(2,self.config.block_size))]:
                values=dict(context=np.zeros((r,t),np.float32),observed=np.ones((r,t),bool),
                            group_ids=np.arange(r,dtype=np.int64)//2,known_future=np.zeros((r,h),np.float32),
                            loc=np.zeros((r,t),np.float32),scale=np.ones((r,t),np.float32))
                if branch=='covariates':values.update(role_ids=np.arange(r,dtype=np.int64)%3)
                self._execute(compiled,values,r,h)


    def eval(self):return self

    def scale(self,inputs,observed):return TimestralModel.scale(self,inputs,observed)

    def predict_block(self,inputs,observed,group_ids,horizon_patches,
                      role_ids=None,known_future=None,known_future_mask=None):
        rows=inputs.shape[0];length=horizon_patches*self.config.patch_size
        if inputs.device.type!='cpu' or inputs.dtype!=torch.float32:
            raise ValueError('OpenVINO requires FP32 CPU input tensors')
        if inputs.ndim!=2 or inputs.shape[1]%self.config.patch_size or observed.shape!=inputs.shape or observed.dtype!=torch.bool:
            raise ValueError('invalid upstream neural input shape or mask')
        covariates=(self.config.covariate_enabled and role_ids is not None and bool((role_ids!=0).any()))
        branch='covariates' if covariates else 'context'
        # Keep upstream float64 normalization on CPU; OpenVINO executes the
        # learned neural operations. CPU-plugin conversion lowers f64 arithmetic.
        data,mask=inputs,observed
        future=torch.zeros((rows,length),dtype=torch.float32) if known_future is None else known_future
        if covariates:
            future_mask=torch.zeros((rows,length),dtype=torch.bool) if known_future_mask is None else known_future_mask
            data=torch.cat([inputs,future],dim=-1)
            mask=torch.cat([observed,future_mask],dim=-1)
        scaled,loc,scale=self.scale(data,mask)
        if covariates:
            scaled,loc,scale=TimestralModel._known_cov_scaling(self,data,mask,scaled,loc,scale,role_ids==2)
        values=dict(context=scaled.contiguous().numpy(),observed=mask.contiguous().numpy(),
                    group_ids=group_ids.contiguous().numpy(),known_future=future.contiguous().numpy(),
                    loc=loc.contiguous().numpy(),scale=scale.contiguous().numpy())
        if covariates:values['role_ids']=role_ids.contiguous().numpy()
        result=self._execute(self.compiled[branch],values,rows,length)
        return torch.from_numpy(result.copy())

    def _execute(self,compiled,values,rows,length):
        result=compiled(values)[compiled.output(0)]
        if result.shape!=(rows,length,self.config.num_quantiles) or result.dtype!=np.float32 or not np.isfinite(result).all():
            raise ValueError('invalid OpenVINO block result')
        return result


class CPUForecaster(TimestralForecaster):
    @property
    def device(self):return torch.device('cpu')


def create_forecaster(artifact_directory,*,forecast_profile='upstream-default'):
    if forecast_profile not in ('upstream-default','bounded-v1'):
        raise ValueError('unsupported forecast profile')
    options=dict(max_context=256,per_shot_horizon_patches=5) if forecast_profile=='bounded-v1' else {}
    return CPUForecaster(OpenVINOBlocks(artifact_directory),**options)
