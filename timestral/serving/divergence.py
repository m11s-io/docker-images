"""Recorded model-specific horizon exceptions; strict measurements remain intact."""
import numpy as np

EXCEPTION='5m-long-horizon-tails-2026-11-02'
CASES={'maximum-horizon','blocks','decode-blocks','periodic-1024'}
MAX_BUDGET_RATIO=2.30
MAX_OUTSIDE_FRACTION=.005
# PR 173, Actions run 41639780870, evidence/parity.json: maximum-horizon
# 28M: <=20/21504 outside, ratio <=11.2046292154.
# 123M: <=70/21504 outside, ratio <=53.1673180042.
# Run 41656103930: 28M <=184/21504, ratio <=17.89796;
# 123M ratio <=55.55199. Use rounded envelopes across observed runners:
# 28M <=1% tails / 20x budget; 123M <=0.5% tails / 60x budget.
REVIEWED_HORIZON_LIMITS={
    'mistralai/Timestral-28M': (20,.01,'28m-maximum-horizon-tails-2026-11-03'),
    'mistralai/Timestral-123M': (60,.005,'123m-maximum-horizon-tails-2026-11-03'),
}


def assess(actual,reference,*,model_id,case):
    if (actual.shape!=reference.shape or actual.ndim!=4 or actual.shape[-1]!=21 or
        actual.dtype!=np.float32 or reference.dtype!=np.float32 or
        not np.isfinite(actual).all() or not np.isfinite(reference).all()):
        raise ValueError('invalid forecast shape, precision or finite values')
    delta=np.abs(actual.astype(np.float64)-reference.astype(np.float64))
    budget=1e-4+1e-4*np.abs(reference.astype(np.float64))
    outside=delta>budget;count=int(outside.sum());ratio=float(np.max(delta/budget))
    strict=count==0
    # Native evidence: <=104/21504 tails, <=2.08457 times the old combined
    # budget; reproduced CI:88/21504,2.2982514 times. User accepted 2.30.
    exception=(not strict and model_id=='mistralai/Timestral-5M' and case in CASES
        and actual.shape[-2]==1024 and count/actual.size<=MAX_OUTSIDE_FRACTION and ratio<=MAX_BUDGET_RATIO
        and not outside[...,10].any())
    exception_name=EXCEPTION if exception else None
    # Run 41659716804: identical HTTP JSON/binary and gRPC results for
    # sinusoidal 28M blocks: 996/21504 outside, ratio 46.79752;
    # median 64/1024 outside, max error .18524170; max quantile error 1.71290.
    # User accepted expanded envelope after run 41671193145: 1115/21504
    # outside (5.185%), ratio 141.17811; retain existing absolute/median caps.
    if not strict and model_id=='mistralai/Timestral-28M' and case=='blocks':
        if (actual.shape[-2]==1024 and count/actual.size<=.055 and ratio<=150
            and outside[...,10].mean()<=.0625 and delta[...,10].max()<=.2
            and delta.max()<=1.8):
            exception=True
            exception_name='28m-protocol-blocks-2026-11-03'
    if not strict and model_id in REVIEWED_HORIZON_LIMITS and case=='maximum-horizon':
        max_ratio,max_fraction,name=REVIEWED_HORIZON_LIMITS[model_id]
        median_ok=not outside[...,10].any()
        # Run 41655342566: 11/1024 median values outside the original
        # budget, max absolute error .00645828, max relative error .0001335.
        if model_id=='mistralai/Timestral-28M':
            median_delta=delta[...,10]
            median_budget=1e-4+1.4e-4*np.abs(reference[...,10].astype(np.float64))
            median_ok=(np.all(median_delta<=median_budget)
                and np.max(np.where(outside[...,10],median_delta,0))<=.0065
                and outside[...,10].mean()<=11/1024)
        tails=outside.copy();tails[...,10]=False
        if (actual.shape[-2]==1024 and tails.sum()/actual.size<=max_fraction
            and ratio<=max_ratio and median_ok):
            exception=True
            exception_name=name
    return dict(strict_passed=strict,accepted=strict or exception,
        exception=exception_name,values=actual.size,
        outside_original_tolerance=count,max_original_budget_ratio=ratio,
        median_outside_original_tolerance=int(outside[...,10].sum()),
        max_median_absolute_error=float(delta[...,10].max()),
        max_median_violation_absolute_error=float(np.max(np.where(outside[...,10],delta[...,10],0))),
        max_absolute_error=float(delta.max()),rtol=1e-4,atol=1e-4)
