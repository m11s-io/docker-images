"""The accepted 5M tail exception never changes the strict measurements."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('divergence',Path(__file__).parents[1]/'serving/divergence.py')
m=importlib.util.module_from_spec(spec)
if Path(spec.origin).exists():spec.loader.exec_module(m)


def test_measured_tail_exception_is_explicit_and_scoped():
    e=np.ones((1,1,1024,21),np.float32);a=e.copy();a.flat[0]+=.0003
    r=m.assess(a,e,model_id='mistralai/Timestral-5M',case='maximum-horizon')
    assert not r['strict_passed'] and r['accepted']
    assert r['outside_original_tolerance']==1 and r['exception']=='5m-long-horizon-tails-2026-11-02'
    for model,case in [('mistralai/Timestral-209M','maximum-horizon'),('mistralai/Timestral-5M','unreviewed')]:
        assert not m.assess(a,e,model_id=model,case=case)['accepted']


def test_exception_rejects_broad_drift_median_drift_and_invalid_outputs():
    e=np.ones((1,1,1024,21),np.float32)
    for a in [e+.0003,e.copy(),e.copy()]:
        if np.array_equal(a,e):a[...,10]+=.0003
        assert not m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')['accepted']
    a=e.copy();a.flat[0]+=.001
    assert not m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')['accepted']
    for a in [e[...,0],e.astype(np.float16),e*np.nan]:
        with pytest.raises(ValueError):m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')


def test_reviewed_ci_tail_envelope():
    e=np.ones((1,1,1024,21),np.float32)
    for ratio,accepted in [(2.29825,True),(2.31,False)]:
        a=e.copy();a.flat[0]+=np.float32(.0002*ratio)
        r=m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')
        assert not r['strict_passed']
        assert r['accepted']==accepted


@pytest.mark.parametrize('size,ratio,count', [('28M',19.9,215),('123M',59.9,107)])
def test_larger_model_reviewed_horizon_limits(size,ratio,count):
    e=np.ones((1,1,1024,21),np.float32)
    def forecast(n, budget_ratio):
        a=e.copy()
        # Only nonmedian quantiles may use the exception.
        a[0,0,:n,0]+=np.float32(.0002*budget_ratio)
        return a
    model='mistralai/Timestral-'+size
    a=forecast(count,ratio)
    r=m.assess(a,e,model_id=model,case='maximum-horizon')
    assert r['accepted'] and not r['strict_passed'] and r['exception']
    assert not m.assess(a,e,model_id=model,case='blocks')['accepted']
    assert not m.assess(forecast(count+1,ratio),e,model_id=model,case='maximum-horizon')['accepted']
    assert not m.assess(forecast(1,ratio+1),e,model_id=model,case='maximum-horizon')['accepted']
    a[...,10]+=.0003
    assert not m.assess(a,e,model_id=model,case='maximum-horizon')['accepted']


def test_28m_reviewed_median_drift_is_bounded():
    e=np.full((1,1,1024,21),-40,np.float32)
    a=e.copy();a[0,0,:11,10]-=.0053
    assert m.assess(a,e,model_id='mistralai/Timestral-28M',case='maximum-horizon')['accepted']
    for model,case in [('mistralai/Timestral-123M','maximum-horizon'),
                       ('mistralai/Timestral-28M','blocks')]:
        assert not m.assess(a,e,model_id=model,case=case)['accepted']
    a[0,0,11,10]-=.0053
    assert not m.assess(a,e,model_id='mistralai/Timestral-28M',case='maximum-horizon')['accepted']


def test_median_absolute_cap_only_applies_to_strict_violations():
    e=np.full((1,1,1024,21),-40,np.float32)
    e[0,0,100,10]=1000
    a=e.copy();a[0,0,:11,10]-=.0053
    # .02 is below the original relative budget at reference=1000.
    a[0,0,100,10]+=.02
    assert m.assess(a,e,model_id='mistralai/Timestral-28M',case='maximum-horizon')['accepted']
    a=e.copy();a[0,0,0,10]-=.007
    assert not m.assess(a,e,model_id='mistralai/Timestral-28M',case='maximum-horizon')['accepted']
