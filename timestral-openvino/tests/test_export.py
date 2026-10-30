"""Safety and numerical contracts for the experimental exporter."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("exporter", ROOT / "export.py")
        cls.module = importlib.util.module_from_spec(spec)
        if spec.loader and (ROOT / "export.py").exists():
            spec.loader.exec_module(cls.module)

    def test_guarded_rewrites_leave_original_untouched(self):
        self.assertTrue(hasattr(self.module, "patch_source"), "guarded source patcher is missing")
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = pathlib.Path(tmp)/"original", pathlib.Path(tmp)/"patched"
            source.joinpath("src/timestral").mkdir(parents=True)
            scaler = "means.unfold(-1, patch_size, patch_size)\nscales.unfold(-1, patch_size, patch_size)\n"
            masks = "started = obs_per_patch.cummax(dim=-1).values\n"
            (source/"src/timestral/scaler.py").write_text(scaler)
            (source/"src/timestral/masks.py").write_text(masks)
            self.module.patch_source(source, dest)
            self.assertEqual((source/"src/timestral/scaler.py").read_text(), scaler)
            self.assertNotIn(".unfold(", (dest/"src/timestral/scaler.py").read_text())
            self.assertIn("cumsum", (dest/"src/timestral/masks.py").read_text())

    def test_drift_fails_without_publishing_partial_copy(self):
        self.assertTrue(hasattr(self.module, "patch_source"), "guarded source patcher is missing")
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = pathlib.Path(tmp)/"original", pathlib.Path(tmp)/"patched"
            src.joinpath("src/timestral").mkdir(parents=True)
            (src/"src/timestral/scaler.py").write_text("upstream changed")
            (src/"src/timestral/masks.py").write_text("upstream changed")
            with self.assertRaisesRegex(ValueError, "source drift"):
                self.module.patch_source(src,dst)
            self.assertFalse(dst.exists())

    def test_output_gate_rejects_shape_dtype_nonfinite_and_parity(self):
        self.assertTrue(hasattr(self.module, "validate_outputs"), "numerical gate is missing")
        import numpy as np
        ref = np.ones((1,32,21),dtype=np.float32)
        self.assertEqual(self.module.validate_outputs(ref,ref)["max_absolute_error"],0)
        for bad in [np.ones((1,32,1),dtype=np.float32),ref.astype(np.float16),ref*float("nan"),ref*float("inf"),ref+0.1]:
            with self.subTest(shape=bad.shape,dtype=bad.dtype):
                with self.assertRaises((ValueError,AssertionError)):
                    self.module.validate_outputs(ref,bad)

    def test_cases_cover_missing_observations(self):
        self.assertTrue(hasattr(self.module, "validation_cases"), "validation cases are missing")
        import numpy as np
        cases = self.module.validation_cases()
        self.assertEqual(set(cases),{"random","sinusoidal","constant","scattered-missing","leading-missing"})
        for context, observed in cases.values():
            self.assertEqual(context.shape,(1,128)); self.assertEqual(context.dtype,np.float32)
            self.assertEqual(observed.shape,(1,128)); self.assertEqual(observed.dtype,np.bool_)
        self.assertFalse(cases["leading-missing"][1][0,:32].any())
        self.assertFalse(cases["scattered-missing"][1].all())

if __name__ == "__main__": unittest.main()
