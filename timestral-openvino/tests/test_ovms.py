import importlib.util
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class OVMSTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("validate_ovms",ROOT/"validate_ovms.py")
        cls.module=importlib.util.module_from_spec(spec)
        if (ROOT/"validate_ovms.py").exists():spec.loader.exec_module(cls.module)

    def test_malformed_tensor_fails(self):
        self.assertTrue(hasattr(self.module,"parse_response"),"OVMS response validator is missing")
        import numpy as np
        good={"outputs":[{"name":"quantiles","datatype":"FP32","shape":[1,32,21],"data":[0.0]*672}]}
        self.assertEqual(self.module.parse_response(good).shape,(1,32,21))
        for bad in [{},{"outputs":[]}, {"outputs":[dict(good["outputs"][0],datatype="FP16")]},
                    {"outputs":[dict(good["outputs"][0],shape=[1,32,1])]},
                    {"outputs":[dict(good["outputs"][0],data=[0.0])]},
                    {"outputs":[dict(good["outputs"][0],data=[float("nan")]*672)]}]:
            with self.assertRaises(ValueError):self.module.parse_response(bad)

    def test_metadata_rejects_unnamed_export_before_inference(self):
        self.assertTrue(hasattr(self.module,"validate_metadata"),"OVMS metadata gate is missing")
        good={"inputs":[{"name":"context","datatype":"FP32","shape":[1,128]},
                        {"name":"observed","datatype":"BOOL","shape":[1,128]}],
              "outputs":[{"name":"quantiles","datatype":"FP32","shape":[1,32,21]}]}
        self.module.validate_metadata(good)
        good["inputs"][0]["name"]="146"
        with self.assertRaises(ValueError):self.module.validate_metadata(good)

if __name__ == "__main__":unittest.main()
