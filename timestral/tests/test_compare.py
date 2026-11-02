"""Forecast-quality arithmetic, frozen data and checked standard-client requests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('compare',Path(__file__).parents[1]/'benchmarks/compare.py')
compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)


def test_accuracy_is_against_truth_not_upstream_parity():
    result=compare.score_case([1,2,3],[4],[3],[[3]],[.5],1)
    assert result['mae']==1
    assert result['mase']==1
    assert result['smape']==pytest.approx(200/7)
    assert result['pinball']==.5
    assert result['wql']==.25


def test_undefined_scales_are_null_not_artificially_perfect():
    result=compare.score_case([0,0],[0],[1],[[1]],[.5],1)
    assert result['mase'] is None and result['wql'] is None
    assert result['mae']==1 and result['smape']==200
    assert compare.score_case([0,0],[0],[0],[[0]],[.5],1)['smape']==0


def test_signed_series_and_missing_history_use_observed_training_pairs():
    result=compare.score_case([-3,np.nan,-1,0],[-1],[-2],[[-2]],[.5],1)
    assert result['mase']==1
    assert result['smape']==pytest.approx(200/3)
    with pytest.raises(ValueError):compare.score_case([1,2],[np.nan],[3],[[3]],[.5],1)


def dataset(tmp_path):
    files={'M4-info.csv':'M4id,SP,Frequency,Horizon\nD1,Daily,1,1\nD2,Daily,1,1\n',
        'Train/Daily-train.csv':'V1,V2,V3,V4\nD1,1,2,3\nD2,2,3,4\n',
        'Test/Daily-test.csv':'V1,V2\nD1,4\nD2,5\n'}
    for name,data in files.items():
        p=tmp_path/name;p.parent.mkdir(exist_ok=True);p.write_text(data)
    ids=sorted(['D1','D2'],key=compare.case_key)
    return dict(directory=str(tmp_path),case_ids={'Daily':ids},files={name:hashlib.sha256(data.encode()).hexdigest() for name,data in files.items()})


def test_frozen_split_does_not_append_future_values_or_accept_file_changes(tmp_path):
    manifest=dataset(tmp_path);cases=compare.load_cases(manifest)
    d1=next(c for c in cases if c['id']=='D1')
    assert d1['history']==[1,2,3] and d1['truth']==[4]
    (tmp_path/'Test/Daily-test.csv').write_text('changed')
    with pytest.raises(ValueError,match='checksum'):compare.load_cases(manifest)


def test_selected_case_cannot_silently_disappear(tmp_path):
    manifest=dataset(tmp_path);manifest['case_ids']['Daily']=['D3']
    with pytest.raises(ValueError):compare.load_cases(manifest)


def row():
    return dict(id='cpu-5M',endpoint='localhost:8080',backend='cpu',
        model_id='mistralai/Timestral-5M',model_revision='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f',
        image='m11s/timestral@sha256:'+'a'*64,actual_image_id='docker.io/m11s/timestral@sha256:'+'a'*64,
        source='b'*40,forecast_profile='bounded-v1',hardware='test-cpu')


def test_wrong_loaded_revision_or_profile_stops_comparison():
    r=row();identity={k:r[k] for k in ('backend','model_id','model_revision','forecast_profile')}
    identity.update(max_context=256,per_shot_horizon_patches=5)
    compare.check_identity(r,identity)
    for change in ({'model_revision':'c'*40},{'per_shot_horizon_patches':32}):
        with pytest.raises(ValueError):compare.check_identity(r,identity|change)


def test_default_profile_rejects_bounded_endpoint_and_accepts_actual_settings():
    r=row()|dict(forecast_profile='upstream-default',max_context=32768,per_shot_horizon_patches=32)
    identity={k:r[k] for k in ('backend','model_id','model_revision','forecast_profile','max_context','per_shot_horizon_patches')}
    compare.check_identity(r,identity)
    with pytest.raises(ValueError):compare.check_identity(r,identity|dict(forecast_profile='bounded-v1',max_context=256,per_shot_horizon_patches=5))


def test_failed_case_is_retained_and_request_never_sees_truth(monkeypatch):
    calls=[]
    def forecast(config,history,horizon,request_id):
        calls.append((list(history),horizon))
        if history[0]==9:raise RuntimeError('failed inference')
        return np.array([3.]),np.array([[3.]]),np.array([.5])
    monkeypatch.setattr(compare,'forecast',forecast)
    cases=[dict(id='good',frequency='Daily',history=[1,2,3],truth=[4],seasonality=1),
           dict(id='bad',frequency='Daily',history=[9,10],truth=[11],seasonality=1)]
    result=compare.evaluate(dict(row=row(),warmups=0,repeats=1),cases)
    assert calls==[([1,2,3],1),([9,10],1)]
    assert len(result)==2 and result[1]['status']=='error'
    assert result[0]['scores']['mae']==1


def test_summary_does_not_hide_missing_rows_or_undefined_scores():
    records=[dict(case_id='a',frequency='Daily',repeat=0,status='success',seconds=.2,scores=dict(mae=1,mase=None,smape=2,pinball=3,wql=None))]
    summary=compare.summarize(records,expected_cases=2,repeats=1)
    assert summary['status']=='incomplete'
    assert summary['frequencies']['Daily']['mase'] is None
    assert summary['frequencies']['Daily']['undefined_mase']==1


def test_retry_preserves_failed_evidence_and_reuses_only_complete_runs(tmp_path):
    path=tmp_path/'cpu-5M.json';failed=dict(run_key='key',summary={'status':'incomplete'},records=[{'status':'error'}])
    path.write_text(json.dumps(failed))
    assert compare.saved_result(path,'key',retry=False)==failed
    assert compare.saved_result(path,'key',retry=True) is None
    assert not path.exists()
    assert json.loads(next(tmp_path.glob('cpu-5M.failed-*.json')).read_text())==failed
    complete=failed|{'summary':{'status':'complete'}};path.write_text(json.dumps(complete))
    assert compare.saved_result(path,'key',retry=True)==complete
    with pytest.raises(ValueError):compare.saved_result(path,'different',retry=True)
