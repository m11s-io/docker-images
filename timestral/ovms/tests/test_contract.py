"""Bounded standard-tensor contract for upstream forecasting in OVMS."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
FILE=ROOT/'timestral/ovms/adapter/contract.py'

class ContractTest(unittest.TestCase):
    def load(self):
        self.assertTrue(FILE.exists(),'forecast contract missing')
        spec=importlib.util.spec_from_file_location('forecast_contract',FILE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def inputs(self):
        import numpy as np
        return {'context':np.zeros((1,1,128),dtype=np.float32),
                'observation_mask':np.ones((1,1,128),dtype=np.bool_),
                'prediction_length':np.array([65],dtype=np.int64)}

    def test_supported_shapes_and_horizons_are_preserved(self):
        m=self.load();a=self.inputs();context,mask,horizon=m.validate_request(a)
        self.assertEqual(context.shape,(1,1,128));self.assertEqual(horizon,65)
        self.assertEqual(mask.dtype.name,'bool')

    def test_unsupported_or_malformed_tensors_fail(self):
        m=self.load();import numpy as np
        for key,value in [('context',np.zeros((2,1,128),dtype=np.float32)),
                          ('context',np.zeros((1,2,128),dtype=np.float32)),
                          ('context',np.zeros((1,1,257),dtype=np.float32)),
                          ('context',np.zeros((1,1,128),dtype=np.float64)),
                          ('context',np.full((1,1,128),np.nan,dtype=np.float32)),
                          ('observation_mask',np.ones((1,1,128),dtype=np.int32)),
                          ('observation_mask',np.ones((1,1,127),dtype=bool)),
                          ('observation_mask',np.zeros((1,1,128),dtype=bool)),
                          ('prediction_length',np.array([0],dtype=np.int64)),
                          ('prediction_length',np.array([321],dtype=np.int64)),
                          ('prediction_length',np.array([32],dtype=np.int32))]:
            with self.subTest(key=key,shape=value.shape):
                a=self.inputs();a[key]=value
                with self.assertRaises(ValueError):m.validate_request(a)
        a=self.inputs();a['past_covariates']=a['context']
        with self.assertRaises(ValueError):m.validate_request(a)

    def test_outputs_cover_all_quantiles_and_metadata(self):
        m=self.load();import numpy as np
        levels=np.linspace(.01,.99,21,dtype=np.float32);levels[10]=.5
        result=m.validate_response(np.ones((1,1,65,21),dtype=np.float32),levels,65)
        self.assertEqual(result['median'].shape,(1,1,65));self.assertEqual(result['quantile_levels'].shape,(21,))
        for bad in [np.ones((1,1,64,21),dtype=np.float32),np.full((1,1,65,21),np.nan,dtype=np.float32)]:
            with self.assertRaises(ValueError):m.validate_response(bad,levels,65)
        with self.assertRaises(ValueError):m.validate_response(np.ones((1,1,65,21),dtype=np.float32),levels[::-1],65)

if __name__=='__main__':unittest.main()
