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

    def test_remote_inventory_is_checked_before_upload_with_pinned_parent(self):
        spec=importlib.util.spec_from_file_location("publish",ROOT/"publish.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(hasattr(module,"upload_bundle"),"preflight upload gate is missing")
        class API:
            def __init__(self,files): self.files=files;self.uploads=[];self.revision=None
            def list_repo_files(self,repo_id,revision):self.revision=revision;return self.files
            def upload_folder(self,**kwargs):self.uploads.append(kwargs);return "commit"
        unexpected=API([".gitattributes","secret.txt"])
        with self.assertRaises(ValueError):module.upload_bundle(unexpected,Path("bundle"),"parent-sha")
        self.assertEqual(unexpected.uploads,[])
        allowed=API([".gitattributes"])
        self.assertEqual(module.upload_bundle(allowed,Path("bundle"),"parent-sha"),"commit")
        self.assertEqual(allowed.revision,"parent-sha")
        self.assertEqual(allowed.uploads[0]["parent_commit"],"parent-sha")

if __name__=="__main__":unittest.main()
