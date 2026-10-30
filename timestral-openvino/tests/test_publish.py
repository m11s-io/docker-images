import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
class PublishTest(unittest.TestCase):
    def test_only_intended_main_workflow_can_publish(self):
        spec=importlib.util.spec_from_file_location("publish",ROOT/"publish.py")
        module=importlib.util.module_from_spec(spec)
        if (ROOT/"publish.py").exists():spec.loader.exec_module(module)
        self.assertTrue(hasattr(module,"validate_environment"),"publish environment gate is missing")
        good={"GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_dispatch",
              "GITHUB_REPOSITORY":"m11s-io/docker-images","HF_OIDC_RESOURCE":"m11s-org/Timestral-5M-OpenVINO-experimental"}
        with patch.dict(os.environ,good,clear=True):module.validate_environment()
        for key,value in [("GITHUB_REF","refs/heads/feature"),("GITHUB_EVENT_NAME","pull_request"),
                          ("HF_OIDC_RESOURCE","other/model"),("GITHUB_ACTIONS","false"),
                          ("GITHUB_REPOSITORY","fork/docker-images")]:
            with self.subTest(key=key),patch.dict(os.environ,dict(good,**{key:value}),clear=True):
                with self.assertRaises(ValueError):module.validate_environment()

if __name__=="__main__":unittest.main()
