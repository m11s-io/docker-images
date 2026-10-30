"""Device rejection paths must fail before loading checkpoint weights."""
from types import SimpleNamespace
import pytest
from serving.upstream import Settings, _check_device

REVISION = 'a'*40

class TorchDevice:
    """Only external hardware discovery is substituted; validation is production."""
    def __init__(self,hip=None,cuda=None,arch='gfx1201'):
        import torch
        self.device = torch.device
        self.version = SimpleNamespace(hip=hip,cuda=cuda)
        self.selected = None
        self.cuda = SimpleNamespace(is_available=lambda:True,device_count=lambda:1,
            get_device_properties=lambda _:SimpleNamespace(gcnArchName=arch,major=12,minor=0),
            get_arch_list=lambda:['sm_120'],set_device=self.select)
    def select(self,index): self.selected=index

@pytest.mark.parametrize('backend,hip,cuda', [('cuda','7.14',None),('rocm',None,'13.0')])
def test_wrong_vendor_framework_is_rejected(backend,hip,cuda):
    with pytest.raises(RuntimeError,match='framework'):
        _check_device(Settings(model_revision=REVISION,backend=backend,model_device='cuda:0'),TorchDevice(hip,cuda))


def test_unsupported_amd_architecture_and_override_fail(monkeypatch):
    settings=Settings(model_revision=REVISION,backend='rocm',model_device='cuda:0')
    with pytest.raises(RuntimeError,match='architecture'):
        _check_device(settings,TorchDevice(hip='7.2',arch='gfx1030'))
    monkeypatch.setenv('HSA_OVERRIDE_GFX_VERSION','12.0.1')
    with pytest.raises(RuntimeError,match='overrides'):
        _check_device(settings,TorchDevice(hip='7.2'))


def test_explicit_device_index_is_checked():
    settings=Settings(model_revision=REVISION,backend='cuda',model_device='cuda:1')
    with pytest.raises(RuntimeError,match='index'):
        _check_device(settings,TorchDevice(cuda='13.0'))
