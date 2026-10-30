"""Throwaway bounded forecast export proof; no production serving changes."""
import os,sys,json,subprocess,shutil
from pathlib import Path
ROOT=Path(os.environ["FORECAST_PROOF_ROOT"])

def cases():
 import numpy as np
 rng=np.random.default_rng(20261030)
 result={}
 for name,length,horizon,missing in [("short",17,1,False),("fixed",128,32,False),("nonaligned",129,65,False),("long-context",256,96,False),("long-horizon",128,160,False),("four-patches",128,128,False),("maximum-horizon",128,320,False),("missing",129,65,True),("multi-block",128,200,False)]:
  x=rng.normal(size=(1,1,length)).astype(np.float32);mask=np.ones_like(x,dtype=bool)
  if missing:mask[...,:32]=False;mask[...,::7]=False;x[~mask]=0
  result[name]={"context":x.tolist(),"mask":mask.tolist(),"horizon":horizon}
 return result


def worker(mode):
 import numpy as np,torch
 torch.set_num_threads(2);torch.set_num_interop_threads(1)
 sys.path.insert(0,str(ROOT/("patched" if mode=="convert" else "prepared/source")/"src"))
 from timestral.loading import load_model
 from timestral.forecaster import TimestralForecaster
 model=load_model(ROOT/"prepared/checkpoint",dtype=torch.float32)
 prepared=cases()
 if mode=="reference":
  forecaster=TimestralForecaster(model,max_context=256,per_shot_horizon_patches=5)
  for case in prepared.values():
   case["outputs"]={}
   for symmetric in [False,True]:
    out=forecaster.forecast(np.array(case["context"],dtype=np.float32),case["horizon"],observation_mask=np.array(case["mask"],dtype=bool),symmetric_averaging=symmetric)
    case["outputs"][str(symmetric)]=out.quantiles.numpy().tolist()
  (ROOT/"reference.json").write_text(json.dumps(prepared,allow_nan=False));print("Reference final forecasts saved",flush=True);return
 if mode=="convert":
  import openvino as ov
  class Block(torch.nn.Module):
   def __init__(self,h):super().__init__();self.model=model;self.h=h
   def forward(self,context,observed):return self.model.predict_block(context,observed,torch.zeros(1,dtype=torch.long),self.h)
  for horizon in range(1,6):
   block=Block(horizon).eval()
   with torch.inference_mode():
    ir=ov.convert_model(block,example_input=(torch.randn(1,128),torch.ones(1,128,dtype=torch.bool)),input=[("context",[1,ov.Dimension(32,256)],ov.Type.f32),("observed",[1,ov.Dimension(32,256)],ov.Type.boolean)])
   ir.input(0).get_tensor().set_names({"context"});ir.input(1).get_tensor().set_names({"observed"});ir.output(0).get_tensor().set_names({"quantiles"})
   ov.save_model(ir,ROOT/f"block-{horizon}.xml",compress_to_fp16=False)
   print("EXPORTED",horizon,flush=True)
  return

if __name__=="__main__":
 if len(sys.argv)>1:worker(sys.argv[1])
 else:
  from huggingface_hub import hf_hub_download
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  from fetch_source import fetch
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"export"))
  from export import patch_source
  (ROOT/"prepared").mkdir(parents=True)
  fetch(ROOT/"prepared/source")
  checkpoint=ROOT/"prepared/checkpoint";checkpoint.mkdir()
  for name in ["config.json","model.safetensors"]:
   cached=hf_hub_download("mistralai/Timestral-5M",name,revision="bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f",token=False)
   shutil.copyfile(cached,checkpoint/name)
  shutil.copyfile(checkpoint/"config.json",ROOT/"config.json")
  patch_source(ROOT/"prepared/source",ROOT/"patched")
  for mode in ["reference","convert"]:subprocess.run([sys.executable,__file__,mode],check=True)
