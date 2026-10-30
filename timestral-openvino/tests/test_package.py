import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("bundle_package", ROOT/"package.py")
        cls.module = importlib.util.module_from_spec(spec)
        if (ROOT/"package.py").exists(): spec.loader.exec_module(cls.module)

    def fixture(self, root):
        for name in self.module.FILES:
            path = root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text("fixture")
        cases = {n: {"max_absolute_error":0,"rtol":1e-4,"atol":1e-4} for n in
                 ["random","sinusoidal","constant","scattered-missing","leading-missing"]}
        for name in ["validation.json","ovms-validation.json"]:
            (root/name).write_text(json.dumps({"passed":True,"cases":cases}))

    def test_rejects_changed_missing_extra_and_symlink_files(self):
        self.assertTrue(hasattr(self.module,"verify"),"bundle verifier is missing")
        for mutation in ["changed","missing","extra","symlink","manifest-traversal"]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); self.fixture(root); self.module.seal(root); self.module.verify(root)
                if mutation=="changed": (root/"config.json").write_text("changed")
                if mutation=="missing": (root/"config.json").unlink()
                if mutation=="extra": (root/"token").write_text("never publish")
                if mutation=="symlink":
                    (root/"config.json").unlink(); (root/"config.json").symlink_to(root/"quantiles.json")
                if mutation=="manifest-traversal":
                    with (root/"SHA256SUMS").open("a") as f:f.write("0"*64+"  ../outside\n")
                with self.assertRaises(ValueError): self.module.verify(root)

    def test_failed_validation_cannot_be_sealed(self):
        self.assertTrue(hasattr(self.module,"seal"),"bundle sealing is missing")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/"validation.json").write_text('{"passed":false}')
            with self.assertRaises(ValueError):self.module.seal(root)

if __name__ == "__main__":unittest.main()
