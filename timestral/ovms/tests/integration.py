"""Validate final forecasts through the built image's standard KServe REST API."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import numpy as np


def request(url, body=None):
    data=None if body is None else json.dumps(body,allow_nan=False).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)


def run(root,url):
    deadline=time.monotonic()+180
    while True:
        try:request(url+'/v2/models/timestral/ready');break
        except (OSError,ValueError):
            if time.monotonic()>deadline:raise TimeoutError('forecast graph did not become ready')
            time.sleep(1)
    reference=json.loads((root/'reference.json').read_text());rows=[]
    for name,case in reference.items():
        body={'inputs':[
            {'name':'context','datatype':'FP32','shape':[1,1,len(case['context'][0][0])],'data':np.array(case['context']).ravel().tolist()},
            {'name':'observation_mask','datatype':'BOOL','shape':[1,1,len(case['mask'][0][0])],'data':np.array(case['mask']).ravel().tolist()},
            {'name':'prediction_length','datatype':'INT64','shape':[1],'data':[case['horizon']]}]}
        response=request(url+'/v2/models/timestral/infer',body)
        outputs={v['name']:v for v in response['outputs']}
        assert set(outputs)=={'quantiles','median','quantile_levels'}
        expected=np.array(case['outputs']['True'],dtype=np.float32)
        quantiles=outputs['quantiles'];assert quantiles['datatype']=='FP32' and quantiles['shape']==list(expected.shape)
        actual=np.array(quantiles['data'],dtype=np.float32).reshape(quantiles['shape'])
        assert np.isfinite(actual).all();np.testing.assert_allclose(actual,expected,rtol=1e-4,atol=1e-4)
        levels=np.array(outputs['quantile_levels']['data'],dtype=np.float32).reshape(outputs['quantile_levels']['shape'])
        median=np.array(outputs['median']['data'],dtype=np.float32).reshape(outputs['median']['shape'])
        assert levels.shape==(21,) and np.count_nonzero(levels==.5)==1
        np.testing.assert_array_equal(median,actual[...,np.flatnonzero(levels==.5)[0]])
        rows.append({'case':name,'shape':list(actual.shape),'max_absolute_error':float(np.max(np.abs(actual-expected)))})
        print('KServe REST final forecast passed:',rows[-1],flush=True)
    # Requests outside the documented feature envelope must not be approximated.
    bad={'inputs':[{'name':'context','datatype':'FP32','shape':[1,1,1],'data':[1.]},
                   {'name':'observation_mask','datatype':'BOOL','shape':[1,1,1],'data':[True]},
                   {'name':'prediction_length','datatype':'INT64','shape':[1],'data':[321]}]}
    try:request(url+'/v2/models/timestral/infer',bad)
    except urllib.error.HTTPError as error:assert 400<=error.code<600
    else:raise AssertionError('unsupported horizon was accepted')
    (root/'image-rest-validation.json').write_text(json.dumps({'passed':True,'cases':rows,'protocol':'KServe V2 REST','unsupported_horizon_rejected':True},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--url',default='http://127.0.0.1:18000')
    args=parser.parse_args();run(args.root,args.url)
